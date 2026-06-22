# NEVA Medic Knowledge — Medic Self-Diagnostics
# Версия: 2.0 | Дата: 2026-06-15 | Архитектор: Claude | Директор: Серж

## Назначение
Медик диагностирует СЕБЯ первым, прежде чем другие компоненты.
Принцип: "Врач — исцели себя сам".

## КОМПОНЕНТЫ СИСТЕМЫ
neva_medic.py           — главный процесс (heal loop, playbooks, AI)
neva_mcp_server.py      — HTTP :9000 (MCP transport, dashboard :9001)
neva_mcp_proxy.py       — stdio proxy для Claude Desktop
neva_approval_server.py — approval gate :8766
neva_auditor_daemon.py  — auditor daemon (Т6) :auditor.sock
neva_status_dot.py      — цветная точка AnyBar (меню бар)
AnyBar.app              — /Applications/AnyBar.app, UDP :1738
medic_knowledge/        — база знаний

## ИНДИКАТОР ДИРЕКТОРА — AnyBar точка в menu bar
🟢 green  — медик жив + MCP :9000 OK → система в порядке
🟡 yellow — ремонтируется / перезапускается → подождить 30с
🔴 red    — медик упал и не восстановился → нужно вмешаться

AnyBar управляется скриптом neva_status_dot.py (проверка каждые 15с).
neva_status_dot.py сам защищён launchd KeepAlive (com.neva.status-dot).

## ЗАЩИТА МЕДИКА — двойной рубеж
1. launchd KeepAlive (com.neva.medic) — macOS поднимает за 10с
2. neva_status_dot.py — независимый watchdog, nohup запуск за ~23с

## Порядок self-диагностики при старте чата
1. neva_status → traffic_light, chronic, open_escs
2. GREEN → "Система в норме"
3. YELLOW → доложить chronic, предложить ремонт
4. RED → немедленно доложить, начать диагностику
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

## ПРИОРИТЕТ 4 — AnyBar и status_dot живы?
ps aux | grep neva_status_dot | grep -v grep
ps aux | grep -i anybar | grep -v grep
launchctl list | grep neva.status-dot
tail -3 ~/Documents/NEVA_MCP_BRIDGE/logs/status_dot.log
Норма: запись не старше 30с, последняя строка не red.

## РЕМОНТ #1 — Медик упал
```bash
# launchd должен поднять сам через 10с (KeepAlive)
# если нет — nohup fallback:
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_medic.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/medic.log 2>&1 &
sleep 5 && ps aux | grep neva_medic.py | grep -v grep
```

## РЕМОНТ #2 — MCP :9000 упал
```bash
kill $(lsof -ti :9000 :9001 2>/dev/null) 2>/dev/null; sleep 2
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_mcp_server.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/mcp_server_net.log 2>&1 &
sleep 5 && curl -s http://127.0.0.1:9000/health
```

## РЕМОНТ #3 — Approval упал
```bash
pkill -f neva_approval_server.py; sleep 2
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_approval_server.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/approval.log 2>&1 &
sleep 3 && curl -s http://127.0.0.1:8766/ping
```

## РЕМОНТ #4 — Auditor daemon упал
```bash
launchctl unload ~/Library/LaunchAgents/com.neva.auditor.plist
sleep 2
launchctl load ~/Library/LaunchAgents/com.neva.auditor.plist
sleep 5 && tail -3 ~/Documents/NEVA_MCP_BRIDGE/logs/auditor.log
```

## РЕМОНТ #5 — Медик завис (процесс есть, лог не растёт)
```bash
pkill -f neva_medic.py; sleep 3
# Затем РЕМОНТ #1
```

## РЕМОНТ #6 — AnyBar не запущен / точка не меняется
```bash
# Запустить AnyBar:
open -a AnyBar
sleep 2
# Тест сигнала:
echo -n "green" | nc -4u -w0 localhost 1738
# Перезапустить status_dot:
launchctl kickstart -k gui/$(id -u)/com.neva.status-dot
```

## Self-test медика
```bash
cd ~/Documents/NEVA_MCP_BRIDGE
/Users/arka/Documents/NEVA/.venv/bin/python3 neva_medic.py --self-test 2>&1 | tail -3
# Ожидание: 19/19 PASS
```

## Признаки здоровой системы
- Точка AnyBar зелёная
- процесс neva_medic.py есть
- curl :9000/health → ok
- heal_end: ok не старше 120с в medic.log
- traffic_light GREEN
- chronic_count = 0

## Признаки проблемы
| Симптом | Причина |
|---|---|
| Точка красная дольше 30с | Медик не восстанавливается → РЕМОНТ #1 вручную |
| Точка жёлтая дольше 60с | MCP не отвечает → РЕМОНТ #2 |
| Точка не видна | AnyBar не запущен → РЕМОНТ #6 |
| medic.log не растёт > 5 мин | Медик завис → РЕМОНТ #5 |
| traffic_light RED + chronic > 3 | Системный сбой → Директор |

## История аварий
| Дата | Авария | Причина | Решение |
|---|---|---|---|
| 2026-06-15 | file_read недоступен в MCP | sys.path загружал старый executor | Патч sys.path.insert(BASE) |
| 2026-06-15 | Медик упал после 3/3 FAIL playbook | Нет защиты | launchd KeepAlive + status_dot watchdog |
| 2026-06-15 | ESC mcp_server_net_http ложный RED | BrokenPipeError при закрытии | :9000 живой, ESC ложный |
