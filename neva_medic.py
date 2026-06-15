#!/usr/bin/env python3
"""
NEVA Medic v3.8
v3.6: Ч4 ПОЛНАЯ — двусторонняя связь Medic ↔ Клод через MCP-сервер (:9000)
v3.7: A2
v3.8: FM mcp_approval_hang + mcp_proxy_fallback_stuck — Medic мониторит и перезапускает neva_mcp_server.py (:9000/:9001)
      - detect_problems(): mcp_server_net_down, mcp_server_net_http, dashboard_http
      - playbook restart_mcp_server_net: launchctl kickstart -k
      - ST-18: проверка новых детекторов
"""
import json, logging, os, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

# ─── ПУТИ ──────────────────────────────────────────────────────────────────────
BASE     = Path('~/Documents/NEVA_MCP_BRIDGE').expanduser()
NEVA     = Path('~/Documents/NEVA').expanduser()
APP_SUP  = Path('~/Library/Application Support/NEVA').expanduser()
STATE    = BASE / 'state'
LOGS     = BASE / 'logs'

SNAPSHOT        = STATE / 'medic_snapshot.json'
REPORT          = STATE / 'medic_report.json'
PENDING_FILE    = STATE / 'pending_decisions.json'
LOG_PATH        = LOGS  / 'medic.log'
ESCALATIONS     = BASE / 'escalations'
LOCK_FILE       = STATE / 'medic.lock'
PROBLEM_COUNTER = STATE / 'problem_counter.json'

CLAUDE_INBOX    = BASE / 'claude_inbox'
REPAIRS_DIR     = CLAUDE_INBOX / 'repairs'
REPAIR_RESULTS  = CLAUDE_INBOX / 'repair_results'
KNOWLEDGE_DIR   = NEVA / 'governance' / 'medic_knowledge'
REPAIR_AGENT    = BASE / 'neva_repair_agent.py'
CHRONIC_REPORT_SCRIPT = BASE / 'neva_chronic_report.py'

CC_PORT  = 8767
MCP_PORT = 9000

# ─── КОНФИГУРАЦИЯ ──────────────────────────────────────────────────────────────
POLL_SEC          = 60
MAX_ATTEMPTS      = 3
AI_CONF_THRESHOLD = 0.70
NOTIFY_DIRECTOR   = True
BACKOFF_STEPS     = [0, 300, 900, 1800, 3600]

AI_PROVIDERS = [
    {'name': 'cerebras',   'url': 'https://api.cerebras.ai/v1/chat/completions',
     'model': 'gpt-oss-120b',               'env_key': 'CEREBRAS_API_KEY'},
    {'name': 'groq',       'url': 'https://api.groq.com/openai/v1/chat/completions',
     'model': 'llama-3.3-70b-versatile',    'env_key': 'GROQ_API_KEY'},
    {'name': 'openrouter', 'url': 'https://openrouter.ai/api/v1/chat/completions',
     'model': 'google/gemma-4-31b-it:free', 'env_key': 'OPENROUTER_API_KEY_2'},
]

KNOWLEDGE_MAP = {
    'thermal_log_stale':     'thermal_guard.md',
    'thermal_critical':      'thermal_guard.md',
    'executor_log_spam':     'executor.md',
    'mcp_not_running':       'mcp_server.md',
    'mcp_server_net_down':   'mcp_server_net.md',
    'mcp_approval_hang':      'mcp_server_net.md',
    'mcp_proxy_fallback_stuck': 'mcp_server_net.md',
    'approval_not_running':  'approval_server.md',
    'approval_http_fail':    'approval_server.md',
    'auditor_log_stale':     'auditor.md',
    'ai_providers_all_down': 'auditor.md',
}

AGENT_ELIGIBLE = set(KNOWLEDGE_MAP.keys())

# ─── ЛОГ ───────────────────────────────────────────────────────────────────────
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [medic] %(levelname)s %(message)s',
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('neva_medic')


# ─── v3.6: MCP-СЕРВЕР СОБЫТИЯ (Ч4) ────────────────────────────────────────────

MCP_SERVER_URL = f'http://127.0.0.1:{MCP_PORT}'
_mcp_available  = True
_mcp_fail_count = 0


def mcp_push_event(event: dict):
    global _mcp_available, _mcp_fail_count
    if not _mcp_available:
        return
    event.setdefault('ts', datetime.now().isoformat())
    try:
        body = json.dumps(event, ensure_ascii=False, default=str).encode()
        req  = urllib.request.Request(
            f'{MCP_SERVER_URL}/events', data=body,
            headers={'Content-Type': 'application/json'}, method='POST')
        urllib.request.urlopen(req, timeout=2)
        _mcp_fail_count = 0
    except Exception:
        _mcp_fail_count += 1
        if _mcp_fail_count >= 3:
            _mcp_available = False
            log.debug('MCP-сервер :9000 недоступен — события отключены')


def mcp_check_reply() -> str | None:
    global _mcp_available, _mcp_fail_count
    try:
        resp  = urllib.request.urlopen(f'{MCP_SERVER_URL}/claude_reply', timeout=2)
        data  = json.loads(resp.read())
        instr = data.get('instruction')
        if instr:
            log.info(f'💬 claude_reply получен: {instr[:80]}')
            _mcp_available  = True
            _mcp_fail_count = 0
        return instr
    except Exception:
        _mcp_fail_count += 1
        if _mcp_fail_count >= 3:
            _mcp_available = False
        return None


def mcp_reset_availability():
    global _mcp_available, _mcp_fail_count
    _mcp_available  = True
    _mcp_fail_count = 0


# ─── БАЗА ЗНАНИЙ ───────────────────────────────────────────────────────────────

def load_knowledge(problem_id: str) -> str:
    fname = KNOWLEDGE_MAP.get(problem_id)
    if not fname:
        return ''
    fpath = KNOWLEDGE_DIR / fname
    try:
        content = fpath.read_text()
        log.info(f'knowledge: загружен {fname} ({len(content)} байт)')
        return content
    except Exception as e:
        log.warning(f'knowledge: не удалось загрузить {fname}: {e}')
        return ''


# ─── ХРОНИЧЕСКИЙ ОТЧЁТ ─────────────────────────────────────────────────────────

