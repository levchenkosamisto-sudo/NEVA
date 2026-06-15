# NEVA Medic Knowledge — Approval Server
# Версия: 1.0 | Дата: 2026-06-13 | Архитектор: Claude

## Назначение
neva_approval_server.py — HTML UI на порте 8766.
Директор подтверждает или отклоняет опасные операции Executor через кнопки в браузере.
Без него все file_write, run_tests, git_commit зависают в очереди.

## Запуск
- Автозапуск: ~/.zshrc — при открытии нового терминала
- Вручную: python3 ~/Documents/NEVA_MCP_BRIDGE/neva_approval_server.py &
- AppSupport копия: ~/Library/Application Support/NEVA/neva_approval_server.py
- Порт: 8766
- Health: GET http://127.0.0.1:8766/health → {"status":"ok"}
- UI: http://127.0.0.1:8766

## Диагностика
- HTTP check: curl -s http://127.0.0.1:8766/health
- Процесс: ps aux | grep neva_approval_server
- Порт занят: lsof -i :8766

## Известные проблемы
### ПРОБЛЕМа #1 — порт 8766 занят старым процессом
- Симптом: curl отвечает или ошибка, ps показывает процесс
- Причина: старый процесс завис и держит порт
- Решение: pkill -f neva_approval_server → подождать 2с → запустить снова
- Playbook: start_approval_server (pkill → wait → run → check_http)

### ПРОБЛЕМА #2 — сервер упал после ребута macOS
- Симптом: .zshrc не выполнился (нет открытого терминала)
- Решение: открыть новый терминал (запустит .zshrc) или запустить вручную

## История аварий
| Дата | Проблема | Решение |
|---|---|---|
| 2026-06-13 07:36 | Approval server упал | Medic AUTO починил за < 2 мин. conf=0.97. |

## Playbook Medic
- problem_id: approval_not_running, approval_http_fail
- mode: AUTO (3 попытки)
- шаги: pkill → wait 1с → запуск через AppSupport python → wait 3с → check_http
- при провале: ESCALATION
- Conf ожидаемый: 0.92+
