# NEVA-TASK-007: UNIFIED FIELD v3.5
## Финальная архитектура. Готова к передаче исполнителям.

**Версия:** 3.5
**Дата:** 2026-06-04
**Статус:** НА ФИНАЛЬНОМ АУДИТЕ
**Заменяет:** v3.0
**Основание:** Инфраструктурный аудит GPT / DeepSeek-R2 / DeepSeek-2 + реальная диагностика Mac + Этап 0 пройден

> **ИЗМЕНЕНИЕ 2026-06-04 (Директор Серж):** Добавлен принцип P16 (Индексация всех документов NEVA).
> Правки внесены до финального аудита — аудиторы оценивают версию с P16.

---

## РАЗДЕЛ 0. ПРИНЦИПЫ-ИСТОЧНИКИ ИСТИНЫ

### ПРИНЦИП P15 — ИЕРАРХИЯ ХРАНИЛИЩ (IMMUTABLE)

```
P15. ИЕРАРХИЯ ХРАНИЛИЩ (IMMUTABLE):
  Kuzu (через Graphiti) = ИСТИНА оперативной памяти AI
  LangGraph SqliteSaver = ЖУРНАЛ выполнения pipeline
  neva_metrics.db      = ТЕЛЕМЕТРИЯ (K_truth история)
  cr-sqlite buffer     = ВРЕМЕННЫЙ буфер (offline)
  Git backup JSONL     = АРХИВ (для восстановления)
  Google Drive snapshot = БЫСТРОЕ ВОССТАНОВЛЕНИЕ

При любом расхождении → Kuzu выигрывает (для атомов памяти).
FalkorDB — ИСКЛЮЧЁН (нет нативной установки macOS ARM64 без Docker).
```

### ПРИНЦИП P16 — ИНДЕКСАЦИЯ ВСЕХ ДОКУМЕНТОВ NEVA (IMMUTABLE) ← НОВЫЙ v3.5

```
P16. ИНДЕКСАЦИЯ ДОКУМЕНТОВ (IMMUTABLE):

  ОДНА МОДЕЛЬ для всех документов NEVA (принцип стандартизации):
    - Движок: Graphiti
    - Embedding: intfloat/multilingual-e5-small (RU+EN)
    - Хранилище индекса: Kuzu (neva.db)

  ИЕРАРХИЯ ИСТИНЫ:
    - RAW файл (governance/, tz/, audits/, chats/, code/) = ИСТИНА 100%
    - Индекс (Kuzu атомы) = УКАЗАТЕЛЬ к RAW + семантический поиск
    - Целевая достоверность индекса: 95% (K_repro target, к чему стремимся)
    - Реальная достоверность e5-small: 0.76–0.84 (MTEB RU), минимум 0.70

  ЛОГИКА ИНДЕКСА:
    - Индекс — это путь к истинному RAW-документу, если документ существует
    - При наличии RAW: атом ведёт к файлу через source_path → открыть оригинал
    - При отсутствии RAW: атом = логический вывод (genealogy chain)

  ПРАВИЛО ЦИТИРОВАНИЯ:
    - Для точности — всегда открывать RAW по source_path
    - Индекс — для навигации и поиска, не для дословного цитирования

  ВСЕ документы NEVA должны быть проиндексированы этой моделью.
  Старый neva_indexer.py (Mistral API) — УДАЛЯЕТСЯ после переиндексации.

  Примечание: это НЕ второй источник истины. RAW = источник,
  индекс = производное. Индекс всегда перестраивается из RAW.
  RAW не восстанавливается из индекса. P15 не нарушается.
```

---

## РАЗДЕЛ 1. СТЕК v3.5 (ПОДТВЕРЖДЁН НА MAC, Этап 0)

