# ТЗ-2: INTELLIGENCE LAYER
## Исполнитель: Gemini
## Проект: NEVA v3.5
## Дата: 2026-06-04

---

## ОБЯЗАТЕЛЬНАЯ ПРОЦЕДУРА ПЕРЕД ИСПОЛНЕНИЕМ

**Прежде чем писать код, Gemini ОБЯЗАН:**

1. **Задать вопросы** по всем неясным местам ТЗ
2. **Назвать противоречия** в требованиях
3. **Назвать слепые зоны** — что не описано, но нужно для реализации
4. **Назвать причины** которые могут помешать выполнить ТЗ или его параметры
5. **Назвать чего не хватает** в ТЗ для полноценной реализации

Только после получения ответов — приступать к разработке.
Формат: "ВОПРОСЫ ПЕРЕД ИСПОЛНЕНИЕМ ТЗ-2" → список вопросов и замечаний.

---

## КОНТЕКСТ ПРОЕКТА

NEVA — система единого информационного поля для AI-агентов.
MacBook Air M1 8GB RAM, macOS, Python venv, Kuzu embedded граф БД.

**Зависимости от ТЗ-1 (DeepSeek):**
Твои модули используют:
```python
from neva_write_queue import write_to_graph     # запись в Kuzu
from neva_coordinator import TopicCoordinator   # Topic Lock
from neva_auth import require_auth              # FastAPI dependency
from neva_metrics_collector import record_k_truth
```
ТЗ-1 и ТЗ-2 разрабатываются параллельно. Используй интерфейсы как контракты.

**Стек:**
- kuzu 0.11.3, graphiti-core 0.29.1
- langgraph 1.2.4, langchain-core 1.4.0
- fastapi 0.136.3, uvicorn 0.47.0 (workers=1)
- apscheduler 3.11.2
- sentence-transformers 5.5.1

---

## МОДУЛИ ТЗ-2 (9 файлов)

1. `neva_graphiti.py`
2. `neva_langgraph_pipeline.py`
3. `neva_trust_engine.py`
4. `neva_ttl_policy.py`
5. `neva_context_api.py`
6. `neva_session_manager.py`
7. `neva_guardian_hook_install.py`
8. `neva_export.py`
9. `neva_stats.py`

---

## ДЕТАЛЬНЫЕ ТРЕБОВАНИЯ

### 1. neva_graphiti.py — Graphiti + Kuzu Wrapper (A1, A2: 95%)

**Что делает:** Инициализация Graphiti с Kuzu backend. Wrapper для всех операций с графом.

**КРИТИЧНЫЙ СИНТАКСИС KuzuDriver (не ошибиться):**
```python
# ПРАВИЛЬНО:
driver = KuzuDriver(db='./neva.db')   # параметр именно db=
driver.setup_schema()                  # НЕ async
await driver.build_indices_and_constraints()  # async
await driver.execute_query(...)        # async
await driver.close()                   # async
```

**Инициализация:**
```python
async def init():
    driver = KuzuDriver(db=str(KUZU_DB_PATH))
    driver.setup_schema()
    await driver.build_indices_and_constraints()
    
    graphiti = Graphiti(
        graph_driver=driver,
        llm_client=get_llm_client(),   # Gemini PRIMARY
        embedder=await load_embedder()  # multilingual-e5-small
    )
    return graphiti
```

**Embedding с fallback при OOM:**
```python
async def load_embedder():
    try:
        from graphiti_core.embedder.sentence_transformers import SentenceTransformerEmbedder
        return SentenceTransformerEmbedder("intfloat/multilingual-e5-small")
    except MemoryError:
        logger.warning("OOM: multilingual-e5-small. Fallback → Gemini API embeddings")
        from graphiti_core.embedder.gemini import GeminiEmbedder
        return GeminiEmbedder()
```

**API /api/v1/metrics должен возвращать:**
```json
{
  "embedding_mode": "local",
  "embedding_model": "intfloat/multilingual-e5-small"
}
```

**Метрика приёмки:**
- [ ] init() без ошибок на M1 ARM64
- [ ] add_episode → факт в графе
- [ ] search() → возвращает результаты
- [ ] При MemoryError → fallback на GeminiEmbedder без краша

---

### 2. neva_langgraph_pipeline.py — Pipeline (A1, A3: 85-95%)

**Что делает:** LangGraph pipeline для обработки запросов. WAL checkpoint + resume.

**КРИТИЧНО — WAL обязателен:**
```python
def get_checkpointer(db_path: str) -> SqliteSaver:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.commit()
    return SqliteSaver(conn)
```

