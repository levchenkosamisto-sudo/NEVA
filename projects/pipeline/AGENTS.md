# AGENTS.md — Правила для Cursor
# Проект: NEVA Pipeline Tools
# Дата: 2026-06-26

## СТЕК
- Python 3.12
- pathlib (не os.path)
- requests (только для Telegram)
- pytest для тестов

## ОБЯЗАТЕЛЬНО
- ruff перед каждым коммитом
- Никаких TODO, pass, NotImplementedError в финальном коде
- Все ошибки логировать, не падать молча
- exit коды: 0 = успех, 1 = ошибка
- stdout: результат работы
- stderr: ошибки и предупреждения

## СТРУКТУРА
tools/pipeline/
  utils.py            — общие функции (load_env, get_required, setup_logger, load_cache, save_cache)
  notify_director.py  — Telegram уведомление при BLOCKED
  inspector_poll.py   — демон мониторинга projects/
  new_project.py      — создание новой папки проекта
  review_checker.py   — проверка чеклиста review.md

## ПРИ БЛОКИРОВКЕ
Писать в questions.md:
  STATUS: BLOCKED
  [описание проблемы]

После получения ответа в answers.md:
  Менять первую строку на: STATUS: RESOLVED

## СТРОГО ЗАПРЕЩЕНО
- Изменять файлы вне папки projects/ и tools/pipeline/
- Менять spec.md, AGENTS.md, TASK.md
- Писать код не по TASK.md
- Пропускать тесты

## strict_type_checking: false
