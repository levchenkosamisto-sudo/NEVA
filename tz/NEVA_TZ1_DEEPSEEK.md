# ТЗ-1: CORE INFRASTRUCTURE
## Исполнитель: DeepSeek
## Проект: NEVA v3.5
## Дата: 2026-06-04

---

## ОБЯЗАТЕЛЬНАЯ ПРОЦЕДУРА ПЕРЕД ИСПОЛНЕНИЕМ

**Прежде чем писать код, DeepSeek ОБЯЗАН:**

1. **Задать вопросы** по всем неясным местам ТЗ
2. **Назвать противоречия** в требованиях
3. **Назвать слепые зоны** — что не описано, но нужно для реализации
4. **Назвать причины** которые могут помешать выполнить ТЗ или его параметры
5. **Назвать чего не хватает** в ТЗ для полноценной реализации

Только после получения ответов — приступать к разработке.
Формат: "ВОПРОСЫ ПЕРЕД ИСПОЛНЕНИЕМ ТЗ-1" → список вопросов и замечаний.

---

## КОНТЕКСТ ПРОЕКТА

NEVA — система единого информационного поля для AI-агентов (Claude, GPT, Gemini, DeepSeek).
Работает на MacBook Air M1 8GB RAM, macOS.

**Железо:**
- MacBook Air M1 8GB RAM, 228GB SSD
- Python venv: ~/Documents/NEVA/venv/
- Google Drive: ~/Library/CloudStorage/GoogleDrive-levchenkosamisto@gmail.com/My Drive/NEVA/snapshots/

**Стек (подтверждён в Этапе 0):**
- kuzu 0.11.3 — embedded граф БД
- graphiti-core 0.29.1 — knowledge graph поверх Kuzu
- langgraph 1.2.4 — pipeline
- fastapi 0.136.3 + uvicorn 0.47.0 — API (workers=1)
- slowapi 0.1.9 — rate limiting
- apscheduler 3.11.2 — scheduler
- sqlite3 (stdlib) — Topic Lock, metrics

---

## МОДУЛИ ТЗ-1 (9 файлов)

1. `neva_auth.py`
2. `neva_rate_limiter.py`
3. `neva_coordinator.py`
4. `neva_write_queue.py`
5. `neva_conflict_resolver_basic.py`
6. `neva_backup.py`
7. `neva_metrics_collector.py`
8. `neva_init.py`
9. `schema_guard.py`

---

## ДЕТАЛЬНЫЕ ТРЕБОВАНИЯ

### 1. neva_auth.py — Авторизация (C1: 95%)

**Что делает:** Auth Middleware для FastAPI. Проверяет API токены.

**Требования:**
- Токены читаются из .env: `NEVA_TOKEN_CLAUDE`, `NEVA_TOKEN_GPT`, `NEVA_TOKEN_GEMINI`, `NEVA_TOKEN_DEEPSEEK`
- Три уровня прав: `read_only`, `read_write`, `admin`
- Без токена → 401 Unauthorized
- Токен есть, прав нет → 403 Forbidden
- Токен admin → все операции
- Публичные endpoints (без проверки): `/api/v1/health`, `/api/v1/metrics`
- Токен передаётся в заголовке: `Authorization: Bearer <token>`

**Метрика приёмки:**
- [ ] 401 без заголовка Authorization
- [ ] 403 при read_only токене на write endpoint
- [ ] 200 при read_write токене на write endpoint
- [ ] /api/v1/health доступен без токена

---

### 2. neva_rate_limiter.py — Rate Limiting (C4: 95%)

**Что делает:** Ограничение запросов per agent_id через slowapi.

**Требования:**
- Лимит writeback: 30 запросов/минуту per agent_id
- Лимит extract: 10 запросов/минуту per agent_id
- При превышении → 429 Too Many Requests
- agent_id берётся из токена (или заголовка X-Agent-ID)
- Сброс лимита: каждую минуту (sliding window)

