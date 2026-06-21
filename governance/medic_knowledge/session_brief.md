# neva_session_brief.py + mcp_executor.py v3.2 — Knowledge Base
# Версия: 1.0 | Дата: 2026-06-15

## НАЗНАЧЕНИЕ

### neva_session_brief.py
Автогенерация NEVA_SESSION_BRIEF.md в конце сессии.
Запуск: python3 ~/Documents/NEVA_MCP_BRIDGE/neva_session_brief.py
Выход: ~/Documents/NEVA/governance/NEVA_SESSION_BRIEF.md

### mcp_executor.py v3.2
NEVA MCP Executor — обработка акций (file_read, file_write, git_status, и др.)
v3.2: поддержка max_lines + summary_only в file_read

## ДИАГНОСТИКА

### session_brief_stale
Симптом: NEVA_SESSION_BRIEF.md не обновлялся > 24ч
```bash
stat ~/Documents/NEVA/governance/NEVA_SESSION_BRIEF.md
```
Решение AUTO:
```bash
python3 ~/Documents/NEVA_MCP_BRIDGE/neva_session_brief.py
```

### session_brief_missing
Симптом: файл отсутствует
```bash
ls ~/Documents/NEVA/governance/NEVA_SESSION_BRIEF.md
```
Решение: запустить neva_session_brief.py

### executor_max_lines_broken
Симптом: file_read с max_lines возвращает весь файл (нет поля truncated)
Причина: запущена старая версия executor (<v3.2)
Проверка:
```bash
grep -n 'max_lines' ~/Documents/NEVA_MCP_BRIDGE/mcp_executor.py
# Ожидание: строки с TASK-3 SPEED_TASK
grep '3.2' ~/Documents/NEVA_MCP_BRIDGE/mcp_executor.py
```
Решение: вернуть mcp_executor.py v3.2 из git или сообщить Архитектору

## FAILURE MODES
| ID | Симптом | Серьёзность | Действие |
|---|---|---|---|
| session_brief_stale | BRIEF не обновлялся > 24ч | LOW | AUTO: запустить скрипт |
| session_brief_missing | файл отсутствует | MEDIUM | AUTO: запустить скрипт |
| executor_max_lines_broken | max_lines не работает | MEDIUM | ASK: сообщить Архитектору |

## PLAYBOOK: update_session_brief
```bash
cd ~/Documents/NEVA_MCP_BRIDGE
/Users/arka/Documents/NEVA/.venv/bin/python3 neva_session_brief.py
# Ожидание: ✅ NEVA_SESSION_BRIEF.md обновлён
```
