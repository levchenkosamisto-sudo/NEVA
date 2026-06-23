# ФИНАЛЬНЫЙ СИНТЕЗ — КРУГ 9 (ПОСЛЕДНИЙ)
# Все блокирующие замечания Кругов 1-8 закрыты.
# Доработка: явный _LOCK.close() перед самоперезапуском.

---

## ПОЛНЫЙ КОД ИЗМЕНЕНИЙ neva_medic.py

```python
from pathlib import Path          # ПЕРВАЯ СТРОКА
import fcntl, sys, os, time, json, shutil, subprocess, signal, requests

# Заглушки — заменить на существующие функции neva_medic.py
def push_event(color, msg=''): pass
def log(msg): print(f'[MEDIC] {msg}')

STATE    = Path.home()/'Documents/NEVA_MCP_BRIDGE/state'
LOGS_DIR = Path.home()/'Documents/NEVA_MCP_BRIDGE/logs'
STATE.mkdir(parents=True, exist_ok=True)

HEARTBEAT = STATE/'neva_medic.heartbeat'
LOCK_PATH = STATE/'neva_medic.lock'
BOOT_LOG  = STATE/'neva_medic_boots.txt'

def write_heartbeat(status):
    tmp = HEARTBEAT.with_suffix('.tmp')
    tmp.write_text(f'{time.time()}|{os.getpid()}|{status}')
    os.replace(tmp, HEARTBEAT)

write_heartbeat('starting')

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

BOOT_LOG.touch(exist_ok=True)
with open(BOOT_LOG, 'a') as f:
    f.write(f'{time.time()}\n')

boots = []
for l in BOOT_LOG.read_text().splitlines():
    try: boots.append(float(l.strip()))
    except ValueError: pass

BOOT_LOG.write_text('\n'.join(str(t) for t in boots if time.time()-t < 86400)+'\n')
recent = [t for t in boots if time.time()-t < 300]
_CRASH_LOOP = len(recent) >= 3

import psutil

def heal_cycle():
    if _CRASH_LOOP:
        write_heartbeat('crash_loop')
        push_event('red')
        log('CRITICAL: crash loop — жду ручного вмешательства')
        time.sleep(3600)
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

PLAYBOOK_COMMANDS = {
    'restart_mcp':      lambda: _restart('com.neva.mcp'),
    'restart_approval': lambda: _restart('com.neva.approval'),
    'restart_auditor':  lambda: _restart('com.neva.auditor'),
    'restart_medic':    lambda: (
        time.sleep(2),
        _LOCK.close(),          # явно освобождаем lock до того как launchd поднимет новый процесс
        _restart('com.neva.medic')
    ),
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

## ОТВЕТЫ НА ЗАМЕЧАНИЯ КРУГА 8

**ChatGPT — restart_medic + _LOCK (НЕ ПРИНЯТО как блокирующее):**
Spinlock retry (5 × 0.3 сек) покрывает окно завершения старого процесса. Это разобрано в Круге 4 — все аудиторы согласились. Тем не менее добавлен явный `_LOCK.close()` для большей надёжности.

**Gemini — UnboundLocalError в Блоке 3 (ОТКЛОНЕНО):**
`boots = []` инициализирована до цикла. `UnboundLocalError` невозможен. Код:
```python
boots = []                          # ← инициализация ЗДЕСЬ
for l in BOOT_LOG.read_text()...:
    try: boots.append(float(l))
    except ValueError: pass
```
Замечание является галлюцинацией — в Python переменная списка инициализированная перед циклом недоступна только если использовать comprehension с тем же именем внутри, чего в коде нет.

---

## ЗАДАНИЕ КРУГА 9 — ПОСЛЕДНИЙ

Это финальный круг. Код прошёл 8 кругов аудита.

**Вопрос один:** Есть ли блокирующие замечания к коду выше?

Обрати внимание — объяснения почему предыдущие замечания отклонены приведены выше.
Если не согласен с отклонением — аргументируй конкретно.
Если блокирующих нет — вердикт ГОТОВ.
Отвечай на русском языке. Максимально коротко.
