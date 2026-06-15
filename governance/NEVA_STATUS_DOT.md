# NEVA STATUS DOT — УСТАНОВЛЕНО
# Дата: 2026-06-15 Сессия 3
# Архитектор: Claude | Директор: Серж

## ЧТО УСТАНОВЛЕНО

### AnyBar
- Приложение: /Applications/AnyBar.app
- Установлено: brew install --cask anybar
- Управление: UDP :1738
- Цвета: green/yellow/red/orange/white

### neva_status_dot.py v1.1
- Файл: ~/Documents/NEVA_MCP_BRIDGE/neva_status_dot.py
- Лог: ~/Documents/NEVA_MCP_BRIDGE/logs/status_dot.log
- Проверка каждые 15с
- 🟢 green  — медик жив + MCP :9000 OK
- 🟡 yellow — ремонтируется / перезапуск
- 🔴 red    — медик не восстановился

### LaunchAgents (KeepAlive)
- com.neva.medic.plist — медик под launchd KeepAlive
- com.neva.status-dot.plist — status_dot под launchd KeepAlive

## АРХИТЕКТУРА

```
macOS menu bar
  └─ AnyBar.app (цветная точка)
       ↑ UDP :1738
launchd KeepAlive
  ├─ com.neva.status-dot → neva_status_dot.py
  |    проверяет каждые 15с:
  |      medic_alive() ← pgrep neva_medic.py
  |      mcp_alive()   ← curl :9000/health
  |    если медик упал → nohup запуск
  |
  └─ com.neva.medic → neva_medic.py
       KeepAlive: true (макос поднимает сам)
```

## ТЕСТИРОВАНИЕ 2026-06-15
- Медик убит вручную
- Точка: зелёная → красная → жёлтая → зелёная
- Время восстановления: ~23с
- Результат: ✅ полностью автоматически

## ЗАПУСК ПОСЛЕ РЕБУТА
```bash
# AnyBar — вручной (Login Item не настроен)
open -a AnyBar
# status_dot и medic — launchd запускает автоматически
```

## ОТКРЫТО
- [ ] Добавить AnyBar в Login Items (чтобы запускался после ребута автоматически)
