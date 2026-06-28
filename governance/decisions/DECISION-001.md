# DECISION-001 — Структура Гит и организация репозитория NEVA

Дата: 2026-06-28
Статус: АКТУАЛЬНО
Директор: Серж
Архитектор: Claude

## Решение
Принята структура репозитория NEVA:
- src/(core/memory/router/reliability/mcp/tools)
- governance/(decisions/architecture/prompts)
- memory/raw/chats/
- audit/(snapshots/responses)
- state/(tasks/)
- tests/(unit/integration/smoke)
- scripts/, .github/workflows/

Корень: AGENTS.md + CLAUDE.md + README.md

## Ветки
main → dev → task/TASK-XXX
Прямые коммиты в main запрещены (pre-push хук + GitHub Branch Protection).
Слияние task→dev: ревью Claude + подтверждение Директора.
Слияние dev→main: только после всех тестов CI.

## Причина
Единый источник истины. Прозрачная история изменений.
Аудиторы ДУМЫ работают со снимками — не с живой системой.

## Отклонённые альтернативы
- Монобранч (только main): нет изоляции задач, невозможен параллельный аудит
- GitFlow (release ветки): избыточно для одного Директора
