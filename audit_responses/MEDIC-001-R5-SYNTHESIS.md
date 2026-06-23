# ФИНАЛЬНЫЙ СИНТЕЗ — КРУГ 6
# Исправленный код с учётом всех 5 блокирующих замечаний Круга 5
# Блокирующих замечаний: 0. Финальная проверка.

---

## ПОЛНЫЙ СТАРТ neva_medic.py (правильный порядок)

```python
# ═══════════════════════════════════════════════════
# БЛОК 0: Только стандартная библиотека — ДО всего
# ═══════════════════════════════════════════════════
from pathlib import Path   # ← ПЕРВАЯ СТРОКА (Gemini: NameError иначе)
import fcntl, sys, os, time, json, shutil, subprocess, signal

# ═══════════════════════════════════════════════════
# БЛОК 1: Мгновенный heartbeat при старте
# ═══════════════════════════════════════════════════
STATE = Path.home()/'Documents/NEVA_MCP_BRIDGE/state'
STATE.mkdir(parents=True, exist_ok=True)
HEARTBEAT = STATE/'neva_medic.heartbeat'

def write_heartbeat(status):
    tmp = HEARTBEAT.with_suffix('.tmp')
    tmp.write_text(f'{time.time()}|{os.getpid()}|{status}')
    os.replace(tmp, HEARTBEAT)  # атомарно (ChatGPT: race при чтении)

write_heartbeat('starting')  # ← ДО lock и boot-счётчика

# ═══════════════════════════════════════════════════
# БЛОК 2: Защита от двойного запуска
# ═══════════════════════════════════════════════════
LOCK_PATH = STATE/'neva_medic.lock'
_LOCK = open(LOCK_PATH, 'w')

def _acquire_lock(retries=5, delay=0.3):
    for i in range(retries):
        try:
            fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if i < retries - 1: time.sleep(delay)
    return False

if not _acquire_lock():
    write_heartbeat('duplicate_exit')
    sys.exit(0)

# ═══════════════════════════════════════════════════
# БЛОК 3: Boot-счётчик crash loop
# ═══════════════════════════════════════════════════
BOOT_LOG = STATE/'neva_medic_boots.txt'
with open(BOOT_LOG, 'a') as f:
    f.write(f'{time.time()}\n')

boots = []
for l in BOOT_LOG.read_text().splitlines():
    try: boots.append(float(l.strip()))
    except ValueError: pass  # (ChatGPT: битая строка → ValueError)

# Ротация: оставляем только последние 24 часа
BOOT_LOG.write_text('\n'.join(str(t) for t in boots if time.time() - t < 86400) + '\n')

recent = [t for t in boots if time.time() - t < 300]
_CRASH_LOOP = len(recent) >= 3

# ═══════════════════════════════════════════════════
# БЛОК 4: Тяжёлые импорты — ТОЛЬКО ЗДЕСЬ
# ═══════════════════════════════════════════════════
import requests
import psutil

# ═══════════════════════════════════════════════════
# БЛОК 5: heal_cycle()
# ═══════════════════════════════════════════════════
def heal_cycle():
    # Проверка crash loop (DeepSeek: флаг не проверялся)
    if _CRASH_LOOP:
        write_heartbeat('crash_loop')
        push_event('red')
        log('CRITICAL: crash loop — жду ручного вмешательства')
        return

    # Обновляем heartbeat в начале цикла
    write_heartbeat('running')

    # Disk check — два уровня (ChatGPT)
    free_gb = shutil.disk_usage('/').free / 1e9
    if free_gb < 0.5:
        push_event('red'); log('CRITICAL: disk < 500MB'); return
    elif free_gb < 2.0:
        push_event('yellow'); log('WARNING: disk < 2GB')

    # MCP health — JSON schema (DeepSeek)
    try:
        resp = requests.get('http://localhost:9000/health', timeout=(3.05, 15)).json()
        assert resp.get('status') == 'ok' and 'version' in resp
    except Exception as e:
        log(f'MCP health failed: {e}')

    # Конец цикла
    write_heartbeat('heal_end')

# ═══════════════════════════════════════════════════
# БЛОК 6: Белый список playbooks
# ═══════════════════════════════════════════════════
def _restart_via_launchctl(service):
    return subprocess.run(
        ['launchctl','kickstart','-k', f'gui/{os.getuid()}/{service}'],
        capture_output=True
    )

PLAYBOOK_COMMANDS = {
    'restart_mcp':      lambda: _restart_via_launchctl('com.neva.mcp'),
    'restart_approval': lambda: _restart_via_launchctl('com.neva.approval'),
    'restart_auditor':  lambda: _restart_via_launchctl('com.neva.auditor'),
    'restart_medic':    lambda: (time.sleep(2), _restart_via_launchctl('com.neva.medic')),
    'clear_logs':       lambda: [
        p.unlink(missing_ok=True)
        for p in Path('logs').glob('*.log')
        if p.exists() and p.stat().st_size > 100*1024*1024
    ],
}
# nohup УБРАН (Gemini: конфликт с launchd KeepAlive → двойной запуск)

def run_playbook(playbook_id):
    if playbook_id not in PLAYBOOK_COMMANDS:
        log(f'BLOCKED unknown playbook: {playbook_id}')
        return False
    return PLAYBOOK_COMMANDS[playbook_id]()

# ═══════════════════════════════════════════════════
# БЛОК 7: save_incident_log — атомарная запись
# ═══════════════════════════════════════════════════
def save_incident_log(data):
    tmp = Path('state/incident_log.json.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, 'state/incident_log.json')

# ═══════════════════════════════════════════════════
# БЛОК 8: neva_status_dot.py — проверка с grace period
# ═══════════════════════════════════════════════════
def check_medic():
    if not HEARTBEAT.exists():
        return 'DEAD'
    try:
        parts = HEARTBEAT.read_text().strip().split('|')
        ts, pid, status = float(parts[0]), int(parts[1]), parts[2]
    except Exception:
        HEARTBEAT.unlink(missing_ok=True)  # битый файл — удаляем
        return 'CORRUPTED'

    age = time.time() - ts
    try:
        proc_uptime = time.time() - psutil.Process(pid).create_time()
    except psutil.NoSuchProcess:
        return 'DEAD'

    # Grace period: не считать зависанием если процесс только стартовал
    if age > 90 and proc_uptime > 120:
        return 'HUNG'
    return 'OK'

def restart_medic():
    # Только launchctl — nohup УБРАН
    subprocess.run(['launchctl','kickstart','-k',
                    f'gui/{os.getuid()}/com.neva.medic'])
```

---

## ИЗМЕНЕНИЯ В com.neva.medic.plist

```xml
<key>ThrottleInterval</key>
<integer>60</integer>
```

---

## ЗАДАНИЕ КРУГА 6

Это последняя проверка перед реализацией.

1. Нет ли ещё блокирующих замечаний к исправленному коду выше?
2. Порядок операций при старте — верный?
3. Всё ли покрыто или есть упущенные edge cases?
4. Финальный вердикт: ГОТОВ / НЕ ГОТОВ к реализации

Если ГОТОВ — обоснуй. Если НЕ ГОТОВ — назови конкретные блокирующие проблемы.
Отвечай на русском языке.
