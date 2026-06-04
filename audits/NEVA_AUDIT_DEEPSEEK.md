# ЗАПРОС НА ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ АУДИТА: NEVA-TASK-007 v3.5
## Аудитор: DeepSeek
## Дата: 2026-06-04

---

## ТВОЯ РОЛЬ

Ты уже дал вердикт УТВЕРЖДАЮ по v3.5 (DeepSeek-R2 и DeepSeek-2).
Теперь нужно финальное подтверждение с учётом результатов Этапа 0,
которые были получены ПОСЛЕ твоего предыдущего аудита.

---

## ИНСТРУКЦИЯ

### ЭТАП 1 — ВОПРОСЫ ПО НОВЫМ ДАННЫМ
Результаты Этапа 0 могут изменить оценку. Задай вопросы если:
1. Результаты Этапа 0 противоречат тому что ты ожидал
2. Что-то в новых данных вызывает сомнения
3. Нужна дополнительная информация для подтверждения вердикта

### ЭТАП 2 — ПОДТВЕРЖДЕНИЕ ИЛИ ПЕРЕСМОТР
- Подтверди УТВЕРЖДАЮ с учётом результатов Этапа 0
- Или измени вердикт если новые данные дают основания

---

## РЕЗУЛЬТАТЫ ЭТАПА 0 (НОВЫЕ — получены после твоего предыдущего аудита)

| Тест | Результат | Комментарий |
|---|---|---|
| Kuzu ARM64 | ✅ работает | нативный wheel, нет rosetta |
| Graphiti + Kuzu совместимость | ✅ schema + индексы | test_graphiti_kuzu_compat.py пройден |
| 10 параллельных записей | ✅ все 10 без ошибок | asyncio.Lock работает корректно |
| RAM baseline (без Ollama) | ✅ ~446MB | прогноз был 770MB — лучше на 40% |
| Backup restore 20/20 | ✅ export→delete→restore совпадает | потерь нет |
| Cerebras structured_output | ✅ gpt-oss-120b работает | добавлен как SECONDARY в Router |

**Что НЕ замерено в Этапе 0:**
- RAM peak с qwen2.5:7b (прогноз ~4.2GB, не проверен)
- MTTR при сбое Kuzu (прогноз ~10с)
- Pipeline resume с шага N при crash

---

## ИЗМЕНЕНИЯ В v3.5 ПОСЛЕ ТВОЕГО ПОСЛЕДНЕГО АУДИТА

| Изменение | Суть |
|---|---|
| AI Router обновлён | Cerebras gpt-oss-120b добавлен как SECONDARY (structured_output ✅) |
| RAM baseline пересмотрен | 770MB расчётное → 446MB реальное (Этап 0) |
| Backup подтверждён | 20/20 тестов restore пройдено |
| Стек подтверждён на железе | Все 6 тестов Этапа 0 зелёные |
| **P16 добавлен** ← НОВОЕ | Принцип индексации всех документов одной моделью |

## ПРИНЦИП P16 — ИНДЕКСАЦИЯ (НОВЫЙ, требует твоей оценки)

```
ОДНА МОДЕЛЬ для всех документов NEVA (стандартизация):
  Graphiti + multilingual-e5-small + Kuzu

RAW файл (governance/, tz/, audits/, chats/, code/) = ИСТИНА 100%
Индекс (Kuzu атомы) = УКАЗАТЕЛЬ к RAW + семантический поиск
Каждый атом хранит source_path → путь к RAW.
Цель достоверности: 95% (K_repro), реально e5-small 0.76–0.84.

Логика: индекс ведёт к истинному RAW-документу (если есть),
иначе атом = логический вывод (genealogy).
НЕ второй источник истины: RAW=источник, индекс=производное.

Правки в ТЗ-1 (твоё): neva_init.py теперь индексирует ВСЕ папки,
каждый атом получает source_path + doc_id + sha256.
Новые команды: --import-all, --reindex, --verify (sha256 RAW vs индекс).
```

**ВОПРОС К ТЕБЕ ПО P16:** Реализуема ли индексация всех документов (включая .docx)
одной моделью e5-small с сохранением source_path в каждом атоме? Видишь ли
риски в требовании sha256-сверки RAW vs индекс при --verify?

---

## ПОЛНЫЙ ДОКУМЕНТ v3.5 (для справки)

### ПРИНЦИП P15 — ИЕРАРХИЯ ХРАНИЛИЩ

