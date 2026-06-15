# NEVA Medic Knowledge — Thermal Guard
# Версия: 1.0 | Дата: 2026-06-13 | Архитектор: Claude

## Назначение
neva_thermal_guard.py — защита Mac M1 8GB от перегрева.
Мониторит RAM/CPU/swap каждые 18с. При перегреве останавливает Ollama.
Версия: v9.4. Статус: PROD.

## Запуск
- Основной: launchd агент com.neva.thermal-guard (plist в ~/Library/LaunchAgents/)
- Fallback: nohup python3 -u ~/Documents/NEVA/neva_thermal_guard.py &
- Venv: ~/Documents/NEVA/.venv/bin/python3
- Лог: ~/Documents/NEVA/thermal.log
- Стейт: ~/Documents/NEVA/thermal_state.json

## Диагностика
- Живой ли: ps aux | grep thermal_guard
- Лог свежий если: thermal.log mtime < 120с (Guard пишет каждые 18с)
- Нормальное состояние в логе: 'state=NOMINAL'
- Тревога: 'state=BLOCKED' или 'state=CRITICAL'

## Известные проблемы
### ПРОБЛЕМА #1 — macOS Sequoia FDA (ХРОНИЧЕСКАЯ)
- Симптом: thermal.log не обновляется > 120с после ребута
- Причина: macOS Sequoia 26.x FDA (Full Disk Access) блокирует launchd агентам запись в файлы
  тихо — launchctl load rc=0, но процесс сразу падает при попытке открыть файл
- Признак: launchctl load rc=0, но ps aux | grep thermal пуст
- Решение: запустить через nohup вместо launchd
- Команда: nohup ~/Documents/NEVA/.venv/bin/python3 -u ~/Documents/NEVA/neva_thermal_guard.py > ~/Documents/NEVA/thermal.log 2>&1 &
- Mitigation добавлен в playbook: nohup_if_stale шаг после launchctl

### ПРОБЛЕМА #2 — Guard не в PATH при ребуте
- Симптом: не запускается через launchd после cold reboot
- Причина: .zshrc не sourced для launchd
- Решение: прописать полный путь к venv python в plist

## История аварий
| Дата | Проблема | Решение |
|---|---|---|
| 2026-06-12 16:44 | Guard упал, thermal.log stale 19436с | Medic создал эскалацию ESC-20260612-223002. Причина: FDA Sequoia. |
| 2026-06-08 | Thermal Guard v9.4 принят | 32/34 PASS |

## Playbook Medic
- problem_id: thermal_log_stale
- mode: AUTO (3 попытки)
- шаги: launchctl unload → load → check → nohup_if_stale
- при провале: ESCALATION → claude_inbox

## Порог эскалации
Guard не живёт > 600с и nohup тоже не помог → эскалация Директору.
Conf ожидаемый от AI при этом контексте: 0.85+
