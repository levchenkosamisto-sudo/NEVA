# ИТОГ ЧАТА 2026-06-03 — Этап 0 и финализация стека NEVA v3.5

**Дата:** 2026-06-03  
**Участники:** Серж (Директор), Claude (Главный архитектор)  
**Результат:** Этап 0 пройден, стек подтверждён на реальном Mac M1

---

## 1. ЧТО БЫЛО СДЕЛАНО НА MAC (ОЧИСТКА)

### Удалено
| Что | Команда | Освобождено |
|---|---|---|
| llama3.2:latest (дубликат) | `ollama rm llama3.2:latest` | 0 (тот же файл) |
| arka-dispatcher:latest | `ollama rm arka-dispatcher:latest` | ~2GB SSD |
| Модели Ollama у sergey | `sudo rm -rf /Users/sergey/.ollama/models/` | ~15GB SSD |
| Docker LaunchDaemons plist | `sudo rm -f /Library/LaunchDaemons/com.docker.*.plist` | мёртвые файлы |

**Итог очистки:** свободно было 22GB → стало **36GB** (+14GB)

### Решение Директора по моделям
- `arka-dispatcher:latest` — **удалена** (не нужна в NEVA)
- `llama3.2:latest` — **удалена** (дубликат llama3.2:3b, одинаковый ID)

### Остались у arka
| Модель | Размер | Назначение |
|---|---|---|
| llama3.2:3b | 2.0 GB | LOCAL-LIGHT, быстрые офлайн задачи |
| qwen2.5:7b | 4.7 GB | LOCAL-HEAVY, сложные офлайн задачи |

---

## 2. УСТАНОВЛЕННЫЕ ПАКЕТЫ (~/Documents/NEVA/venv)

```bash
pip install "graphiti-core[kuzu]" kuzu langgraph langchain-core \
            sentence-transformers fastapi uvicorn \
            slowapi apscheduler psutil cerebras-cloud-sdk
```

### Версии (подтверждены установкой)
| Пакет | Версия |
|---|---|
| kuzu | 0.11.3 |
| graphiti-core | 0.29.1 |
| langgraph | 1.2.4 |
| langchain-core | 1.4.0 |
| sentence-transformers | 5.5.1 |
| fastapi | 0.136.3 |
| uvicorn | 0.47.0 |
| slowapi | 0.1.9 |
| apscheduler | 3.11.2 |
| pydantic | 2.13.4 |
| httpx | 0.28.1 |
| cerebras-cloud-sdk | 1.67.0 |
| psutil | установлен |
| torch | 2.12.0 |
| transformers | 5.10.1 |
| numpy | 2.4.6 |
| openai | 2.40.0 |

**Важно:** флаг `--break-system-packages` НЕ нужен в активированном venv.

---

## 3. РЕЗУЛЬТАТЫ ЭТАПА 0 (все тесты на реальном Mac M1)

### Тест 1 — Kuzu ARM64
```python
import kuzu, os
db = kuzu.Database('test_neva.db')
conn = kuzu.Connection(db)
conn.execute('CREATE NODE TABLE IF NOT EXISTS Test (id INT64, PRIMARY KEY (id))')
conn.execute('CREATE (:Test {id: 1})')
result = conn.execute('MATCH (n:Test) RETURN count(n)').get_next()
# Результат: Kuzu работает. Узлов: 1 ✅
```

### Тест 2 — Правильный синтаксис KuzuDriver
```python
# ВАЖНО: параметры KuzuDriver.__init__:
# (self, db: str = ':memory:', max_concurrent_queries: int = 1)
driver = KuzuDriver(db='./neva.db')  # НЕ database_path!

# setup_schema — НЕ async (обычный вызов)
driver.setup_schema()

# Остальные — async:
await driver.build_indices_and_constraints()
await driver.execute_query(...)
await driver.close()
```

### Тест 3 — Graphiti + Kuzu совместимость
```
✓ Schema создана
✓ Индексы созданы  
✓ Graphiti + Kuzu: совместимость подтверждена ✅
```

### Тест 4 — 10 параллельных записей
```
asyncio.gather(*[write_one(i) for i in range(10)])
Параллельно записано узлов: 10 ✅
# KuzuDriver с max_concurrent_queries=1 сам сериализует запросы
```

