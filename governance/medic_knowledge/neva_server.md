# NEVA Medic Knowledge — NEVA Context API (Server)
# Версия: 1.0 | Дата: 2026-06-15 | Архитектор: Claude

## Назначение
neva_context_api.py v1 — NEVA сервер памяти (Kuzu + FastAPI).
Порт: 8000. P16 структура атома. Токен аутентификация.
Файл: ~/Documents/NEVA/neva_context_api.py
БД: ~/Documents/NEVA/neva.db (файл Kuzu)
Лог: ~/Documents/NEVA/logs/ (если есть)
Статус: PROD (ТАСК-007 Этап 1 утверждён)

## Запуск
```bash
cd ~/Documents/NEVA
NEVA_ADMIN_TOKEN=$(grep NEVA_ADMIN_TOKEN .env | cut -d'=' -f2) \
NEVA_AGENT_TOKEN=$(grep NEVA_AGENT_TOKEN .env | cut -d'=' -f2) \
/Users/arka/Documents/NEVA/.venv/bin/python3 -m uvicorn \
  neva_context_api:app --host 127.0.0.1 --port 8000 --workers 1
```

## Диагностика
```bash
# Живой ли:
ps aux | grep neva_context_api | grep -v grep
# HTTP health:
curl -s http://127.0.0.1:8000/health
# Порт слушает:
lsof -i :8000 | head -3
```

## Известные проблемы

### neva_server_not_running — сервер не отвечает
Причина A: не запущен после ребута
Причина B: Кузу-БД заблокирована (захвачен несколькими процессами сразу)
Причина C: неверный токен в .env
Диагностика: curl :8000/health → lsof -i :8000 → grep .env
Решение: запустить (см. выше)

### neva_server_kuzu_lock — БД заблокирована
Причина: Kuzu не поддерживает множественных writers
Решение: kill все процессы на :8000, запустить один --workers 1
Предупреждение: НИКОГДА не запускать с --workers > 1

## Playbook: restart_neva_server
```bash
kill $(lsof -ti :8000 2>/dev/null) 2>/dev/null
sleep 2
cd ~/Documents/NEVA
NEVA_ADMIN_TOKEN=$(grep NEVA_ADMIN_TOKEN .env | cut -d'=' -f2) \
NEVA_AGENT_TOKEN=$(grep NEVA_AGENT_TOKEN .env | cut -d'=' -f2) \
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -m uvicorn \
  neva_context_api:app --host 127.0.0.1 --port 8000 --workers 1 \
  >> ~/Documents/NEVA/logs/neva_server.log 2>&1 &
sleep 4
curl -s http://127.0.0.1:8000/health
```

## Самотест
```bash
cd ~/Documents/NEVA
NEVA_ADMIN_TOKEN=$(grep NEVA_ADMIN_TOKEN .env | cut -d'=' -f2) \
NEVA_AGENT_TOKEN=$(grep NEVA_AGENT_TOKEN .env | cut -d'=' -f2) \
/Users/arka/Documents/NEVA/.venv/bin/python3 neva_self_diagnostics.py --self-test
# Ожидание: 7/8 PASS, 0 FAIL
```
