# ТЕХНИЧЕСКОЕ ЗАДАНИЕ ДЛЯ CURSOR
# Проект: NEVA Dev Pipeline — реализация пайплайна разработки
# Директор: Серж | Дата: 2026-06-26

---

## ЧТО НУЖНО РЕАЛИЗОВАТЬ

Набор Python-скриптов и bash-утилит которые реализуют пайплайн
разработки NEVA: Claude пишет спецификацию, Cursor пишет код,
Claude проверяет результат.

---

## ФАЙЛЫ КОТОРЫЕ НУЖНО СОЗДАТЬ

### 1. tools/pipeline/notify_director.py
Назначение: получает путь к questions.md, отправляет Telegram уведомление Директору.

Интерфейс:
  Вход: путь к файлу (sys.argv[1])
  Действие: читает questions.md, извлекает блок BLOCKED, отправляет в Telegram
  Выход: print OK или ERROR

Контракты:
  - Читает NEVA_TELEGRAM_TOKEN и NEVA_TELEGRAM_CHAT_ID из .env
  - Если файл не содержит STATUS: BLOCKED — не отправляет, выходит с кодом 0
  - Если Telegram недоступен — пишет в лог, выходит с кодом 1
  - Сообщение формат: "🔴 BLOCKED: [ИМЯ ПРОЕКТА]\n[первые 500 символов причины]"

Edge cases:
  - questions.md не существует → exit 0, лог WARNING
  - questions.md пустой → exit 0, лог WARNING
  - Telegram timeout > 10 сек → retry 1 раз → exit 1

### 2. tools/pipeline/inspector_poll.py
Назначение: периодически проверяет questions.md во всех проектах,
дублирует fswatch на случай потери событий.

Интерфейс:
  Запуск: python3 inspector_poll.py (работает как демон)
  Флаги: --interval 180 (секунды, default 180)
         --projects-dir ~/Documents/NEVA/projects
         --dry-run (только лог, без Telegram)

Контракты:
  - Сканирует все подпапки projects/ каждые N секунд
  - Если questions.md содержит STATUS: BLOCKED и время модификации
    файла < 10 минут — вызывает notify_director.py
  - Не дублирует уведомления: хранит {путь: время_последней_отправки}
    в памяти, не отправляет повторно если прошло < 10 минут
  - Логирует все события в logs/inspector_poll.log

Edge cases:
  - projects/ не существует → создать, продолжить
  - questions.md заблокирован другим процессом → пропустить итерацию
  - notify_director.py вернул exit 1 → логировать, не падать

### 3. tools/pipeline/new_project.sh
Назначение: создаёт папку нового проекта с шаблонами файлов.

Интерфейс:
  Вход: имя проекта (аргумент 1)
  Действие: создаёт ~/Documents/NEVA/projects/[ИМЯ]/ со всеми файлами
  Выход: print "Проект [ИМЯ] создан: [путь]"

Создаёт файлы-шаблоны:
  spec.md        — с разделами: Требования / Контракты / Edge Cases / Примеры I/O
  AGENTS.md      — с правилами: ruff обязателен, mypy опционален,
                   формат questions.md, формат STATUS: RESOLVED
  tests_spec.py  — пустой файл с импортами и комментарием TODO
  smoke_test.sh  — шаблон с TODO для заполнения Клодом
  questions.md   — пустой с заголовком STATUS: IDLE
  logs/          — пустая папка

Edge cases:
  - Проект уже существует → exit 1 + сообщение об ошибке
  - Нет прав на запись → exit 1 + сообщение

### 4. tools/pipeline/review_checker.py
Назначение: проверяет что review.md содержит заполненный чеклист.

Интерфейс:
  Вход: путь к review.md (sys.argv[1])
  Выход: exit 0 если все пункты [x], exit 1 если есть незакрытые [ ]
  Print: список незакрытых пунктов или "OK — все пункты закрыты"

Контракты:
  - Ищет строки вида "- [ ]" и "- [x]"
  - Считает незакрытые пункты
  - Если незакрытых > 0 → перечисляет их и exit 1

Edge cases:
  - review.md не существует → exit 1 + "review.md не найден"
  - Нет ни одного пункта чеклиста → exit 1 + "чеклист пуст"

---

## ПРАВИЛА ДЛЯ CURSOR (AGENTS.md)

- Язык: Python 3.12
- Форматирование: ruff (обязательно перед каждым коммитом)
- Типизация: mypy опционально (strict_type_checking: false для этого проекта)
- Тесты: pytest, файлы tests/test_*.py
- Никаких TODO, pass, NotImplementedError в финальном коде
- При блокировке: писать questions.md → STATUS: BLOCKED\n[причина]
- После ответа: менять на STATUS: RESOLVED
- Структура: каждый скрипт в отдельном файле, общие утилиты в tools/pipeline/utils.py

---

## ПОРЯДОК ВЫПОЛНЕНИЯ

1. Создать структуру папок: tools/pipeline/
2. Реализовать utils.py (общие функции: чтение .env, логирование)
3. Реализовать notify_director.py
4. Реализовать inspector_poll.py
5. Реализовать new_project.sh
6. Реализовать review_checker.py
7. Запустить ruff на всех файлах
8. Запустить pytest
9. Обновить test_report.md