### Тест 5 — RAM baseline замер
```
RAM до: 396 MB
RAM после Kuzu+Graphiti: 446 MB (+50 MB)
RAM после multilingual-e5-small: 351 MB (macOS перераспределил)
ИТОГО NEVA baseline: ~446 MB ✅
```
**Вывод:** расчётные 770MB оказались завышены вдвое. Реально ~446MB.

### Тест 6 — Backup restore
```
Записано фактов: 20
Экспортировано в JSONL: 20 строк
БД удалена
Восстановлено фактов: 20
✓ Restore OK: 20 → 20 совпадает ✅
```
**Важно:** при restore использовать MERGE (не CREATE) во избежание duplicate primary key.

### Тест 7 — Cerebras structured_output
```
gpt-oss-120b: {"fact": "The Earth orbits the Sun", "confidence": 0.99}
✓ structured_output работает ✅

zai-glm-4.7: ✗ Ошибка (NoneType) — не использовать
```

---

## 4. API КЛЮЧИ (~/Documents/NEVA/.env)

| Ключ | Статус | Назначение |
|---|---|---|
| GEMINI_API_KEY | ✅ есть | PRIMARY LLM |
| CEREBRAS_API_KEY | ✅ **добавлен в этом чате** | SECONDARY LLM |
| GROQ_API_KEY | ✅ есть | FAST LLM |
| DEEPSEEK_API_KEY | ✅ есть | BACKUP через OpenRouter |
| OPENROUTER_API_KEY | ✅ есть | доступ к GPT и другим |
| OPENROUTER_API_KEY_2 | ✅ есть | второй аккаунт |
| MISTRAL_API_KEY | ✅ есть | FALLBACK |
| COHERE_API_KEY | ✅ есть | НЕ в Router (не подходит для extraction) |
| GITHUB_TOKEN | ✅ есть | Git синхронизация |
| XAI_API_KEY (Grok) | ❌ нет | не получен |
| OpenAI | ❌ нет | не нужен |
| Anthropic | ❌ нет | не нужен |

### Добавить в .env (Ollama настройки)
```bash
OLLAMA_KEEP_ALIVE=1m        # офлайн редко — выгружать через 1 мин
OLLAMA_NUM_PARALLEL=1       # для qwen2.5:7b
CEREBRAS_MODEL=gpt-oss-120b # подтверждённая модель
```

---

## 5. ФИНАЛЬНЫЙ AI ROUTER v3.5

| Уровень | Провайдер | Модель | Ключ |
|---|---|---|---|
| PRIMARY | Gemini API | gemini-1.5-flash | GEMINI_API_KEY |
| SECONDARY | Cerebras | gpt-oss-120b ← **НОВЫЙ** | CEREBRAS_API_KEY |
| FAST | Groq | llama-3.3-70b | GROQ_API_KEY |
| BACKUP | DeepSeek (OpenRouter) | deepseek-r1 | OPENROUTER_API_KEY |
| FALLBACK | Mistral | mistral-large | MISTRAL_API_KEY |
| LOCAL-HEAVY | Ollama | qwen2.5:7b | — |
| LOCAL-LIGHT | Ollama | llama3.2:3b | — |
| EMERGENCY | keyword extraction | — | — |

**Почему так:**
- Gemini PRIMARY: длинный контекст, отличные JSON схемы, высокая квота
- Cerebras SECONDARY: gpt-oss-120b — та же модель что в ARKA, structured_output подтверждён
- Groq FAST: только короткие запросы, rate limit 30 req/мин недостаточен для PRIMARY
- Cohere убран: не подходит для knowledge graph extraction

---

## 6. КЛЮЧЕВЫЕ АРХИТЕКТУРНЫЕ РЕШЕНИЯ

### P15 — Иерархия хранилищ (IMMUTABLE)
```
Kuzu (через Graphiti) = ИСТИНА (Kuzu — хранилище, Graphiti — слой доступа)
LangGraph SqliteSaver = ЖУРНАЛ выполнения pipeline
neva_metrics.db       = ТЕЛЕМЕТРИЯ (K_truth time-series)
cr-sqlite buffer      = ВРЕМЕННЫЙ буфер (offline)
Git backup JSONL      = АРХИВ (история, построчные диффы)
Google Drive snapshot = БЫСТРОЕ ВОССТАНОВЛЕНИЕ (бинарный snapshot)

При расхождении → Kuzu выигрывает.
```

