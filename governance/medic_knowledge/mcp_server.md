# NEVA Medic Knowledge — MCP Server (Claude Desktop)
# Версия: 1.0 | Дата: 2026-06-13 | Архитектор: Claude

## Назначение
mcp_server.py v3.3 — MCP сервер, Claude Desktop запускает его автоматически при старте.
Обеспечивает Claude инструменты: file_read, file_write, git_status, run_tests, diagnostics, system_info.
Если mcp_server.py не запущен — Claude полностью слеп, не может читать/писать файлы.

## Запуск
- Автоматически: Claude Desktop через MCP config (~/Library/Application Support/Claude/)
- Вручную НЕ запускается отдельно — только через Claude Desktop
- Soft restart: open -a Claude (закрывает и открывает приложение)
- Hard restart: osascript quit Claude → open -a Claude

## Диагностика
- Живой ли: ps aux | grep mcp_server.py
- Если Claude Desktop запущен но mcp_server.py не в ps — MCP config сломан
- Версия: grep "v3.3" ~/Documents/NEVA_MCP_BRIDGE/mcp_server.py | head -1

## Два уровня рестарта (Т2 MEDIC-V3, реализовано в Сессии 1)
- Уровень 1 AUTO: open -a Claude → wait 15с → check ps (NO confirm)
- Уровень 2 ASK: osascript quit + open → pending_decisions → ждём Директора

## Известные проблемы
### ПРОБЛЕМА #1 — mcp_server не стартует после ребута Claude
- Симптом: ps aux | grep mcp_server пуст, хотя Claude Desktop запущен
- Причина: MCP config повреждён или путь к скрипту изменился
- Диагностика: cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
- Решение: проверить путь к mcp_server.py в конфиге

### ПРОБЛЕМА #2 — AppSupport sync рассинхронизация
- Симптом: mcp_server.py в AppSupport старее чем в BASE_DIR
- Решение: bash ~/Documents/NEVA_MCP_BRIDGE/sync_to_appsupport.sh

## Playbook Medic
- problem_id: mcp_not_running
- mode: AUTO (soft restart уровень 1: open -a Claude)
- при провале уровня 1: ASK (уровень 2 hard restart)
- Conf ожидаемый: 0.82
