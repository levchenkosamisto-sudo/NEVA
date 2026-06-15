# MCP Proxy — База знаний медика
# Программа: neva_mcp_proxy.py v1.0
# Обновлено: 2026-06-15 Сессия 4

## НАЗНАЧЕНИЕ
Прокси: stdio (Claude Desktop MCP) → HTTP :9000/mcp (постоянный HTTP-сервер).
Зачем: mcp_server.py (stdio) умирает вместе с Claude Desktop.
neva_mcp_server.py (HTTP) живёт через launchd — прокси связывает их.
Фоллбэк: если :9000 недоступен — прокси работает напрямую через mcp_executor.

## АРХИТЕКТУРА
```
Claude Desktop → stdio → [neva_mcp_proxy.py]
                               ↓ HTTP POST /mcp  (если :9000 живой)
                               [neva_mcp_server.py :9000]  ← launchd KeepAlive
                               ↓ fallback доступен (если :9000 пал)
                               [mcp_executor.py напрямую]
```
Режимы: proxy / fallback. Переключение автоматическое (CHECK_EVERY=10 запросов).

## КОНФИГ (claude_desktop_config.json)
```json
"neva_proxy": {
  "command": "/Users/arka/Documents/NEVA/.venv/bin/python3",
  "args": ["/Users/arka/Documents/NEVA_MCP_BRIDGE/neva_mcp_proxy.py"]
}
```

## ЛОГ
Файл: `logs/mcp_proxy.log`
Норма: `Сервер :9000 ✔ доступен (режим proxy)` при старте

## ПРОБЛЕМЫ И РЕШЕНИЯ

### ПРОБЛЕМА proxy_fallback_mode
Симптом: в `mcp_proxy.log` запись `Режим: fallback` или `Сервер :9000 недоступен`.
Причина: neva_mcp_server.py упал или не запустился.
Действия:
1. Проверить сервер: `curl -s http://127.0.0.1:9000/health`
2. Если нет ответа — восстановить сервер:
   `launchctl kickstart -k gui/$(id -u)/com.neva.mcp-server`
3. Прокси автоматически вернётся в режим proxy через 10 запросов.
Результат: текущее Claude Desktop сессию не нужно перезапускать.

### ПРОБЛЕМА proxy_import_error
Симптом: `Fallback error: No module named mcp_executor` в логе.
Действия:
```bash
ls ~/Documents/NEVA_MCP_BRIDGE/mcp_executor.py
ls ~/Documents/NEVA_MCP_BRIDGE/mcp_validator.py
# Если отсутствуют:
cp ~/Documents/NEVA/tools/mcp_executor/mcp_executor.py ~/Documents/NEVA_MCP_BRIDGE/
cp ~/Documents/NEVA/tools/mcp_executor/mcp_validator.py ~/Documents/NEVA_MCP_BRIDGE/
```

### ПРОБЛЕМА proxy_retry_loop
Симптом: `proxy attempt 3/3: <URLError...>` повторяется в логе.
Причина: :9000 недоступен или временный сбой сети.
Действия: аналогично proxy_fallback_mode.

## ДИАГНОСТИКА
```bash
tail -20 ~/Documents/NEVA_MCP_BRIDGE/logs/mcp_proxy.log
curl -s http://127.0.0.1:9000/health | python3 -m json.tool
# Норма: version 2.1
```

*Создано: 2026-06-15 (Сессия 4) | Архитектор: Claude | Директор: Серж*