### Двойной backup
```python
# JSONL delta → Git (каждые 6 часов)
# Kuzu snapshot → Google Drive (каждые 24 часа)
# Google Drive path: ~/Library/CloudStorage/GoogleDrive-levchenkosamisto@gmail.com/My Drive/NEVA/snapshots/

# Восстановление при сбое:
# 1. Restore Kuzu snapshot (секунды)
# 2. Донакатить JSONL delta (минуты)
# Потеря данных: максимум 6 часов
```

### neva_write_queue.py — правильная реализация
```python
import asyncio, inspect, logging

logger = logging.getLogger("neva.write_queue")
_write_lock = asyncio.Lock()  # Queue не нужна — только Lock
_write_counter = 0

async def write_to_graph(operation, *args, **kwargs):
    """
    Единственная точка записи в Kuzu граф.
    Kuzu имеет max_concurrent_queries=1 встроенно,
    Lock — дополнительная защита на уровне приложения.
    """
    global _write_counter
    async with _write_lock:
        _write_counter += 1
        logger.debug(f"Write #{_write_counter}: {operation.__name__}")
        try:
            result = operation(*args, **kwargs)
            if inspect.isawaitable(result):  # не iscoroutine — ловит все awaitable
                return await result
            return result
        except Exception as e:
            logger.error(f"Write #{_write_counter} failed: {e}")
            raise
```

### Topic Lock — SQLite persistent
```python
# В neva_pipeline.db (WAL mode)
# expires_at в UTC ISO для совместимости с SQLite
from datetime import datetime, timezone, timedelta

expires = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()

# Cleanup:
# DELETE WHERE expires_at < strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')
```

### K_truth формула (зафиксирована)
```python
TRUST_WEIGHTS = {
    "director_approved": 0.95,
    "guardian_hook":     0.88,
    "gemini":            0.82,
    "cerebras":          0.82,  # добавлен в этом чате
    "groq":              0.80,
    "llama":             0.65,
    "keyword":           0.55,
    "unknown":           0.60,
}

def calculate_k_truth(active_facts: list) -> float:
    if not active_facts:
        return 0.0
    weights = [TRUST_WEIGHTS.get(f.get("author_ai","unknown"), 0.60)
               for f in active_facts]
    return round(sum(weights) / len(weights), 3)

# confidence_update() при верификации Директором:
# verified=True: weight += 0.02 (max 0.95)
# verified=False: weight -= 0.03 (min 0.50)
```

### sed на macOS (BSD sed) — ВАЖНО
```bash
# ПРАВИЛЬНО для macOS M1:
sed -i '' "s|$OLD_EMBED_MODEL|$NEW_EMBED_MODEL|" .env
# Разделитель | вместо / (пути моделей содержат /)
# '' после -i обязательно для BSD sed
```

---

## 7. РЕШЕНИЯ ПРИНЯТЫЕ В ЭТОМ ЧАТЕ

| Решение | Статус | Обоснование |
|---|---|---|
| Kuzu вместо FalkorDB+Docker | ✅ ПРИНЯТО + ПОДТВЕРЖДЕНО | pip install, ARM64, нет Docker |
| Gemini как PRIMARY LLM | ✅ ПРИНЯТО | XAI_API_KEY отсутствует |
| Cerebras как SECONDARY | ✅ ПРИНЯТО + ПОДТВЕРЖДЕНО | gpt-oss-120b structured_output работает |
| Groq → роль FAST | ✅ ПРИНЯТО | rate limit 30 req/мин |
| Cohere убран из Router | ✅ ПРИНЯТО | не подходит для extraction |
| arka-dispatcher удалена | ✅ РЕШЕНИЕ ДИРЕКТОРА | не нужна в NEVA |
| llama3.2:latest удалена | ✅ ПРИНЯТО | дубликат |
| Модели sergey удалены | ✅ ВЫПОЛНЕНО | 15GB освобождено |
| Docker plist удалены | ✅ ВЫПОЛНЕНО | мёртвые файлы |
| OLLAMA_KEEP_ALIVE=1m | ✅ РЕШЕНИЕ ДИРЕКТОРА | офлайн редко |
| Двойной backup Git+GDrive | ✅ ПРИНЯТО | snapshot GDrive, delta Git |
| Cerebras CEREBRAS_API_KEY | ✅ ДОБАВЛЕН В .env | ключ получен и проверен |

---

## 8. ВАЖНЫЕ ТЕХНИЧЕСКИЕ НАХОДКИ