**Semaphore — не более 3 параллельных pipeline:**
```python
_pipeline_semaphore = asyncio.Semaphore(3)

async def run_pipeline(state: NEVAState) -> dict:
    async with _pipeline_semaphore:
        coordinator = get_coordinator()
        if not await coordinator.acquire(state["topic"],
                                          state["author_ai"],
                                          state["session_id"]):
            raise HTTPException(409, detail={
                "error": "topic_locked",
                "retry_after": 5
            })
        try:
            result = await app.ainvoke(state,
                config={"configurable": {"thread_id": state["session_id"]}})
            return result
        finally:
            await coordinator.release(state["topic"], state["author_ai"])
```

**NEVAState обязательные поля:**
```python
class NEVAState(TypedDict):
    topic: str
    author_ai: str
    session_id: str
    content: str
    step: int           # для resume с шага N
    k_truth: float
    timestamp: str
```

**Resume при сбое:** LangGraph checkpoint → при restart продолжает с шага N, не с начала.

**Метрика приёмки:**
- [ ] WAL включён при инициализации
- [ ] Semaphore(3): 4-й pipeline ждёт
- [ ] При сбое на шаге N → resume с шага N (не с начала)
- [ ] 409 если topic занят
- [ ] Topic Lock освобождается в finally (даже при исключении)

---

### 3. neva_trust_engine.py — K_truth (A4: 85%)

**Что делает:** Расчёт K_truth и управление весами доверия.

**ТОЧНАЯ ФОРМУЛА (не изменять):**
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
    """Только активные факты (invalid_at IS NULL)."""
    if not active_facts:
        return 0.0
    weights = [TRUST_WEIGHTS.get(f.get("author_ai", "unknown"), 0.60)
               for f in active_facts]
    return round(sum(weights) / len(weights), 3)

def confidence_update(author_ai: str, verified: bool) -> None:
    """Верификация Директором изменяет вес."""
    delta = +0.02 if verified else -0.03
    new_weight = max(0.50, min(0.95,
        TRUST_WEIGHTS.get(author_ai, 0.60) + delta))
    TRUST_WEIGHTS[author_ai] = new_weight
    # Сохранить в neva_metrics.db для персистентности
```

**Алерт при K_truth < 0.70:**
```python
if k_truth < 0.70:
    logger.warning(f"K_truth упал до {k_truth} — ниже минимума 0.70!")
    # macOS уведомление Директору
