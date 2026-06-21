# NEVA MCP Server Net — Knowledge Base для Medic
# Версия: 2.2 | Компонент: neva_mcp_server.py

## НАЗНАЧЕНИЕ
neva_mcp_server.py — HTTP MCP сервер для Claude.ai (Streamable HTTP transport).
- Порт 9000: JSON-RPC endpoint (`/mcp`)
- Порт 9001: Live Dashboard (auto-refresh 3s)
- Запускается через launchd (com.neva.mcp-server) или вручную
- НЕ путать с mcp_server.py (stdio, для Claude Desktop)

## ДИАГНОСТИКА — БЫСТРЫЙ ЧЕКЛИСТ

### 1. Процесс запущен?
```
ps aux | grep neva_mcp_server
```
Если нет → FM-MN-01 → playbook restart_mcp_server_net

### 2. HTTP отвечает?
```
curl http://127.0.0.1:9000/health
# Ожидание: {"status": "ok", "version": "2.2"}
```
Процесс есть, HTTP нет → FM-MN-02 → lsof -i :9000

### 3. Порт занят?
```
lsof -i :9000
lsof -i :9001
```
Если другой процесс занял → pkill -f neva_mcp_server && restart

### 4. Лог ошибок
```
tail -50 ~/Documents/NEVA_MCP_BRIDGE/logs/mcp_server_net.log
```
Поискать: ImportError, Address already in use, Traceback

### 5. launchd статус
```
launchctl list | grep mcp-server
```
Если пусто → plist не зарегистрирован:
```
launchctl load ~/Library/LaunchAgents/com.neva.mcp-server.plist
```

## FAILURE MODES

| ID | Симптом | Причина | Действие |
|---|---|---|---|
| FM-MN-01 | процесс не в ps aux | упал / не стартовал | AUTO: restart_mcp_server_net |
| FM-MN-02 | процесс есть, :9000 молчит | завис / порт занят | AUTO: restart_mcp_server_net |
| FM-MN-03 | :9001 не отвечает | DashboardHandler не стартовал | AUTO: restart_mcp_server_net |
| FM-MN-04 | approval_hang=true | deadlock в write queue | AUTO: restart_mcp_server_net |
| FM-MN-05 | proxy_fallback_stuck=true | neva_mcp_proxy завис | AUTO: restart_mcp_server_net |

## PLAYBOOK: restart_mcp_server_net

```bash
# Шаг 1: launchd kickstart (KeepAlive=true перезапустит)
launchctl kickstart -k gui/$(id -u)/com.neva.mcp-server

# Шаг 2: подождать 5с
sleep 5

# Шаг 3: проверить HTTP
curl http://127.0.0.1:9000/health

# Fallback если launchd не работает:
pkill -f neva_mcp_server.py
cd ~/Documents/NEVA_MCP_BRIDGE
/Users/arka/Documents/NEVA/.venv/bin/python3 neva_mcp_server.py &
```

## КОДЫ ОШИБОК И ЗНАЧЕНИЕ

| Код/Сообщение | Причина | Решение |
|---|---|---|
| `Address already in use` | порт 9000/9001 занят | lsof -i :9000, pkill старый процесс |
| `ImportError: neva_mcp_events` | файл не найден в NEVA_MCP_BRIDGE | проверить наличие файла |
| `ImportError: neva_mcp_patch` | файл не найден | проверить наличие файла |
| `EXECUTOR IMPORT FAILED` | mcp_executor.py не найден | некритично, сервер работает без executor |
| `ACTION_NOT_ALLOWED` | запрос попал на старый сервер (mcp_server.py) | перезапустить neva_mcp_server.py |
| `executor: 'data'` | живой сервер — старая версия без batch | перезапустить на v2.2 |
| `status: rejected` | mcp_validator отклонил action | то же — старый процесс |

## ВАЖНЫЕ КОНСТАНТЫ
```python
MCP_PORT  = 9000   # JSON-RPC endpoint
DASH_PORT = 9001   # Live Dashboard
BASE      = ~/Documents/NEVA_MCP_BRIDGE
NEVA      = ~/Documents/NEVA
ADMIN_TOKEN = из ~/Documents/NEVA/.env (NEVA_ADMIN_TOKEN=...)
```

## ACTION=BATCH (v2.2, TASK-1 SPEED_TASK)

Параллельное выполнение read-only actions:
```json
{
  "action": "batch",
  "params": {
    "actions": [
      {"action": "file_read",   "params": {"path": "/path/A"}},
      {"action": "file_lines",  "params": {"path": "/path/B", "start": 1, "end": 20}},
      {"action": "neva_chronic", "params": {}}
    ]
  }
}
```
Ответ: `{"status": "ok", "results": [...], "count": 3}`

Read-only (параллельно): file_read, file_lines, file_tree, git_status,
  system_info, neva_status, neva_chronic, medic_events
Write (последовательно): file_write, file_patch, file_append, claude_reply

## SELF-TEST
```bash
cd ~/Documents/NEVA_MCP_BRIDGE
/Users/arka/Documents/NEVA/.venv/bin/python3 neva_mcp_server.py --self-test
# Ожидание: 8/8 PASS
# ST-08 проверяет action=batch
```

## ВЕРСИЯ СЕРВЕРА
```bash
curl http://127.0.0.1:9000/health | python3 -m json.tool
# {"status": "ok", "version": "2.2", "transport": "streamable-http", "port": 9000}
```
