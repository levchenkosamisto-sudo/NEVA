# THERMAL-AUDIT-001 — ОТВЕТЫ ИСПОЛНИТЕЛЯ (КРУГ 1)
# Дата: 2026-06-23 | Архитектор: Claude | Директор: Серж

---

## ВОПРОСЫ ПО КОДУ

**Q-КОД-1 (все 4): Критерии перехода DEGRADED→HEALTHY — что блокирует?**

Ответ: DEGRADED не переходит в HEALTHY напрямую. Из FSM:
DEGRADED → допустимые переходы: NOMINAL, DEGRADED_HIGH, BLOCKED.
Переход в NOMINAL возможен только через BLOCKED→UNBLOCKING→NOMINAL.
Причина постоянного DEGRADED в логах: powermetrics=None (sudo недоступен через launchd).
_determine_level() при temp=None всегда возвращает 'DEGRADED' или 'DEGRADED_HIGH'.
Пока powermetrics не работает — выйти из DEGRADED в NOMINAL невозможно по коду.

**Q-КОД-2 (все 4): Race condition в 2 FAIL тестах — где именно?**

Ответ: Self-test #1 (powermetrics) и #5 (ollama_serve) — зависят от внешних ресурсов
(sudo + сеть). Race condition: многопроцессный _powermetrics_worker() запускается через
multiprocessing.Queue. При параллельном запуске self-test и основного цикла — два
процесса могут одновременно вызвать powermetrics. Нет mutex на уровне процессов.
Второй race: _write_state() использует atomic rename (os.replace), но _load_state()
не защищён блокировкой — возможно чтение во время записи между replace и fsync.

**Q-КОД-3 (все 4): powermetrics без sudo — как обрабатывается, почему error.log пуст?**

Ответ: _powermetrics_worker() вызывает sudo powermetrics.
При отсутствии sudo-прав → PermissionError → result_queue.put(('error', ...)).
Ошибка логируется в thermal.log через logger.error(), НЕ в stderr.
launchd пишет stderr в thermal_error.log. Поскольку ошибка обрабатывается внутри
Python кода (try/except) — stderr остаётся пустым. Это объясняет пустой error.log.
При error → _determine_level() получает temp=None → возвращает DEGRADED.

**Q-КОД-4 (все 4): ollama_available=False при serve_up=True — логика?**

Ответ: _update_ollama_available() устанавливает available=False если:
  (1) cooldown_until_wall активен (время не истекло), ИЛИ
  (2) stopped_models не пуст (модель была выгружена), ИЛИ
  (3) pending_operation не None (выгрузка в процессе).
В текущем состоянии: stopped_models=[qwen2.5:7b] → available=False.
serve_up=True = API /api/tags отвечает 200.
Это корректное разделение: Ollama-сервис жив, но модель недоступна для NEVA.

**Q-КОД-5 (все 4): ThrottleInterval=30 — launchd перезапускает или процесс спит?**

Ответ: ThermalGuard — ПОСТОЯННЫЙ процесс (KeepAlive=true).
ThrottleInterval=30 означает: если процесс упал, launchd подождёт 30с перед рестартом.
Сам процесс работает непрерывно в while True с внутренними sleep().
Поллинг: poll_nominal_sec=30, poll_active_sec=10, poll_pending_sec=2.
106 000 строк логов = процесс работал ~5+ дней непрерывно.

**Q-КОД-6 (ChatGPT): Гистерезис HEALTHY↔DEGRADED?**

Ответ: Для температурных состояний — да, гистерезис есть.
WARM→NOMINAL требует: temp < WARM_TEMP_C-3 И swap < SWAP_WARN_FALL_GB (двойное условие).
Для DEGRADED←→NOMINAL: нет явного гистерезиса — зависит только от наличия temp (None vs не-None).
recovery_hysteresis_sec=60 применяется только для BLOCKED→UNBLOCKING.

**Q-КОД-7 (ChatGPT): Атомарность записи thermal_state.json?**

Ответ: ДА, атомарная запись реализована полностью:
  tempfile.NamedTemporaryFile → json.dump → flush → fsync(file) →
  os.replace(tmp, STATE_PATH) → fsync(dir_fd).
_load_state() не имеет блокировки при чтении — потенциальный race при чтении
в момент между replace и fsync директории. Практически маловероятно.

**Q-КОД-8 (ChatGPT): Может ли отсутствие powermetrics удерживать в DEGRADED?**