**Метрика приёмки:**
- [ ] 31-й writeback запрос → 429
- [ ] 11-й extract запрос → 429
- [ ] Разные agent_id — независимые лимиты

---

### 3. neva_coordinator.py — Topic Lock (C2: 90%)

**Что делает:** Координация параллельных агентов через SQLite persistent locks.

**КРИТИЧНО:** asyncio.Lock работает только внутри одного процесса.
Topic Lock в SQLite — единственный способ координации между сессиями.

**Точный контракт (не отступать):**

```python
class TopicCoordinator:
    def __init__(self, db_path: str):
        # SQLite WAL mode обязателен
        pass

    async def acquire(self, topic: str, agent_id: str,
                      session_id: str, timeout_s: int = 30) -> bool:
        # True если lock получен, False если занят
        # Сначала cleanup_expired()
        pass

    async def release(self, topic: str, agent_id: str) -> bool:
        # True если успешно освобождён
        pass

    def _cleanup_expired(self):
        # DELETE WHERE expires_at < now (UTC ISO)
        pass
```

**SQLite схема (точная):**
```sql
CREATE TABLE IF NOT EXISTS topic_locks (
    topic      TEXT PRIMARY KEY,
    locked_by  TEXT NOT NULL,
    session_id TEXT NOT NULL,
    locked_at  TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_locks_expires ON topic_locks(expires_at);
```

**expires_at формат:** UTC ISO `2026-06-04T10:30:00+00:00`
**Cleanup SQL:** `DELETE FROM topic_locks WHERE expires_at < strftime('%Y-%m-%dT%H:%M:%S+00:00','now')`

**Метрика приёмки:**
- [ ] acquire → release → re-acquire одного topic: OK
- [ ] acquire занятого topic → False (не блокирует, не ждёт)
- [ ] expires_at прошёл → topic автоматически освобождается
- [ ] SQLite WAL → переживает restart сервера
- [ ] 409 HTTP если topic занят (интеграция с Pipeline)

---

### 4. neva_write_queue.py — Write Queue (Kuzu single-writer)

**Что делает:** Единственная точка записи в Kuzu граф. Гарантирует что в один момент
пишет только один агент (Kuzu не поддерживает параллельную запись).

**ТОЧНЫЙ КОД (не изменять логику):**

```python
import asyncio, inspect, logging

logger = logging.getLogger("neva.write_queue")
_write_lock = asyncio.Lock()
_write_counter = 0

async def write_to_graph(operation, *args, **kwargs):
    """
    Единственная точка записи в Kuzu граф.
    Поддерживает async и sync функции:
      await write_to_graph(graphiti.add_episode, ...)        # async
      await write_to_graph(asyncio.to_thread, sync_func, ..) # sync
    """
    global _write_counter
    async with _write_lock:
        _write_counter += 1
        logger.debug(f"Write #{_write_counter}: {getattr(operation, '__name__', operation)}")
        try:
            result = operation(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        except Exception as e:
            logger.error(f"Write #{_write_counter} failed: {e}")
            raise
```

**ПРЕДУПРЕЖДЕНИЕ:** Lock работает только внутри одного Python процесса.
При workers > 1 нужен внешний семафор. Для NEVA MVP: uvicorn workers=1.

**Метрика приёмки:**
- [ ] 10 параллельных write_to_graph → нет database locked
- [ ] async операция → awaitable корректно
- [ ] sync операция через asyncio.to_thread → корректно
- [ ] Счётчик _write_counter инкрементируется

---

### 5. neva_conflict_resolver_basic.py — Conflict Resolver MVP (B2: 60%)

**Что делает:** Базовое обнаружение конфликтов между фактами.
MVP уровень — similarity based. Полный resolver (atom_edges) → Этап 2.

**Требования:**
- Сравнивает новый факт с существующими через cosine similarity
- Если similarity > 0.85 и факты противоречат → создаёт CONFLICT атом
- CONFLICT атом содержит: оба конфликтующих факта, similarity score, timestamp
- Не удаляет оригинальные факты (RAW данные не удаляются)
- Логирует конфликт для Директора

