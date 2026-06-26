#!/usr/bin/env python3
"""
NEVA Inspector v6 — независимый сторожевой монитор.
Архитектура утверждена аудиторами INSPECTOR-001 (7 кругов ДУМЫ, 2026-06-25).

Директор: Серж | Архитектор: Claude
Запуск: launchd com.neva.inspector.plist (KeepAlive=true)
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

# ─── КОНФИГУРАЦИЯ ─────────────────────────────────────────────────────────────
NEVA_DIR    = Path.home() / 'Documents/NEVA'
BRIDGE_DIR  = Path.home() / 'Documents/NEVA_MCP_BRIDGE'
STATE_DIR   = BRIDGE_DIR / 'state'
LOG_PATH    = BRIDGE_DIR / 'logs/inspector.log'

STATUS_FILE    = STATE_DIR / 'inspector_status.json'
HEARTBEAT_FILE = STATE_DIR / 'inspector_heartbeat'
MAINTENANCE    = STATE_DIR / 'inspector_maintenance'
SUPPRESS_CLAUDE = STATE_DIR / 'inspector_suppress_claude'

POLL_SEC       = 30      # интервал цикла
STALE_KILL_SEC = 900     # 15 мин в STALE → pkill (было 5 мин — слишком агрессивно)
GRACE_DEFAULT  = 30      # grace period по умолчанию
CONFIRM_CYCLES = 2       # циклов для подтверждения DEAD/STALE
MEDIC_HEARTBEAT_MAX_AGE = 90  # если medic.log старше → medic завис

# ─── ПРОГРАММЫ ────────────────────────────────────────────────────────────────
PROGRAMS = {
    'claude_desktop':    {'match': 'Claude',               'http': None,          'log': None,               'grace': 30,  'stale_timeout': None},
    'neva_medic':        {'match': 'neva_medic.py',        'http': None,          'log': 'medic.log',        'grace': 30,  'stale_timeout': 180},
    'neva_mcp_server':   {'match': 'neva_mcp_server.py',   'http': ':9000/health','log': None,               'grace': 30,  'stale_timeout': 120},
    'neva_thermal_guard':{'match': 'neva_thermal_guard.py','http': None,          'log': 'thermal.log',      'grace': 30,  'stale_timeout': 120},
    'neva_approval':     {'match': 'neva_approval_server', 'http': ':8766/health','log': None,               'grace': 30,  'stale_timeout': 120},
    'background_auditor':{'match': 'background_auditor',   'http': None,          'log': None,               'grace': 60,  'stale_timeout': None},
    'neva_control_ctr':  {'match': 'neva_control_center',  'http': ':9001',       'log': None,               'grace': 30,  'stale_timeout': 120},
    'desktop_commander': {'match': 'desktop-commander',    'http': None,          'log': None,               'grace': 30,  'stale_timeout': 300},
    'ollama':            {'match': 'ollama',               'http': ':11434',      'log': None,               'grace': 60,  'stale_timeout': None},
    'chrome_cdp':        {'match': 'Google Chrome',        'http': ':9222/json',  'log': None,               'grace': 30,  'stale_timeout': None},
}

# ─── ЛОГИРОВАНИЕ ──────────────────────────────────────────────────────────────
import logging
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [inspector] %(levelname)s %(message)s',
    handlers=[logging.FileHandler(LOG_PATH)]
)
log = logging.getLogger('neva_inspector')

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────
CLAUDE_INBOX = Path.home() / 'Documents/NEVA_MCP_BRIDGE/claude_inbox'

def write_claude_inbox(title: str, body: str):
    """Пишет сообщение в claude_inbox — Claude прочитает в начале следующей сессии."""
    try:
        CLAUDE_INBOX.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        f = CLAUDE_INBOX / f'inspector_{ts}.json'
        import json as _j
        f.write_text(_j.dumps({
            'ts': datetime.now().isoformat(),
            'from': 'neva_inspector',
            'title': title,
            'body': body,
            'priority': 'HIGH',
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        log.error(f'claude_inbox write error: {e}')

def tg(msg: str, silent: bool = False):
    try:
        import urllib.request, urllib.parse
        TOKEN   = '8577539474:AAFL14KKxZ9GGWOuxb14qGHL1HJpJaIjmq0'
        CHAT_ID = '1919255029'
        data = urllib.parse.urlencode({
            'chat_id': CHAT_ID, 'text': msg,
            'disable_notification': silent,
        }).encode()
        urllib.request.urlopen(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            data, timeout=5
        )
    except Exception:
        pass

# ─── HTTP PING ─────────────────────────────────────────────────────────────────
def http_ok(port_path: str) -> bool:
    """Пингует localhost:PORT/path. Возвращает True если HTTP 200."""
    try:
        import urllib.request
        url = f'http://127.0.0.1{port_path}' if port_path.startswith(':') else port_path
        r = urllib.request.urlopen(url, timeout=3)
        return r.status < 500
    except Exception:
        return False

# ─── LOG FRESHNESS ─────────────────────────────────────────────────────────────
def log_age(log_name: str) -> float | None:
    """Возвращает возраст лог файла в секундах или None если нет файла."""
    paths = [BRIDGE_DIR / 'logs' / log_name, NEVA_DIR / log_name]
    for p in paths:
        if p.exists():
            return time.time() - p.stat().st_mtime
    return None

# ─── KILL ─────────────────────────────────────────────────────────────────────
def kill_graceful(pid: int, timeout: int = 5):
    """SIGTERM → wait → SIGKILL по PID."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=timeout)
    except psutil.TimeoutExpired:
        try:
            psutil.Process(pid).kill()
        except psutil.NoSuchProcess:
            pass
    except psutil.NoSuchProcess:
        pass

