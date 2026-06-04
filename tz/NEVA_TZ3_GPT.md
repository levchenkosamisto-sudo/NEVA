# ТЗ-3: OPERATIONS LAYER
## Исполнитель: GPT
## Проект: NEVA v3.5
## Дата: 2026-06-04

---

## ОБЯЗАТЕЛЬНАЯ ПРОЦЕДУРА ПЕРЕД ИСПОЛНЕНИЕМ

**Прежде чем писать код, GPT ОБЯЗАН:**

1. **Задать вопросы** по всем неясным местам ТЗ
2. **Назвать противоречия** в требованиях
3. **Назвать слепые зоны** — что не описано, но нужно для реализации
4. **Назвать причины** которые могут помешать выполнить ТЗ или его параметры
5. **Назвать чего не хватает** в ТЗ для полноценной реализации

Только после получения ответов — приступать к разработке.
Формат: "ВОПРОСЫ ПЕРЕД ИСПОЛНЕНИЕМ ТЗ-3" → список вопросов и замечаний.

---

## КОНТЕКСТ

ТЗ-3 — Operations Layer: мониторинг, диагностика, CLI, буферизация.
Это самый критичный слой для работы Директора в реальном времени.

**Зависимости:**
```python
from neva_metrics_collector import record_k_truth, get_k_truth_history  # ТЗ-1
from neva_context_api import app  # FastAPI app из ТЗ-2
```

**Железо:**
- MacBook Air M1 8GB RAM, 228GB SSD
- macOS (BSD sed, launchd, osascript для уведомлений)
- Ollama: llama3.2:3b (2GB), qwen2.5:7b (4.7GB), KEEP_ALIVE=1m

---

## МОДУЛИ ТЗ-3 (7 файлов)

1. `neva_health_monitor.py`
2. `neva_self_diagnostics.py`
3. `neva_cli.py`
4. `neva_buffer_retry.py`
5. `neva_ollama_watchdog.py`
6. `neva_watchdog_install.py`
7. `.env.example`

---

## ДЕТАЛЬНЫЕ ТРЕБОВАНИЯ

### 1. neva_health_monitor.py — Health Monitor M1 (D1, D4: 75-80%)

**Что делает:** Мониторинг ресурсов M1 Mac. Трендовый анализ. Алерты Директору.

**Метрики для сбора (каждые 60 секунд):**
```python
{
    "timestamp": str,           # UTC ISO
    "ram_used_mb": float,       # psutil.virtual_memory().used / 1024**2
    "ram_total_mb": float,
    "ram_percent": float,
    "cpu_percent": float,
    "disk_free_gb": float,      # shutil.disk_usage("/").free / 1024**3
    "disk_percent": float,
    "ollama_running": bool,
    "neva_api_up": bool,
    "kuzu_connected": bool,
    "k_truth": float
}
```

**Трендовый анализ (D4: 80%):**
- Sliding window: последние 60 замеров (1 час)
- Линейная регрессия по RAM
- Если RAM растёт 3 замера подряд → WARNING
- Если тренд предсказывает OOM через < 30 минут → CRITICAL алерт

**АЛЕРТЫ (macOS notifications через osascript):**
```python
def notify_director(title: str, message: str, urgent: bool = False):
    """macOS уведомление через osascript."""
    import subprocess
    script = f'display notification "{message}" with title "NEVA: {title}"'
    subprocess.run(["osascript", "-e", script])

# Пороги алертов:
ALERTS = {
    "ram_percent > 85":    ("⚠️ RAM", "RAM > 85%"),
    "ram_percent > 95":    ("🚨 RAM КРИТИЧНО", "RAM > 95%"),
    "disk_free_gb < 20":   ("⚠️ SSD", f"Свободно < 20GB"),
    "disk_free_gb < 10":   ("🚨 SSD КРИТИЧНО", "Свободно < 10GB"),
    "k_truth < 0.70":      ("⚠️ K_truth", f"K_truth упал ниже 0.70"),
    "neva_api_up == False": ("🚨 API", "NEVA API недоступен"),
}
```

**Режим batch lock при Ollama активном:**
```python
if ollama_active and ram_percent > 75:
    logger.warning("Ollama активен + RAM > 75% — batch extraction заблокирован")
    # POST /api/v1/admin/batch_lock
```