Ответ: ДА, это главная причина текущей ситуации.
_determine_level() при temp=None ВСЕГДА возвращает DEGRADED (или DEGRADED_HIGH).
Нет альтернативного пути в NOMINAL без температурных данных.
Это архитектурное решение (безопасное поведение при неизвестной температуре),
но оно блокирует систему навсегда при отсутствии sudo.

---

## ВОПРОСЫ ПО АРХИТЕКТУРЕ

**Q-АРХ-1 (все 4): Место ThermalGuard в иерархии NEVA?**

Ответ: ThermalGuard — независимый страж (watchdog), НЕ часть ядра оркестратора.
Отдельный launchd агент. Не вызывается NEVA напрямую.
Взаимодействие: только через thermal_state.json (файловый IPC).
Medic читает thermal_state.json как один из индикаторов здоровья системы.
ThermalGuard не знает о задачах NEVA — управляет только Ollama на уровне ресурсов.
Иерархия: Medic (оркестратор здоровья) > ThermalGuard (ресурсный страж).

**Q-АРХ-2 (все 4): Kill-action при CRITICAL — почему не реализован?**

Ответ: Осознанное архитектурное решение текущего этапа (MVP).
_do_critical() только выгружает модели Ollama через API keep_alive=0.
Kill процессов (subprocess.kill) не реализован по трём причинам:
  (1) Нет прав без sudo в launchd user agent
  (2) Риск повреждения данных при kill без graceful shutdown
  (3) Medic должен быть ответственным за kill (L2/L3 эскалация)
Планируется в Этапе 2 через UDS команду к Medic: "CRITICAL → Medic.kill_noncritical()"

**Q-АРХ-3 (все 4): UDS — что уже ходит через UDS, что через файлы?**

Ответ: Текущая реализация: UDS НЕ реализован для ThermalGuard.
Весь обмен — через thermal_state.json (файловый IPC).
Medic читает файл при каждом цикле мониторинга.
ThermalGuard не уведомляет Medic активно — только обновляет файл.
Планируется: UDS для push-уведомлений CRITICAL/BLOCKED от ThermalGuard к Medic.

**Q-АРХ-4 (все 4): Кто кем управляет — ThermalGuard→Medic или наоборот?**

Ответ: Текущая реальность — ThermalGuard автономен.
Medic читает thermal_state.json пассивно (pull-модель).
ThermalGuard не вызывает Medic и не знает о нём.
При BLOCKED: ThermalGuard только пишет файл. Medic решает что делать.
Планируемая модель: ThermalGuard PUSH → Medic (через UDS) при CRITICAL.
Medic имеет приоритет: может переопределить решение ThermalGuard.

**Q-АРХ-5 (все 4): Расширяемость на Этап 2?**

Ответ: Частично заложена. _determine_level() — единая точка оценки угрозы,
легко расширяется новыми метриками. CONFIG динамически перезагружается (config_reload_sec=60).
Не заложено: нет абстракции для новых типов actions (только _unload_model).
Добавление kill-action, throttling потребует изменения _act() и _do_critical().
FSM_TRANSITIONS — статичный словарь, добавление новых состояний безопасно.

**Q-АРХ-6 (Gemini): Почему не NSProcessInfo.thermalState вместо powermetrics?**

Ответ: NSProcessInfo.thermalState — это Objective-C/Swift API.
Вызов из Python требует PyObjC или ctypes bridge.
На момент разработки: PyObjC не входил в стек NEVA (Python 3.12 + venv).
Ограничение: NSProcessInfo даёт только 4 уровня (Nominal/Fair/Serious/Critical),
без числовой температуры и без данных RAM/swap.
powermetrics выбран как единый источник (температура + детальные метрики).
Проблема sudo — известный компромисс.

---

## ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ДЛЯ АУДИТОРОВ

ВАЖНО: Вся система NEVA работает на бесплатных решениях без подписок.
- powermetrics — встроен в macOS, бесплатен
- psutil — open source, бесплатен
- launchd — встроен в macOS, бесплатен
- Ollama — open source, бесплатен
- Python 3.12 + venv — бесплатен
- NSProcessInfo/PyObjC — бесплатны, но требуют pip install pyobjc

Ограничение: любое предлагаемое решение должно быть:
  (1) Бесплатным сейчас и навсегда (no SaaS, no paid API)
  (2) Работающим offline или с бесплатными локальными инструментами
  (3) Совместимым с Mac M1 + macOS Sequoia + Python 3.12
