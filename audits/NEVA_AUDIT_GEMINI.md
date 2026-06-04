# ЗАПРОС НА АУДИТ: NEVA-TASK-007 v3.5
## Аудитор: Gemini
## Дата: 2026-06-04

---

## ТВОЯ РОЛЬ

Ты — независимый технический аудитор архитектурного документа системы NEVA v3.5.
Система NEVA — это unified knowledge field для AI-агентов (Claude, GPT, Gemini, DeepSeek),
работающая на MacBook Air M1 8GB RAM.

**ВАЖНО:** Это финальный аудит перед передачей ТЗ разработчикам.
Предыдущие аудиторы: DeepSeek-R2 (УТВЕРЖДАЮ ✅), DeepSeek-2 (УТВЕРЖДАЮ ✅).
GPT дал условное одобрение — все его замечания уже внесены в v3.5.
Твой аудит v3.5 ещё не проводился.

---

## ИНСТРУКЦИЯ — ДВА ЭТАПА

### ЭТАП 1 — СНАЧАЛА ЗАДАЙ ВОПРОСЫ
Перед вынесением вердикта:
1. Задай все вопросы по неясным или недостаточно описанным местам
2. Укажи что отсутствует в документе для полноценного аудита
3. Назови противоречия которые ты видишь
4. Только после получения ответов переходи к Этапу 2

### ЭТАП 2 — АУДИТ И ВЕРДИКТ
После ответов на вопросы:
- Вынеси вердикт: **УТВЕРЖДАЮ** / **УСЛОВНО УТВЕРЖДАЮ** / **ОТКЛОНЯЮ**
- Если УСЛОВНО — перечисли конкретные условия (не более 5)
- Оцени риски по каждому блоку A–E
- Подтверди или оспорь результаты Этапа 0

---

## ЖЕЛЕЗО И ОКРУЖЕНИЕ

- MacBook Air M1 8GB RAM, 228GB SSD, свободно ~36GB
- macOS, пользователь: arka (основной)
- Python venv: ~/Documents/NEVA/venv/
- Google Drive смонтирован: ~/Library/CloudStorage/GoogleDrive-levchenkosamisto@gmail.com/

---

## УСТАНОВЛЕННЫЕ ПАКЕТЫ (подтверждено)

```
kuzu 0.11.3
graphiti-core 0.29.1
langgraph 1.2.4
langchain-core 1.4.0
sentence-transformers 5.5.1
fastapi 0.136.3
uvicorn 0.47.0
slowapi 0.1.9
apscheduler 3.11.2
pydantic 2.13.4
httpx 0.28.1
cerebras-cloud-sdk 1.67.0
psutil
```

---

## РЕЗУЛЬТАТЫ ЭТАПА 0 (РЕАЛЬНЫЕ ЗАМЕРЫ НА MAC)

Все тесты выполнены на реальном железе Директора:

| Тест | Результат |
|---|---|
| Kuzu ARM64 нативный wheel | ✅ работает |
| Graphiti + Kuzu совместимость | ✅ schema + индексы созданы |
| 10 параллельных записей (write_queue) | ✅ все 10 без ошибок, нет database locked |
| RAM baseline (без Ollama) | ✅ ~446MB (прогноз был 770MB — на 40% лучше) |
| Backup restore 20/20 | ✅ export→delete→restore, количество фактов совпадает |
| Cerebras structured_output | ✅ gpt-oss-120b работает корректно |

**Что НЕ замерено в Этапе 0:**
- RAM peak с qwen2.5:7b активным (прогноз ~4.2GB)
- MTTR при сбое Kuzu (прогноз ~10с)
- Pipeline resume с шага N при crash

---

## АРХИТЕКТУРНЫЙ МАНИФЕСТ NEVA-TASK-007 v3.5

### ПРИНЦИП P15 — ИЕРАРХИЯ ХРАНИЛИЩ (IMMUTABLE)