# ─── FIND PROCESS ─────────────────────────────────────────────────────────────
def find_proc(match: str):
    """Ищет процесс по имени. Возвращает psutil.Process или None."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            name = proc.info['name'] or ''
            if match in cmdline or match in name:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

# ─── STATE MACHINE ────────────────────────────────────────────────────────────
# Хранит состояние каждой программы между циклами
_prog_state: dict = {}

def check_program(name: str, cfg: dict) -> dict:
    """Проверяет одну программу. Возвращает dict с текущим статусом."""
    now = time.time()
    prev = _prog_state.get(name, {
        'status': 'UNKNOWN', 'pid': None, 'create_time': None,
        'dead_cycles': 0, 'stale_cycles': 0, 'recover_cycles': 0,
        'dead_since': None, 'stale_since': None, 'start_detected_at': None,
    })

    proc = find_proc(cfg['match'])
    pid  = proc.info['pid'] if proc else None
    ctime = proc.info['create_time'] if proc else None

    # Смена PID → переход в STARTING
    pid_changed = (pid is not None and pid != prev['pid'] and
                   ctime != prev['create_time'])
    if pid_changed:
        state = {**prev, 'pid': pid, 'create_time': ctime,
                 'status': 'STARTING', 'start_detected_at': now,
                 'dead_cycles': 0, 'stale_cycles': 0}
        _prog_state[name] = state
        return _make_result(name, state, now)

    grace = cfg.get('grace', GRACE_DEFAULT)
    stale_timeout = cfg.get('stale_timeout')
    status = prev['status']

    # ── STARTING → DEAD или ALIVE ──────────────────────────────────────────
    if status == 'STARTING':
        if pid is None:
            # PID исчез немедленно → DEAD
            state = {**prev, 'status': 'DEAD', 'pid': None,
                     'dead_since': now, 'dead_cycles': 1}
        elif now - prev['start_detected_at'] >= grace:
            # Grace истёк, процесс жив → ALIVE
            state = {**prev, 'status': 'ALIVE'}
        else:
            state = prev  # всё ещё STARTING
        _prog_state[name] = state
        return _make_result(name, state, now)

    # ── Нет PID → проверяем DEAD ───────────────────────────────────────────
    if pid is None:
        dead_cycles = prev['dead_cycles'] + 1
        if dead_cycles >= CONFIRM_CYCLES:
            state = {**prev, 'status': 'DEAD', 'pid': None,
                     'dead_since': prev.get('dead_since') or now,
                     'dead_cycles': dead_cycles}
        else:
            state = {**prev, 'dead_cycles': dead_cycles}
        _prog_state[name] = state
        return _make_result(name, state, now)

    # ── PID есть, проверяем ALIVE/STALE ───────────────────────────────────
    # Сброс dead_cycles
    prev = {**prev, 'dead_cycles': 0, 'dead_since': None}

    # HTTP и лог проверки
    http_alive = True
    log_alive  = True
    has_http   = bool(cfg.get('http'))
    has_log    = bool(cfg.get('log'))

    if has_http:
        http_alive = http_ok(cfg['http'])
    if has_log and stale_timeout:
        age = log_age(cfg['log'])
        log_alive = (age is None) or (age < stale_timeout)

    is_healthy = (not has_http or http_alive) and (not has_log or log_alive)

    if is_healthy:
        # Восстановление STALE → ALIVE
        state = {**prev, 'status': 'ALIVE', 'pid': pid,
                 'create_time': ctime, 'stale_cycles': 0,
                 'stale_since': None}
    else:
        # Деградация → STALE
        stale_cycles = prev['stale_cycles'] + 1
        if stale_cycles >= CONFIRM_CYCLES:
            state = {**prev, 'status': 'STALE', 'pid': pid,
                     'stale_cycles': stale_cycles,
                     'stale_since': prev.get('stale_since') or now}
        else:
            state = {**prev, 'stale_cycles': stale_cycles, 'pid': pid}

    _prog_state[name] = state
    return _make_result(name, state, now)

def _make_result(name: str, state: dict, now: float) -> dict:
    uptime = None
    if state.get('create_time') and state['status'] not in ('DEAD', 'UNKNOWN'):
        uptime = int(now - state['create_time'])
    dead_secs = int(now - state['dead_since']) if state.get('dead_since') else None
    stale_secs = int(now - state['stale_since']) if state.get('stale_since') else None
    return {
        'status': state['status'],
        'pid': state.get('pid'),
        'uptime_sec': uptime,
        'dead_sec': dead_secs,
        'stale_sec': stale_secs,
    }

# ─── ТРИГГЕРЫ ДЕЙСТВИЙ ────────────────────────────────────────────────────────
_cooldowns: dict = {}
_action_counts: dict = {}
_pkill_counts: dict = {}    # счётчик pkill по имени процесса

def _cooldown_ok(action: str, cooldown_sec: int, max_per_hour: int) -> bool:
    now = time.time()
    last = _cooldowns.get(action, 0)
    count = _action_counts.get(action, [])
    count = [t for t in count if now - t < 3600]
    if now - last < cooldown_sec:
        return False
    if len(count) >= max_per_hour:
        return False
    return True

def _cooldown_set(action: str):
    now = time.time()
    _cooldowns[action] = now
    _action_counts.setdefault(action, []).append(now)

def check_triggers(programs: dict):
    """Проверяет триггеры и выполняет действия."""
    if MAINTENANCE.exists():
        return

    # Защита памяти: если swap > 6GB — останавливаем все действия Inspector
    # Свап на SSD изнашивает NAND. Inspector не должен усугублять.
    import psutil as _ps
    swap_gb = _ps.swap_memory().used / 1024**3
    if swap_gb > 6.0:
        log.warning(f'SWAP ЗАЩИТА: {swap_gb:.1f}GB — все действия Inspector заморожены')
        tg(f'⚠️ Inspector: swap={swap_gb:.1f}GB > 6GB.\nВсе автодействия заморожены до снижения свапа.\nПерезагрузи Мак для очистки памяти.', silent=False)
        write_claude_inbox(
            f'SWAP КРИТИЧЕСКИЙ: {swap_gb:.1f}GB',
            f'swap={swap_gb:.1f}GB превысил 6GB. Все действия Inspector заморожены.\n'
            f'Нужно: 1) перезагрузить Мак, 2) найти причину утечки памяти.'
        )
        return  # не выполняем никаких pkill и restart

    now = time.time()

    # ── STALE → DEAD эскалация (любой процесс) ────────────────────────────
    now_ts = time.time()
    for name, result in programs.items():
        if result['status'] == 'STALE':
            stale_sec = result.get('stale_sec') or 0
            if stale_sec >= STALE_KILL_SEC:
                pid = result.get('pid')
                if pid:
                    # Лимит pkill: не более 3 раз за 3 часа на один процесс
                    kills = [t for t in _pkill_counts.get(name, [])
                             if now_ts - t < 10800]
                    if len(kills) >= 3:
                        log.error(f'STALE→СТОП: {name} убит {len(kills)}р за 3ч — не помогает. Эскалация.')
                        tg(f'🆘 Inspector: {name} убит {len(kills)} раз за 3ч — не восстанавливается.\nТребуется вмешательство Директора.')
                        write_claude_inbox(
                            f'Inspector: {name} не восстанавливается',
                            f'{name} убит {len(kills)} раз за 3 часа и не восстанавливается.\n'
                            f'Нужна диагностика и исправление кода.'
                        )
                    else:
                        log.warning(f'STALE→pkill: {name} pid={pid} stale={stale_sec}с (попытка {len(kills)+1}/3)')
                        kill_graceful(pid)
                        _pkill_counts.setdefault(name, []).append(now_ts)
                        tg(f'⚡ Inspector: {name} завис {stale_sec//60}мин → pkill (попытка {len(kills)+1}/3)')

    # ── Действие 1: Desktop Commander мёртв >60с ──────────────────────────
    dc = programs.get('desktop_commander', {})
    if (dc.get('status') == 'DEAD' and
            dc.get('dead_sec', 0) >= 60 and
            _cooldown_ok('restart_dc', 600, 3)):
        log.warning('Действие 1: Desktop Commander мёртв — перезапуск MCP')
        try:
            subprocess.run(['pkill', '-f', 'desktop-commander'],
                           capture_output=True, timeout=5)
        except Exception:
            pass
        try:
            subprocess.run(['launchctl', 'unload',
                           str(Path.home()/'Library/LaunchAgents/com.neva.mcp-server.plist')],
                           capture_output=True, timeout=5)
            time.sleep(1)
            subprocess.run(['launchctl', 'load',
                           str(Path.home()/'Library/LaunchAgents/com.neva.mcp-server.plist')],
                           capture_output=True, timeout=5)
        except Exception as e:
            log.error(f'DC restart error: {e}')
        _cooldown_set('restart_dc')
        tg('🔧 Inspector: Desktop Commander мёртв → перезапустил MCP серверы.')

    # ── Действие 2: Claude Desktop + Medic мертвы >5 мин ─────────────────
    claude = programs.get('claude_desktop', {})
    medic  = programs.get('neva_medic', {})
    if (claude.get('status') == 'DEAD' and
            claude.get('dead_sec', 0) >= 300 and
            medic.get('status') == 'DEAD' and
            medic.get('dead_sec', 0) >= 300 and
            not SUPPRESS_CLAUDE.exists() and
            _cooldown_ok('restart_claude', 900, 2)):
        log.warning('Действие 2: Claude+Medic мертвы → перезапуск Claude Desktop')
        try:
            # Проверяем через AppleScript — есть ли процесс Claude
            r = subprocess.run(
                ['osascript', '-e',
                 'tell app "System Events" to count processes whose name is "Claude"'],
                capture_output=True, text=True, timeout=10
            )
            count = int(r.stdout.strip() or '0')
            if count == 0:
                subprocess.run(
                    ['osascript', '-e', 'tell application "Claude" to activate'],
                    capture_output=True, timeout=15
                )
                _cooldown_set('restart_claude')
                tg('⚠️ Inspector: Claude Desktop + Medic мертвы >5 мин.\n'
                   'Перезапустил Claude Desktop.\n'
                   'Claude должен прочитать SESSION_BRIEF и поднять Medic.')
            else:
                log.info('Claude процесс есть в System Events — не перезапускаем')
                tg('⚠️ Inspector: Claude Desktop недоступен, Medic мёртв.\n'
                   'Claude процесс есть но не отвечает. Нужно твоё вмешательство.')
        except Exception as e:
            log.error(f'Claude restart error: {e}')

# ─── СИСТЕМА ──────────────────────────────────────────────────────────────────
def get_system() -> dict:
    vm  = psutil.virtual_memory()
    sw  = psutil.swap_memory()
    cpu = psutil.cpu_percent(interval=1)
    return {
        'mem_pct':  round(vm.percent, 1),
        'swap_gb':  round(sw.used / 1024**3, 2),
        'cpu_pct':  round(cpu, 1),
    }

# ─── QWEN ДИАГНОЗ ─────────────────────────────────────────────────────────────
_last_state_hash: str = ''
_last_qwen_ts: float = 0

def maybe_qwen_diagnosis(programs: dict) -> str | None:
    """Вызывает qwen только при изменении статусов."""
    global _last_state_hash, _last_qwen_ts
    import hashlib
    matrix = {k: v['status'] for k, v in programs.items()}
    h = hashlib.md5(json.dumps(matrix, sort_keys=True).encode()).hexdigest()
    if h == _last_state_hash:
        return None
    _last_state_hash = h
    _last_qwen_ts = time.time()
    try:
        import urllib.request
        payload = json.dumps({
            'model': 'qwen2.5:7b',
            'prompt': (
                'Ты монитор системы NEVA на Mac M1. '
                'Дай одну строку диагноза на русском (макс 100 символов).\n'
                f'Статусы: {json.dumps(matrix, ensure_ascii=False)}'
            ),
            'stream': False,
        }).encode()
        r = urllib.request.urlopen(
            'http://127.0.0.1:11434/api/generate',
            payload, timeout=5
        )
        resp = json.loads(r.read())
        return resp.get('response', '').strip()[:100]
    except Exception:
        return None

# ─── ЗАПИСЬ СОСТОЯНИЯ ─────────────────────────────────────────────────────────
_last_diagnosis: str = '—'

def write_status(programs: dict, system: dict, qwen: str | None):
    global _last_diagnosis
    if qwen:
        _last_diagnosis = qwen
    data = {
        'ts':           datetime.now().isoformat(),
        'programs':     programs,
        'system':       system,
        'qwen_diagnosis': _last_diagnosis,
        'qwen_ts':      datetime.fromtimestamp(_last_qwen_ts).isoformat() if _last_qwen_ts else None,
        'maintenance':  MAINTENANCE.exists(),
    }
    tmp = STATUS_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    os.replace(tmp, STATUS_FILE)  # атомарная запись

# ─── ГЛАВНЫЙ ЦИКЛ ─────────────────────────────────────────────────────────────
def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f'=== NEVA Inspector v6 started PID={os.getpid()} ===')
    tg('🔍 NEVA Inspector v6 запущен.')

    prev_statuses: dict = {}

    while True:
        try:
            # 1. Мониторинг всех программ
            programs = {name: check_program(name, cfg)
                        for name, cfg in PROGRAMS.items()}

            # 2. Система
            system = get_system()

            # 3. qwen диагноз (только при изменениях)
            qwen = maybe_qwen_diagnosis(programs)

            # 4. Атомарная запись состояния
            write_status(programs, system, qwen)

            # 5. Уведомление: только DEAD и восстановление из DEAD
            # STARTING/STALE/ALIVE флуктуации — только в лог
            alerts = []
            for name, result in programs.items():
                prev_st = prev_statuses.get(name)
                curr_st = result['status']
                if prev_st and prev_st != curr_st:
                    log.info(f'СТАТУС: {name} {prev_st} → {curr_st}')
                    if curr_st == 'DEAD':
                        alerts.append(f'💀 {name}: упал')
                    elif prev_st == 'DEAD' and curr_st in ('ALIVE', 'STARTING'):
                        alerts.append(f'✅ {name}: восстановлен')
                prev_statuses[name] = curr_st
            # Батчинг: одно сообщение на все события за цикл
            if alerts:
                msg = '🔍 NEVA Inspector:\n' + '\n'.join(alerts)
                tg(msg)
                # Пишем в claude_inbox для чтения в следующей сессии
                write_claude_inbox(
                    'Inspector: изменение статусов программ',
                    '\n'.join(alerts)
                )

            # 6. Проверка триггеров действий
            check_triggers(programs)

            # 7. Heartbeat ПОСЛЕ всего (включая триггеры)
            HEARTBEAT_FILE.touch()

        except Exception as e:
            log.error(f'Ошибка цикла: {e}', exc_info=True)
            tg(f'❌ Inspector: ошибка цикла: {e}')

        time.sleep(POLL_SEC)


if __name__ == '__main__':
    main()