**APScheduler расписание:**
```python
scheduler.add_job(collect_metrics, 'interval', seconds=60, id='health_monitor')
scheduler.add_job(analyze_trends, 'interval', minutes=5, id='trend_analysis')
```

**Метрика приёмки:**
- [ ] RAM растёт 3 замера подряд → WARNING в логах
- [ ] disk_free < 20GB → macOS уведомление
- [ ] k_truth < 0.70 → уведомление
- [ ] neva self-test включает проверку Health Monitor

---

### 2. neva_self_diagnostics.py — Self Diagnostics (D1: 75%)

**Что делает:** Единый runner для всех диагностических проверок.

**Команды:**
```bash
python neva_self_diagnostics.py --health    # быстрая проверка (< 5с)
python neva_self_diagnostics.py --diag      # полная диагностика (< 30с)
python neva_self_diagnostics.py --self-test # все тесты (< 60с)
```

**8 тестов для --self-test:**
```
1. Kuzu: файл neva.db существует, Connection открывается
2. Graphiti: /api/v1/health возвращает {"kuzu": "connected"}
3. Ollama: ollama list показывает llama3.2:3b и qwen2.5:7b
4. Gemini API: тестовый запрос < 5с
5. write_queue: тестовая запись без ошибок
6. backup: neva_backup/ директория существует, git статус OK
7. Topic Lock: acquire → release работает
8. P16 индекс: /api/v1/search возвращает атом с непустым source_path
```

**Вывод --health:**
```
✓ Kuzu: connected (file-based, 142 facts)
✓ Graphiti: ready
✓ Ollama: running (llama3.2:3b, qwen2.5:7b)
✓ Gemini API: reachable (0.8s)
✓ write_queue: ready (lock free)
✓ K_truth: 0.81
⚠ RAM: 67% (5.4GB / 8GB)
✓ SSD: 36GB free
```

**Вывод --self-test:**
```
Running 8 tests...
1/8 ✓ Kuzu connection
2/8 ✓ Graphiti health
3/8 ✓ Ollama models
4/8 ✓ Gemini API
5/8 ✓ write_queue
6/8 ✓ backup directory
7/8 ✓ Topic Lock
8/8 ✓ K_truth formula
Result: 8/8 PASS (took 12.3s)
```

**Метрика приёмки:**
- [ ] --health завершается < 5 секунд
- [ ] --self-test: 8/8 тестов за < 60 секунд
- [ ] Любой тест с ✗ → exit code 1

---

### 3. neva_cli.py — CLI (D1)

**Что делает:** Командная строка для Директора. Все команды через /api/v1/.

**Команды:**
```bash
neva health              # → GET /api/v1/health
neva stats               # → GET /api/v1/stats
neva metrics             # → GET /api/v1/metrics
neva state               # → GET /api/v1/state
neva export              # → GET /api/v1/export (admin)
neva backup              # запустить backup вручную
neva self-test           # → neva_self_diagnostics.py --self-test
neva start               # запустить NEVA сервер
neva stop                # остановить
neva status              # статус сервера
```

**Конфигурация:**
```python
NEVA_HOST = os.getenv("NEVA_HOST", "http://localhost:8000")
NEVA_TOKEN = os.getenv("NEVA_ADMIN_TOKEN", "")
```

**Метрика приёмки:**
- [ ] `neva health` → JSON статус
- [ ] `neva self-test` → 8/8 или список ошибок
- [ ] Все команды используют /api/v1/ prefix

---

### 4. neva_buffer_retry.py — FastAPI Buffer Middleware (E1 offline)

**ВАЖНО:** Это FastAPI Middleware, не изолированный скрипт.
Это было замечанием GPT в предыдущем аудите — исправлено в v3.5.

**Что делает:** Перехватывает POST запросы при недоступности Graphiti.
Агенты получают 202 Accepted вместо 503. Буферизация в cr-sqlite.

