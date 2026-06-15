# NEVA Medic Knowledge — Medic Self-Diagnostics
# Версия: 1.0 | Дата: 2026-06-15 | Архитектор: Claude | Директор: Серж

## Назначение
Медик диагностирует СЕБЯ первым, прежде чем другие компоненты.
Принцип: "Врач — исцели себя сам".

## Компоненты медика
neva_medic.py          — главный процесс (heal loop, playbooks, AI)
neva_mcp_server.py     — HTTP :9000 (MCP transport, dashboard :9001)
neva_mcp_proxy.py      — stdio proxy для Claude Desktop
neva_approval_server.py — approval gate :8766
neva_auditor_daemon.py — auditor daemon (Т6) :auditor.sock
medic_knowledge/       — база знаний

## Порядок self-диагностики при старте чата
1. neva_status → traffic_light, chronic, open_escs
2. GREEN → "Система в норме"
3. YELLOW → доложить chronic, предложить ремонт
4. RED → немедленно доложить, начать диагностику НИЖЕ
5. ВСЕГДА сначала себя, потом другие компоненты

## ПРИОРИТЕТ 0 — Медик жив?
ps aux | grep neva_medic.py | grep -v grep
tail -5 ~/Documents/NEVA_MCP_BRIDGE/logs/medic.log
Норма: heal_end строки не старше 120с.

## ПРИОРИТЕТ 1 — MCP сервер :9000?
curl -s http://127.0.0.1:9000/health
Ожидание: {"status": "ok", "version": "2.0"}

## ПРИОРИТЕТ 2 — Approval сервер :8766?
curl -s http://127.0.0.1:8766/ping 2>/dev/null || echo "DEAD"

## ПРИОРИТЕТ 3 — Auditor daemon жив?
ps aux | grep neva_auditor_daemon | grep -v grep
launchctl list | grep neva.auditor
tail -3 ~/Documents/NEVA_MCP_BRIDGE/logs/auditor.log
Норма: heartbeat строки не старше 120с.

## РЕМОНТ #1 — Медик упал
pkill -f neva_medic.py; sleep 2
cd ~/Documents/NEVA_MCP_BRIDGE
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u neva_medic.py \
  >> logs/medic.log 2>&1 </dev/null &
sleep 3 && ps aux | grep neva_medic.py | grep -v grep

## РЕМОНТ #2 — MCP :9000 упал
pkill -f neva_mcp_server.py; sleep 2
cd ~/Documents/NEVA_MCP_BRIDGE
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u neva_mcp_server.py \
  >> logs/mcp_server_net.log 2>&1 </dev/null &
sleep 5 && curl -s http://127.0.0.1:9000/health

## РЕМОНТ #3 — Approval упал
pkill -f neva_approval_server.py; sleep 2
cd ~/Documents/NEVA_MCP_BRIDGE
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u neva_approval_server.py \
  >> logs/approval.log 2>&1 </dev/null &
sleep 3 && curl -s http://127.0.0.1:8766/ping

## РЕМОНТ #4 — Auditor daemon упал
launchctl unload ~/Library/LaunchAgents/com.neva.auditor.plist
sleep 2
launchctl load ~/Library/LaunchAgents/com.neva.auditor.plist
sleep 5
ps aux | grep neva_auditor_daemon | grep -v grep
tail -3 ~/Documents/NEVA_MCP_BRIDGE/logs/auditor.log

## РЕМОНТ #5 — Медик завис (процесс есть, лог не растёт)
pkill -f neva_medic.py; sleep 3
# Затем РЕМОНТ #1

## Self-test медика
cd ~/Documents/NEVA_MCP_BRIDGE
/Users/arka/Documents/NEVA/.venv/bin/python3 neva_medic.py --self-test 2>&1 | tail -3
Ожидание: 19/19 PASS

## Признаки здорового медика
- процесс neva_medic.py есть
- curl :9000/health → ok
- heal_end: ok не старше 120с в medic.log
- traffic_light GREEN или YELLOW
- chronic_count = 0 (допустимо ≤ 2 MEDIUM)

## Признаки больного медика
| Симптом | Причина |
|---|---|
| Нет процесса neva_medic.py | Упал |
| medic.log не растёт > 5 мин | Завис на AI или I/O |
| medic.log растёт очень быстро | Бесконечный цикл |
| traffic_light RED + chronic > 3 | Системный сбой → Директор |
| :9000 не отвечает | neva_mcp_server.py упал |

## История аварий медика
| Дата | Авария | Причина | Решение |
|---|---|---|---|
| 2026-06-15 | file_read недоступен в MCP | neva_mcp_server.py не реализовал action | Ручной ввод Директором |
| 2026-06-15 | ESC mcp_server_net_http ложный RED | BrokenPipeError при закрытии соединения | :9000 живой, ESC ложный |
