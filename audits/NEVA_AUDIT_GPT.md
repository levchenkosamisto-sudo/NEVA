# ЗАПРОС НА АУДИТ: NEVA-TASK-007 v3.5
## Аудитор: GPT
## Дата: 2026-06-04

---

## ТВОЯ РОЛЬ

Ты — независимый технический аудитор архитектурного документа системы NEVA v3.5.
Система NEVA — это unified knowledge field для AI-агентов (Claude, GPT, Gemini, DeepSeek),
работающая на MacBook Air M1 8GB RAM.

**КОНТЕКСТ:** В предыдущих раундах аудита ты (GPT) дал 13 замечаний по v3.2, 12 по v3.3,
и условное одобрение по v3.4. Все твои замечания были приняты и внесены в v3.5.
Это финальный аудит — подтверди что v3.5 закрывает все твои предыдущие замечания,
и вынеси итоговый вердикт.

---

## ИНСТРУКЦИЯ — ДВА ЭТАПА

### ЭТАП 1 — СНАЧАЛА ЗАДАЙ ВОПРОСЫ
Перед вынесением вердикта:
1. Задай все вопросы по неясным или недостаточно описанным местам
2. Укажи что отсутствует в документе для полноценного аудита
3. Проверь — все ли твои предыдущие замечания закрыты корректно
4. Только после получения ответов переходи к Этапу 2

### ЭТАП 2 — АУДИТ И ВЕРДИКТ
После ответов на вопросы:
- Вынеси вердикт: **УТВЕРЖДАЮ** / **УСЛОВНО УТВЕРЖДАЮ** / **ОТКЛОНЯЮ**
- Если УСЛОВНО — не более 3 конкретных условий (предыдущие уже закрыты)
- Подтверди что результаты Этапа 0 достаточны как доказательство

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

| Тест | Результат |
|---|---|
| Kuzu ARM64 нативный wheel | ✅ работает |
| Graphiti + Kuzu совместимость | ✅ schema + индексы созданы |
| 10 параллельных записей (write_queue) | ✅ все 10 без ошибок |
| RAM baseline (без Ollama) | ✅ ~446MB (прогноз 770MB — лучше на 40%) |
| Backup restore 20/20 | ✅ export→delete→restore совпадает |
| Cerebras structured_output | ✅ gpt-oss-120b работает |

**Что НЕ замерено:**
- RAM peak с qwen2.5:7b (прогноз ~4.2GB)
- MTTR при сбое Kuzu (прогноз ~10с)
- Pipeline resume с шага N при crash

---

## ЧТО ИЗМЕНИЛОСЬ В v3.5 ПОСЛЕ ТВОИХ ЗАМЕЧАНИЙ

Ниже список твоих ключевых замечаний и как они закрыты:

| Замечание (от GPT) | Закрытие в v3.5 |
|---|---|
| write_queue: Queue не используется | Убрана, оставлен только asyncio.Lock() |
| Проверка перед удалением sergey/.ollama | Добавлена проверка + подтверждение |
| не нужен в venv | Убран из всех команд |
| Стресс-тест Kuzu отсутствует | test_kuzu_concurrency.py добавлен в Этап 0 |
| Health Monitor: нет алерта SSD < 20GB | Добавлен disk_free_alert |
| Graphiti MCP + Kuzu совместимость не подтверждена | Тест добавлен в Этап 0, пройден ✅ |
| Cohere не подходит для extraction | Cohere убран из Router |
| Plan деградации embedding не описан | Fallback на GeminiEmbedder при MemoryError |
| P15 упоминает FalkorDB | P15 переписан: только Kuzu |
| docker-compose.yml содержит FalkorDB | docker-compose.yml убран из ТЗ-3 |
| test_kuzu: один Connection на всех | Каждый поток — свой Connection |
| write_to_graph: await обычной функции | asyncio.to_thread() добавлен |
| expires_at: разные форматы datetime | Унифицирован UTC ISO |
| Buffer: должен быть Middleware | NEVABufferMiddleware реализован как FastAPI Middleware |

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
```

### ПРИНЦИП P16 — ИНДЕКСАЦИЯ ВСЕХ ДОКУМЕНТОВ (IMMUTABLE) ← НОВЫЙ v3.5

```
ОДНА МОДЕЛЬ для всех документов NEVA (стандартизация):
  Graphiti + multilingual-e5-small + Kuzu