```
Граф БД:         Kuzu embedded 0.11.3 (pip install kuzu) — файл neva.db
Knowledge graph: Graphiti (graphiti-core[kuzu] 0.29.1)
Pipeline:        LangGraph 1.2.4 + SqliteSaver (WAL mode)
Embedding:       intfloat/multilingual-e5-small (~230MB, скачана)
API:             FastAPI 0.136.3 + uvicorn 0.47.0 (workers=1)
Rate limiting:   slowapi 0.1.9
Scheduler:       APScheduler 3.11.2
Write sync:      asyncio.Lock() (neva_write_queue.py)
Topic Lock:      SQLite topic_locks (persistent, WAL)
```

### AI Router (финальный)

| Уровень | Провайдер | Ключ |
|---|---|---|
| PRIMARY | Gemini API | ✅ |
| SECONDARY | Cerebras gpt-oss-120b | ✅ |
| FAST | Groq | ✅ |
| BACKUP | DeepSeek (OpenRouter) | ✅ |
| FALLBACK | Mistral | ✅ |
| LOCAL-HEAVY | Ollama qwen2.5:7b | — |
| LOCAL-LIGHT | Ollama llama3.2:3b | — |
| EMERGENCY | keyword extraction | — |

### Memory Budget (реальные замеры Этапа 0)

| Компонент | Базовый | Пиковый (с Ollama) |
|---|---|---|
| Kuzu (embedded) | ~80MB | ~80MB |
| multilingual-e5-small | ~230MB | ~230MB |
| Graphiti + FastAPI | ~280MB | ~280MB |
| LangGraph + SqliteSaver | ~130MB | ~130MB |
| cr-sqlite + session | ~50MB | ~50MB |
| **NEVA stack (РЕАЛЬНО Этап 0)** | **~446MB** ✅ | **~446MB** |
| qwen2.5:7b (Ollama) | — | ~4.7GB |

Baseline реально ~446MB (прогноз был 770MB — лучше на 40%).

---

## РАЗДЕЛ 2. ФОРМУЛЫ И КОНТРАКТЫ (ЗАФИКСИРОВАНЫ)

### K_truth — точная формула

```python
TRUST_WEIGHTS = {
    "director_approved": 0.95,
    "guardian_hook":     0.88,
    "gemini":            0.82,
    "cerebras":          0.82,
    "groq":              0.80,
    "llama":             0.65,
    "keyword":           0.55,
    "unknown":           0.60,
}

def calculate_k_truth(active_facts: list[dict]) -> float:
    if not active_facts:
        return 0.0
    weights = [TRUST_WEIGHTS.get(f.get("author_ai","unknown"), 0.60)
               for f in active_facts]
    return round(sum(weights) / len(weights), 3)

def confidence_update(author_ai: str, verified: bool) -> None:
    delta = +0.02 if verified else -0.03
    new_weight = max(0.50, min(0.95,
        TRUST_WEIGHTS.get(author_ai, 0.60) + delta))
    TRUST_WEIGHTS[author_ai] = new_weight
```

### Атом документа — поля для индексации (P16) ← НОВОЕ v3.5

```python
# Каждый атом, извлечённый из документа NEVA, обязан содержать:
{
    "content": str,            # извлечённый факт/атом
    "author_ai": str,          # источник
    "source_path": str,        # ПУТЬ К RAW: "governance/NEVA-TASK-007-v3.5.md"
    "doc_id": str,             # "NEVA-TASK-007"
    "doc_version": str,        # "3.5"
    "sha256": str,             # хеш RAW файла (проверка целостности)
    "indexed_at": str,         # UTC ISO
    "atom_type": str,          # FACT/DECISION/RULE/TASK/CONFLICT/COMPONENT
}
# source_path обязателен если атом извлечён из существующего файла.
# Если атом = логический вывод (нет RAW) → source_path = null, genealogy заполнен.
```

### Topic Lock — SQLite persistent

```sql
CREATE TABLE IF NOT EXISTS topic_locks (
    topic      TEXT PRIMARY KEY,
    locked_by  TEXT NOT NULL,
    session_id TEXT NOT NULL,
    locked_at  TEXT NOT NULL,
    expires_at TEXT NOT NULL  -- UTC ISO, +30 секунд
);
CREATE INDEX IF NOT EXISTS idx_locks_expires ON topic_locks(expires_at);
-- Cleanup: DELETE WHERE expires_at < strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
```

