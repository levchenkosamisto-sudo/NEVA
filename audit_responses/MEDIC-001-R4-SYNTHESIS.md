# ФИНАЛЬНЫЙ СИНТЕЗ — КРУГ 5
# Полное итоговое решение после 4 кругов аудита
# Все замечания закрыты. Блокирующих замечаний: 0.

---

## ФИНАЛЬНЫЙ КОД — ИЗМЕНЕНИЯ В neva_medic.py

### Блок 1: Старт процесса (первые строки до импортов)
```python
import fcntl, sys, os, time
from pathlib import Path

# 1. Мгновенный heartbeat при старте (до тяжёлых импортов)
HEARTBEAT = Path.home()/'Documents/NEVA_MCP_BRIDGE/state/neva_medic.heartbeat'
HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
HEARTBEAT.write_text(f'{time.time()}|{os.getpid()}|starting')

# 2. Защита от двойного запуска — spinlock с retry
LOCK_PATH = Path.home()/'Documents/NEVA_MCP_BRIDGE/state/neva_medic.lock'
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
    sys.exit(0)

# 3. Boot-счётчик — защита от crash loop
BOOT_LOG = Path.home()/'Documents/NEVA_MCP_BRIDGE/state/neva_medic_boots.txt'
with open(BOOT_LOG, 'a') as f:
    f.write(f'{time.time()}\n')
boots = [float(l) for l in BOOT_LOG.read_text().splitlines() if l]
recent = [t for t in boots if time.time() - t < 300]
if len(recent) >= 3:
    HEARTBEAT.write_text(f'{time.time()}|{os.getpid()}|crash_loop')
    # push_event вызовем после импортов
    _CRASH_LOOP = True
else:
    _CRASH_LOOP = False
```

### Блок 2: В heal_cycle() — heartbeat + таймауты
```python
def heal_cycle():
    # Обновляем heartbeat в начале каждого цикла
    HEARTBEAT.write_text(f'{time.time()}|{os.getpid()}|running')

    # Проверка диска — два уровня
    free_gb = shutil.disk_usage('/').free / 1e9
    if free_gb < 0.5:
        push_event('red'); log('CRITICAL: disk < 500MB'); return
    elif free_gb < 2.0:
        push_event('yellow'); log('WARNING: disk < 2GB')

    # Все сетевые вызовы с явным timeout
    try:
        resp = requests.get('http://localhost:9000/health', timeout=(3.05, 15)).json()
        assert resp.get('status') == 'ok' and 'version' in resp
    except Exception as e:
        log(f'MCP health check failed: {e}')

    # ... остальная логика ...

    # Обновляем heartbeat в конце цикла
    HEARTBEAT.write_text(f'{time.time()}|{os.getpid()}|heal_end')
```

### Блок 3: run_playbook() — белый список
```python
PLAYBOOK_COMMANDS = {
    'restart_mcp':      lambda: subprocess.run(['launchctl','kickstart','-k',f'gui/{os.getuid()}/com.neva.mcp']),
    'restart_approval': lambda: subprocess.run(['launchctl','kickstart','-k',f'gui/{os.getuid()}/com.neva.approval']),
    'restart_auditor':  lambda: subprocess.run(['launchctl','kickstart','-k',f'gui/{os.getuid()}/com.neva.auditor']),
    'restart_medic':    lambda: subprocess.run(['launchctl','kickstart','-k',f'gui/{os.getuid()}/com.neva.medic']),
    'clear_logs':       lambda: [p.unlink() for p in Path('logs').glob('*.log') if p.stat().st_size > 100*1024*1024],
}

def run_playbook(playbook_id):
    if playbook_id not in PLAYBOOK_COMMANDS:
        log(f'BLOCKED unknown playbook: {playbook_id}')
        return False
    return PLAYBOOK_COMMANDS[playbook_id]()
```

### Блок 4: save_incident_log() — атомарная запись
```python
def save_incident_log(data):
    tmp = Path('state/incident_log.json.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, 'state/incident_log.json')
```

---

## ФИНАЛЬНЫЙ КОД — ИЗМЕНЕНИЯ В neva_status_dot.py

```python
import psutil, signal

HEARTBEAT = Path.home()/'Documents/NEVA_MCP_BRIDGE/state/neva_medic.heartbeat'

def check_medic():
    if not HEARTBEAT.exists():
        return 'DEAD'
    try:
        ts, pid, status = HEARTBEAT.read_text().strip().split('|')
        ts, pid = float(ts), int(pid)
    except Exception:
        return 'CORRUPTED'

    age = time.time() - ts

    # Grace period — не проверять heartbeat если процесс только запустился
    try:
        proc_uptime = time.time() - psutil.Process(pid).create_time()
    except psutil.NoSuchProcess:
        return 'DEAD'

    if age > 90 and proc_uptime > 120:
        return 'HUNG'  # реальное зависание
    return 'OK'

def restart_medic():
    # Основной метод — launchctl
    result = subprocess.run(['launchctl','kickstart','-k',
                             f'gui/{os.getuid()}/com.neva.medic'],
                            capture_output=True)
    if result.returncode != 0:
        # Fallback — nohup только если launchd недоступен
        subprocess.Popen(['nohup','python3', str(MEDIC_PATH)],
                         stdout=open('/dev/null','w'), stderr=subprocess.STDOUT)
```

---

## ИЗМЕНЕНИЯ В com.neva.medic.plist

```xml
<key>ThrottleInterval</key>
<integer>60</integer>
```

---

## ИТОГОВАЯ ТАБЛИЦА — ВСЁ ПРИНЯТОЕ

| # | Изменение | Строк | Статус |
|---|---|---|---|
| 1 | Heartbeat при старте + PID | 3 | ✅ |
| 2 | fcntl.flock() spinlock retry | 10 | ✅ |
| 3 | Boot-счётчик plain text | 8 | ✅ |
| 4 | ThrottleInterval в .plist | 2 | ✅ |
| 5 | Белый список playbooks | 10 | ✅ |
| 6 | os.replace() атомарная запись | 3 | ✅ |
| 7 | Timeout на все сетевые вызовы | 3 | ✅ |
| 8 | JSON schema MCP :9000 | 3 | ✅ |
| 9 | Disk check 2 уровня | 6 | ✅ |
| 10 | Grace period в status_dot | 5 | ✅ |
| 11 | launchctl вместо nohup + fallback | 8 | ✅ |

**Отклонено:**
- HTTP /health endpoint — медик не должен быть сервером
- threading.Timer kill изнутри — ненадёжно при зависании GIL

---

## ЗАДАНИЕ КРУГА 5

Это финальная валидация. Проверь:
1. Нет ли противоречий между блоками финального кода
2. Правильный ли порядок операций при старте (heartbeat → lock → boot-счётчик → импорты)
3. Нет ли упущенных edge case
4. Готов ли план к реализации или нужны доработки