**CONFLICT атом структура:**
```python
{
    "type": "CONFLICT",
    "fact_a_id": str,
    "fact_b_id": str,
    "similarity": float,
    "detected_at": str,  # UTC ISO
    "resolver": "basic_similarity",
    "status": "unresolved"
}
```

**Метрика приёмки:**
- [ ] Два одинаковых факта → CONFLICT атом создан
- [ ] Два несхожих факта → CONFLICT не создаётся
- [ ] Оригинальные факты сохранены после обнаружения конфликта
- [ ] K_consistency = доля CONFLICT атомов ≤ 2% при нормальной работе

---

### 6. neva_backup.py — Двойной Backup (E3: 95%)

**Что делает:** Инкрементальный backup в два хранилища.

**АРХИТЕКТУРА:**

| Что | Куда | Когда | Формат |
|---|---|---|---|
| JSONL delta (факты) | neva_backup/ → Git | каждые 6 часов | один факт = одна строка |
| Kuzu snapshot (БД) | Google Drive | каждые 24 часа | директория Kuzu |

**Пути:**
```python
GIT_BACKUP_DIR = Path("neva_backup")  # в Git репозитории
GDRIVE_DIR = Path.home() / "Library/CloudStorage" / \
    "GoogleDrive-levchenkosamisto@gmail.com" / "My Drive" / "NEVA" / "snapshots"
KUZU_DB_PATH = Path("neva.db")
```

**Функции:**
```python
async def backup_incremental() -> dict:
    # Только факты с sequence_id > last_backup_sequence
    # Сохранить в delta_{YYYYMMDD_HHMM}.jsonl
    # git add + git commit
    # Вернуть {"backed_up": int, "file": str}

async def backup_snapshot() -> dict:
    # Скопировать директорию neva.db на Google Drive
    # Имя: kuzu_snapshot_{YYYYMMDD_HHMM}
    # Хранить только последние 7 снимков
    # Вернуть {"snapshot": str, "kept": int}

async def restore_from_snapshot(snapshot_path: str = None) -> dict:
    # 1. Найти последний snapshot (если не указан)
    # 2. Скопировать на место neva.db
    # 3. Донакатить JSONL delta новее snapshot
    # Вернуть {"restored_from": str, "delta_applied": int}

async def restore_from_jsonl_only() -> dict:
    # Fallback: только из JSONL если нет snapshot
```

**sequence_id:** integer, не datetime. Хранится в neva_metrics.db.
Причина: datetime уязвим к timezone при смене настроек Mac.

**КРИТИЧНО для macOS:**
```bash
# sed на macOS BSD — правильный синтаксис:
sed -i '' "s|$OLD|$NEW|" .env  # разделитель | не /
```

**Метрика приёмки:**
- [ ] backup_incremental → JSONL создан, git commit выполнен
- [ ] backup_snapshot → директория скопирована на Google Drive
- [ ] restore_from_snapshot → snapshot + delta → все факты восстановлены
- [ ] Только 7 последних snapshot на Google Drive
- [ ] Google Drive путь проверяется при старте (алерт если недоступен)
- [ ] test_backup_restore.py: export→delete→restore → count фактов совпадает

---

### 7. neva_metrics_collector.py — Метрики (D2, D3)

**Что делает:** Сбор и хранение метрик K_truth в SQLite time-series.

**БД:** neva_metrics.db (отдельный файл, не neva_pipeline.db)

**Схема:**
```sql
CREATE TABLE k_truth_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,     -- UTC ISO
    k_truth REAL NOT NULL,
    fact_count INTEGER NOT NULL,
    embedding_mode TEXT,         -- "local" | "api_fallback"
    agent_counts TEXT            -- JSON: {"claude": 10, "gpt": 5}
);

CREATE TABLE backup_sequence (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_sequence INTEGER NOT NULL DEFAULT 0,
    last_backup_at TEXT
);
```

