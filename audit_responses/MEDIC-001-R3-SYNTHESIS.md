# СИНТЕЗ РЕШЕНИЙ — КРУГ 4
# Финальный план после 3 кругов аудита (4 аудитора)
# Учтены замечания: ChatGPT, DeepSeek, Grok, Gemini

---

## ИЗМЕНЕНИЯ ОТНОСИТЕЛЬНО КРУГА 3

1. Lock-файл: /tmp → state/neva_medic.lock (Gemini: /tmp очищается macOS)
2. Boot-счётчик: JSON → plain text append (Gemini: JSON ломается при переполнении диска)
3. threading.Timer: УБРАТЬ — риск deadlock в GIL (ChatGPT + Gemini). Заменить на внешний контроль через status_dot по heartbeat
4. launchctl kickstart: основной метод + nohup только fallback если launchd недоступен > 30 сек (DeepSeek)
5. Disk threshold: два уровня warning/critical (ChatGPT)
6. status_dot роль: только AnyBar + экстренный kickstart. НЕ основной перезапуск (Gemini)

---

## ФИНАЛЬНЫЙ ПЛАН ВНЕДРЕНИЯ

### БЛОК 1 — КРИТИЧЕСКИЙ (внедрить немедленно)

**1.1 Защита от двойного запуска — fcntl.flock()**
```python
import fcntl, sys
_LOCK = open(Path.home()/'Documents/NEVA_MCP_BRIDGE/state/neva_medic.lock', 'w')
try:
    fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(0)
```
Надёжность: максимальная (гарантия ядра, авто-снятие при падении).

**1.2 Белый список playbooks — убрать выполнение произвольного bash от AI**
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

**1.3 Атомарная запись incident_log.json**
```python
def save_incident_log(data):
    tmp = Path('state/incident_log.json.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, 'state/incident_log.json')
```

**1.4 Heartbeat-файл — единственный источник истины**
```python
HEARTBEAT = Path.home()/'Documents/NEVA_MCP_BRIDGE/state/neva_medic.heartbeat'

def heal_cycle():
    HEARTBEAT.write_text(str(time.time()))  # начало цикла
    try:
        # ... вся логика heal_cycle ...
        pass
    finally:
        HEARTBEAT.write_text(str(time.time()))  # конец цикла
```
status_dot проверяет: `time.time() - float(HEARTBEAT.read_text()) > 90` → медик завис → pkill

---

### БЛОК 2 — ВЫСОКИЙ ПРИОРИТЕТ

**2.1 Crash loop защита — ThrottleInterval + plain text boot-счётчик**

В com.neva.medic.plist:
```xml
<key>ThrottleInterval</key><integer>60</integer>
```

В коде:
```python
BOOT_LOG = Path.home()/'Documents/NEVA_MCP_BRIDGE/state/neva_medic_boots.txt'
# append текстом — не ломается при переполнении диска
with open(BOOT_LOG, 'a') as f:
    f.write(f'{time.time()}\n')
# читаем и проверяем
boots = [float(l) for l in BOOT_LOG.read_text().splitlines() if l]
recent = [t for t in boots if time.time() - t < 300]
if len(recent) >= 3:
    push_event('red')
    sys.exit(1)
```

**2.2 Таймауты на все сетевые вызовы**
```python
# Везде в коде — явный timeout
requests.get('http://localhost:9000/health', timeout=(3.05, 15))
requests.get('http://localhost:8766/ping',   timeout=(3.05, 10))
```
threading.Timer НЕ используем — внешний контроль через heartbeat надёжнее.

**2.3 status_dot — launchctl вместо nohup**
```python
# Основной перезапуск:
subprocess.run(['launchctl','kickstart','-k',f'gui/{os.getuid()}/com.neva.medic'])
# Fallback только если launchd недоступен > 30 сек:
subprocess.Popen(['nohup','python3',MEDIC_PATH], ...)
```

---

### БЛОК 3 — СРЕДНИЙ ПРИОРИТЕТ

**3.1 JSON schema validation для MCP :9000**
```python
resp = requests.get('http://localhost:9000/health', timeout=5).json()
assert resp.get('status') == 'ok'
assert 'version' in resp
```

**3.2 Disk check — два уровня**
```python
free_gb = shutil.disk_usage('/').free / 1e9
if free_gb < 0.5:
    push_event('red'); log('CRITICAL: disk < 500MB')
elif free_gb < 2.0:
    push_event('yellow'); log('WARNING: disk < 2GB')
```

**3.3 launchd PathState для watchdog status_dot**
```xml
<key>WatchPaths</key>
<array>
    <string>/Users/arka/Documents/NEVA_MCP_BRIDGE/state/neva_medic.heartbeat</string>
</array>
```

---

## ИТОГОВАЯ ТАБЛИЦА ПРИОРИТЕТОВ

| # | Изменение | Блок | Строк кода | Риск без него |
|---|---|---|---|---|
| 1 | fcntl.flock() | Критический | 5 | Двойной запуск |
| 2 | Белый список playbooks | Критический | 15 | RCE от AI |
| 3 | os.replace() для лога | Критический | 3 | Битый JSON |
| 4 | Heartbeat-файл | Критический | 5 | Слепая зона зависания |
| 5 | ThrottleInterval .plist | Высокий | 2 xml | Crash loop |
| 6 | Boot-счётчик plain text | Высокий | 10 | Crash loop |
| 7 | Timeout на все вызовы | Высокий | 5 | Зависание heal_cycle |
| 8 | launchctl в status_dot | Высокий | 5 | Race condition |
| 9 | JSON schema MCP | Средний | 5 | Ложный GREEN |
| 10 | Disk check 2 уровня | Средний | 8 | Слепая зона диска |
| 11 | WatchPaths launchd | Средний | 4 xml | Нет watchdog для watchdog |

---

## ВОПРОС АУДИТОРАМ КРУГА 4

Grok дал поверхностный ответ в Круге 3 — согласился со всем без анализа.
Для всех аудиторов: есть ли архитектурные решения которые ПРОТИВОРЕЧАТ друг другу?
Конкретно — совместимы ли одновременно:
- fcntl.flock() + launchctl kickstart (могут конфликтовать при быстром перезапуске)
- heartbeat как источник истины + launchd KeepAlive (кто приоритетнее)
- boot-счётчик + ThrottleInterval (не дублируют ли функцию)
