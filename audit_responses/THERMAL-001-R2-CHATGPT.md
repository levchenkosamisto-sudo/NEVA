# ChatGPT — THERMAL-001-R2
Дата: 2026-06-23 11:28:56.226821

ТИП: РЕВЬЮ

ПРОБЛЕМА А — powermetrics требует sudo → вечный DEGRADED
Найденные ошибки/коллизии

Текущее решение создаёт единую точку отказа: отсутствие температуры = отсутствие восстановления.

FSM смешивает две разные сущности:

состояние сенсора;

состояние системы.

temp=None трактуется как деградация системы, хотя это деградация телеметрии.

После перезагрузки или изменения прав система может навсегда остаться в DEGRADED без механизма выхода.

Нарушен принцип graceful degradation.

Лучшее решение

Разделить:

Python
Запустить
sensor_status = OK | DEGRADED | FAILED
thermal_level = NOMINAL | WARM | HOT | CRITICAL

Источник температуры:

Python
Запустить
try:
    temp = read_powermetrics()
    sensor_status = "OK"
except PermissionError:
    temp = None
    sensor_status = "FAILED"

FSM работает даже без температуры:

Python
Запустить
if temp is None:
    return ThermalLevel.NOMINAL

а в state:

JSON
{
  "sensor_status": "FAILED",
  "thermal_level": "NOMINAL"
}

Дополнительно использовать бесплатный резервный источник через PyObjC:

Python
Запустить
from Foundation import NSProcessInfo

state = NSProcessInfo.processInfo().thermalState()

Маппинг:

Python
Запустить
0 -> NOMINAL
1 -> WARM
2 -> HOT
3 -> CRITICAL

Логика:

Python
Запустить
powermetrics
    ↓
если недоступен
    ↓
NSProcessInfo
    ↓
если недоступен
    ↓
sensor_failed
Риски

NSProcessInfo даёт уровни без числовой температуры.

Переключение между источниками требует унификации порогов.

Альтернатива

Самое простое:

Python
Запустить
if temp is None:
    return ThermalLevel.NOMINAL

и отдельный warning в логе.

ПРОБЛЕМА Б — race condition в multiprocessing
Найденные ошибки/коллизии

Self-test и основной цикл используют один и тот же механизм чтения температуры.

Нет межпроцессной синхронизации.

_load_state()