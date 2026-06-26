# THERMAL-AUDIT-001 — РЕШЕНИЯ АРХИТЕКТОРА v10
# Принятые и отклонённые предложения аудиторов
# Дата: 2026-06-23 | Архитектор: Claude | Директор: Серж

---

## ПРИНЯТЫЕ РЕШЕНИЯ (реализованы в v10)

### А. Каскад источников температуры (консенсус всех 4)
ПРИНЯТО: powermetrics → NSProcessInfo (PyObjC) → fallback(swap+mem)
Реализация: _read_temp() теперь возвращает (temp, is_stale, source).
NSProcessInfo.thermalState() маппируется в виртуальные °C:
  Nominal=30°C, Fair=60°C, Serious=80°C, Critical=95°C
При fallback (оба источника недоступны) — FSM работает только по swap/mem.
Система выходит из DEGRADED без sudo.

### Б. fcntl.LOCK_SH при чтении state (консенсус всех 4)
ПРИНЯТО: _load_state() добавлен shared lock при json.load().
_write_state() использует atomic rename (os.replace) — exclusive lock не нужен,
но LOCK_SH при чтении защищает от partial read в момент rename.

### В. UDS push → Medic при CRITICAL/BLOCKED (консенсус всех 4)
ПРИНЯТО: _notify_medic_uds() — fire-and-forget, timeout=1с.
Вызывается в _do_critical() и _do_degraded_high().
При недоступности Medic — молча пропускает (FileNotFoundError/ConnectionRefused).

---

## ОТКЛОНЁННЫЕ ПРЕДЛОЖЕНИЯ

### ОТКЛОНЕНО-1: sudoers NOPASSWD для powermetrics
Предложили: ChatGPT, Gemini
Вариант: sudo visudo → добавить '%admin ALL=(root) NOPASSWD: /usr/bin/powermetrics'

ПРИЧИНА ОТКЛОНЕНИЯ:
  (1) Требует ручной настройки на каждой машине — нарушает принцип zero-setup NEVA
  (2) Создаёт постоянную привилегию sudo для AI-процесса — риск безопасности
  (3) Не решает проблему архитектурно: sudo = костыль, NSProcessInfo = правильный путь
  (4) При переустановке macOS или создании нового пользователя — требует повторной настройки
  (5) Противоречит политике: NEVA не должна требовать sudo-привилегий

### ОТКЛОНЕНО-2: asyncio вместо multiprocessing для powermetrics
Предложил: Gemini
Вариант: заменить multiprocessing.Queue на asyncio для _powermetrics_worker

ПРИЧИНА ОТКЛОНЕНИЯ:
  (1) powermetrics — синхронный subprocess, его нельзя сделать async без blocking event loop
  (2) asyncio.create_subprocess_exec() требует полного рефакторинга цикла ThermalGuard
  (3) Риск больше выгоды: основной цикл — while True + time.sleep(), не event loop
  (4) Принятое решение (fcntl.LOCK_SH) проще и решает реальный race

### ОТКЛОНЕНО-3: IOKit/SMC через ctypes для температуры
Предложил: DeepSeek (упомянул как третий источник)
Вариант: ctypes → IOKit → SMC напрямую, обход powermetrics

ПРИЧИНА ОТКЛОНЕНИЯ:
  (1) Недокументированный приватный API Apple — может сломаться в любом обновлении macOS
  (2) Требует написания ~100 строк нетривиального ctypes кода с магическими константами
  (3) NSProcessInfo делает то же самое через официальный API
  (4) Добавляет хрупкую зависимость без измеримого выигрыша над NSProcessInfo

### ОТКЛОНЕНО-4: FSEvents/inotify на thermal_state.json вместо UDS
Предложил: Grok
Вариант: Medic подписывается на FSEvents файла состояния вместо UDS

ПРИЧИНА ОТКЛОНЕНИЯ:
  (1) FSEvents — Objective-C/Swift API, из Python требует PyObjC
  (2) Изменяет архитектуру Medic (он должен реагировать на файл, а не на сокет)
  (3) Pull-модель с задержкой FS event vs push-модель UDS — хуже для CRITICAL
  (4) UDS проще: один метод _notify_medic_uds(), не требует изменений в Medic на данном этапе

### ОТКЛОНЕНО-5: multiprocessing.Manager.dict() для shared state
Предложил: Grok
Вариант: заменить thermal_state.json на Manager.dict() в памяти

ПРИЧИНА ОТКЛОНЕНИЯ:
  (1) thermal_state.json — контракт между ThermalGuard и Medic. Medic читает файл, не память.
  (2) Manager.dict() живёт только пока жив ThermalGuard — при краше Medic теряет состояние
  (3) Файл обеспечивает персистентность через перезапуски launchd (ThrottleInterval=30)
  (4) Атомарная запись через os.replace уже надёжна — проблема только в чтении (решена fcntl)

---

## ИТОГ v10

Принято: 3 из 9 предложений аудиторов
Отклонено: 6 предложений (с обоснованием выше)
Синтаксис: PASS (python3 -m py_compile)
Self-test: обновлён до 11 тестов (добавлены #9 NSProcessInfo, #10 fcntl, #11 UDS)