### Write Queue

```python
_write_lock = asyncio.Lock()
_write_counter = 0

async def write_to_graph(operation, *args, **kwargs):
    global _write_counter
    async with _write_lock:
        _write_counter += 1
        result = operation(*args, **kwargs)
        import inspect
        if inspect.isawaitable(result):
            return await result
        return result
```

### Двойной Backup

| Что | Куда | Когда |
|---|---|---|
| JSONL delta | Git | каждые 6 часов |
| Kuzu snapshot | Google Drive | каждые 24 часа |

Восстановление: snapshot (секунды) + донакат delta (минуты). Потеря max 6 часов.

### TTL Policy

```python
TTL_RULES = {
    "FACT":      timedelta(days=30),
    "DECISION":  timedelta(days=90),
    "RULE":      timedelta(days=365),
    "TASK":      timedelta(days=7),
    "CONFLICT":  timedelta(days=14),
    "COMPONENT": None,  # вечно
}
```

### KuzuDriver — синтаксис

```python
driver = KuzuDriver(db='./neva.db')   # параметр db=
driver.setup_schema()                  # НЕ async
await driver.build_indices_and_constraints()  # async
await driver.execute_query(...)        # async
await driver.close()                   # async
```

---

## РАЗДЕЛ 3. РАСПРЕДЕЛЕНИЕ ТЗ

### ТЗ-1 → DeepSeek (Core Infrastructure)
neva_auth.py, neva_rate_limiter.py, neva_coordinator.py, neva_write_queue.py,
neva_conflict_resolver_basic.py, neva_backup.py, neva_metrics_collector.py,
neva_init.py (← импорт governance + source_path по P16), schema_guard.py

### ТЗ-2 → Gemini (Intelligence Layer)
neva_graphiti.py, neva_langgraph_pipeline.py, neva_trust_engine.py,
neva_ttl_policy.py, neva_context_api.py (← + endpoints document/search по P16),
neva_session_manager.py, neva_guardian_hook_install.py, neva_export.py, neva_stats.py

### ТЗ-3 → GPT (Operations Layer)
neva_health_monitor.py, neva_self_diagnostics.py, neva_cli.py,
neva_buffer_retry.py (Middleware), neva_ollama_watchdog.py,
neva_watchdog_install.py, .env.example

---

## РАЗДЕЛ 4. ПЛАН ПЕРЕИНДЕКСАЦИИ (P16) ← НОВОЕ v3.5

```
ПЕРЕИНДЕКСАЦИЯ ВСЕЙ NEVA (после разработки модулей):

1. neva_init.py --import-governance   # все документы governance/
2. neva_init.py --import-all          # все папки: tz/, audits/, chats/, code/, docs/
3. Каждый атом получает source_path + doc_id + sha256 (P16)
4. Проверить K_repro ≥ 0.70 на контрольной выборке документов
5. Сверить: каждый RAW документ → находится через /api/v1/search
6. Удалить старый neva_indexer.py + index/semantic_index.json
7. Удалить старые *_INDEX.json и *_INDEX.docx (заменены Graphiti)
8. Зафиксировать DECISION атом: "Переиндексация NEVA по P16 завершена"

КРИТЕРИЙ УСПЕХА:
- Любой документ NEVA находится через семантический поиск
- Каждый найденный атом ведёт к RAW через source_path
- K_repro ≥ 0.70 (цель 0.95)
- Один индекс, одна модель (стандартизация выполнена)
```

---

## РАЗДЕЛ 5. ПОКРЫТИЕ 23 ЗАДАЧ v3.5

