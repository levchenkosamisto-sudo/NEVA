# NEVA Medic Knowledge — MCP Executor
# Версия: 1.0 | Дата: 2026-06-13 | Архитектор: Claude

## Назначение
mcp_server.py v3.3 + mcp_executor.py v3.1 — инструментальный слой NEVA.
Принимает команды от Claude Desktop через MCP протокол, выполняет file_read/write/git/run_tests.
background_auditor.py v6.9 — аудитор каждой операции через FlagmanRouter (Cerebras→Groq→OpenRouter).
Статус: PROD. BASE_DIR: ~/Documents/NEVA_MCP_BRIDGE

## Запуск
- mcp_server.py: Claude Desktop запускает автоматически через MCP config
- background_auditor.py: LaunchAgent com.neva.auditor (или вручную через .zshrc)
- neva_approval_server.py: порт 8766, автозапуск через ~/.zshrc
- AppSupport sync: ~/Library/Application Support/NEVA/ — копии всех py файлов

## Диагностика
- Живой ли mcp_server: ps aux | grep mcp_server.py
- Живой ли auditor: ps aux | grep background_auditor
- Auditor лог свежий если: auditor.log mtime < 300с
- Approval Gate: GET http://127.0.0.1:8766/health
- Спам в err.log: com.neva.executor.err.log — > 50 одинаковых строк за 5 мин

## Известные проблемы
### ПРОБЛЕМА #1 — FM-EX-05: спам в executor.err.log
- Симптом: com.neva.executor.err.log растёт быстро, > 50 строк ошибок за 5 мин
- Типичные строки: "Operation not permitted", "can't open file"
- Причина: старый com.neva.executor plist запускает системный python вместо venv
- Статус: com.neva.executor УДАЛЁН (2026-06-12). Спам вернётся при ребуте если plist остался.
- Диагностика: launchctl list | grep executor; ls ~/Library/LaunchAgents/ | grep executor
- Решение: если plist есть — launchctl unload + удалить файл
- Playbook Medic: executor_log_spam → restart_executor_launchd
- Conf ожидаемый при этом контексте: 0.88

### ПРОБЛЕМА #2 — Cerebras HTTP 403
- Симптом: FlagmanRouter логирует "cerebras: HTTP 403"
- Причина: истёк API ключ или превышен лимит
- Решение: проверить CEREBRAS_API_KEY в .env, обновить на сайте
- FlagmanRouter переключается на Groq автоматически

### ПРОБЛЕМА #3 — OpenRouter HTTP 404
- Симптом: FlagmanRouter логирует "openrouter: HTTP 404"
- Причина: неверная модель в конфиге
- Решение: обновить модель в AI_PROVIDERS конфиге

## История аварий
| Дата | Проблема | Решение |
|---|---|---|
| 2026-06-12 | com.neva.executor спам в err.log | Удалён plist. sudoers исправлен. |
| 2026-06-11 | MCP Executor v6.3 интегрирован | 31/31 PASS, FlagmanRouter conf=1.0 |

## Playbook Medic
- problem_id: executor_log_spam
- mode: AUTO
- шаги: launchctl kickstart -k gui/UID/com.neva.executor
- при провале: ESCALATION