RAW файл = ИСТИНА 100% | Индекс (атомы) = УКАЗАТЕЛЬ к RAW + поиск
Каждый атом хранит source_path → путь к RAW.
Цель: 95% (K_repro), реально e5-small 0.76–0.84.
Индекс — путь к истинному документу, если есть; иначе логический вывод.
НЕ второй источник истины: RAW=источник, индекс=производное (перестраивается из RAW).
Старый neva_indexer.py (Mistral) удаляется после переиндексации.
```

**ВОПРОС К АУДИТОРУ ПО P16:** Ты ранее резал "два источника истины" (Отказ I в v3.3 — SQLite Facts Store рядом с Kuzu). Подтверди: схема "RAW-файлы + Graphiti-индекс с source_path" — это НЕ повтор той проблемы, т.к. RAW и индекс в иерархии (источник→производное), а не два равноправных источника?

---

### СТЕК v3.5

| Компонент | Решение | Причина |
|---|---|---|
| Граф БД | Kuzu embedded | ARM64 нативный, нет Docker |
| Knowledge graph API | Graphiti 0.29.1 | bi-temporal, совместим с Kuzu |
| Pipeline | LangGraph + SqliteSaver WAL | checkpoint + resume |
| Embedding | multilingual-e5-small | уже скачана, RU+EN |
| API | FastAPI + uvicorn workers=1 | workers=1 из-за asyncio.Lock |
| Rate limiting | slowapi | per agent_id |
| Scheduler | APScheduler | TTL + backup |
| Write sync | asyncio.Lock() | Kuzu single-writer |
| Topic Lock | SQLite persistent | переживает restart |

---

### КЛЮЧЕВЫЕ КОНТРАКТЫ

#### K_truth формула

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
K_truth = sum(weights) / count(active_facts)
confidence_update(): verified → +0.02, не verified → -0.03
```

#### Write Queue (исправлен по замечанию GPT)

```python
_write_lock = asyncio.Lock()  # Queue убрана

async def write_to_graph(operation, *args, **kwargs):
    async with _write_lock:
        result = operation(*args, **kwargs)
        import inspect
        if inspect.isawaitable(result):
            return await result
        return result
# Sync функции: await write_to_graph(asyncio.to_thread, sync_func, ...)
```

#### Buffer Middleware (исправлен — теперь FastAPI Middleware, не скрипт)

```python
class NEVABufferMiddleware(BaseHTTPMiddleware):
    WRITE_ENDPOINTS = {"/api/v1/extract", "/api/v1/writeback"}
    MAX_BUFFER_SIZE = 5 * 1024 * 1024  # 5MB

    async def dispatch(self, request, call_next):
        if request.method == "POST" and request.url.path in self.WRITE_ENDPOINTS:
            content_length = int(request.headers.get("content-length", 0))
            if content_length > self.MAX_BUFFER_SIZE:
                return JSONResponse({"error": "payload_too_large"}, status_code=413)
            if not await is_graphiti_available():
                body = await request.body()
                await buffer_write({"endpoint": request.url.path, "body": body.decode()})
                return JSONResponse({"status": "buffered"}, status_code=202)
        return await call_next(request)
```

#### Topic Lock (SQLite WAL)

```sql
CREATE TABLE topic_locks (
    topic TEXT PRIMARY KEY,
    locked_by TEXT NOT NULL,
    session_id TEXT NOT NULL,
    locked_at TEXT NOT NULL,
    expires_at TEXT NOT NULL  -- UTC ISO +30с
);
```

#### Двойной Backup

