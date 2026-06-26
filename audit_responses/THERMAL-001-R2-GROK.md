# Grok — THERMAL-001-R2
Дата: 2026-06-23 11:14:52.417722

ПРОБЛЕМА А: powermetrics требует sudo → DEGRADED навсегда

КРИТИКА: Полная блокировка системы без sudo. temp=None → DEGRADED, нет fallback. Критично для user-agent, нарушает автономность.

ЛУЧШЕЕ РЕШЕНИЕ: Перейти на NSProcessInfo.thermalState через PyObjC (без sudo, 4 уровня).

Python
Копировать
import objc
from Foundation import NSProcessInfo

thermal_state = NSProcessInfo.processInfo().thermalState
# NSProcessInfoThermalStateNominal / Fair / Serious / Critical

В _determine_level(): map к NOMINAL/WARM/DEGRADED/CRITICAL. Убрать powermetrics fallback.

РИСКИ: Меньше детализации (нет °C). Редкие изменения thermalState.

АЛЬТЕРНАТИВА: launchd-агент с sudo-скриптом + IPC (file/uds), но сложнее.

ПРОБЛЕМА Б: race condition в multiprocessing (2 FAIL)

КРИТИКА: Queue без mutex + _load_state() без lock при os.replace(). Два процесса → corrupted state, race на запись/чтение.

ЛУЧШЕЕ РЕШЕНИЕ: threading.Lock + multiprocessing.Manager.dict() или file lock (fcntl).

Python
Копировать
import fcntl
import threading

lock = threading.Lock()
def _atomic_write(state):
    with open(temp, 'w') as f:
        json.dump(state, f)
        f.flush(); os.fsync(f.fileno())
    with open(state_file, 'w') as f: fcntl.flock(f, fcntl.LOCK_EX)
    os.replace(temp, state_file)

def _load_state():
    with open(state_file) as f: fcntl.flock(f, fcntl.LOCK_SH)
    return json.load...

РИСКИ: Overhead lock'ов на Mac.

АЛЬТЕРНАТИВА: Один процесс (threading вместо multiprocessing) + queue.

ПРОБЛЕМА В: нет UDS → нет push в Medic

КРИТИКА: Только pull по файлу. Задержки, polling overhead, Medic не реагирует instantly.

ЛУЧШЕЕ РЕШЕНИЕ: Unix Domain Socket (asyncio или threading).

Python
Копировать
# ThermalGuard server
import socket, asyncio
async def uds_server():
    sock = socket.socket(socket.AF_UNIX)
    sock.bind('/tmp/thermalguard.sock')
    sock.listen()
    while True:
        conn, _ = await asyncio.get_event_loop().sock_accept(sock)
        conn.send(json.dumps(state).encode())

# Medic client
sock.connect('/tmp/thermalguard.sock')
data = sock.recv(1024)

launchd plist с Socket key для auto-bind.

РИСКИ: Socket cleanup (unlink на exit), permissions.

АЛЬТЕРНАТИВА: Периодический write в shared file + Medic inotify (fsevents via PyObjC).