```

**Метрика приёмки:**
- [ ] director_approved факты → K_truth ближе к 0.95
- [ ] только llama факты → K_truth ≈ 0.65
- [ ] confidence_update(verified=True) → weight += 0.02
- [ ] K_truth < 0.70 → предупреждение в логах

---

### 4. neva_ttl_policy.py — TTL Policy (B1: 100%)

**Что делает:** Устаревание фактов по типу. Запускается APScheduler каждые 6 часов.

**ПРАВИЛА TTL (точные):**
```python
TTL_RULES = {
    "FACT":      timedelta(days=30),
    "DECISION":  timedelta(days=90),
    "RULE":      timedelta(days=365),
    "TASK":      timedelta(days=7),
    "CONFLICT":  timedelta(days=14),
    "COMPONENT": None,  # вечно, никогда не инвалидируется
}
```

**Логика:**
- Инвалидировать только факты без верификации Директора
- verified facts (director_approved=True) → не инвалидировать
- Инвалидация = заполнить `invalid_at` через Graphiti API (не DELETE)
- Через Graphiti API, не прямой SQL в Kuzu

**Интеграция с APScheduler:**
```python
scheduler.add_job(run_ttl_check, 'interval', hours=6, id='ttl_check')
```

**Метрика приёмки:**
- [ ] FACT старше 30 дней без верификации → invalid_at заполнен
- [ ] COMPONENT → никогда не инвалидируется
- [ ] director_approved факт → не инвалидируется даже если старый
- [ ] run_ttl_check() → возвращает {"deprecated": int}

---

### 5. neva_context_api.py — FastAPI API (A5, C3: 80-95%)

**Что делает:** REST API для всех агентов. Единственная точка входа для записи/чтения.

**ОБЯЗАТЕЛЬНЫЕ ENDPOINTS:**

```
POST /api/v1/writeback       — записать факты (write_write права)
POST /api/v1/extract         — извлечь и записать из текста
GET  /api/v1/state           — получить текущее состояние (все агенты)
GET  /api/v1/health          — статус системы (без токена)
GET  /api/v1/metrics         — метрики K_truth, RAM, etc.
GET  /api/v1/stats           — статистика по агентам
POST /api/v1/session/start   — начать сессию
POST /api/v1/session/end     — завершить сессию
GET  /api/v1/export          — экспорт для аудиторов (admin)
GET  /api/v1/search          — семантический поиск → атомы + source_path (P16)
GET  /api/v1/document/{doc_id} — метаданные документа + source_path к RAW (P16)
```

**ВСЕ endpoints используют /api/v1/ prefix.**

**P16 — /api/v1/search response (путь к истинному документу):**
```json
{
  "query": "K_truth формула",
  "results": [
    {
      "content": "K_truth = взвешенное среднее по источнику",
      "source_path": "governance/NEVA-TASK-007-v3.5.md",
      "doc_id": "NEVA-TASK-007",
      "doc_version": "3.5",
      "score": 0.87,
      "atom_type": "RULE"
    }
  ]
}
```
Агент находит атом по смыслу → берёт source_path → открывает полный RAW документ.

**P16 — /api/v1/document/{doc_id} response:**
```json
{
  "doc_id": "NEVA-TASK-007",
  "doc_version": "3.5",
  "source_path": "governance/NEVA-TASK-007-v3.5.md",
  "sha256": "abc123...",
  "atom_count": 42,
  "indexed_at": "2026-06-04T10:00:00+00:00"
}
```

**/api/v1/state response:**
```json
{
  "k_truth": 0.81,
  "fact_count": 142,
  "active_agents": ["claude", "gemini"],
  "last_updated": "2026-06-04T10:00:00+00:00",
  "embedding_mode": "local"
}
```

**/api/v1/health response:**
```json
{
  "status": "ok",
  "kuzu": "connected",
  "graphiti": "ready",
  "ollama": "running",
  "k_truth": 0.81
}
```

**K_latency /api/v1/state: < 3 секунды (цель), < 5 секунд (минимум)**

**Метрика приёмки:**
- [ ] Все endpoints доступны с правильным токеном
- [ ] /api/v1/health без токена → 200
- [ ] /api/v1/writeback без токена → 401
- [ ] K_latency /api/v1/state < 3s при < 1000 фактов
- [ ] K_throughput: 2-8 атомов/с через /api/v1/extract
- [ ] P16: /api/v1/search возвращает атомы с непустым source_path
- [ ] P16: /api/v1/document/{doc_id} → source_path ведёт к существующему RAW
- [ ] P16: поиск по смыслу находит нужный документ (K_repro ≥ 0.70)

---

### 6. neva_session_manager.py — Session Manager (C3: 80%)

**Что делает:** Управление сессиями агентов. Передача контекста между сессиями.

**Контракт start_session:**
```python
async def start_session(agent_id: str, topic: str) -> dict:
    """
    Возвращает:
    - session_id: уникальный ID
    - state_snapshot: последние факты по теме
    - k_truth: текущий K_truth
    - active_locks: список locked topics
    """
    session_id = f"{agent_id}_{topic}_{uuid4().hex[:8]}"
    snapshot = await graphiti.search(topic, num_results=50)
    k_truth = calculate_k_truth(snapshot)
    
    return {
        "session_id": session_id,
        "state_snapshot": snapshot,
        "k_truth": k_truth,
        "topic": topic,
        "started_at": datetime.now(timezone.utc).isoformat()
    }

async def end_session(session_id: str, agent_id: str, topic: str) -> dict:
    """Освобождает Topic Lock, сохраняет статистику сессии."""
    await coordinator.release(topic, agent_id)
    return {"session_id": session_id, "status": "ended"}
```

**Метрика приёмки:**
- [ ] start_session → session_id + snapshot + k_truth
- [ ] end_session → Topic Lock освобождён
- [ ] Два агента с разными topic → независимые сессии

---

### 7. neva_guardian_hook_install.py — Guardian Hook (E1: 90%)

**Что делает:** Устанавливает git post-commit hook → POST /api/v1/extract.

**Логика:**
```bash
# .git/hooks/post-commit (устанавливается скриптом)
#!/bin/bash
DIFF=$(git diff HEAD~1 HEAD --name-only 2>/dev/null || git show --name-only HEAD --format="" | head -20)
curl -s -X POST http://localhost:8000/api/v1/extract \
  -H "Authorization: Bearer $NEVA_TOKEN_GUARDIAN" \
  -H "Content-Type: application/json" \
  -d "{\"content\": \"git commit: $DIFF\", \"author_ai\": \"guardian_hook\"}" \
  || echo "NEVA: сервер недоступен, факт не записан"
