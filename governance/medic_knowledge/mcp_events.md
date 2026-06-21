# neva_mcp_events.py v1.1 — Knowledge Base
# Версия: 1.0 | Дата: 2026-06-15

## НАЗНАЧЕНИЕ
Ring buffer событий Medic ↔ Claude.
Медик пишет события → MCP сервер хранит → Claude читает.
Если сломан — дашборд слеп, claude_reply не доходит до медика.

## ДИАГНОСТИКА

### events_module_broken
Симптом: import fails или сервер стартовал без модуля
```bash
cd ~/Documents/NEVA_MCP_BRIDGE
python3 -c "from neva_mcp_events import push_event, get_events; print('OK')"
```
Решение: проверить файл, перезапустить neva_mcp_server.py

### events_ring_empty
Симптом: медик работает > 5 мин, но get_events возвращает []
Причина: модуль загружен в другом процессе (не внутри сервера)
Решение: перезапустить сервер — он загрузит модуль в свой процесс

## FAILURE MODES
| ID | Симптом | Действие |
|---|---|---|
| events_module_broken | import fail | AUTO: restart mcp_server_net |
| events_ring_empty | буфер пуст > 10мин | AUTO: restart mcp_server_net |

## SELF-TEST
```bash
python3 /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_mcp_events.py
# Ожидание: 5/5 PASS
```

## ИСПОЛЬЗОВАНИЕ since_ts (v1.1)
```python
# Только новые события с момента последней проверки
events = get_events(20, since_ts='2026-06-15T21:00:00')
```