```
Kuzu (через Graphiti) = ИСТИНА (единственный источник для атомов памяти)
LangGraph SqliteSaver = ЖУРНАЛ выполнения pipeline
neva_metrics.db       = ТЕЛЕМЕТРИЯ (K_truth история)
cr-sqlite buffer      = ВРЕМЕННЫЙ буфер (при offline)
Git backup JSONL      = АРХИВ (инкрементальный)
Google Drive snapshot = БЫСТРОЕ ВОССТАНОВЛЕНИЕ

При любом расхождении → Kuzu выигрывает.
FalkorDB — ИСКЛЮЧЁН (нет нативной установки macOS ARM64 без Docker).
```

### ПРИНЦИП P16 — ИНДЕКСАЦИЯ ВСЕХ ДОКУМЕНТОВ (IMMUTABLE) ← НОВЫЙ v3.5

```
ОДНА МОДЕЛЬ для всех документов NEVA (стандартизация):
  Движок: Graphiti | Embedding: multilingual-e5-small | Хранилище: Kuzu

ИЕРАРХИЯ ИСТИНЫ:
  RAW файл (governance/, tz/, audits/, chats/, code/) = ИСТИНА 100%
  Индекс (Kuzu атомы) = УКАЗАТЕЛЬ к RAW + семантический поиск
  Цель достоверности: 95% (K_repro target), реально e5-small 0.76–0.84

ЛОГИКА:
  Индекс — путь к истинному RAW-документу (если есть), иначе логический вывод.
  Каждый атом хранит source_path → путь к RAW.
  Для точности — открывать RAW. Индекс — для навигации/поиска.

Это НЕ второй источник истины: RAW = источник, индекс = производное.
Индекс перестраивается из RAW. P15 не нарушается.
Старый neva_indexer.py (Mistral) удаляется после переиндексации.
```

**ВОПРОС К АУДИТОРУ ПО P16:** Согласен ли ты что схема "RAW=истина 100%, Graphiti-индекс=производное с source_path" НЕ создаёт второй источник истины и не нарушает P15? Видишь ли риски в единой модели индексации e5-small для всех документов (включая .docx)?

---

### СТЕК v3.5

| Компонент | Решение | Причина |
|---|---|---|
| Граф БД | Kuzu embedded (pip install kuzu) | ARM64 нативный, нет Docker/VM |
| Knowledge graph API | Graphiti (graphiti-core[kuzu] 0.29.1) | bi-temporal, совместим с Kuzu |
| Pipeline | LangGraph + SqliteSaver (WAL mode) | checkpoint + resume |
| Embedding | intfloat/multilingual-e5-small (~230MB) | уже скачана, RU+EN |
| API | FastAPI + uvicorn (workers=1) | workers=1 из-за asyncio.Lock |
| Rate limiting | slowapi | per agent_id |
| Scheduler | APScheduler | TTL + backup расписание |
| Write sync | asyncio.Lock() в neva_write_queue.py | Kuzu не поддерживает параллельную запись |
| Topic Lock | SQLite topic_locks (persistent) | переживает restart |

**AI Router:**
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

---

### КЛЮЧЕВЫЕ КОНТРАКТЫ

#### K_truth формула (зафиксирована)

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

#### Topic Lock (SQLite persistent)

```sql
CREATE TABLE IF NOT EXISTS topic_locks (
    topic      TEXT PRIMARY KEY,
    locked_by  TEXT NOT NULL,
    session_id TEXT NOT NULL,
    locked_at  TEXT NOT NULL,
    expires_at TEXT NOT NULL  -- UTC ISO, +30 секунд
);
-- Cleanup: DELETE WHERE expires_at < strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
```

#### Write Queue

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

#### Двойной Backup

| Что | Куда | Когда |
|---|---|---|
| JSONL delta (факты) | Git репозиторий | каждые 6 часов |
| Kuzu snapshot (бинарный) | Google Drive | каждые 24 часа |