| ID | Задача | Покрытие | Механизм |
|---|---|---|---|
| A1 | Единое состояние | 95% | Kuzu=истина (P15) + Topic Lock |
| A2 | Атомарная память | 95% | Graphiti bi-temporal + TTL + DELETE=405 |
| A3 | Воспроизводимый контекст | 85% | RRF + e5-small + reindex + P16 source_path |
| A4 | K_truth | 85% | формула + confidence_update |
| A5 | Диалог через состояние | 95% | MCP + /api/v1/ |
| B1 | TTL Policy | 100% | APScheduler |
| B2 | Conflict Resolver | 60% MVP | similarity>0.85 |
| B3 | Genealogy | 50% | LangGraph trace + P16 (атом без RAW = вывод) |
| B4 | Audit Trail | 95% | author_ai + source_path + session_id + timestamp |
| C1 | Авторизация | 95% | API токены |
| C2 | Координация | 90% | SQLite topic_locks |
| C3 | Передача контекста | 80% | start_session |
| C4 | Rate Limiting | 95% | slowapi |
| D1 | Health Dashboard | 75% | CLI + /api/v1/health |
| D2 | История K_truth | 95% | SQLite time-series |
| D3 | Статистика | 90% | /api/v1/stats |
| D4 | Трендовый мониторинг | 80% | sliding window |
| E1 | Guardian Hook | 90% | post-commit |
| E2 | Импорт governance | 85% | neva_init.py + P16 индексация |
| E3 | Backup | 95% | двойной |
| E4 | Экспорт | 85% | SHA256 |
| F1 | atom_edges | Этап 2 | — |
| F2 | Community subgraph | Этап 2 | — |

**Среднее покрытие MVP: 87%**

---

## РАЗДЕЛ 6. МЕТРИКИ

### Качество
| Метрика | Цель | Минимум |
|---|---|---|
| K_consistency | < 2% | < 5% |
| K_truth (online) | 0.75–0.83 | ≥ 0.70 |
| K_truth (llama offline) | 0.60–0.68 | ≥ 0.55 |
| K_repro (индекс P16) | 0.76–0.84 (цель 0.95) | ≥ 0.70 |

### Производительность
| Метрика | Цель | Минимум |
|---|---|---|
| K_latency /api/v1/state | < 3s | < 5s |
| K_throughput | 2–8 атомов/с | ≥ 1/с |
| K_compression | 4x–8x | ≥ 2x |

### Ресурсы M1 8GB (Этап 0)
| Метрика | Расчётное | Реально | Лимит |
|---|---|---|---|
| RAM baseline | ~770MB | ~446MB ✅ | < 1GB |
| RAM peak (Ollama) | ~4.2GB | не замерен | < 6GB |
| Backup restore | 100% | 20/20 ✅ | 100% |

---

## РАЗДЕЛ 7. РЕЗУЛЬТАТЫ ЭТАПА 0

| Тест | Результат |
|---|---|
| Kuzu ARM64 | ✅ работает |
| Graphiti + Kuzu совместимость | ✅ schema + индексы |
| 10 параллельных записей | ✅ все 10 без ошибок |
| RAM baseline | ✅ ~446MB |
| Backup restore 20/20 | ✅ совпадает |
| Cerebras structured_output | ✅ gpt-oss-120b работает |

---

## СТАТУС ДОКУМЕНТА

```
[ ] Финальный аудит v3.5 + P16 (Gemini, GPT, DeepSeek)
[ ] Три УТВЕРЖДАЮ / УСЛОВНО УТВЕРЖДАЮ
[ ] Утверждён Директором (Серж)
═══ РАЗРАБОТКА ═══
[ ] ТЗ-1 v3.5 → DeepSeek
[ ] ТЗ-2 v3.5 → Gemini
[ ] ТЗ-3 v3.5 → GPT
[ ] Этап 1 завершён
[ ] Этап 2: neva self-test 8/8
[ ] Этап 3: MVP принят
═══ ПЕРЕИНДЕКСАЦИЯ (P16) ═══
[ ] Вся NEVA переиндексирована одной моделью
[ ] Старый neva_indexer.py удалён
[ ] Guardian → governance/
```