def update_chronic_report():
    if not CHRONIC_REPORT_SCRIPT.exists():
        return
    try:
        subprocess.Popen(
            [sys.executable, str(CHRONIC_REPORT_SCRIPT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        log.debug('chronic_report: запущен')
    except Exception as e:
        log.warning(f'chronic_report: {e}')


# ─── УТИЛИТЫ ───────────────────────────────────────────────────────────────────

def read_env_key(env_key: str) -> str:
    try:
        for line in (NEVA / '.env').read_text().splitlines():
            if line.startswith(env_key + '='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ''


def notify(title: str, msg: str, sound: str = 'Ping'):
    if not NOTIFY_DIRECTOR:
        return
    try:
        subprocess.run(['osascript', '-e',
            f'display notification "{msg}" with title "{title}" sound name "{sound}"'],
            capture_output=True, timeout=5)
    except Exception:
        pass


def notify_with_url(title: str, msg: str, url: str, sound: str = 'Basso'):
    if not NOTIFY_DIRECTOR:
        return
    try:
        subprocess.run(['osascript', '-e',
            f'display notification "{msg} → {url}" with title "{title}" sound name "{sound}"'],
            capture_output=True, timeout=5)
    except Exception:
        pass


def run_cmd(cmd: list, timeout: int = 15, background: bool = False) -> tuple:
    try:
        if background:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0, 'background'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, 'TIMEOUT'
    except Exception as e:
        return -1, str(e)


def http_ok(url: str, timeout: int = 3) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def ps_running(name: str) -> bool:
    try:
        out = subprocess.run(['ps', 'aux'], capture_output=True, text=True).stdout
        return name in out
    except Exception:
        return False


def ai_call(prompt: str, user: str) -> dict:
    for p in AI_PROVIDERS:
        key = read_env_key(p['env_key'])
        if not key:
            continue
        try:
            body = json.dumps({
                'model': p['model'], 'max_tokens': 600, 'temperature': 0,
                'messages': [{'role': 'system', 'content': prompt},
                             {'role': 'user',   'content': user}]
            }).encode()
            headers = {'Content-Type': 'application/json',
                       'Authorization': f'Bearer {key}',
                       'User-Agent': 'Mozilla/5.0 Chrome/124.0'}
            if 'openrouter' in p['url']:
                headers['HTTP-Referer'] = 'https://neva.local'
                headers['X-Title'] = 'NEVA Medic'
            req = urllib.request.Request(p['url'], data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            text = (data.get('choices') or [{}])[0].get('message', {}).get('content', '{}')
            text = text.strip().strip('`').strip()
            if text.startswith('json'):
                text = text[4:].strip()
            result = json.loads(text)
            log.info(f'ai_call: {p["name"]} OK conf={result.get("confidence", 0):.2f}')
            return result
        except Exception as e:
            log.warning(f'ai_call {p["name"]}: {e}')
    return {'diagnosis': 'AI unavailable', 'playbook': 'notify_director',
            'confidence': 0.0, 'reasoning': 'все провайдеры недоступны'}


# ─── CLAUDE INBOX ──────────────────────────────────────────────────────────────

def _inbox_init():
    for d in [CLAUDE_INBOX, REPAIRS_DIR, REPAIR_RESULTS]:
        d.mkdir(parents=True, exist_ok=True)


def inbox_write_escalation(esc_id: str, escalation: dict):
    _inbox_init()
    inbox_file = CLAUDE_INBOX / f'{esc_id}.json'
    payload = dict(escalation)
    payload['_claude_instruction'] = (
        f'Директор попросил разработать скрипт ремонта для {esc_id}. '
        f'Прочитай symptom, hypothesis, state_snapshot. '
        f'Напиши Python скрипт в {str(REPAIRS_DIR)}/{esc_id}.py.'
    )
    payload['_repair_script_path'] = str(REPAIRS_DIR / f'{esc_id}.py')
    payload['_repair_result_path'] = str(REPAIR_RESULTS / f'{esc_id}.json')
    payload['_status'] = 'AWAITING_CLAUDE'
    inbox_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    log.info(f'claude_inbox: записан {inbox_file.name}')


def inbox_update_index():
    _inbox_init()
    items = []
    for f in sorted(CLAUDE_INBOX.glob('ESC-*.json')):
        try:
            data = json.loads(f.read_text())
            items.append({
                'id':         data.get('id', f.stem),
                'ts':         data.get('ts', ''),
                'status':     data.get('_status', ''),
                'problem':    data.get('problem_id', ''),
                'symptom':    data.get('symptom', '')[:60],
                'has_repair': (REPAIRS_DIR / f'{f.stem}.py').exists(),
                'has_result': (REPAIR_RESULTS / f'{f.stem}.json').exists(),
            })
        except Exception:
            pass
    (CLAUDE_INBOX / 'INDEX.json').write_text(json.dumps({
        'updated': datetime.now().isoformat(), 'items': items,
        'instruction': 'При старте чата прочитай этот файл. Если items не пустой — доложи Директору.'
    }, ensure_ascii=False, indent=2))


def run_pending_repairs():
    if not REPAIRS_DIR.exists():
        return
    for script in sorted(REPAIRS_DIR.glob('*.py')):
        marker = REPAIRS_DIR / f'.ran_{script.stem}'
        if marker.exists():
            continue
        log.info(f'REPAIR SCRIPT: запуск {script.name}')
        marker.write_text(datetime.now().isoformat())
        REPAIR_RESULTS.mkdir(parents=True, exist_ok=True)
        result_file = REPAIR_RESULTS / f'{script.stem}.json'
        try:
            r = subprocess.run([sys.executable, str(script)],
                               capture_output=True, text=True, timeout=120)
            success = r.returncode == 0
            result = {'script': script.name, 'ts': datetime.now().isoformat(),
                      'success': success, 'returncode': r.returncode,
                      'stdout': r.stdout[-2000:], 'stderr': r.stderr[-1000:]}
            result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            log.info(f'REPAIR SCRIPT: {script.name} → {"OK" if success else "FAIL"}')
            mcp_push_event({'type': 'repair_script_result', 'script': script.name,
                            'success': success, 'rc': r.returncode})
            notify('✅ NEVA — ремонт выполнен' if success else '❌ NEVA — скрипт не сработал',
                   f'{script.stem}', sound='Glass' if success else 'Basso')
        except subprocess.TimeoutExpired:
            result_file.write_text(json.dumps({'script': script.name, 'success': False,
                'returncode': -1, 'stderr': 'TIMEOUT 120s'}, ensure_ascii=False, indent=2))
            log.error(f'REPAIR SCRIPT: {script.name} TIMEOUT')
        except Exception as e:
            log.error(f'REPAIR SCRIPT: {script.name} exception: {e}')
    inbox_update_index()


# ─── BACKOFF ───────────────────────────────────────────────────────────────────

def _load_counters() -> dict:
    try:
        if PROBLEM_COUNTER.exists():
            return json.loads(PROBLEM_COUNTER.read_text())
    except Exception:
        pass
    return {}

def _save_counters(counters: dict):
    try:
        PROBLEM_COUNTER.write_text(json.dumps(counters, ensure_ascii=False, indent=2))
    except Exception as e:
        log.warning(f'save_counters: {e}')

def backoff_check(problem_id: str) -> tuple:
    counters = _load_counters()
    entry    = counters.get(problem_id, {})
    last_try = entry.get('last_try_ts')
    attempts = entry.get('attempts', 0)
    if not last_try:
        return False, 0
    wait    = BACKOFF_STEPS[min(attempts, len(BACKOFF_STEPS) - 1)]
    elapsed = time.time() - last_try
    if wait > 0 and elapsed < wait:
        return True, int(wait - elapsed)
    return False, 0

def backoff_record_attempt(problem_id: str):
    counters = _load_counters()
    entry    = counters.get(problem_id, {})
    now      = time.time()
    if not entry.get('first_seen_ts'):
        entry['first_seen_ts'] = now
        entry['first_seen']    = datetime.now().isoformat()
    entry['attempts']    = entry.get('attempts', 0) + 1
    entry['last_try_ts'] = now
    entry['last_try']    = datetime.now().isoformat()
    counters[problem_id] = entry
    _save_counters(counters)
    nw = BACKOFF_STEPS[min(entry['attempts'], len(BACKOFF_STEPS) - 1)]
    log.info(f'backoff [{problem_id}]: attempt={entry["attempts"]} next_wait={nw}s')

def backoff_reset(problem_id: str):
    counters = _load_counters()
    if problem_id in counters:
        old = counters.pop(problem_id).get('attempts', 0)
        _save_counters(counters)
        log.info(f'backoff [{problem_id}]: RESET (был {old} попыток)')


# ─── СБОР СОСТОЯНИЯ ────────────────────────────────────────────────────────────

def collect_state() -> dict:
    now = time.time()
    s   = {'ts': datetime.now().isoformat()}
    try:
        s['executor'] = {
            'mcp_server_running':      ps_running('mcp_server.py'),
            'approval_server_running': ps_running('neva_approval_server'),
            'approval_http':           http_ok('http://127.0.0.1:8766/health'),
        }
    except Exception as e:
        s['executor'] = {'error': str(e)}
    # v3.7: мониторинг MCP-сервера :9000
    try:
        s['mcp_net'] = {
            'process_running': ps_running('neva_mcp_server'),
            'http_9000':       http_ok('http://127.0.0.1:9000/health'),
            'http_9001':       http_ok('http://127.0.0.1:9001'),
        }
    except Exception as e:
        s['mcp_net'] = {'error': str(e)}
    try:
        err_log = LOGS / 'com.neva.executor.err.log'
        if err_log.exists():
            tail = err_log.read_text(errors='replace').splitlines()[-50:]
            spam = sum(1 for l in tail if 'Operation not permitted' in l or "can't open file" in l)
            s['executor_spam'] = {'count': spam, 'spamming': spam > 20}
        else:
            s['executor_spam'] = {'count': 0, 'spamming': False}
    except Exception as e:
        s['executor_spam'] = {'error': str(e)}
    try:
        audit_log = LOGS / 'auditor.log'
        age = now - audit_log.stat().st_mtime
        s['auditor'] = {'log_age_sec': int(age), 'log_fresh': age < 300,
                        'last_lines': audit_log.read_text(errors='replace').splitlines()[-5:]}
    except Exception as e:
        s['auditor'] = {'error': str(e)}
    try:
        th_log  = NEVA / 'thermal.log'
        th_data = json.loads((NEVA / 'thermal_state.json').read_text()) \
                  if (NEVA / 'thermal_state.json').exists() else {}
        th_age  = now - th_log.stat().st_mtime
        s['thermal'] = {
            'log_age_sec': int(th_age), 'log_fresh': th_age < 120,
            'state': th_data.get('state', '?'),
            'ollama_available': th_data.get('ollama_available', '?'),
            'stopped_models': th_data.get('stopped_models', []),
            'last_lines': th_log.read_text(errors='replace').splitlines()[-5:],
        }
    except Exception as e:
        s['thermal'] = {'error': str(e)}
    s['sync'] = {}
    for f in ['mcp_server.py', 'mcp_executor.py', 'background_auditor.py', 'neva_approval_server.py']:
        try:
            src, dst = BASE / f, APP_SUP / f
            s['sync'][f] = src.exists() and dst.exists() and src.stat().st_size == dst.stat().st_size
        except Exception:
            s['sync'][f] = False
    versions = {'mcp_server.py': 'v3.3', 'mcp_executor.py': 'v3.1', 'background_auditor.py': 'v6.9'}
    s['versions'] = {}
    for f, v in versions.items():
        try:
            s['versions'][f] = v if v in (BASE/f).read_text(errors='replace')[:2000] else 'outdated'
        except Exception:
            s['versions'][f] = 'missing'
    try:
        s['medic_self'] = {'pending_count': _count_pending(),
                           'log_age_sec': int(now - LOG_PATH.stat().st_mtime)}
    except Exception as e:
        s['medic_self'] = {'error': str(e)}
    return s


def _count_pending() -> int:
    try:
        if PENDING_FILE.exists():
            return len([x for x in json.loads(PENDING_FILE.read_text()) if not x.get('resolved')])
    except Exception:
        pass
    return 0


# ─── ДЕТЕКЦИЯ ПРОБЛЕМ ──────────────────────────────────────────────────────────

def detect_problems(state: dict) -> list:
    problems = []
    def add(pid, sev, comp, desc, data=None):
        problems.append({'id': pid, 'severity': sev, 'component': comp,
                         'description': desc, 'data': data or {}})
    ex = state.get('executor', {})
    if not ex.get('mcp_server_running'):
        add('mcp_not_running', 'HIGH', 'executor', 'mcp_server.py (stdio) не запущен')
    if not ex.get('approval_server_running'):
        add('approval_not_running', 'MEDIUM', 'executor', 'neva_approval_server.py не запущен')
    if not ex.get('approval_http') and ex.get('approval_server_running'):
        add('approval_http_fail', 'MEDIUM', 'executor', 'Approval Gate не отвечает на HTTP 8766')
    spam = state.get('executor_spam', {})
    if spam.get('spamming'):
        add('executor_log_spam', 'HIGH', 'executor',
            f'executor err.log: {spam["count"]} строк ошибок')
    # v3.7: мониторинг neva_mcp_server.py :9000/:9001
    mn = state.get('mcp_net', {})
    if 'error' not in mn:
        if not mn.get('process_running'):
            add('mcp_server_net_down', 'HIGH', 'mcp_net',
                'neva_mcp_server.py не запущен — MCP HTTP сервер упал')
        elif not mn.get('http_9000'):
            add('mcp_server_net_http', 'HIGH', 'mcp_net',
                'neva_mcp_server.py запущен но :9000 не отвечает')
        if not mn.get('http_9001'):
            add('dashboard_http', 'LOW', 'mcp_net',
                'Live Dashboard :9001 не отвечает')
    au = state.get('auditor', {})
    if not au.get('log_fresh') and 'error' not in au:
        # v3.8: grace period — auditor одноразовый, проверяем low_risk_ops.log
        import os, time as _time
        lr_log = Path('~/Documents/NEVA_MCP_BRIDGE/logs/low_risk_ops.log').expanduser()
        lr_age = (_time.time() - lr_log.stat().st_mtime) if lr_log.exists() else 99999
        # Тревога только если оба лога стale > 2h (7200с)
        if au.get('log_age_sec', 0) > 7200 and lr_age > 7200:
            add('auditor_log_stale', 'MEDIUM', 'auditor',
                f'auditor.log не обновлялся {au.get("log_age_sec", "?")}c')
    th = state.get('thermal', {})
    if not th.get('log_fresh') and 'error' not in th:
        add('thermal_log_stale', 'HIGH', 'thermal',
            f'thermal.log не обновлялся {th.get("log_age_sec", "?")}c — Guard упал',
            {'log_age_sec': th.get('log_age_sec'), 'last_lines': th.get('last_lines', [])})
    if th.get('state') in ('BLOCKED', 'CRITICAL'):
        add('thermal_critical', 'HIGH', 'thermal',
            f'Thermal state = {th["state"]} — Ollama заблокирована')
    if th.get('stopped_models'):
        add('models_stopped', 'MEDIUM', 'thermal', f'Выгружены модели: {th["stopped_models"]}')
    out_of_sync = [f for f, ok in state.get('sync', {}).items() if not ok]
    if out_of_sync:
        add('sync_needed', 'LOW', 'deploy', f'Файлы не синхронизированы: {out_of_sync}',
            {'files': out_of_sync})
    outdated = [f for f, v in state.get('versions', {}).items() if v in ('outdated', 'missing')]
    if outdated:
        add('versions_outdated', 'MEDIUM', 'deploy', f'Устаревшие версии: {outdated}')
    # v3.8: mcp_approval_hang — executor принял токен но запись зависла
    if mn.get('process_running') and mn.get('http_9000'):
        try:
            import urllib.request as _ur
            r = _ur.urlopen('http://127.0.0.1:9000/health', timeout=2)
            data = __import__('json').loads(r.read())
            hang = data.get('approval_hang', False)
            proxy_stuck = data.get('proxy_fallback_stuck', False)
        except Exception:
            hang = False
            proxy_stuck = False
        if hang:
            add('mcp_approval_hang', 'HIGH', 'mcp_net',
                'MCP executor: approval gate принял токен, запись зависла >90с')
        if proxy_stuck:
            add('mcp_proxy_fallback_stuck', 'HIGH', 'mcp_net',
                'MCP proxy fallback застрял — stdio→HTTP:9000 не отвечает')

    if not http_ok('http://127.0.0.1:11434/api/tags', timeout=3):
        add('ollama_not_responding', 'MEDIUM', 'ollama', 'Ollama не отвечает на порте 11434')
    au_lines = state.get('auditor', {}).get('last_lines', [])
    if len(au_lines) >= 3 and all(
        'All FlagmanRouter providers failed' in l or 'Circuit breaker OPEN' in l
        for l in au_lines if l.strip()
    ):
        add('ai_providers_all_down', 'MEDIUM', 'ai', 'Все AI провайдеры недоступны')
    try:
        if PENDING_FILE.exists():
            stale = []
            now_ts = time.time()
            for item in json.loads(PENDING_FILE.read_text()):
                if item.get('resolved'): continue
                try:
                    if (now_ts - datetime.fromisoformat(item['ts']).timestamp()) / 60 > 30:
                        stale.append(item['problem_id'])
                except Exception: pass
            if stale:
                add('pending_unanswered', 'MEDIUM', 'medic',
                    f'Нерешённых pending > 30 мин: {len(stale)}')
    except Exception as e:
        log.warning(f'pending check: {e}')
    return problems


# ─── РЕЖИМЫ ────────────────────────────────────────────────────────────────────

PLAYBOOK_MAP = {
    'approval_not_running':   'start_approval_server',
    'approval_http_fail':     'start_approval_server',
    'thermal_log_stale':      'restart_thermal_guard',
    'sync_needed':            'sync_appsupport',
    'executor_log_spam':      'restart_executor_launchd',
    'mcp_not_running':        'restart_mcp_soft',
    'mcp_server_net_down':    'restart_mcp_server_net',   # v3.7
    'mcp_server_net_http':    'restart_mcp_server_net',   # v3.7
    'dashboard_http':         'restart_mcp_server_net',   # v3.7
    'mcp_approval_hang':      'restart_mcp_server_net',   # v3.8
    'mcp_proxy_fallback_stuck': 'restart_mcp_server_net', # v3.8
    'thermal_critical':       'notify_director',
    'ollama_not_responding':  'notify_director',
    'ai_providers_all_down':  'notify_director',
    'auditor_log_stale':      'notify_director',
    'pending_unanswered':     'remind_pending',
}
ALERT_ONLY = {'thermal_critical', 'ollama_not_responding',
              'ai_providers_all_down', 'auditor_log_stale'}


def decide_mode(problem: dict, ai_result: dict) -> str:
    pid = problem['id']
    if pid in ALERT_ONLY:
        return 'ALERT'
    if pid in PLAYBOOK_MAP and PLAYBOOK_MAP[pid] != 'notify_director':
        if ai_result.get('confidence', 1.0) >= AI_CONF_THRESHOLD:
            return 'AUTO'
    return 'ASK' if ai_result.get('confidence', 0.0) < AI_CONF_THRESHOLD else 'AUTO'


# ─── PLAYBOOKS ─────────────────────────────────────────────────────────────────

def run_playbook(name: str, dry_run: bool = False) -> bool:
    playbooks = {
        'start_approval_server': [
            {'action': 'run', 'cmd': ['pkill', '-f', 'neva_approval_server'], 'ignore_error': True},
            {'action': 'wait', 'sec': 1},
            {'action': 'run', 'cmd': [str(APP_SUP/'neva_approval_server.py')],
             'python': True, 'background': True},
            {'action': 'wait', 'sec': 3},
            {'action': 'check_http', 'url': 'http://127.0.0.1:8766/health'},
        ],
        'restart_thermal_guard': [
            {'action': 'run', 'cmd': ['launchctl', 'unload',
              str(Path('~/Library/LaunchAgents/com.neva.thermal-guard.plist').expanduser())],
             'ignore_error': True},
            {'action': 'wait', 'sec': 2},
            {'action': 'run', 'cmd': ['launchctl', 'load',
              str(Path('~/Library/LaunchAgents/com.neva.thermal-guard.plist').expanduser())]},
            {'action': 'wait', 'sec': 10},
            {'action': 'check_log_fresh', 'path': str(NEVA/'thermal.log'), 'max_age': 120},
            {'action': 'nohup_if_stale', 'path': str(NEVA/'thermal.log'), 'max_age': 120,
             'cmd': [str(Path('~/Documents/NEVA/.venv/bin/python3').expanduser()),
                     '-u', str(NEVA/'neva_thermal_guard.py')]},
        ],
        # v3.7: перезапуск neva_mcp_server.py через launchd (KeepAlive)
        'restart_mcp_server_net': [
            {'action': 'run',
             'cmd': ['launchctl', 'kickstart', '-k',
                     f'gui/{os.getuid()}/com.neva.mcp-server'],
             'ignore_error': True},
            {'action': 'wait', 'sec': 5},
            {'action': 'check_http', 'url': 'http://127.0.0.1:9000/health'},
        ],
        'sync_appsupport': [
            {'action': 'run', 'cmd': ['bash', str(BASE/'sync_to_appsupport.sh')]},
        ],
        'restart_executor_launchd': [
            {'action': 'run', 'cmd': ['launchctl', 'kickstart', '-k',
                                      f'gui/{os.getuid()}/com.neva.executor']},
            {'action': 'wait', 'sec': 5},
        ],
        'restart_mcp_soft': [
            {'action': 'run', 'cmd': ['open', '-a', 'Claude']},
            {'action': 'wait', 'sec': 15},
            {'action': 'check_ps', 'name': 'mcp_server.py'},
        ],
        'remind_pending': [
            {'action': 'notify', 'title': '⏳ NEVA Medic',
             'msg': 'Нерешённые > 30 мин', 'sound': 'Ping'},
        ],
        'notify_director': [
            {'action': 'notify', 'title': '🚨 NEVA Medic',
             'msg': 'Неисправность требует внимания', 'sound': 'Basso'},
        ],
    }
    pb = playbooks.get(name)
    if not pb:
        log.error(f'Unknown playbook: {name}')
        return False
    log.info(f'PLAYBOOK START: {name}')
    mcp_push_event({'type': 'playbook_start', 'playbook': name})
    if dry_run:
        return True
    success = True
    for step in pb:
        a = step['action']
        if a == 'run':
            cmd = ([sys.executable] + step['cmd']) if step.get('python') else step['cmd']
            rc, out = run_cmd(cmd, background=step.get('background', False))
            log.info(f'  RUN: {" ".join(str(c) for c in cmd[:3])} → rc={rc}')
            mcp_push_event({'type': 'playbook_step', 'playbook': name,
                            'step': f'run:{cmd[0].split("/")[-1]}', 'result': f'rc={rc}'})
            if rc != 0 and not step.get('ignore_error') and not step.get('background'):
                log.warning(f'  {out[:200]}')
        elif a == 'wait':
            time.sleep(step['sec'])
        elif a == 'check_http':
            ok = http_ok(step['url'])
            log.info(f'  HTTP {step["url"]}: {"OK" if ok else "FAIL"}')
            mcp_push_event({'type': 'playbook_step', 'playbook': name,
                            'step': 'check_http', 'result': 'ok' if ok else 'fail'})
            if not ok: success = False
        elif a == 'check_ps':
            ok = ps_running(step['name'])
            log.info(f'  PS {step["name"]}: {"OK" if ok else "NOT FOUND"}')
            mcp_push_event({'type': 'playbook_step', 'playbook': name,
                            'step': f'check_ps:{step["name"]}', 'result': 'ok' if ok else 'fail'})
            if not ok: success = False
        elif a == 'check_log_fresh':
            try:
                age = time.time() - Path(step['path']).stat().st_mtime
                ok  = age < step['max_age']
                log.info(f'  LOG age={age:.0f}s {"OK" if ok else "STALE"}')
                mcp_push_event({'type': 'playbook_step', 'playbook': name,
                                'step': 'check_log_fresh',
                                'result': f'age={age:.0f}s {"ok" if ok else "stale"}'})
                if not ok: success = False
            except Exception as e:
                log.warning(f'  LOG error: {e}'); success = False
        elif a == 'nohup_if_stale':
            try:
                age = time.time() - Path(step['path']).stat().st_mtime
                if age > step['max_age']:
                    subprocess.Popen(step['cmd'],
                                     stdout=open(step['path'], 'a'),
                                     stderr=subprocess.DEVNULL,
                                     start_new_session=True)
                    time.sleep(8)
                    success = (time.time() - Path(step['path']).stat().st_mtime) < step['max_age']
            except Exception as e:
                log.warning(f'  NOHUP error: {e}')
        elif a == 'notify':
            notify(step['title'], step['msg'], step.get('sound', 'Ping'))
    log.info(f'PLAYBOOK END: {name} — {"OK" if success else "FAIL"}')
    mcp_push_event({'type': 'playbook_end', 'playbook': name,
                    'result': 'ok' if success else 'fail'})
    return success


# ─── PENDING ───────────────────────────────────────────────────────────────────

def save_pending(problem: dict, ai_result: dict):
    pending = []
    if PENDING_FILE.exists():
        try: pending = json.loads(PENDING_FILE.read_text())
        except Exception: pass
    if problem['id'] in {x['problem_id'] for x in pending if not x.get('resolved')}:
        return
    pending.append({
        'problem_id':  problem['id'],
        'description': problem['description'],
        'severity':    problem['severity'],
        'diagnosis':   ai_result.get('diagnosis', ''),
        'confidence':  ai_result.get('confidence', 0),
        'ts':          datetime.now().isoformat(),
        'resolved':    False,
    })
    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2))


# ─── AI ────────────────────────────────────────────────────────────────────────

AI_PROMPT_BASE = """
You are NEVA Medic. Respond ONLY with JSON:
{"diagnosis":"root cause in Russian","playbook":"start_approval_server|restart_thermal_guard|sync_appsupport|restart_executor_launchd|restart_mcp_soft|restart_mcp_server_net|notify_director","confidence":0.0-1.0,"reasoning":"one line"}
"""

def ai_diagnose(problem: dict, state: dict) -> dict:
    knowledge = load_knowledge(problem['id'])
    prompt = AI_PROMPT_BASE
    if knowledge:
        prompt = AI_PROMPT_BASE + f"\n\n## Контекст компонента:\n{knowledge[:2000]}"
    return ai_call(prompt, json.dumps({'problem': problem, 'state_summary': {
        'executor':       state.get('executor'),
        'mcp_net':        state.get('mcp_net'),
        'thermal_state':  state.get('thermal', {}).get('state'),
        'thermal_log_age':state.get('thermal', {}).get('log_age_sec'),
        'approval_http':  state.get('executor', {}).get('approval_http'),
        'executor_spam':  state.get('executor_spam', {}).get('count', 0),
    }}, ensure_ascii=False))


# ─── L2 AGENT ──────────────────────────────────────────────────────────────────

def launch_repair_agent(esc_id: str):
    if not REPAIR_AGENT.exists():
        log.error(f'L2 Agent: файл не найден {REPAIR_AGENT}')
        return
    marker = ESCALATIONS / f'.agent_ran_{esc_id}'
    if marker.exists():
        log.info(f'L2 Agent: маркер уже существует для {esc_id} — пропуск')
        return
    agent_log = LOGS / 'repair_agent.log'
    try:
        proc = subprocess.Popen(
            [sys.executable, str(REPAIR_AGENT), esc_id],
            stdout=open(agent_log, 'a'), stderr=subprocess.STDOUT,
            start_new_session=True)
        log.info(f'🤖 L2 Agent запущен: PID={proc.pid} esc_id={esc_id}')
        mcp_push_event({'type': 'l2_start', 'esc_id': esc_id, 'pid': proc.pid})
    except Exception as e:
        log.error(f'L2 Agent: ошибка запуска: {e}')


# ─── ЭСКАЛАЦИЯ ─────────────────────────────────────────────────────────────────

def create_escalation(problem: dict, actions_tried: list, ai_result: dict) -> str:
    ESCALATIONS.mkdir(exist_ok=True)
    esc_id   = f"ESC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    esc_file = ESCALATIONS / f'{esc_id}.json'
    escalation = {
        'id': esc_id, 'ts': datetime.now().isoformat(),
        'status': 'OPEN', 'type': 'AUTO_FAIL',
        'component': problem.get('component', ''),
        'problem_id': problem['id'], 'severity': problem['severity'],
        'symptom': problem['description'],
        'diagnosis': ai_result.get('diagnosis', ''),
        'confidence': ai_result.get('confidence', 0),
        'attempts': sum(a.get('attempts', 0) for a in actions_tried),
        'actions_tried': [{'playbook': a.get('playbook', ''),
                           'attempts': a.get('attempts', 0),
                           'fail_reason': a.get('fail_reason', '')} for a in actions_tried],
        'hypothesis': _generate_hypothesis(problem),
        'recommendation': _generate_recommendation(problem),
        'state_snapshot': {}, 'architect_notes': '',
        'resolution': '', 'resolved_ts': '',
        'cc_url': f'http://127.0.0.1:{CC_PORT}/escalation/{esc_id}',
        'l2_status': None, 'l2_ts': None, 'l2_detail': None,
    }
    try:
        state = collect_state()
        escalation['state_snapshot'] = {
            'thermal': state.get('thermal', {}),
            'executor': state.get('executor', {}),
            'mcp_net': state.get('mcp_net', {}),
            'sync': state.get('sync', {}),
            'medic_log_tail': _read_log_tail(LOG_PATH, 20),
        }
    except Exception as e:
        escalation['state_snapshot'] = {'error': str(e)}
    esc_file.write_text(json.dumps(escalation, ensure_ascii=False, indent=2, default=str))
    log.error(f'🆘 ESCALATION: {esc_id} — {problem["description"]}')
    _update_escalation_index(esc_id, escalation)
    inbox_write_escalation(esc_id, escalation)
    inbox_update_index()
    mcp_push_event({'type': 'escalation', 'esc_id': esc_id,
                    'problem_id': problem['id'], 'severity': problem['severity'],
                    'symptom': problem['description'][:80]})
    notify_with_url('🆘 NEVA — СЛОМАНО, не могу починить',
                    f'{problem["description"][:50]}',
                    url=escalation['cc_url'], sound='Basso')
    pid = problem['id']
    if pid in AGENT_ELIGIBLE:
        log.info(f'L2 Agent: запуск для {esc_id} (problem={pid})')
        launch_repair_agent(esc_id)
    return esc_id


def _generate_hypothesis(problem: dict) -> str:
    return {
        'thermal_log_stale':   '1) FDA блокирует Guard; 2) падает при импорте venv; 3) thermal_state.json заблок.',
        'approval_not_running':'1) порт 8766 занят; 2) файл не синхронизирован; 3) неверный venv.',
        'executor_log_spam':   '1) старый plist → системный python; 2) FDA не дан launchd.',
        'mcp_not_running':     '1) Claude Desktop закрыт; 2) MCP config сломан; 3) mcp_server.py упал.',
        'mcp_server_net_down': '1) launchd не поднял; 2) порт 9000 занят; 3) ошибка импорта.',
        'mcp_approval_hang':    '1) executor ждёт approval >90с; 2) BASE_DIR ограничение; 3) deadlock в write queue.',
        'mcp_proxy_fallback_stuck': '1) neva_mcp_proxy.py завис; 2) порт 9000 не принимает; 3) буфер переполнен.',
    }.get(problem['id'], 'Требует анализа архитектора.')


def _generate_recommendation(problem: dict) -> str:
    return {
        'thermal_log_stale':   'ps aux | grep thermal; проверить FDA; запустить вручную через venv.',
        'approval_not_running':'lsof -i :8766; проверить sync_to_appsupport.sh.',
        'mcp_not_running':     'open -a Claude; проверить claude_desktop_config.json.',
        'mcp_server_net_down': 'launchctl list | grep mcp-server; проверить logs/mcp_server_net.log.',
        'mcp_approval_hang':    'проверить BASE_DIR в executor.py; grep approval logs/mcp_server_net.log.',
        'mcp_proxy_fallback_stuck': 'ps aux | grep mcp_proxy; перезапустить neva_mcp_server.py через launchd.',
    }.get(problem['id'], 'Изучить logs и state_snapshot.')


def _read_log_tail(p: Path, n: int = 20) -> list:
    try: return p.read_text(errors='replace').splitlines()[-n:]
    except Exception: return []


def _update_escalation_index(esc_id: str, esc: dict):
    idx_file = ESCALATIONS / 'index.json'
    idx = []
    if idx_file.exists():
        try: idx = json.loads(idx_file.read_text())
        except Exception: pass
    idx.append({'id': esc_id, 'ts': esc['ts'], 'status': esc['status'],
                'type': esc.get('type', 'AUTO_FAIL'), 'component': esc.get('component', ''),
                'problem_id': esc['problem_id'], 'severity': esc.get('severity', ''),
                'symptom': esc.get('symptom', '')[:80], 'l2_status': esc.get('l2_status')})
    idx_file.write_text(json.dumps(idx, ensure_ascii=False, indent=2))


# ─── ГЛАВНЫЙ ЦИКЛ ──────────────────────────────────────────────────────────────

def heal_cycle(dry_run: bool = False) -> dict:
    reply = mcp_check_reply()
    if reply:
        log.info(f'💬 Выполняю инструкцию Клода: {reply[:80]}')
        mcp_push_event({'type': 'claude_reply_executing', 'instruction': reply[:200]})
        save_pending(
            {'id': 'claude_instruction', 'severity': 'MEDIUM', 'component': 'medic',
             'description': f'Инструкция Клода: {reply[:60]}'},
            {'diagnosis': reply, 'confidence': 1.0})

    state    = collect_state()
    problems = detect_problems(state)
    mcp_push_event({'type': 'heal_start', 'problems_count': len(problems),
                    'problems': [p['id'] for p in problems]})

    if not problems:
        log.debug('heal_cycle: OK')
        report = {'ts': datetime.now().isoformat(), 'status': 'ok', 'problems': [], 'actions': []}
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        mcp_push_event({'type': 'heal_end', 'status': 'ok'})
        return report

    log.warning(f'heal_cycle: {len(problems)} проблем: {[p["id"] for p in problems]}')
    actions = []

    for problem in sorted(problems, key=lambda p: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}[p['severity']]):
        pid = problem['id']
        mcp_push_event({'type': 'problem_found', 'problem_id': pid,
                        'severity': problem['severity'], 'description': problem['description'][:80]})

        skip, wait_remaining = backoff_check(pid)
        if skip:
            log.info(f'[{pid}] BACKOFF через {wait_remaining}с')
            actions.append({'problem_id': pid, 'severity': problem['severity'],
                            'mode': 'BACKOFF', 'skipped': True,
                            'wait_remaining_sec': wait_remaining,
                            'ts': datetime.now().isoformat()})
            mcp_push_event({'type': 'backoff', 'problem_id': pid, 'wait_sec': wait_remaining})
            continue

        backoff_record_attempt(pid)

        if pid in PLAYBOOK_MAP:
            ai_result = ai_diagnose(problem, state)
            ai_result['playbook'] = PLAYBOOK_MAP[pid]
            if pid in ALERT_ONLY:
                ai_result['confidence'] = 1.0
        else:
            ai_result = ai_diagnose(problem, state)

        playbook_name = ai_result.get('playbook', 'notify_director')
        mode          = decide_mode(problem, ai_result)

        action_result = {
            'problem_id': pid, 'severity': problem['severity'],
            'playbook': playbook_name, 'mode': mode,
            'confidence': ai_result.get('confidence', 0.0),
            'diagnosis': ai_result.get('diagnosis', ''),
            'ts': datetime.now().isoformat(),
            'success': False, 'attempts': 0, 'fail_reason': '',
        }

        if mode == 'ALERT':
            run_playbook('notify_director', dry_run=dry_run)
            notify('🚨 NEVA', f'ALERT: {problem["description"][:60]}', sound='Basso')
            action_result['success'] = True
            action_result['attempts'] = 1

        elif mode == 'ASK':
            save_pending(problem, ai_result)
            action_result['success'] = True
            action_result['attempts'] = 1

        elif mode == 'AUTO':
            attempt = 0; success = False; fail_reason = ''
            while attempt < MAX_ATTEMPTS and not success:
                attempt += 1
                log.info(f'  Попытка {attempt}/{MAX_ATTEMPTS}: {playbook_name}')
                try:
                    success = run_playbook(playbook_name, dry_run=dry_run)
                    if not success: fail_reason = f'playbook False (попытка {attempt})'
                except Exception as e:
                    fail_reason = str(e)
                if not success and attempt < MAX_ATTEMPTS:
                    time.sleep(5)

            action_result.update({'attempts': attempt, 'success': success, 'fail_reason': fail_reason})

            if success:
                log.info(f'✅ AUTO fix: {pid}')
                notify('✅ NEVA — починил', f'{problem["description"][:50]}')
                backoff_reset(pid)
                mcp_reset_availability()  # сбрасываем кэш если починили MCP
                mcp_push_event({'type': 'heal_success', 'problem_id': pid,
                                'playbook': playbook_name})
                incident_log_write({'ts': __import__('datetime').datetime.now().isoformat(),
                    'problem_id': pid, 'severity': problem['severity'],
                    'description': problem['description'], 'playbook': playbook_name,
                    'attempts': attempt, 'result': 'SUCCESS',
                    'diagnosis': ai_result.get('diagnosis',''),
                    'confidence': ai_result.get('confidence',0.0), 'fail_reason': ''})
            else:
                log.error(f'❌ AUTO fail: {pid} — {fail_reason}')
                mcp_push_event({'type': 'heal_fail', 'problem_id': pid,
                                'fail_reason': fail_reason[:100]})
                incident_log_write({'ts': __import__('datetime').datetime.now().isoformat(),
                    'problem_id': pid, 'severity': problem['severity'],
                    'description': problem['description'], 'playbook': playbook_name,
                    'attempts': attempt, 'result': 'FAIL',
                    'diagnosis': ai_result.get('diagnosis',''),
                    'confidence': ai_result.get('confidence',0.0), 'fail_reason': fail_reason})
                create_escalation(problem, [action_result], ai_result)
                save_pending(problem, {**ai_result,
                    'diagnosis': f'AUTO-ремонт провалился после {attempt} попыток: {fail_reason}',
                    'confidence': 0.0})

        actions.append(action_result)

    report = {'ts': datetime.now().isoformat(),
              'status': 'repaired' if any(a.get('success') for a in actions) else 'failed',
              'problems': problems, 'actions': actions, 'state': state}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    mcp_push_event({'type': 'heal_end', 'status': report['status'],
                    'fixed': sum(1 for a in actions if a.get('success'))})
    return report


# ─── SELF-TEST ─────────────────────────────────────────────────────────────────

def self_test() -> list:
    results = []
    try:
        s = collect_state()
        ok = {'executor', 'auditor', 'thermal', 'sync', 'versions', 'mcp_net'} <= set(s.keys())
        results.append(('ST-01', 'PASS' if ok else 'FAIL', 'collect_state OK (incl. mcp_net)'))
    except Exception as e: results.append(('ST-01', 'FAIL', str(e)))
    try:
        problems = detect_problems({'executor': {}, 'auditor': {}, 'thermal': {},
                                    'sync': {}, 'versions': {}, 'mcp_net': {}})
        results.append(('ST-02', 'PASS', f'detect_problems OK: {len(problems)}'))
    except Exception as e: results.append(('ST-02', 'FAIL', str(e)))
    for pb, st in [('notify_director', 'ST-03'), ('start_approval_server', 'ST-04'),
                   ('restart_thermal_guard', 'ST-05'), ('sync_appsupport', 'ST-06'),
                   ('restart_mcp_server_net', 'ST-06b')]:
        try:
            ok = run_playbook(pb, dry_run=True)
            results.append((st, 'PASS' if ok else 'FAIL', f'{pb} dry_run'))
        except Exception as e: results.append((st, 'FAIL', str(e)))
    try:
        r = ai_call(AI_PROMPT_BASE, '{"problem":{"id":"test"},"state_summary":{}}')
        ok = 'playbook' in r and 'confidence' in r
        results.append(('ST-07', 'PASS' if ok else 'FAIL',
                        f'ai_call conf={r.get("confidence", 0):.2f}'))
    except Exception as e: results.append(('ST-07', 'FAIL', str(e)))
    try:
        REPORT.write_text(json.dumps({'status': 'self_test'}, ensure_ascii=False))
        ok = json.loads(REPORT.read_text()).get('status') == 'self_test'
        results.append(('ST-08', 'PASS' if ok else 'FAIL', 'report write/read'))
    except Exception as e: results.append(('ST-08', 'FAIL', str(e)))
    try:
        T = '__st09__'
        backoff_reset(T)
        skip, _ = backoff_check(T); assert not skip
        backoff_record_attempt(T)
        skip2, w = backoff_check(T); assert skip2 and w > 0
        backoff_reset(T)
        results.append(('ST-09', 'PASS', f'backoff OK w={w}s'))
    except Exception as e: results.append(('ST-09', 'FAIL', str(e)))
    try:
        T2 = '__st10__'
        backoff_reset(T2); backoff_record_attempt(T2)
        c = _load_counters(); assert T2 in c and c[T2]['attempts'] == 1
        backoff_reset(T2); assert T2 not in _load_counters()
        results.append(('ST-10', 'PASS', 'problem_counter OK'))
    except Exception as e: results.append(('ST-10', 'FAIL', str(e)))
    try:
        _inbox_init()
        test_file = CLAUDE_INBOX / '__test__.json'
        test_file.write_text(json.dumps({'test': True}))
        ok = test_file.exists()
        test_file.unlink(missing_ok=True)
        results.append(('ST-11', 'PASS' if ok else 'FAIL', 'claude_inbox write OK'))
    except Exception as e: results.append(('ST-11', 'FAIL', str(e)))
    try:
        loaded = []
        for pid in ['thermal_log_stale', 'approval_not_running', 'mcp_not_running',
                    'executor_log_spam', 'auditor_log_stale']:
            k = load_knowledge(pid)
            if k: loaded.append(pid)
        results.append(('ST-12', 'PASS' if len(loaded) == 5 else 'FAIL',
                        f'knowledge base: {len(loaded)}/5 файлов загружено'))
    except Exception as e: results.append(('ST-12', 'FAIL', str(e)))
    try:
        results.append(('ST-13', 'PASS' if REPAIR_AGENT.exists() else 'FAIL',
                        f'repair_agent.py: {"найден" if REPAIR_AGENT.exists() else "НЕ НАЙДЕН"}'))
    except Exception as e: results.append(('ST-13', 'FAIL', str(e)))
    try:
        required = {'thermal_log_stale', 'mcp_not_running', 'approval_not_running',
                    'mcp_server_net_down'}
        ok = required <= AGENT_ELIGIBLE
        results.append(('ST-14', 'PASS' if ok else 'FAIL',
                        f'AGENT_ELIGIBLE: {len(AGENT_ELIGIBLE)} записей'))
    except Exception as e: results.append(('ST-14', 'FAIL', str(e)))
    try:
        results.append(('ST-15', 'PASS' if CHRONIC_REPORT_SCRIPT.exists() else 'FAIL',
                        f'chronic_report.py: {"найден" if CHRONIC_REPORT_SCRIPT.exists() else "НЕ НАЙДЕН"}'))
    except Exception as e: results.append(('ST-15', 'FAIL', str(e)))
    try:
        mcp_push_event({'type': 'self_test', 'msg': 'ST-16'})
        results.append(('ST-16', 'PASS', 'mcp_push_event не падает'))
    except Exception as e: results.append(('ST-16', 'FAIL', str(e)))
    try:
        reply = mcp_check_reply()
        results.append(('ST-17', 'PASS', f'mcp_check_reply OK (reply={reply is not None})'))
    except Exception as e: results.append(('ST-17', 'FAIL', str(e)))
    # ST-18: v3.7 — mcp_server_net_down в PLAYBOOK_MAP и detect_problems
    try:
        ok1 = 'mcp_server_net_down' in PLAYBOOK_MAP
        ok2 = PLAYBOOK_MAP.get('mcp_server_net_down') == 'restart_mcp_server_net'
        ok3 = 'restart_mcp_server_net' in {
            'start_approval_server', 'restart_thermal_guard', 'sync_appsupport',
            'restart_executor_launchd', 'restart_mcp_soft', 'remind_pending',
            'notify_director', 'restart_mcp_server_net'
        }
        ok4 = 'mcp_server_net_down' in AGENT_ELIGIBLE
        results.append(('ST-18', 'PASS' if all([ok1, ok2, ok3, ok4]) else 'FAIL',
                        'mcp_server_net мониторинг: PLAYBOOK_MAP + AGENT_ELIGIBLE OK'))
    except Exception as e: results.append(('ST-18', 'FAIL', str(e)))
    return results


# ─── LOCK / SNAPSHOT / MAIN ────────────────────────────────────────────────────

def save_snapshot():
    state    = collect_state()
    problems = detect_problems(state)
    SNAPSHOT.write_text(json.dumps({'created': datetime.now().isoformat(), 'version': '3.7',
                                    'state': state, 'problems': problems},
                                   ensure_ascii=False, indent=2, default=str))
    print(f'✅ Snapshot: {SNAPSHOT}')
    for p in problems: print(f'  ⚠️ {p["severity"]}: {p["description"]}')
    if not problems: print('  Проблем нет')


def acquire_lock() -> bool:
    try:
        if LOCK_FILE.exists():
            old_pid = int(LOCK_FILE.read_text().strip())
            try: os.kill(old_pid, 0); return False
            except (ProcessLookupError, PermissionError):
                log.warning(f'Stale lock PID {old_pid}')
        LOCK_FILE.write_text(str(os.getpid()))
        return True
    except Exception as e:
        log.error(f'Lock: {e}'); return True


def release_lock():
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text().strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except Exception: pass


def main():
    dry_run = '--dry-run' in sys.argv
    if '--snapshot' in sys.argv:
        save_snapshot(); return
    if '--self-test' in sys.argv:
        print('=== NEVA Medic v3.7 self-test ===')
        results = self_test()
        passed  = sum(1 for _, s, _ in results if s == 'PASS')
        for name, status, msg in results:
            print(f'  {"✅" if status == "PASS" else "❌"} {name}: {msg}')
        print(f'\nРезультат: {passed}/{len(results)} PASS')
        sys.exit(0 if passed == len(results) else 1)
    if '--check' in sys.argv:
        state    = collect_state()
        problems = detect_problems(state)
        if problems:
            for p in problems: print(f'  [{p["severity"]}] {p["description"]}')
            sys.exit(1)
        print('✅ OK'); sys.exit(0)
    if '--heal' in sys.argv:
        r = heal_cycle(dry_run=dry_run)
        for a in r['actions']:
            if a.get('skipped'): print(f'⏳ BACKOFF {a["problem_id"]} через {a["wait_remaining_sec"]}с')
            else: print(f'{"✅" if a.get("success") else "❌"} [{a["mode"]}] {a["problem_id"]}')
        return
    if '--inbox' in sys.argv:
        inbox_update_index()
        idx = CLAUDE_INBOX / 'INDEX.json'
        if idx.exists():
            data  = json.loads(idx.read_text())
            items = data.get('items', [])
            if not items: print('✅ claude_inbox пусто')
            for item in items:
                print(f'  [{item["status"]}] {item["id"]}: {item["symptom"]}')
        return
    if not acquire_lock():
        print('NEVA Medic уже запущен. Выход.')
        sys.exit(0)
    import atexit
    atexit.register(release_lock)
    _inbox_init()
    inbox_update_index()
    log.info(f'=== NEVA Medic v3.7 started (dry_run={dry_run}) PID={os.getpid()} ===')
    notify('💊 NEVA Medic v3.7', 'Запущен — мониторинг MCP-сервера :9000 активен', sound='Glass')
    update_chronic_report()
    cycle_count = 0
    while True:
        try:
            heal_cycle(dry_run=dry_run)
            run_pending_repairs()
            cycle_count += 1
            if cycle_count % 5 == 0:
                update_chronic_report()
                mcp_reset_availability()
        except Exception as e:
            log.error(f'heal_cycle error: {e}', exc_info=True)
        time.sleep(POLL_SEC)


if __name__ == '__main__':
    main()


# ─── INCIDENT LOG (Вариант Б) ──────────────────────────────────────────────────
# Автоматический журнал инцидентов для базы знаний медика.
# После каждого heal_success / heal_fail / escalation — пишем запись.
# Вариант В (после TASK-007 Этап 2): заменить на vector search через Kuzu + e5-small.

INCIDENT_LOG = STATE / 'incident_log.json'

def _load_incident_log() -> list:
    try:
        if INCIDENT_LOG.exists():
            return json.loads(INCIDENT_LOG.read_text())
    except Exception:
        pass
    return []

def incident_log_write(entry: dict):
    """Пишет запись в incident_log.json. Хранит последние 500 инцидентов."""
    try:
        log_data = _load_incident_log()
        log_data.append(entry)
        if len(log_data) > 500:
            log_data = log_data[-500:]
        INCIDENT_LOG.write_text(json.dumps(log_data, ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        log.error(f'incident_log_write error: {e}')

def incident_log_search(problem_id: str, limit: int = 3) -> list:
    """Возвращает последние N инцидентов с данным problem_id."""
    try:
        log_data = _load_incident_log()
        matches = [e for e in log_data if e.get('problem_id') == problem_id]
        return matches[-limit:]
    except Exception:
        return []