### KuzuDriver — не очевидное поведение
- Параметр `db=` (не `database_path=`)
- `setup_schema()` — синхронный метод (не await)
- `build_indices_and_constraints()` — async
- `max_concurrent_queries=1` встроен — Kuzu сам сериализует запросы
- Kuzu БД — это **директория** на диске (не один файл)
  - backup через `shutil.copytree()`, не `shutil.copy2()`

### Graphiti методы (подтверждены)
```python
# Доступные методы KuzuDriver:
build_indices_and_constraints, close, execute_query,
setup_schema, search_ops, episode_node_ops,
entity_node_ops, community_node_ops, graph_ops
```

### RAM на M1 (реальные замеры)
- Расчётный baseline: ~770MB
- Реальный baseline: **~446MB** (macOS Unified Memory эффективнее)
- После загрузки embedding модели: macOS перераспределяет → цифры нелинейные

### Cerebras модели (доступны)
- `gpt-oss-120b` — ✅ structured_output работает
- `zai-glm-4.7` — ❌ structured_output не работает (NoneType)

---

## 9. СТАТУС ДОКУМЕНТА NEVA-TASK-007 v3.5

### История версий
```
v1.0 → v1.1 → v2.0 → v3.0 → v3.1 → v3.2 → v3.3 → v3.4 → v3.5
Всего замечаний закрыто: 55+
```

### Текущий статус аудита v3.5
| Аудитор | Вердикт | Основание |
|---|---|---|
| DeepSeek-R2 | УТВЕРЖДАЮ ✅ | полный аудит v3.5 |
| DeepSeek-2 | УТВЕРЖДАЮ ✅ | полный аудит v3.5 |
| GPT | условно | нужен аудит с результатами Этапа 0 |
| Gemini | не проводился | нужен финальный аудит v3.5 |

### Что нужно в следующем чате
1. Передать v3.5 + результаты Этапа 0 аудиторам GPT и Gemini
2. Получить финальное APPROVED
3. После утверждения — передать ТЗ-1/2/3 исполнителям

---

## 10. СТРУКТУРА ПРОЕКТА

```
~/Documents/NEVA/
├── venv/                    — Python окружение (все пакеты установлены)
├── .env                     — API ключи (включая новый CEREBRAS_API_KEY)
├── governance/              — документы проекта
├── tools/neva_context_server/ — здесь будет код NEVA
├── neva_backup/             — JSONL delta файлы → Git
├── chats/                   — этот файл и другие итоги чатов
└── (вне репо) ~/Library/CloudStorage/.../NEVA/snapshots/ — Kuzu snapshots
```

### Файлы созданные в этом чате
| Файл | Описание |
|---|---|
| NEVA_TASK007_v3.5.txt | Финальный архитектурный документ |
| NEVA_CONTEXT_FOR_NEW_CHAT.md | Контекст для передачи в новый чат |
| test_backup_restore.py | Тест backup/restore (пройден ✅) |
| CHAT_2026-06-03_etap0-stek.md | Этот файл |

---

## 11. КОМАНДЫ ДЛЯ ВОСПРОИЗВЕДЕНИЯ ЭТАПА 0

```bash
# Активировать venv
cd ~/Documents/NEVA && source venv/bin/activate

# Проверить Kuzu
python -c "import kuzu; db=kuzu.Database('t.db'); import shutil; shutil.rmtree('t.db'); print('OK')"

# Проверить Graphiti+Kuzu
python -c "
import asyncio, shutil
from graphiti_core.driver.kuzu_driver import KuzuDriver
async def t():
    d = KuzuDriver(db='./t.db'); d.setup_schema()
    await d.build_indices_and_constraints(); await d.close()
    print('OK')
asyncio.run(t()); shutil.rmtree('./t.db')
"

# Проверить Cerebras
python -c "
import os; from dotenv import load_dotenv; load_dotenv('.env')
from cerebras.cloud.sdk import Cerebras
c = Cerebras(api_key=os.environ.get('CEREBRAS_API_KEY'))
r = c.chat.completions.create(model='gpt-oss-120b',
    messages=[{'role':'user','content':'Say OK in JSON: {\"status\":\"ok\"}'}],
    response_format={'type':'json_object'}, max_tokens=20)
print(r.choices[0].message.content)
"
```

---

*Итог составлен: 2026-06-04*  
*Следующий шаг: финальный аудит v3.5 → утверждение → передача ТЗ*
