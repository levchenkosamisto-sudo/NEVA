# neva_github_watcher.py — MEDIC KNOWLEDGE
# Версия: 2.1 | Дата: 2026-06-19 | DUMA

## Назначение
Следит за GitHub репо output/ на ответы аудиторов ДУМЫ.
Ждёт всех 3 аудиторов, затем Cerebras синтезирует и доставляет Claude через claude_reply.

## Расположение
/Users/arka/Documents/NEVA/neva_github_watcher.py

## State файл (читает Medic)
/Users/arka/Documents/NEVA/neva_watcher_state.json

Поля state:
  service:    'neva_github_watcher'
  version:    '2.1'
  status:     ok / warn / error / stopped
  timestamp:  ISO время последнего обновления
  pid:        PID процесса
  last_file:  последний обработанный файл
  round_data: количество ответов по кругам

## Признаки сбоя (Medic проверяет)
- state.status == 'error' более 3 минут
- state.timestamp не обновлялся более 3 минут
- процесс отсутствует в ps aux

## Действие Medic при сбое
1. L1: перезапустить через launchd (launchctl stop/start com.neva.github-watcher)
2. L2: проверить GITHUB_TOKEN, Cerebras API, интернет
3. L3: ping_director

## Запуск
```bash
python3 /Users/arka/Documents/NEVA/neva_github_watcher.py
```

## Диагностика
```bash
python3 /Users/arka/Documents/NEVA/neva_github_watcher.py --health
python3 /Users/arka/Documents/NEVA/neva_github_watcher.py --diag
python3 /Users/arka/Documents/NEVA/neva_github_watcher.py --self-test
```

## Зависимости
- GITHUB_TOKEN в /Users/arka/Documents/NEVA/.env
- CEREBRAS_API_KEY в /Users/arka/Documents/NEVA/.env
- GEMINI_API_KEY в /Users/arka/Documents/NEVA/.env
- Интернет (облачные API, не Ollama)
- BRIDGE_DIR: /Users/arka/Documents/NEVA_MCP_BRIDGE

## ThermalGuard
При CRITICAL/EMERGENCY — пропускает цикл, ждёт 5 мин.
Пишет thermal статус в state файл.

## Log файл
/Users/arka/Documents/NEVA/logs/watcher.log

## launchd plist
/Users/arka/Library/LaunchAgents/com.neva.github-watcher.plist
Управление:
  launchctl load ~/Library/LaunchAgents/com.neva.github-watcher.plist
  launchctl stop com.neva.github-watcher
  launchctl start com.neva.github-watcher
