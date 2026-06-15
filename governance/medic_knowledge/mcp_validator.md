# MCP Validator — База знаний медика
# Программа: mcp_validator.py v3.0
# Обновлено: 2026-06-15 Сессия 4

## НАЗНАЧЕНИЕ
Библиотека валидации MCP-запросов перед выполнением mcp_executor.
Защищает: от неразрешённых action, подозрительных путей, превышения объёма.
Источник: `~/Documents/NEVA/tools/mcp_executor/mcp_validator.py`
Копия: `~/Documents/NEVA_MCP_BRIDGE/mcp_validator.py`
Обе копии должны быть синхронными.

## АРХИТЕКТУРА
```
mcp_server.py / neva_mcp_server.py / neva_mcp_proxy.py
  ↓ import mcp_validator
  ↓ validate(raw_json) → {'ok': True/False, 'data': {...}}
  ↓ mcp_executor.run(validated)
```

## РАЗРЕШЁННЫЕ ACTIONS
```
git_status, file_tree, file_read, file_write,
system_info, run_playbook, diagnostics, run_tests,
ollama_list, ollama_run, git_commit
```
Запрещено: `git_push` (намеренно отсутствует).
Добавить в ALLOWED_ACTIONS: только через Claude + двойное ревью.

## ЗАЩИТА
- `PATH_SUSPICIOUS`: `..` в пути, `/etc`, `/sys` → блок
- `CONTENT_TOO_LARGE_100KB`: file_write превышает 100 KB → блок
- `confirmed` / `_server_confirmed`: игнорируются из JSON, выставляются только сервером
- `git_commit` — обязательный список files[] + message

## ПРОБЛЕМЫ И РЕШЕНИЯ

### ПРОБЛЕМА validator_import_error
Симптом: `ImportError: No module named mcp_validator` в логах.
Причина: файл отсутствует в NEVA_MCP_BRIDGE.
Действия (Playbook: AUTO, conf 0.90):
```bash
cp ~/Documents/NEVA/tools/mcp_executor/mcp_validator.py \
   ~/Documents/NEVA_MCP_BRIDGE/mcp_validator.py
launchctl kickstart -k gui/$(id -u)/com.neva.mcp-server
# Проверка:
tail -3 ~/Documents/NEVA_MCP_BRIDGE/logs/mcp_server_net.log
# Норма: EXECUTOR IMPORT OK или отсутствие IMPORT FAILED
```

### ПРОБЛЕМА validator_action_blocked
Симптом: `ACTION_NOT_ALLOWED: <action>` в ответе executor.
Причина: action не добавлен в ALLOWED_ACTIONS или неверное название.
Действия: **эскалация к архитектору** — изменение ALLOWED_ACTIONS относится к КРАСНОЙ ЗОНЕ.

### ПРОБЛЕМА validator_path_suspicious
Симптом: `PATH_SUSPICIOUS` в ответе.
Причина: путь содержит `..`, `/etc`, или `/sys`.
Действия: проверить путь в запросе Claude. Как правило — ошибка в запросе, не баг.

### ПРОБЛЕМА validator_desync (КРАСНАЯ ЗОНА)
Симптом: копии в tools/ и NEVA_MCP_BRIDGE/ рассинхронизировались.
Действия: **эскалация**. Синхронизацию делает архитектор вручную.

## ДИАГНОСТИКА
```bash
# Сравнить версии:
md5 ~/Documents/NEVA/tools/mcp_executor/mcp_validator.py
md5 ~/Documents/NEVA_MCP_BRIDGE/mcp_validator.py
# Норма: совпадают

python3 -c "import sys; sys.path.insert(0,'~/Documents/NEVA_MCP_BRIDGE'); from mcp_validator import validate; print(validate('{\"action\": \"git_status\"}'))"
```

*Создано: 2026-06-15 (Сессия 4) | Архитектор: Claude | Директор: Серж*