Восстановление: snapshot (секунды) + донакат delta (минуты). Потеря max 6 часов.

#### TTL Policy

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

#### LangGraph Pipeline

```python
_pipeline_semaphore = asyncio.Semaphore(3)  # max 3 параллельных

async def run_pipeline(state):
    async with _pipeline_semaphore:
        if not await coordinator.acquire(state["topic"], ...):
            raise HTTPException(409, {"error": "topic_locked", "retry_after": 5})
        try:
            return await app.ainvoke(state)
        finally:
            await coordinator.release(state["topic"], state["author_ai"])
```

#### Embedding Fallback (при OOM)

```python
async def load_embedder():
    try:
        return SentenceTransformerEmbedder("intfloat/multilingual-e5-small")
    except MemoryError:
        return GeminiEmbedder()  # API fallback, 0 RAM
```

---

### РАСПРЕДЕЛЕНИЕ ТЗ

**ТЗ-1 → DeepSeek:**
neva_auth.py, neva_rate_limiter.py, neva_coordinator.py (Topic Lock),
neva_write_queue.py, neva_conflict_resolver_basic.py, neva_backup.py
(двойной backup), neva_metrics_collector.py, neva_init.py, schema_guard.py

**ТЗ-2 → Gemini:**
neva_graphiti.py (KuzuDriver wrapper), neva_langgraph_pipeline.py,
neva_trust_engine.py (K_truth), neva_ttl_policy.py (APScheduler),
neva_context_api.py (/api/v1/*), neva_session_manager.py,
neva_guardian_hook_install.py, neva_export.py (SHA256), neva_stats.py

**ТЗ-3 → GPT:**
neva_health_monitor.py, neva_self_diagnostics.py, neva_cli.py,
neva_buffer_retry.py (FastAPI Middleware), neva_ollama_watchdog.py,
neva_watchdog_install.py (launchd), .env.example

---

## 23 ЗАДАЧИ — ЦЕЛЕВОЕ ПОКРЫТИЕ v3.5

### Блок A — Пять базовых свойств
| ID | Задача | Покрытие | Механизм |
|---|---|---|---|
| A1 | Единое состояние знаний | 95% | Kuzu=истина (P15) + SQLite Topic Lock |
| A2 | Атомарная управляемая память | 95% | Graphiti bi-temporal + TTL + DELETE=405 |
| A3 | Воспроизводимый контекст | 85% | RRF + multilingual-e5-small + reindex |
| A4 | Измеримая достоверность (K_truth) | 85% | Взвешенная формула + confidence_update |
| A5 | Диалог через состояние | 95% | MCP (Claude Desktop) + REST /api/v1/ |

### Блок B — Жизненный цикл знаний
| ID | Задача | Покрытие | Механизм |
|---|---|---|---|
| B1 | TTL Policy | 100% | APScheduler: FACT=30д, DECISION=90д, RULE=365д |
| B2 | Conflict Resolver | 60% (MVP) | similarity>0.85; atom_edges → Этап 2 |
| B3 | Genealogy | 50% | LangGraph trace; multi-hop → Этап 2 |
| B4 | Audit Trail | 95% | author_ai + source + model_used + session_id + timestamp |

### Блок C — Управление агентами
| ID | Задача | Покрытие | Механизм |
|---|---|---|---|
| C1 | Авторизация агентов | 95% | API токены, права read_write/read_only/admin |
| C2 | Координация параллельных агентов | 90% | SQLite topic_locks + expires_at=30с |
| C3 | Передача контекста между сессиями | 80% | start_session(agent_id, topic) |
| C4 | Rate Limiting | 95% | slowapi per agent_id: 30/мин write, 10/мин extract |

### Блок D — Наблюдаемость
| ID | Задача | Покрытие | Механизм |
|---|---|---|---|
| D1 | Health Dashboard | 75% | CLI + /api/v1/health |
| D2 | История K_truth | 95% | SQLite time-series каждые 5 мин |
| D3 | Статистика агентов | 90% | /api/v1/stats |
| D4 | Трендовый мониторинг | 80% | sliding window 1ч, линейная предикция |

### Блок E — Интеграция
| ID | Задача | Покрытие | Механизм |
|---|---|---|---|
| E1 | Guardian Hook | 90% | post-commit → POST /api/v1/extract |
| E2 | Импорт governance/* | 85% | neva_init.py --import-governance |
| E3 | Backup | 95% | JSONL delta→Git 6ч + snapshot→GDrive 24ч |
| E4 | Экспорт для аудиторов | 85% | /api/v1/export + SHA256 |

### Блок F — Этап 2 (не в MVP)
| ID | Задача | Статус |
|---|---|---|
| F1 | atom_edges search (multi-hop) | Этап 2 |
| F2 | Community subgraph (K_compression 6x-8x) | Этап 2 |

**Среднее покрытие MVP (A1–E4): 87%**

---

## ЦЕЛЕВЫЕ МЕТРИКИ

### Качество знаний
| Метрика | Цель | Минимум |
|---|---|---|
| K_consistency | < 2% | < 5% |
| K_truth (Gemini/Cerebras online) | 0.75–0.83 | ≥ 0.70 |
| K_truth (llama offline) | 0.60–0.68 | ≥ 0.55 |
| K_repro | 0.76–0.84 | ≥ 0.70 |

### Производительность
| Метрика | Цель | Минимум |
|---|---|---|
| K_compression | 4x–8x | ≥ 2x |
| K_latency /api/v1/state | < 3s | < 5s |
| K_throughput | 2–8 атомов/с | ≥ 1/с |

### Ресурсы M1 8GB
| Метрика | Расчётное | Реально (Этап 0) | Лимит |
|---|---|---|---|
| RAM baseline (без Ollama) | ~770MB | **~446MB** ✅ | < 1GB |
| RAM peak (с qwen2.5:7b) | ~4.2GB | не замерен | < 6GB |
| Backup restore | 100% | **100% (20/20)** ✅ | 100% |

### Отказоустойчивость
| Сценарий | Поведение |
|---|---|
| Graphiti недоступен | Buffer Middleware → 202 Accepted → cr-sqlite буфер |
| Gemini rate limit | Автофallback: Cerebras → Groq → DeepSeek → Mistral |
| Ollama OOM | KEEP_ALIVE=1m → выгружается, reload при следующем запросе |
| Mac выключился | GDrive snapshot + Git JSONL → restore за минуты |
| SSD < 20GB | Health Monitor алерт Директору |

---

## ИСТОРИЯ АУДИТОВ (для контекста)

- v1.0 → аудит → v1.1 → аудит → v2.0
- v2.0 → аудит 4 экспертов → v3.0
- v3.0 → инфраструктурный аудит → v3.1 (Kuzu вместо FalkorDB+Docker)
- v3.1 → v3.2 → v3.3 → v3.4 → v3.5
- Итого замечаний закрыто: 55+
- Этап 0: пройден полностью на реальном Mac

---

## КРИТЕРИЙ УТВЕРЖДЕНИЯ

Документ считается утверждённым когда:
- Три независимых аудитора дали УТВЕРЖДАЮ или УСЛОВНО УТВЕРЖДАЮ
- Все условия из УСЛОВНО выполнены
- Результаты Этапа 0 приняты как доказательство работоспособности стека

**Текущий статус:**
- DeepSeek-R2: УТВЕРЖДАЮ ✅
- DeepSeek-2: УТВЕРЖДАЮ ✅
- GPT: условно (замечания внесены в v3.5)
- **Gemini: твой вердикт ← ожидается**

---

## НАЧНИ С ЭТАПА 1 — ЗАДАЙ ВОПРОСЫ

Что неясно? Чего не хватает для полного аудита? Какие противоречия видишь?
