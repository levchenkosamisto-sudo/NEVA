# NEVA Medic Knowledge — Control Center
# Версия: 1.0 | Дата: 2026-06-15 | Архитектор: Claude

## Назначение
neva_control_center.py v2.6 — визуальный UI системы NEVA.
Порт: 8767. Отображает: статус всех процессов, логи, thermal, medic, executor.
Файл: ~/Documents/NEVA_MCP_BRIDGE/neva_control_center.py
Статус: PROD (не критический — UI только)

## Запуск
```bash
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_control_center.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/control_center.log 2>&1 &
```

## Диагностика
```bash
# Живой ли:
ps aux | grep neva_control_center | grep -v grep
# HTTP отвечает:
curl -s http://127.0.0.1:8767/ | head -3
# API статус:
curl -s http://127.0.0.1:8767/api/status | python3 -m json.tool | head -20
```

## Известные проблемы

### cc_not_running — Control Center не запущен
Причина: не запущен после ребута (нет launchd агента, запуск через .zshrc)
Решение: nohup запуск (см. выше)
Приоритет: MEDIUM (не влияет на работу системы)

### cc_port_busy — порт 8767 занят
Решение: kill $(lsof -ti :8767) && перезапустить

## Playbook: restart_control_center
```bash
kill $(lsof -ti :8767 2>/dev/null) 2>/dev/null
sleep 1
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_control_center.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/control_center.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:8767/ | head -1
```

## История аварий
| Дата | Проблема | Решение |
|---|---|---|
| 2026-06-15 | CC не запущен после рестарта медика | nohup запуск вручную |
