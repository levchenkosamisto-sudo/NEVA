# CURSOR-001 — ФИНАЛЬНАЯ АРХИТЕКТУРА (утверждена 5 кругами ДУМЫ)
Директор: Серж | Архитектор: Claude | Дата: 2026-06-26

---

## КОНЦЕПЦИЯ

Пайплайн разработки где Claude — архитектор и аудитор, Cursor — исполнитель.
Claude никогда не пишет код. Cursor никогда не проектирует.
Коммуникация через файлы на диске. Экономия токенов Claude Desktop: 84%.

---

## ПАЙПЛАЙН — 4 ЭТАПА

ЭТАП 1: СПЕЦИФИКАЦИЯ (Claude Desktop)
  Вход: задача от Директора
  Claude создаёт пакет документов:
    spec.md       — требования, контракты вход/выход, edge cases, примеры I/O
    AGENTS.md     — правила для Cursor
    tests_spec.py — тесты контрактов (до кода)
    smoke_test.sh — интеграционный тест реального запуска
  Директор утверждает пакет → Этап 2
  Токены Claude: ~500

ЭТАП 2: РЕАЛИЗАЦИЯ (Cursor)
  Cursor читает пакет из папки проекта
  Последовательность:
    1. Пишет код по spec.md + AGENTS.md
    2. ruff (всегда)
    3. mypy (если AGENTS.md: strict_type_checking: true)
    4. pytest → test_report.md
    5. smoke_test.sh → smoke_report.md
  При блокировке:
    Cursor: questions.md → STATUS: BLOCKED + описание
    fswatch --event Modified → notify_director.py → Telegram
    Inspector poll каждые 3 мин (резерв)
    Claude → answers.md
    Cursor → STATUS: RESOLVED → продолжает
    Лимит: 3 итерации → эскалация Директору
  Токены Claude: 0 (при блокировке ~200/итерация)

ЭТАП 3: РЕВЬЮ (Claude Desktop)
  Claude читает: git diff + test_report.md + smoke_report.md + questions.md
  Заполняет review.md — чеклист:
    - [ ] Все функции из spec.md реализованы
    - [ ] Каждое требование покрыто тестом или smoke-проверкой
    - [ ] Каждый edge case покрыт тестом
    - [ ] Нет заглушек (TODO, pass, NotImplementedError)
    - [ ] ruff — чисто
    - [ ] smoke_test.sh — PASS
  ГОТОВ → Этап 4
  НЕ ГОТОВ → Cursor исправляет → повтор (до 3 циклов)
  Токены Claude: ~400-600

ЭТАП 4: УТВЕРЖДЕНИЕ (Директор)
  Директор читает review.md → утверждает → деплой
  Токены Claude: 0

---

## СТРУКТУРА ПАПКИ ПРОЕКТА

~/Documents/NEVA/projects/[ИМЯ]/
  spec.md           ← Claude, Этап 1
  AGENTS.md         ← Claude, Этап 1
  tests_spec.py     ← Claude, Этап 1
  smoke_test.sh     ← Claude, Этап 1
  src/              ← Cursor, Этап 2
  test_report.md    ← Cursor, Этап 2
  smoke_report.md   ← Cursor, Этап 2
  questions.md      ← Cursor (BLOCKED → RESOLVED)
  answers.md        ← Claude при блокировке
  review.md         ← Claude, Этап 3
  logs/             ← архив после завершения

---

## ТРИГГЕР БЛОКИРОВОК

  fswatch ~/Documents/NEVA/projects/ --event Modified \
    --exclude '\.swp$' --exclude '~$' --exclude '\.tmp$' \
    | grep questions.md \
    | xargs grep -l BLOCKED \
    | xargs python3 notify_director.py
  + Inspector poll каждые 3 мин как резерв
