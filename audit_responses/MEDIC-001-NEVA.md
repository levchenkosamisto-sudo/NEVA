# NEVA Medic Knowledge — NEVA Medic сам
# Версия: 2.0 | Дата: 2026-06-15 | Архитектор: Claude

## Назначение
neva_medic.py v3.8 — L1 авторемонт системы NEVA.
Цикл heal каждую минуту. AI-диагностика + playbook. knowledge base v5.0.
Файл: ~/Documents/NEVA_MCP_BRIDGE/neva_medic.py
Лог: ~/Documents/NEVA_MCP_BRIDGE/logs/medic.log
Статус: PROD (критический — без него 0 авторемонта)

## ДВОЙНАЯ ЗАЩИТА МЕДИКА (2026-06-15)

```
macOS launchd (PID 1)
  └─ com.neva.medic → KeepAlive: true
       Падение медика → launchd поднимает за 10с (автоматически)

neva_status_dot.py (watchdog, каждые 15с)
  └─ medic_alive()? → нет → nohup запуск за ~23с
       → точка: yellow (ремонт) → green (ок)
neva_status_dot.py сам защищён launchd KeepAlive (com.neva.status-dot)
```

Модель: systemd watchdog chain — OS supervisor (макос) + app watchdog (status_dot)

## АРХИТЕКТУРА
```
neva_medic.py heal_cycle() (каждую 60с)
  ├─ mcp_check_reply()      ← читает ответ Claude из :9000/claude_reply
  ├─ detect_problems()     ← проверяет все компоненты
  ├─ ai_diagnose()         ← FlagmanRouter (Cerebras→Groq→OpenRouter)
  ├─ load_knowledge()      ← читает medic_knowledge/*.md
  ├─ run_playbook()        ← выполняет bash команды
  ├─ incident_log_write()  ← пишет state/incident_log.json
  └─ push_event()          ← отправляет событие в MCP :9000
```

## Запуск
```bash
# launchd KeepAlive (com.neva.medic) — автоматически при входе в систему
# Fallback вручной:
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_medic.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/medic.log 2>&1 &
```

## Диагностика
```bash
# Живой ли:
ps aux | grep neva_medic | grep -v grep
# Лог свежий:
tail -10 ~/Documents/NEVA_MCP_BRIDGE/logs/medic.log
# launchd статус:
launchctl list com.neva.medic
# Self-test:
/Users/arka/Documents/NEVA/.venv/bin/python3 \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_medic.py --self-test
```

## Известные проблемы

### medic_not_running — медик упал
Защита 1: launchd KeepAlive поднимает за 10с (автоматически)
Защита 2: neva_status_dot watchdog поднимает через ~23с (nohup)
Если оба не помогли → точка остаётся красной → вмешательство Директора
Playbook: restart_medic (nohup)

### medic_ai_all_fail — все AI провайдеры недоступны
Медик работает но conf=0 — playbook не запускается
Решение: проверить API ключи в .env

## Playbook: restart_medic
```bash
kill $(ps aux | grep neva_medic | grep -v grep | awk '{print $2}') 2>/dev/null
sleep 2
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_medic.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/medic.log 2>&1 &
sleep 5
ps aux | grep neva_medic | grep -v grep
```

## История аварий
| Дата | Проблема | Решение |
|---|---|---|
| 2026-06-15 | Медик упал после 3/3 FAIL playbook, нет защиты | Установлен launchd KeepAlive + status_dot watchdog |