```
Kuzu (через Graphiti) = ИСТИНА
LangGraph SqliteSaver = ЖУРНАЛ
neva_metrics.db       = ТЕЛЕМЕТРИЯ
cr-sqlite buffer      = ВРЕМЕННЫЙ буфер
Git backup JSONL      = АРХИВ
Google Drive snapshot = БЫСТРОЕ ВОССТАНОВЛЕНИЕ
```

### СТЕК

| Компонент | Решение |
|---|---|
| Граф БД | Kuzu embedded 0.11.3 |
| Knowledge graph | Graphiti 0.29.1 |
| Pipeline | LangGraph + SqliteSaver WAL |
| Embedding | multilingual-e5-small |
| API | FastAPI + uvicorn workers=1 |
| Scheduler | APScheduler |
| Write sync | asyncio.Lock() |
| Topic Lock | SQLite WAL persistent |

**AI Router (финальный с Cerebras):**
| Уровень | Провайдер |
|---|---|
| PRIMARY | Gemini API |
| SECONDARY | Cerebras gpt-oss-120b ← новое |
| FAST | Groq |
| BACKUP | DeepSeek (OpenRouter) |
| FALLBACK | Mistral |
| LOCAL-HEAVY | Ollama qwen2.5:7b |
| LOCAL-LIGHT | Ollama llama3.2:3b |
| EMERGENCY | keyword extraction |

### K_truth формула

```python
TRUST_WEIGHTS = {
    "director_approved": 0.95,
    "guardian_hook":     0.88,
    "gemini":            0.82,
    "cerebras":          0.82,  # ← добавлен
    "groq":              0.80,
    "llama":             0.65,
    "keyword":           0.55,
    "unknown":           0.60,
}
```

### Двойной Backup

| Что | Куда | Когда |
|---|---|---|
| JSONL delta | Git | каждые 6 часов |
| Kuzu snapshot | Google Drive | каждые 24 часа |

Восстановление: snapshot + delta. Потеря max 6 часов.

### Topic Lock

```sql
CREATE TABLE topic_locks (
    topic TEXT PRIMARY KEY,
    locked_by TEXT NOT NULL,
    session_id TEXT NOT NULL,
    locked_at TEXT NOT NULL,
    expires_at TEXT NOT NULL  -- UTC ISO +30с
);
```

### Write Queue

```python
_write_lock = asyncio.Lock()
async def write_to_graph(operation, *args, **kwargs):
    async with _write_lock:
        result = operation(*args, **kwargs)
        import inspect
        if inspect.isawaitable(result):
            return await result
        return result
```

---

## 23 ЗАДАЧИ — ПОКРЫТИЕ v3.5

| ID | Задача | Покрытие |
|---|---|---|
| A1 | Единое состояние | 95% |
| A2 | Атомарная память | 95% |
| A3 | Воспроизводимый контекст | 85% |
| A4 | K_truth | 85% |
| A5 | Диалог через состояние | 95% |
| B1 | TTL Policy | 100% |
| B2 | Conflict Resolver | 60% MVP |
| B3 | Genealogy | 50% |
| B4 | Audit Trail | 95% |
| C1 | Авторизация | 95% |
| C2 | Координация агентов | 90% |
| C3 | Передача контекста | 80% |
| C4 | Rate Limiting | 95% |
| D1 | Health Dashboard | 75% |
| D2 | История K_truth | 95% |
| D3 | Статистика | 90% |
| D4 | Трендовый мониторинг | 80% |
| E1 | Guardian Hook | 90% |
| E2 | Импорт governance | 85% |
| E3 | Backup | 95% |
| E4 | Экспорт | 85% |
| F1 | atom_edges | Этап 2 |
| F2 | Community subgraph | Этап 2 |

**Среднее MVP: 87%**

---

## МЕТРИКИ

| Метрика | Цель | Реально (Этап 0) |
|---|---|---|
| RAM baseline | < 1GB | ~446MB ✅ |
| K_truth online | 0.75–0.83 | — (расчётное) |
| K_latency /state | < 3s | — |
| Backup restore | 100% | 20/20 ✅ |
| K_throughput | 2–8/с | — |

---

## НАЧНИ С ЭТАПА 1

Есть ли вопросы по результатам Этапа 0?
Подтверждаешь ли свой вердикт УТВЕРЖДАЮ с учётом новых данных?
