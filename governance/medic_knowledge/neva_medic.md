# NEVA Medic Knowledge — NEVA Medic сам
# Версия: 1.0 | Дата: 2026-06-15 | Архитектор: Claude

## Назначение
neva_medic.py v3.8 — L1 авторемонт системы NEVA.
Цикл heal каждую минуту. AI-диагностика + playbook исполнение. knowledge base v4.0.
Файл: ~/Documents/NEVA_MCP_BRIDGE/neva_medic.py
Лог: ~/Documents/NEVA_MCP_BRIDGE/logs/medic.log
Статус: PROD (критический — без него 0 авторемонта)

## АРХИТЕКТУРА
```
neva_medic.py heal_cycle() (каждую 60с)
  ├─ mcp_check_reply()      ← читает ответ Claude из :9000/claude_reply
  ├─ detect_problems()     ← проверяет все компоненты
  ├─ ai_diagnose()         ← FlagmanRouter (Cerebras→Groq→OpenRouter)
  ├─ load_knowledge()      ← читает medic_knowledge/*.md
  ├─ run_playbook()        ← выполняет bash команды
  ├─ incident_log_write()  ← пишет state/incident_log.json
  └─ push_event()          ← отправляет событие в MCP сервер
```

## Запуск
```bash
# Login Items (LaunchAgent) — основной
# Fallback вручной:
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_medic.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/medic.log 2>&1 &
```

## Диагностика
```bash
# Живой ли:
ps aux | grep neva_medic | grep -v grep
# Лог свежий если mtime < 120с:
stat -f %m ~/Documents/NEVA_MCP_BRIDGE/logs/medic.log
# Последние события:
tail -20 ~/Documents/NEVA_MCP_BRIDGE/logs/medic.log
# Самотест:
/Users/arka/Documents/NEVA/.venv/bin/python3 \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_medic.py --self-test
```

## Известные проблемы

### medic_not_running — медик упал
Причина A: упал после неудачного playbook (3/3 FAIL)
Причина B: исчерпан цикл рестартов Login Items
Причина C: exception в heal_cycle без перехвата ошибки
Решение: nohup запуск (см. выше)

### medic_knowledge_stale — книга знаний не загружается
Причина: файл не найден в medic_knowledge/
Решение: проверить путь ~/Documents/NEVA/governance/medic_knowledge/

### medic_ai_all_fail — все AI провайдеры недоступны
Причина: Cerebras/Groq/OpenRouter — все 403/429/timeout
Действие: медик работает но conf=0 — AI диагноз недоступен, playbook не запускается
Решение: проверить API ключи в .env, обновить при необходимости

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
| 2026-06-15 | Медик упал после 3/3 FAIL restart_mcp_server_net | nohup запуск вручную |
