# mcp_server_net knowledge
# Обновлено: 2026-06-15

## КОМПОНЕНТ
venv правильный: /Users/arka/Documents/NEVA/.venv/bin/python3
NEVA_MCP_BRIDGE/.venv НЕ существует — причина exit 78
Порты: :9000 API / :9001 Dashboard

## ЗАПУСК
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_mcp_server.py >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/mcp_server_net.log 2>&1 &

## EXIT 78 launchd
Причина: plist указывает на несуществующий .venv
Диагностика: launchctl list, grep mcp-server
Решение: исправить plist на /Users/arka/Documents/NEVA/.venv/bin/python3
Временное решение: nohup запуск

## mcp_approval_hang
Причина: executor принял токен, запись зависла >90с
Playbook: restart_mcp_server_net

## mcp_proxy_fallback_stuck
Причина: neva_mcp_proxy.py не передаёт на :9000
Playbook: restart_mcp_server_net