**Функции:**
```python
async def record_k_truth(k_truth: float, fact_count: int, ...) -> None
async def get_k_truth_history(hours: int = 24) -> list[dict]
async def get_last_backup_sequence() -> int
async def set_last_backup_sequence(seq: int) -> None
```

**Расписание:** запись K_truth каждые 5 минут (APScheduler).

**Алерт:** если K_truth < 0.70 → logger.warning + macOS уведомление.

**Метрика приёмки:**
- [ ] K_truth записывается каждые 5 минут
- [ ] get_k_truth_history(24) → список за 24 часа
- [ ] backup_sequence сохраняется между restartами

---

### 8. neva_init.py — Импорт и индексация документов (E2: 85%, P16)

**Что делает:** Импорт ВСЕХ документов NEVA в граф. Единая модель индексации (P16).

**ПРИНЦИП P16 (IMMUTABLE):**
- Одна модель индексации для всех документов: Graphiti + multilingual-e5-small
- RAW файл = ИСТИНА 100%, индекс = УКАЗАТЕЛЬ к RAW
- Каждый атом хранит source_path → путь к исходному файлу
- Цель достоверности: 95% (K_repro), реально 0.76–0.84

**Команды:**
```bash
python neva_init.py --import-governance   # импорт governance/
python neva_init.py --import-all          # ВСЕ папки: governance/, tz/, audits/, chats/, code/, docs/
python neva_init.py --status              # показать что импортировано
python neva_init.py --verify              # проверить целостность (sha256 RAW vs индекс)
python neva_init.py --reindex             # полная переиндексация всей NEVA
```

**ОБЯЗАТЕЛЬНЫЕ ПОЛЯ АТОМА (P16) — не отступать:**
```python
{
    "content": str,            # извлечённый атом
    "author_ai": "guardian_hook",
    "source_path": str,        # ПУТЬ К RAW: "governance/NEVA-TASK-007-v3.5.md"
    "doc_id": str,             # извлечь из имени/содержимого: "NEVA-TASK-007"
    "doc_version": str,        # "3.5"
    "sha256": str,             # хеш RAW файла
    "indexed_at": str,         # UTC ISO
    "atom_type": str,          # FACT/DECISION/RULE/TASK/COMPONENT
}
# source_path обязателен для всех атомов из существующих файлов.
```

**Логика импорта:**
- Читать файлы из указанных папок (.md, .docx, .txt)
- Для .docx использовать python-docx для извлечения текста
- Каждый документ → batch ingestion через Graphiti (write_to_graph!)
- Вычислить sha256 RAW файла → записать в каждый атом документа
- author_ai = "guardian_hook", confidence = 0.88
- Не импортировать повторно если sha256 совпадает (документ не изменился)
- Если sha256 изменился → переиндексировать документ (старые атомы invalidate)
- Логировать: "Импортировано: X документов, Y атомов, source_path записан"

**Поддерживаемые форматы:** .md, .docx, .txt (расширяемо)

**Метрика приёмки:**
- [ ] --import-governance → все документы governance/ в графе
- [ ] --import-all → все папки проиндексированы
- [ ] Каждый атом имеет непустой source_path
- [ ] sha256 атома совпадает с sha256 RAW файла
- [ ] Повторный запуск без изменений → пропускает (sha256 match)
- [ ] Изменённый документ → старые атомы invalidate, новые created
- [ ] --verify: расхождение sha256 RAW vs индекс →報告 ошибку
- [ ] .docx документы импортируются через python-docx
- [ ] --status показывает: документов X, атомов Y, покрытие папок

---

### 9. schema_guard.py — Валидация атомов

**Что делает:** Защита от некорректных атомов. Валидация перед записью в граф.

**6 типов атомов:**
```python
ATOM_TYPES = {"FACT", "DECISION", "RULE", "TASK", "CONFLICT", "COMPONENT"}
```