**ТОЧНАЯ РЕАЛИЗАЦИЯ:**
```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class NEVABufferMiddleware(BaseHTTPMiddleware):
    WRITE_ENDPOINTS = {"/api/v1/extract", "/api/v1/writeback"}
    MAX_BUFFER_SIZE = 5 * 1024 * 1024  # 5MB

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path in self.WRITE_ENDPOINTS:
            content_length = int(request.headers.get("content-length", 0))
            if content_length > self.MAX_BUFFER_SIZE:
                return JSONResponse(
                    {"error": "payload_too_large",
                     "max_bytes": self.MAX_BUFFER_SIZE},
                    status_code=413)
            if not await is_graphiti_available():
                body = await request.body()
                await buffer_write({
                    "endpoint": request.url.path,
                    "body": body.decode("utf-8"),
                    "headers": dict(request.headers),
                    "queued_at": time.time()  # Unix epoch UTC
                })
                return JSONResponse(
                    {"status": "buffered", "retry_scheduled": True},
                    status_code=202)
        return await call_next(request)

# Регистрация в main app (в neva_context_api.py):
# app.add_middleware(NEVABufferMiddleware)
```

**Retry логика:**
```python
async def retry_buffered():
    """Воспроизвести буферизованные запросы когда Graphiti доступен."""
    if not await is_graphiti_available():
        return
    pending = await get_buffered_requests()
    for req in pending:
        await replay_request(req)
        await mark_replayed(req["id"])
```

**APScheduler:**
```python
scheduler.add_job(retry_buffered, 'interval', minutes=1, id='buffer_retry')
```

**Метрика приёмки:**
- [ ] POST при Graphiti down → 202 (не 503)
- [ ] Payload > 5MB → 413
- [ ] Graphiti восстановлен → pending запросы воспроизведены
- [ ] Middleware зарегистрирован в FastAPI app

---

### 5. neva_ollama_watchdog.py — Ollama Watchdog

**Что делает:** Следит за Ollama. Перезапускает если упал.
Учитывает KEEP_ALIVE=1m (модель выгружается сама — это нормально).

**Логика:**
```python
async def check_ollama():
    try:
        r = await httpx.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            return True  # Ollama работает
    except:
        pass
    return False  # Ollama не отвечает

async def restart_ollama():
    """Перезапустить Ollama через launchctl."""
    subprocess.run(["launchctl", "start", "com.ollama"])
    await asyncio.sleep(10)
    if await check_ollama():
        logger.info("Ollama перезапущен успешно")
        notify_director("Ollama", "Перезапущен автоматически")
    else:
        logger.error("Ollama не поднялся после перезапуска!")
        notify_director("🚨 Ollama", "Не запускается! Нужна ручная проверка")
```

**ВАЖНО:** Отсутствие моделей в памяти (KEEP_ALIVE=1m выгрузил) ≠ Ollama упал.
Проверять через `/api/tags`, не через процесс.

**APScheduler:**
```python
scheduler.add_job(check_ollama_health, 'interval', minutes=5, id='ollama_watchdog')
```

**Метрика приёмки:**
- [ ] Ollama отвечает → watchdog молчит
- [ ] Ollama не отвечает → попытка перезапуска
- [ ] После 3 неудачных попыток → алерт Директору

---

### 6. neva_watchdog_install.py — launchd (macOS autostart)

**Что делает:** Устанавливает NEVA как macOS LaunchAgent (автозапуск при логине).

**Plist путь:** `~/Library/LaunchAgents/com.neva.server.plist`

```python
PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neva.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>{venv_python}</string>
        <string>{neva_main}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{neva_dir}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>{neva_dir}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{neva_dir}/logs/neva.log</string>
    <key>StandardErrorPath</key>
    <string>{neva_dir}/logs/neva_error.log</string>
</dict>
</plist>"""

def install():
    # Генерировать plist с реальными путями
    # launchctl load ~/Library/LaunchAgents/com.neva.server.plist

def uninstall():
    # launchctl unload + удалить plist

def status():
    # launchctl list | grep com.neva
```

**Команды:**
```bash
python neva_watchdog_install.py --install
python neva_watchdog_install.py --uninstall
python neva_watchdog_install.py --status
```

**Метрика приёмки:**
- [ ] --install → plist создан + launchctl load
- [ ] --status → показывает running/stopped
- [ ] NEVA запускается при логине пользователя arka

---

### 7. .env.example — Шаблон конфигурации

