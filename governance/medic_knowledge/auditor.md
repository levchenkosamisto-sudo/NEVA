# NEVA Medic Knowledge — Background Auditor
# Версия: 2.0 | Дата: 2026-06-15 | Архитектор: Claude | Директор: Серж

## Назначение
background_auditor.py v6.9 — библиотека аудита MCP операций.
neva_auditor_daemon.py v1.0 — standalone daemon (Архитектура Т6, PROD с 2026-06-15).
Живёт через launchd KeepAlive. Unix socket: auditor.sock. Heartbeat каждые 60с.

## Архитектура Т6 (PROD)
[mcp_server.py] → JSON → auditor.sock → [neva_auditor_daemon.py] → ExecutorAuditWorker → auditor.log

## Управление
launchctl load/unload ~/Library/LaunchAgents/com.neva.auditor.plist
Self-test: python3 neva_auditor_daemon.py --self-test  (ожидание: 5/5 PASS)
Диагностика: python3 neva_auditor_daemon.py --diag

## Диагностика
ps aux | grep neva_auditor_daemon | grep -v grep
launchctl list | grep neva.auditor
tail -5 logs/auditor.log
Норма: heartbeat строки не старше 120с, "worker=alive"

## ПРОБЛЕМА auditor_log_stale — РЕШЕНИЕ
Шаг 1: ps aux | grep neva_auditor_daemon → если мёртв:
Шаг 2A (launchd есть):
  launchctl unload ~/Library/LaunchAgents/com.neva.auditor.plist
  sleep 2
  launchctl load ~/Library/LaunchAgents/com.neva.auditor.plist
Шаг 2B (launchd нет):
  cp ~/Documents/NEVA_MCP_BRIDGE/com.neva.auditor.plist ~/Library/LaunchAgents/
  launchctl load ~/Library/LaunchAgents/com.neva.auditor.plist
Шаг 3: sleep 10 && tail -3 logs/auditor.log → должен быть "ExecutorAuditWorker started"
Шаг 4: нет результата → ЭСКАЛАЦИЯ Директору

## ПРОБЛЕМА ImportError mcp_validator
cp /Users/arka/Documents/NEVA/tools/mcp_executor/mcp_validator.py \
   ~/Documents/NEVA_MCP_BRIDGE/mcp_validator.py

## ПРОБЛЕМА suspended tty input при ручном запуске
Всегда добавлять </dev/null при фоновом запуске:
nohup python3 -u script.py >> log.log 2>&1 </dev/null &

## Playbook Medic
problem_id: auditor_log_stale | mode: AUTO | conf ожидаемый: 0.88
Шаги: ps → launchctl unload/load → sleep 10 → проверить лог → эскалация

## История аварий
| Дата | Авария | Причина | Решение |
|---|---|---|---|
| 2026-06-15 | auditor_log_stale 5 попыток | Т6 не была реализована, daemon не существовал | Создан neva_auditor_daemon.py + plist |
