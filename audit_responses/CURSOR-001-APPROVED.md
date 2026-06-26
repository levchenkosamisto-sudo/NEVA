# CURSOR-001 — УТВЕРЖДЁННАЯ АРХИТЕКТУРА
Директор: Серж | Архитектор: Claude | Дата: 2026-06-26
Статус: УТВЕРЖДЕНО после аудита ДУМЫ (4 аудитора, 2 круга)

---

## ПАЙПЛАЙН (4 этапа)

Этап 1: СПЕЦИФИКАЦИЯ
  Claude пишет: spec.md + AGENTS.md + tests_spec.py
  tests_spec.py = контракты вход/выход, edge cases (не реализация)
  Директор утверждает → переход к Этапу 2
  Токены Claude: ~500

Этап 2: РЕАЛИЗАЦИЯ
  Cursor читает: spec.md + AGENTS.md + tests_spec.py
  Cursor: пишет код → ruff/mypy → pytest → test_report.md
  При блокировке: Cursor пишет questions.md → fswatch → Telegram Директору
  Claude читает questions.md → пишет answers.md
  Токены Claude: 0 (только при блокировке ~200)

Этап 3: РЕВЬЮ
  Claude читает: git diff + test_report.md
  Пишет review.md: код + тесты + edge cases покрыты?
  Токены Claude: ~300-500

Этап 4: УТВЕРЖДЕНИЕ
  Директор читает review.md → утверждает → деплой
  Токены Claude: 0

---

## КОММУНИКАЦИЯ

Транспорт: файлы на диске (общая папка проекта)
Структура: ~/Documents/NEVA/projects/[ИМЯ]/
  spec.md          — требования + контракты
  AGENTS.md        — правила для Cursor
  tests_spec.py    — тесты до кода
  tasks.md         — декомпозиция задач (Cursor заполняет)
  questions.md     — вопросы Cursor
  answers.md       — ответы Claude
  test_report.md   — вывод pytest
  review.md        — финальное ревью Claude

Триггер: fswatch на questions.md → Telegram Директору
Репо: монорепо NEVA, подпапка projects/

---

## РЕШЕНИЯ АУДИТОРОВ (консенсус 4/4)

Транспорт:    файлы на диске ✅
Триггер:      fswatch + Telegram ✅
Исполнитель:  Cursor ✅ (решение Директора)
TDD:          Claude пишет тесты до кода ✅
Упрощение:    6→4 этапа ✅
Линтер:       ruff + mypy перед pytest ✅

---

## ЭКОНОМИЯ ТОКЕНОВ CLAUDE DESKTOP

До: Claude пишет код + тесты + проверяет = ~5000 токенов/задача
После: Claude только spec + ревью = ~800 токенов/задача
Экономия: ~84%