| Что | Куда | Когда |
|---|---|---|
| JSONL delta | Git | каждые 6 часов |
| Kuzu snapshot | Google Drive | каждые 24 часа |

---

### РАСПРЕДЕЛЕНИЕ ТЗ

**ТЗ-1 → DeepSeek:** Auth, Rate Limiting, Topic Lock, Write Queue,
Conflict Resolver MVP, двойной Backup, Metrics Collector, Init, Schema Guard

**ТЗ-2 → Gemini:** Graphiti wrapper, LangGraph Pipeline, Trust Engine,
TTL Policy, Context API /api/v1/*, Session Manager, Guardian Hook, Export, Stats

**ТЗ-3 → GPT:** Health Monitor (M1 + trending), Self Diagnostics,
CLI, Buffer Middleware, Ollama Watchdog, launchd install, .env.example

---

## 23 ЗАДАЧИ — ЦЕЛЕВОЕ ПОКРЫТИЕ

### Блок A — Базовые свойства
| ID | Задача | Покрытие | Механизм |
|---|---|---|---|
| A1 | Единое состояние знаний | 95% | Kuzu=истина + Topic Lock |
| A2 | Атомарная память | 95% | Graphiti bi-temporal + TTL + DELETE=405 |
| A3 | Воспроизводимый контекст | 85% | RRF + multilingual-e5-small |
| A4 | K_truth | 85% | формула + confidence_update |
| A5 | Диалог через состояние | 95% | MCP + /api/v1/ |

### Блок B — Жизненный цикл
| ID | Задача | Покрытие | Механизм |
|---|---|---|---|
| B1 | TTL Policy | 100% | APScheduler |
| B2 | Conflict Resolver | 60% MVP | similarity>0.85 |
| B3 | Genealogy | 50% | LangGraph trace |
| B4 | Audit Trail | 95% | все поля + checkpoint |

### Блок C — Агенты
| ID | Задача | Покрытие | |
|---|---|---|---|
| C1 | Авторизация | 95% | API токены |
| C2 | Координация | 90% | SQLite topic_locks |
| C3 | Передача контекста | 80% | start_session |
| C4 | Rate Limiting | 95% | slowapi |

### Блок D — Наблюдаемость
| ID | Задача | Покрытие | |
|---|---|---|---|
| D1 | Health Dashboard | 75% | CLI + /api/v1/health |
| D2 | История K_truth | 95% | SQLite time-series |
| D3 | Статистика агентов | 90% | /api/v1/stats |
| D4 | Трендовый мониторинг | 80% | sliding window |

### Блок E — Интеграция
| ID | Задача | Покрытие | |
|---|---|---|---|
| E1 | Guardian Hook | 90% | post-commit |
| E2 | Импорт governance | 85% | neva_init.py |
| E3 | Backup | 95% | двойной |
| E4 | Экспорт | 85% | SHA256 |

**Среднее покрытие MVP: 87%**

---

## МЕТРИКИ

### Качество
| Метрика | Цель | Минимум |
|---|---|---|
| K_consistency | < 2% | < 5% |
| K_truth (online) | 0.75–0.83 | ≥ 0.70 |
| K_truth (offline/llama) | 0.60–0.68 | ≥ 0.55 |
| K_repro | 0.76–0.84 | ≥ 0.70 |

### Производительность
| Метрика | Цель | Минимум |
|---|---|---|
| K_latency /state | < 3s | < 5s |
| K_throughput | 2–8 атомов/с | ≥ 1/с |
| K_compression | 4x–8x | ≥ 2x |

### Ресурсы M1 8GB
| Метрика | Расчётное | Реально | Лимит |
|---|---|---|---|
| RAM baseline | ~770MB | ~446MB ✅ | < 1GB |
| RAM peak (Ollama) | ~4.2GB | не замерен | < 6GB |
| Backup restore | 100% | 20/20 ✅ | 100% |

---

## НАЧНИ С ЭТАПА 1

Проверь: все ли твои предыдущие замечания закрыты корректно в v3.5?
Задай вопросы если что-то неясно или недостаточно.