**Правила валидации:**
- Тип атома должен быть из ATOM_TYPES
- `author_ai` обязателен
- `director_approved` может выставить ТОЛЬКО Директор (не AI агент)
- Если AI пытается записать `director_approved=True` → PermissionError
- `content` не пустой, не None
- `timestamp` в UTC ISO формате

**Метрика приёмки:**
- [ ] Неизвестный тип атома → ValidationError
- [ ] AI устанавливает director_approved → PermissionError
- [ ] Пустой content → ValidationError
- [ ] Корректный атом → проходит без ошибок

---

## ТРЕБУЕМЫЕ ПАРАМЕТРЫ СИСТЕМЫ (твоя часть)

После реализации ТЗ-1 система должна обеспечивать:

| Параметр | Требование | Как измерить |
|---|---|---|
| C1 Авторизация | 95% покрытие | тест: 401/403/200 по сценариям |
| C2 Координация | 90% покрытие | тест: 3 агента параллельно, нет race condition |
| C4 Rate Limiting | 95% покрытие | тест: 31-й запрос → 429 |
| E3 Backup | 95% покрытие | test_backup_restore.py 20/20 |
| K_consistency | < 2% конфликтов | доля CONFLICT атомов |
| RAM overhead (твои модули) | < 50MB | psutil |
| Backup restore | 100% | export→delete→restore |
| Topic Lock persistence | 100% | restart → lock сохранён |

---

## ОГРАНИЧЕНИЯ И ПРАВИЛА

1. **uvicorn workers=1** — asyncio.Lock работает только в одном процессе
2. **Kuzu single-writer** — ВСЯ запись только через write_to_graph()
3. **RAW данные не удаляются** — CONFLICT не удаляет оригиналы
4. **UTC ISO везде** — все timestamps в UTC, формат ISO
5. **macOS sed** — `sed -i ''` не `sed -i`
6. **Google Drive путь** — проверять существование при старте
7. **Git commit** — только через subprocess.run, не через библиотеки
8. **sequence_id** — основа backup, не datetime
9. **P16 индексация** — neva_init.py: каждый атом обязан иметь source_path к RAW.
   Одна модель индексации (Graphiti + e5-small). RAW = истина 100%, индекс = указатель.

---

## ФАЙЛЫ КОТОРЫЕ НЕ ТРОГАТЬ (не в ТЗ-1)

Эти модули разрабатывает Gemini (ТЗ-2):
- neva_graphiti.py — Graphiti wrapper
- neva_trust_engine.py — K_truth расчёт
- neva_context_api.py — FastAPI endpoints

Эти модули разрабатывает GPT (ТЗ-3):
- neva_health_monitor.py
- neva_buffer_retry.py

---

## ИНТЕРФЕЙСЫ ДЛЯ ВЗАИМОДЕЙСТВИЯ С ТЗ-2 И ТЗ-3

Твои модули должны экспортировать:

```python
# Из neva_write_queue.py — используется всеми
from neva_write_queue import write_to_graph

# Из neva_coordinator.py — используется Pipeline (ТЗ-2)
from neva_coordinator import TopicCoordinator
coordinator = TopicCoordinator("neva_pipeline.db")

# Из neva_auth.py — используется как FastAPI dependency
from neva_auth import require_auth, require_admin

# Из neva_metrics_collector.py — используется ТЗ-3
from neva_metrics_collector import record_k_truth, get_k_truth_history
from neva_metrics_collector import get_last_backup_sequence, set_last_backup_sequence
```

---

## НАЧНИ С ВОПРОСОВ

Формат ответа:
```
ВОПРОСЫ ПЕРЕД ИСПОЛНЕНИЕМ ТЗ-1:

1. [вопрос или противоречие]
2. [слепая зона]
3. [чего не хватает]
4. [причина которая может помешать выполнению]
...
```

Только после ответов на вопросы — приступай к разработке.
