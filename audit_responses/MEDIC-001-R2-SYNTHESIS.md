# СИНТЕЗ РЕШЕНИЙ — КРУГ 3
# Лучшие решения по итогам Круга 2 от 4 аудиторов

---

## 1. Двойной запуск (launchd + status_dot + оператор)

**Принятое решение:** fcntl.flock() — атомарная блокировка ядра macOS.

```python
import fcntl, sys
_lock_file = open('/tmp/neva_medic.lock', 'w')
try:
    fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(0)  # уже запущен — тихий выход
```

Дополнительно: убрать nohup из status_dot, заменить на:
```bash
launchctl kickstart -k gui/$(id -u)/com.neva.medic
```

Сложность: Очень низкая. Надёжность: Максимальная (гарантия ядра).

---

## 2. Crash loop (бесконечные перезапуски)

**Принятое решение:** ThrottleInterval в .plist + boot-счётчик внутри медика.

В com.neva.medic.plist:
```xml
<key>ThrottleInterval</key>
<integer>60</integer>
```

В neva_medic.py при старте:
```python
boot_file = Path('/tmp/neva_medic_boots.json')
boots = json.loads(boot_file.read_text()) if boot_file.exists() else []
boots = [t for t in boots if time.time() - t < 300]  # окно 5 минут
if len(boots) >= 3:
    push_event('red')
    sys.exit(1)  # стоп — слишком много перезапусков
boots.append(time.time())
boot_file.write_text(json.dumps(boots))
```

Сложность: Низкая. Надёжность: Высокая.

---

## 3. Нет heartbeat / health endpoint

**Принятое решение:** Heartbeat-файл (быстро) + HTTP /health endpoint (надёжно).

```python
# В heal_cycle() в начале каждого цикла:
Path('/tmp/neva_medic.heartbeat').write_text(str(time.time()))
```

status_dot проверяет heartbeat а не только лог:
```python
hb = Path('/tmp/neva_medic.heartbeat')
if hb.exists() and time.time() - float(hb.read_text()) > 120:
    # медик завис
```

Сложность: Очень низкая. Надёжность: Высокая.

---

## 4. Зависание внутри heal_cycle (ai_diagnose, сетевые вызовы)

**Принятое решение:** threading.Timer как watchdog + timeout на все сетевые вызовы.

```python
import threading

def _cycle_watchdog():
    push_event('red')
    os.kill(os.getpid(), signal.SIGTERM)

def heal_cycle():
    timer = threading.Timer(90, _cycle_watchdog)  # если цикл > 90 сек
    timer.start()
    try:
        # ... весь heal_cycle ...
        pass
    finally:
        timer.cancel()
```

Все requests/curl с явным timeout=15.

Сложность: Средняя. Надёжность: Высокая.

---

## 5. MCP :9000 отвечает HTTP 200 но данные мусор

**Принятое решение:** JSON schema validation + semantic ping.

```python
import json
resp = requests.get('http://localhost:9000/health', timeout=5).json()
assert resp.get('status') == 'ok', f"MCP bad status: {resp}"
assert 'version' in resp, "MCP missing version"
```

Сложность: Низкая. Надёжность: Средняя → Высокая.

---

## 6. run_playbook() — AI может выполнить любую команду

**Принятое решение:** Белый список ID плейбуков + approval gate для опасных.

```python
SAFE_PLAYBOOKS = {
    'restart_mcp', 'restart_approval', 'restart_medic',
    'restart_auditor', 'clear_logs', 'reload_knowledge'
}

def run_playbook(playbook_id, cmd):
    if playbook_id not in SAFE_PLAYBOOKS:
        log(f'BLOCKED: unknown playbook {playbook_id}')
        return False
    # выполнять только предопределённую команду из словаря, не cmd от AI
    return PLAYBOOK_COMMANDS[playbook_id]()
```

Сложность: Низкая. Надёжность: Максимальная.

---

## 7. incident_log.json — нет атомарной записи

**Принятое решение:** Write-and-rename через os.replace().

```python
tmp = Path('state/incident_log.json.tmp')
tmp.write_text(json.dumps(data, indent=2))
os.replace(tmp, 'state/incident_log.json')
```

Сложность: Очень низкая. Надёжность: Высокая.

---

## 8. Диск полон — медик не может писать логи

**Принятое решение:** Проверка диска в начале цикла + fallback в stderr.

```python
import shutil
free_gb = shutil.disk_usage('/').free / 1e9
if free_gb < 0.5:
    print('[CRITICAL] disk < 500MB', file=sys.stderr)
    push_event('red')
```

Сложность: Низкая. Надёжность: Высокая.

---

## 9. Нет watchdog для watchdog (status_dot)

**Принятое решение:** launchd PathState на heartbeat-файл status_dot.

В com.neva.status-dot.plist добавить мониторинг heartbeat медика:
```xml
<key>WatchPaths</key>
<array>
    <string>/tmp/neva_medic.heartbeat</string>
</array>
```

status_dot пишет свой heartbeat каждые 15 сек — медик его проверяет.

Сложность: Низкая. Надёжность: Средняя.

---

## ИТОГ: ПРИОРИТЕТ ВНЕДРЕНИЯ

| Приоритет | Изменение | Сложность | Эффект |
|---|---|---|---|
| 1 | fcntl.flock() — защита от двойного запуска | Очень низкая | Критический |
| 2 | Белый список playbooks | Низкая | Критический |
| 3 | os.replace() для incident_log | Очень низкая | Высокий |
| 4 | Heartbeat-файл | Очень низкая | Высокий |
| 5 | ThrottleInterval + boot-счётчик | Низкая | Высокий |
| 6 | threading.Timer watchdog | Средняя | Высокий |
| 7 | launchctl вместо nohup | Низкая | Высокий |
| 8 | JSON schema для MCP | Низкая | Средний |
| 9 | Disk check | Низкая | Средний |
| 10 | Watchdog для watchdog | Низкая | Средний |
