# ОТВЕТЫ ДИРЕКТОРА — КРУГ 4
# Принятые замечания аудиторов + обоснование отклонений

---

## ПРИНЯТО

**1. fcntl.flock() — spinlock с retry вместо мгновенного sys.exit()**
Gemini прав: при быстром перезапуске launchctl kickstart -k может породить новый процесс до завершения старого. Новый получит BlockingIOError и умрёт — launchd поднимет его снова только через ThrottleInterval.
Решение: retry 5 попыток с паузой 0.3 сек перед выходом.

```python
def acquire_lock(retries=5, delay=0.3):
    for i in range(retries):
        try:
            fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if i < retries - 1: time.sleep(delay)
    return False
if not acquire_lock():
    sys.exit(0)
```

**2. Heartbeat — писать в первые миллисекунды старта + включать PID**
Gemini: heartbeat нужно писать ДО импорта тяжёлых модулей, сразу при старте.
ChatGPT: status_dot должен проверять heartbeat только если uptime процесса > 120 сек.
Принимаю оба решения вместе — они дополняют друг друга.

```python
# Первые строки neva_medic.py:
HEARTBEAT = Path.home()/'Documents/NEVA_MCP_BRIDGE/state/neva_medic.heartbeat'
HEARTBEAT.write_text(f'{time.time()}|{os.getpid()}|starting')
```

```python
# В status_dot при проверке:
ts, pid, status = HEARTBEAT.read_text().split('|')
proc_uptime = time.time() - psutil.Process(int(pid)).create_time()
if time.time() - float(ts) > 90 and proc_uptime > 120:
    # только тогда считаем зависанием
    os.kill(int(pid), signal.SIGTERM)
```

**3. Boot-счётчик + ThrottleInterval — оба нужны, не дублируют**
Все трое аудиторов согласились:
- ThrottleInterval: замедляет launchd, защита на уровне ОС
- Boot-счётчик: понимает причину, поднимает тревогу Директору
Оставляем оба.

---

## ОТКЛОНЕНО

**HTTP /health endpoint для медика**
Предложил Gemini в Круге 3. Отклонено.
Причина: медик — watchdog, не сервер. Открывать порт значит добавлять зависимость и точку отказа. Heartbeat-файл решает ту же задачу без сетевого стека.

**threading.Timer для kill изнутри**
Предложили ChatGPT/DeepSeek в Круге 2. Отклонено.
Причина: если GIL заблокирован или процесс завис в системном вызове — callback не выполнится (Gemini, Круг 3). Внешний контроль через status_dot по heartbeat надёжнее.

---

## БЛОКИРУЮЩИХ ЗАМЕЧАНИЙ ОСТАЛОСЬ: 0

Все критические замечания закрыты. Круг 5 — финальная валидация итогового решения.