```bash
# NEVA v3.5 — Шаблон .env
# Скопировать: cp .env.example .env
# Заполнить все поля перед запуском

# ── AI API КЛЮЧИ ────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key_here
CEREBRAS_API_KEY=your_cerebras_api_key_here
GROQ_API_KEY=your_groq_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
MISTRAL_API_KEY=your_mistral_api_key_here

# ── NEVA ТОКЕНЫ ДЛЯ АГЕНТОВ ─────────────────────
NEVA_TOKEN_CLAUDE=generate_secure_token_here
NEVA_TOKEN_GPT=generate_secure_token_here
NEVA_TOKEN_GEMINI=generate_secure_token_here
NEVA_TOKEN_DEEPSEEK=generate_secure_token_here
NEVA_TOKEN_GUARDIAN=generate_secure_token_here
NEVA_ADMIN_TOKEN=generate_secure_admin_token_here

# ── AI ROUTER ───────────────────────────────────
LLM_PRIMARY=gemini
LLM_SECONDARY=cerebras
LLM_FAST=groq
LLM_BACKUP=deepseek_openrouter
LLM_FALLBACK=mistral

# ── OLLAMA ──────────────────────────────────────
OLLAMA_KEEP_ALIVE=1m
OLLAMA_NUM_PARALLEL=1

# ── ПУТИ ────────────────────────────────────────
NEVA_DB_PATH=./neva.db
NEVA_PIPELINE_DB=./neva_pipeline.db
NEVA_METRICS_DB=./neva_metrics.db

# ── СЕРВЕР ──────────────────────────────────────
NEVA_HOST=0.0.0.0
NEVA_PORT=8000

# ── GIT/BACKUP ──────────────────────────────────
GITHUB_TOKEN=your_github_token_here
NEVA_BACKUP_DIR=./neva_backup

# ── ДОПОЛНИТЕЛЬНО (опционально) ─────────────────
COHERE_API_KEY=your_cohere_key_here   # не используется в router
DEEPSEEK_API_KEY=your_deepseek_key_here
```

---

## ТРЕБУЕМЫЕ ПАРАМЕТРЫ СИСТЕМЫ (твоя часть)

| Параметр | Требование | Как измерить |
|---|---|---|
| D1 Health Dashboard | 75% | --health < 5с, все ключевые метрики |
| D4 Трендовый мониторинг | 80% | sliding window 1ч, алерты работают |
| --self-test | 8/8 за < 60с | запустить в чистом окружении |
| Buffer 202 | при Graphiti down | тест с остановленным Graphiti |
| Buffer replay | при восстановлении | тест restart Graphiti |
| Disk alert | при < 20GB | тест с mock disk_usage |
| RAM trend alert | 3 подряд рост | тест с mock данными |
| launchd autostart | при логине arka | тест restart Mac |

---

## ОГРАНИЧЕНИЯ

1. **macOS sed:** `sed -i ''` — обязательно, иначе ломается
2. **osascript:** единственный способ macOS уведомлений
3. **launchd не systemd** — plist формат, LaunchAgents не LaunchDaemons
4. **Middleware регистрируется в ТЗ-2** (neva_context_api.py) — координировать с Gemini
5. **KEEP_ALIVE=1m** — отсутствие Ollama модели в памяти ≠ Ollama упал
6. **workers=1** — uvicorn, иначе asyncio.Lock не работает

---

## ВЗАИМОДЕЙСТВИЕ С ТЗ-1 И ТЗ-2

Что нужно от ТЗ-1 (DeepSeek):
```python
from neva_metrics_collector import record_k_truth, get_k_truth_history
# Используется в Health Monitor для K_truth алертов
```

Что нужно от ТЗ-2 (Gemini):
```python
# neva_buffer_retry.py регистрируется в neva_context_api.py:
# app.add_middleware(NEVABufferMiddleware)
# Координировать с Gemini — они добавляют строку в их файл
```

---

## НАЧНИ С ВОПРОСОВ

Формат ответа:
```
ВОПРОСЫ ПЕРЕД ИСПОЛНЕНИЕМ ТЗ-3:

1. [вопрос или противоречие]
2. [слепая зона]
3. [чего не хватает]
4. [причина которая может помешать]
...
```

Только после ответов — приступай к разработке.
