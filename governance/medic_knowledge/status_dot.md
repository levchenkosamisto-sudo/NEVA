# NEVA Medic Knowledge — Status Dot (AnyBar)
# Версия: 1.0 | Дата: 2026-06-15 | Архитектор: Claude

## Назначение
neva_status_dot.py v1.1 + AnyBar.app — визуальный индикатор для Директора.
Цветная точка в menu bar macOS. Проверка каждые 15с.
Файл: ~/Documents/NEVA_MCP_BRIDGE/neva_status_dot.py
Лог: ~/Documents/NEVA_MCP_BRIDGE/logs/status_dot.log
Статус: PROD (launchd KeepAlive com.neva.status-dot)

## СЕМАФОР ЦВЕТОВ
🟢 green  — медик жив + MCP :9000 OK
🟡 yellow — ремонт / перезапуск / инициализация
🔴 red    — медик не восстановился за ~23с → нужно вмешательство

## ДИАГНОСТИКА
```bash
# status_dot живой?
ps aux | grep neva_status_dot | grep -v grep
launchctl list | grep neva.status-dot
# AnyBar живой?
ps aux | grep -i anybar | grep -v grep
# Последние события:
tail -5 ~/Documents/NEVA_MCP_BRIDGE/logs/status_dot.log
```

## ИЗВЕСТНЫЕ ПРОБЛЕМЫ

### status_dot_not_running
Защита: launchd KeepAlive поднимает автоматически
Решение: launchctl kickstart -k gui/$(id -u)/com.neva.status-dot

### anybar_not_running — точка не видна
Причина: AnyBar не запущен (нет в Login Items или не одобрен macOS)
Решение:
  open -a AnyBar
  Или: System Settings → Основные → Объекты входа → добавить AnyBar

### launchctl kickstart зависает
Причина: баг launchd на некоторых сервисах
Решение: не использовать kickstart в status_dot (убрано в v1.1), только nohup

## PLAYBOOK: restart_status_dot
```bash
launchctl kickstart -k gui/$(id -u)/com.neva.status-dot
sleep 5
ps aux | grep neva_status_dot | grep -v grep
tail -3 ~/Documents/NEVA_MCP_BRIDGE/logs/status_dot.log
```

## PLAYBOOK: restart_anybar
```bash
open -a AnyBar
sleep 2
echo -n "yellow" | nc -4u -w0 localhost 1738
sleep 15
tail -3 ~/Documents/NEVA_MCP_BRIDGE/logs/status_dot.log
```

## История аварий
| Дата | Проблема | Решение |
|---|---|---|
| 2026-06-15 | kickstart зависал на 15с, медик не восстанавливался | Убран kickstart, только nohup в v1.1 |
| 2026-06-15 | Gatekeeper блокировал AnyBar | Разрешено через Privacy & Security → Open Anyway |
