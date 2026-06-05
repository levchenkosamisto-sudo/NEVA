# NEVA-TASK-007 — ЭТАП 1 УТВЕРЖДЁН
# Директор: Серж
# Дата утверждения: 2026-06-05
# Архитектор: Claude

---

## СТАТУС: ЭТАП 1 ✅ УТВЕРЖДЁН ДИРЕКТОРОМ

---

## ЧТО РЕАЛИЗОВАНО И РАБОТАЕТ

- Сервер FastAPI на порту 8000 ✅
- Kuzu embedded БД (neva.db) ✅
- Auth — токены NEVA_ADMIN_TOKEN + NEVA_AGENT_TOKEN ✅
- Topic Lock — SQLite coordinator ✅
- Write Queue — asyncio.Lock ✅
- API цепочка: HTTP → dispatcher → executor → Kuzu ✅
- P16 структура атома (валидация 8 полей) ✅
- Search endpoint (текстовый CONTAINS) ✅
- Health Monitor (Threshold Reactive Throttling) ✅
- Buffer Middleware (202 при недоступности) ✅
- Watchdog Install (launchd plist) ✅
- Self-test: 7/8 PASS, 0 FAIL ✅
- Git: коммит 2138c39 ✅

## РЕАЛЬНОЕ ПОКРЫТИЕ ЭТАПА 1

| Группа | Покрытие |
|---|---|
| C (координация, auth) | ~80% |
| D (мониторинг) | ~60% |
| E (Guardian/backup) | ~50% |
| A (память/граф) | ~40% |
| B (TTL/конфликты) | ~20% |

Среднее покрытие MVP: ~50–60%

---

## ЧТО ОТКРЫТО ДЛЯ ЭТАПА 2

- [ ] Подключить graphiti-core (не самописный класс)
- [ ] neva_langgraph_pipeline.py — реальная реализация
- [ ] e5-small embedding — семантический поиск
- [ ] TTL Policy — реальный (убрать MockGraph)
- [ ] Trust Engine — подключить к pipeline
- [ ] Session Manager — интегрировать
- [ ] Backup GDrive — убрать TODO
- [ ] K_truth — считать в реальном времени
- [ ] Guardian Hook — реальная индексация
- [ ] self-test backup SKIP → PASS
- [ ] MCP Executor интеграция (DRAFT в docs/)

---

## ПОСЛЕ ЭТАПА 2

- [ ] neva self-test 8/8 PASS
- [ ] Этап 3: MVP принят полностью
- [ ] Переиндексация всей NEVA по P16
- [ ] Старый neva_indexer.py удалён

---

## ФАЙЛЫ НА ДИСКЕ (~/Documents/NEVA/)

### ТЗ-1 (DeepSeek) — Core Infrastructure
neva_auth.py, neva_rate_limiter.py, neva_coordinator.py,
neva_write_queue.py, neva_conflict_resolver_basic.py,
neva_backup.py, neva_metrics_collector.py,
neva_init.py, schema_guard.py

### ТЗ-2 (Gemini/Claude) — Intelligence Layer
tools/neva_graphiti.py, neva_context_api.py,
neva_trust_engine.py (частично), neva_ttl_policy.py (заглушка),
neva_session_manager.py, neva_guardian_hook_install.py,
neva_export.py, neva_stats.py

### ТЗ-3 (Claude) — Operations Layer
neva_health_monitor.py, neva_buffer_retry.py,
neva_self_diagnostics.py, neva_watchdog_install.py,
neva_ollama_watchdog.py

### Dispatcher
dispatcher/dispatcher.py — HTTP → executor routing

### Tools
tools/mcp_executor/ — PENDING AUDIT (после Этапа 2)

---

## ЗАПУСК СИСТЕМЫ

```bash
cd ~/Documents/NEVA
NEVA_ADMIN_TOKEN=$(grep NEVA_ADMIN_TOKEN .env | cut -d'=' -f2) \
NEVA_AGENT_TOKEN=$(grep NEVA_AGENT_TOKEN .env | cut -d'=' -f2) \
python -m uvicorn neva_context_api:app --host 127.0.0.1 --port 8000 --workers 1
```

## SELF-TEST

```bash
cd ~/Documents/NEVA
NEVA_ADMIN_TOKEN=$(grep NEVA_ADMIN_TOKEN .env | cut -d'=' -f2) \
NEVA_AGENT_TOKEN=$(grep NEVA_AGENT_TOKEN .env | cut -d'=' -f2) \
python neva_self_diagnostics.py --self-test
```

Ожидание: 7/8 PASS, 0 FAIL
