# ФИНАЛЬНЫЙ СИНТЕЗ — КРУГ 7
# Все блокирующие замечания Кругов 1-6 закрыты
# Блокирующих: 0. Финальная проверка перед реализацией.

---

## ПОЛНЫЙ СТАРТ neva_medic.py

```python
from pathlib import Path          # ← ПЕРВАЯ СТРОКА
import fcntl, sys, os, time, json, shutil, subprocess, signal

STATE = Path.home()/'Documents/NEVA_MCP_BRIDGE/state'
STATE.mkdir(parents=True, exist_ok=True)
HEARTBEAT = STATE/'neva_medic.heartbeat'

def write_heartbeat(status):
    tmp = HEARTBEAT.with_suffix('.tmp')
    tmp.write_text(f'{time.time()}|{os.getpid()}|{status}')
    os.replace(tmp, HEARTBEAT)

write_heartbeat('starting')

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

BOOT_LOG = STATE/'neva_medic_boots.txt'
with open(BOOT_LOG, 'a') as f:
    f.write(f'{time.time()}\n')

boots = []
for l in BOOT_LOG.read_text().splitlines():
    try: boots.append(float(l.strip()))
    except ValueError: pass

BOOT_LOG.write_text('\n'.join(str(t) for t in boots if time.time() - t < 86400) + '\n')
recent = [t for t in boots if time.time() - t < 300]
_CRASH_LOOP = len(recent) >= 3

import requests
import psutil

def write_heartbeat(status):
    tmp = HEARTBEAT.with_suffix('.tmp')
    tmp.write_text(f'{time.time()}|{os.getpid()}|{status}')
    os.replace(tmp, HEARTBEAT)

def heal_cycle():
    if _CRASH_LOOP:
        write_heartbeat('crash_loop')
        push_event('red')
        log('CRITICAL: crash loop — жду ручного вмешательства')
        time.sleep(3600)  # держим процесс живым — launchd не перезапускает
        sys.exit(1)

    write_heartbeat('running')

    free_gb = shutil.disk_usage('/').free / 1e9
    if free_gb < 0.5:
        push_event('red'); log('CRITICAL: disk < 500MB'); return
    elif free_gb < 2.0:
        push_event('yellow'); log('WARNING: disk < 2GB')

    try:
        resp = requests.get('http://localhost:9000/health', timeout=(3.05, 15)).json()
        assert resp.get('status') == 'ok' and 'version' in resp
    except requests.exceptions.RequestException as e:
        log(f'MCP network error: {e}')
    except Exception as e:
        log(f'MCP health failed: {e}')

    write_heartbeat('heal_end')

def _restart(service):
    return subprocess.run(
        ['launchctl','kickstart','-k', f'gui/{os.getuid()}/{service}'],
        capture_output=True
    )

LOGS_DIR = Path.home()/'Documents/NEVA_MCP_BRIDGE/logs'

PLAYBOOK_COMMANDS = {
    'restart_mcp':      lambda: _restart('com.neva.mcp'),
    'restart_approval': lambda: _restart('com.neva.approval'),
    'restart_auditor':  lambda: _restart('com.neva.auditor'),
    'restart_medic':    lambda: (time.sleep(2), _restart('com.neva.medic')),
    'clear_logs':       lambda: [
        p.unlink(missing_ok=True)
        for p in LOGS_DIR.glob('*.log')
        if p.exists() and p.stat().st_size > 100*1024*1024
    ],
}

def run_playbook(playbook_id):
    if playbook_id not in PLAYBOOK_COMMANDS:
        log(f'BLOCKED unknown playbook: {playbook_id}')
        return False
    return PLAYBOOK_COMMANDS[playbook_id]()

def save_incident_log(data):
    tmp = STATE/'incident_log.json.tmp'
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, STATE/'incident_log.json')
```

---

## neva_status_dot.py

```python
def check_medic():
    if not HEARTBEAT.exists():
        return 'DEAD'
    try:
        parts = HEARTBEAT.read_text().strip().split('|')
        ts, pid, status = float(parts[0]), int(parts[1]), parts[2]
    except Exception:
        HEARTBEAT.unlink(missing_ok=True)
        return 'CORRUPTED'
    age = time.time() - ts
    try:
        proc_uptime = time.time() - psutil.Process(pid).create_time()
    except psutil.NoSuchProcess:
        return 'DEAD'
    except psutil.AccessDenied:
        return 'UNKNOWN'
    if age > 90 and proc_uptime > 120:
        return 'HUNG'
    return 'OK'

def restart_medic():
    subprocess.run(['launchctl','kickstart','-k',
                    f'gui/{os.getuid()}/com.neva.medic'])
```

---

## com.neva.medic.plist

```xml
<key>ThrottleInterval</key>
<integer>60</integer>
```

---

## ЗАДАНИЕ КРУГА 7

Финальная проверка — последний шанс найти блокирующие замечания перед реализацией.

1. Есть ли блокирующие замечания?
2. Нет ли новых противоречий между блоками?
3. Финальный вердикт: ГОТОВ / НЕ ГОТОВ

Если НЕ ГОТОВ — назови конкретные блокирующие. Если ГОТОВ — подтверди.
Отвечай на русском языке. Максимально коротко.