```

**При недоступности NEVA:** hook не ломает git commit, просто логирует.

**Команда установки:**
```bash
python neva_guardian_hook_install.py --install   # установить
python neva_guardian_hook_install.py --remove    # удалить
python neva_guardian_hook_install.py --status    # проверить
```

**Метрика приёмки:**
- [ ] git commit → POST /api/v1/extract вызван
- [ ] NEVA недоступен → git commit всё равно завершён
- [ ] --status показывает установлен ли hook

---

### 8. neva_export.py — Экспорт для аудиторов (E4: 85%)

**Что делает:** Экспорт всех активных фактов с SHA256 для верификации.

**Endpoint:** `GET /api/v1/export` (требует admin токен)

**Response:**
```json
{
  "exported_at": "2026-06-04T10:00:00+00:00",
  "fact_count": 142,
  "sha256": "abc123...",
  "facts": [...]
}
```

**SHA256** считается от JSON строки всех фактов (sorted by id).
Аудитор может пересчитать SHA256 и сравнить.

**Метрика приёмки:**
- [ ] /api/v1/export без admin токена → 403
- [ ] SHA256 совпадает при повторном запросе с теми же фактами
- [ ] Экспорт содержит все активные факты

---

### 9. neva_stats.py — Статистика (D3: 90%)

**Что делает:** Статистика по агентам через /api/v1/stats.

**Response:**
```json
{
  "total_facts": 142,
  "by_agent": {
    "claude": {"count": 50, "avg_confidence": 0.82},
    "gemini": {"count": 40, "avg_confidence": 0.80},
    "deepseek": {"count": 30, "avg_confidence": 0.78}
  },
  "by_type": {
    "FACT": 90, "DECISION": 30, "RULE": 15, "TASK": 7
  },
  "conflict_rate": 0.014,
  "k_truth_current": 0.81
}
```

**Метрика приёмки:**
- [ ] /api/v1/stats возвращает by_agent статистику
- [ ] conflict_rate = count(CONFLICT) / count(all_facts)
- [ ] avg_confidence рассчитывается корректно

---

## ТРЕБУЕМЫЕ ПАРАМЕТРЫ СИСТЕМЫ (твоя часть)

| Параметр | Требование | Как измерить |
|---|---|---|
| A1 Единое состояние | 95% | Kuzu = единственная истина |
| A2 Атомарная память | 95% | bi-temporal + TTL работает |
| A3 Воспроизводимый контекст | 85% | K_repro 0.76–0.84 |
| A4 K_truth | 85% | формула точная, алерт при < 0.70 |
| A5 Диалог через состояние | 95% | все endpoints работают |
| B1 TTL Policy | 100% | все типы атомов по расписанию |
| K_latency /state | < 3s | curl timing |
| K_throughput | 2–8/с | batch test |
| Pipeline resume | с шага N | crash test |
| Semaphore(3) | 4-й ждёт | concurrent test |

---

## ОГРАНИЧЕНИЯ

1. **workers=1** — asyncio.Lock из ТЗ-1 работает только в одном процессе
2. **ВСЯ запись через write_to_graph()** из ТЗ-1 — нельзя писать в Kuzu напрямую
3. **TTL** — только invalidate, не DELETE (RAW данные не удаляются)
4. **UTC ISO** — все timestamps
5. **KuzuDriver параметр db=** — не database_path
6. **P16 индексация** — /api/v1/search и /api/v1/document обязаны возвращать source_path.
   Одна модель: Graphiti + e5-small. Индекс ведёт к RAW (истина 100%).

---

## ФАЙЛЫ КОТОРЫЕ НЕ ТРОГАТЬ

ТЗ-1 (DeepSeek): neva_auth.py, neva_rate_limiter.py, neva_coordinator.py,
neva_write_queue.py, neva_conflict_resolver_basic.py, neva_backup.py,
neva_metrics_collector.py, neva_init.py, schema_guard.py

ТЗ-3 (GPT): neva_health_monitor.py, neva_buffer_retry.py,
neva_self_diagnostics.py, neva_cli.py

---

## НАЧНИ С ВОПРОСОВ

Формат ответа:
```
ВОПРОСЫ ПЕРЕД ИСПОЛНЕНИЕМ ТЗ-2:

1. [вопрос или противоречие]
2. [слепая зона]
3. [чего не хватает]
4. [причина которая может помешать]
...
```

Только после ответов — приступай к разработке.
