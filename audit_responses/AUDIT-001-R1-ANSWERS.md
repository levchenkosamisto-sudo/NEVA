# NEVA AUDIT-001 — ОТВЕТЫ ИСПОЛНИТЕЛЯ (Этап 3)
# Директор: Серж | Архитектор: Claude | Дата: 2026-06-22

---

## CHATGPT — Q1: Архитектурная схема NEVA

**Вопрос:** Какова архитектурная схема NEVA — агенты, их роли, механизм оркестрации?

**Ответ:** NEVA построена на 5 слоях:
- **L0 Director** — Серж → Claude Desktop → Approval Gate :8766
- **L1 Orchestration** — FlagmanRouter (Cerebras→Groq→GitHub→OpenRouter→qwen→llama) + dispatcher
- **L2 Execution** — MCP Server v2.4 (порт 9000+9001) + Medic L1/L2/L3
- **L3 Knowledge** — Kuzu graph DB (P16 атомы) + SQLite + GitHub SSOT
- **L4 Reliability** — ThermalGuard v9.4 + IntegrityChecker + SchemaGuard + Watchdog

---

## CHATGPT — Q2: Модели

**Вопрос:** Какие модели используются?

**Ответ:** 6 провайдеров в порядке приоритета:
1. Cerebras gpt-oss-120b — PRIMARY (0.009с)
2. Groq llama-3.3-70b — RESERVE (0.016с)
3. GitHub Models — GPT-4o, Gemini, DeepSeek R1 (бесплатно)
4. OpenRouter×2 — mistral-7b + meta-llama (~2000 запросов/день)
5. qwen2.5:7b (4.7GB) — LOCAL PRIMARY
6. llama3.2:3b (2GB) — FALLBACK

---

## CHATGPT — Q3: Память и контекст

**Вопрос:** Как реализовано управление памятью и контекстом?

**Ответ:** Три слоя:
- **Kuzu graph DB** — структурные связи и P16 атомы (8 полей: id, content, type, source, timestamp, tags, links, embedding)
- **Graphiti-core** — временной граф эпизодов (планируется Этап 2)
- **GitHub** — SSOT 500GB для кода, документов, истории чатов
- **SQLite** — metadata, логи, topic locks
- Контекст передаётся через handoff-пакеты (~500 токенов вместо полной истории)

---

## CHATGPT — Q4: Инструменты (MCP, API, shell)

**Вопрос:** Какая система инструментов используется?

**Ответ:** MCP Server v2.4 на порту 9000 (JSON-RPC) + Dashboard на 9001. Инструменты: file_read/write, shell_exec, script_deploy, git_tools, neva_graphiti, system_tools. Approval Gate :8766 блокирует деструктивные операции до подтверждения Директора.

---

## CHATGPT — Q5: Производительность

**Вопрос:** Задержки, токены, параллелизм, CPU/GPU?

**Ответ:** Cerebras 0.009с, Groq 0.016с. Все процессы через launchd (не параллельные потоки). Neural Engine не используется явно — Ollama работает через Metal. Токен-экономия: Claude читает только архитектуру, код пишет Cursor по JSON-спецификации.

---

## CHATGPT — Q6: Надёжность (retry, watchdog)

**Вопрос:** Как реализовано восстановление после ошибок?

**Ответ:** Трёхуровневый авторемонт:
- **L1 Medic** — автоматический restart процесса
- **L2 AI Repair** — Cerebras/Groq анализирует ошибку и патчит
- **L3 Claude** — эскалация к архитектору при CHRONIC
- **Exponential backoff**: 60с→5м→15м→30м→1ч
- **Watchdog** — launchd plist, перезапуск при падении

---

## CHATGPT — Q7: Безопасность

**Вопрос:** Права доступа, shell-команды, утечка данных?

**Ответ:** neva_integrity_checker.py — SHA256+HMAC baseline 11 файлов. mcp_gate_server.py — whitelist разрешённых операций. schema_guard.py — защита схемы Kuzu. API-ключи только в macOS Keychain, не в коде. Approval Gate для деструктивных shell-операций.

---

## CHATGPT — Q8: Экономика токенов

**Вопрос:** Стоимость токенов, контроль расхода?

**Ответ:** Billing Guard (планируется Этап 2A): дневной лимит $0.50 на OpenRouter, блокировка платных моделей без Approval. ~2000 бесплатных запросов/день через OpenRouter + неограниченно через GitHub Models. Claude Desktop — только архитектурные решения.

---

## CHATGPT — Q9: Mac M1 оптимизация

**Вопрос:** MLX/Ollama, unified memory, локальные модели?

**Ответ:** Ollama с Metal backend. qwen2.5:7b требует ~8GB RAM, e5-small RAG ~2GB — взаимоисключающая активация (не одновременно). llama3.2:3b (2GB) — постоянный fallback. MLX не используется (Ollama достаточно). Мониторинг RAM через ThermalGuard.

---

## GEMINI — Q1: Unified Memory

**Вопрос:** Как NEVA обходит проблему 16GB RAM на M1?

**Ответ:** Взаимоисключающая активация: qwen2.5:7b (8GB) ИЛИ e5-small RAG (2GB) — никогда одновременно. RAMManager переключает режимы. При простое >5 мин — выгрузка модели. Статический вес моделей: llama3.2:3b всегда в памяти (2GB), остальные по требованию. ~6GB остаётся на OS + NEVA процессы.

---

## GEMINI — Q2: Execution Backends

**Вопрос:** ANE или MPS/CPU?

**Ответ:** Ollama использует Metal (GPU ядра M1) автоматически для inference. ANE явно не задействован — llama.cpp через Ollama выбирает Metal. CPU используется для Python-процессов NEVA (не inference). Нет явного MLX — это задача Этапа 3.

---

## GEMINI — Q3: SSD деградация при свопинге

**Вопрос:** Мониторинг износа SSD при переполнении RAM?

**Ответ:** Текущий статус: НЕ МОНИТОРИТСЯ — это открытый риск R15. ThermalGuard v9.4 следит за CPU/температурой, но не за memory_pressure и SSD write. Задача Этапа 2: добавить мониторинг memory_pressure + kill неактивных процессов при >85% RAM.

---

## GEMINI — Q4: Routing Overhead

**Вопрос:** Сколько токенов тратится на маршрутизацию?

**Ответ:** FlagmanRouter — простая цепочка приоритетов по health-check (не LLM-роутинг). Overhead минимален: проверка статуса провайдера через HTTP health-check каждые 60с. Токены на маршрутизацию = 0 (rule-based, не AI-based).

---

## GEMINI — Q5: Loop Detection

**Вопрос:** Защита от бесконечных вызовов между агентами?

**Ответ:** Exponential backoff с CHRONIC detection: после 5 неудачных попыток — статус CHRONIC, эскалация к Директору. Topic Lock (SQLite coordinator) предотвращает параллельные конкурирующие задачи. Write Queue (asyncio.Lock) — единственный писатель в Kuzu.

---

## GEMINI — Q6: Консистентность состояния

**Вопрос:** Синхронизация State между агентами при ограниченной RAM?

**Ответ:** Единая точка записи — Write Queue (asyncio.Lock). Topic Lock координирует задачи. State хранится в Kuzu (граф) + SQLite (metadata). Агенты не держат state в памяти — читают из БД. При падении агента state восстанавливается из snapshot.

---

## GEMINI — Q7: Data Leakage

**Вопрос:** Гарантия локального контура, нет ли скрытых запросов к внешним API?

**Ответ:** НЕТ гарантии полного локального контура — NEVA явно использует 8 внешних API-провайдеров. Это архитектурное решение, не баг. Локальный fallback: qwen2.5:7b + llama3.2:3b через Ollama. При отключении интернета — только локальные модели. Billing Guard (Этап 2A) добавит контроль какие данные уходят наружу.

---

## GEMINI — Q8: Prompt Injection

**Вопрос:** Защита от перехвата через системные промпты?

**Ответ:** Текущий статус: ЧАСТИЧНО. mcp_gate_server.py фильтрует опасные shell-команды. Approval Gate блокирует деструктивные операции. Но явной защиты от prompt injection в цепочке агентов нет — это открытый риск для Этапа 2. SchemaGuard защищает схему данных, но не промпты.

---

## DEEPSEEK — Q1: FSM и ThermalGuard

**Вопрос:** Как 32 из 34 PASS соотносятся с 9 состояниями FSM, и какие два не проходят?

**Ответ:** 9 состояний FSM: NORMAL, WARM, HOT, CRITICAL, EMERGENCY, COOLING, RECOVERY, MAINTENANCE, UNKNOWN. 34 теста покрывают переходы между состояниями + граничные условия (не 1 тест = 1 состояние). 2 FAIL: переход EMERGENCY→RECOVERY при одновременном CPU spike + network timeout (race condition). Задача Этапа 2: исправить race condition.

---

## DEEPSEEK — Q2: Конфликт qwen + e5-small

**Вопрос:** Механизм обнаружения и разрешения конфликта активации?

**Ответ:** RAMManager (планируется) мониторит memory_pressure. Текущая реализация: взаимоисключение через launchd — только один процесс запускается. При запросе семантического поиска: если qwen активна → ждать выгрузки (таймаут 30с) → запустить e5-small. При RAM >85% → принудительная выгрузка qwen.

---

## DEEPSEEK — Q3: FlagmanRouter переключение

**Вопрос:** Как определяется момент переключения Cerebras→Groq?

**Ответ:** Health-check каждые 60с: HTTP запрос к провайдеру с таймаутом 5с. Если timeout/error → провайдер помечается DEGRADED → следующий в цепочке. Нет синхронизации state при переключении — каждый запрос независим (stateless роутинг). In-flight запросы при сбое: retry на следующем провайдере с тем же промптом.

---

## DEEPSEEK — Q4: Medic триггеры L1→L2→L3

**Вопрос:** Критерии перехода между уровнями?

**Ответ:**
- **L1** (restart): процесс не отвечает на health-check >30с
- **L2** (AI repair): L1 не помог после 3 попыток ИЛИ ошибка в коде (traceback detected)
- **L3** (Claude): L2 не помог после 3 попыток ИЛИ CHRONIC status ИЛИ архитектурная проблема
- Контекст для L3: последние 50 строк лога + traceback + версия файла + diff последних изменений

---

## DEEPSEEK — Q5: Атомарность Kuzu при параллельных запросах

**Вопрос:** Как MCP обеспечивает атомарность записи в Kuzu на портах 9000 и 9001?

**Ответ:** Write Queue (asyncio.Lock) — единственный механизм. Все записи в Kuzu идут через одну очередь независимо от порта. Порт 9001 — только read-only Dashboard (не пишет). Транзакций в Kuzu embedded нет — atomicity обеспечивается через Lock на уровне Python.

---

## DEEPSEEK — Q6: DUMA watcher синтез

**Вопрос:** Как watcher обрабатывает GitHub input/output?

**Ответ:** neva_github_watcher.py (в разработке): polling GitHub репо каждые 60с → обнаруживает новые файлы в output/ → Cerebras синтезирует ответы аудиторов в единый документ → сохраняет в audit_responses/ → уведомляет Директора через Approval Gate. Алгоритм согласования версий: last-write-wins по timestamp файла.

---

## DEEPSEEK — Q7: Approval Gate условия + backoff

**Вопрос:** При каких условиях запрашивается Approval, как backoff интегрирован с CHRONIC?

**Ответ:** Approval Gate триггеры: shell_exec с sudo, удаление файлов, изменение .env/ключей, деплой в продакшн, платные API вызовы >$0.10. CHRONIC + backoff: при достижении CHRONIC статуса backoff останавливается (не продолжает ретраи), создаётся Approval запрос к Директору с полным контекстом проблемы.

---

## DEEPSEEK — Q8: Распределение 8 API-ключей

**Вопрос:** Стратегия распределения и ротации при исчерпании лимитов?

**Ответ:** Ключи хранятся в macOS Keychain. FlagmanRouter назначает роли: Cerebras+Groq — оркестрация и аудит, GitHub Models — бесплатные задачи, OpenRouter×2 — параллельные запросы (2 аккаунта = 2000 запросов/день), OpenAI/Gemini/DeepSeek — специализированные задачи. При исчерпании лимита провайдер помечается RATE_LIMITED → следующий в цепочке. Ротация: автоматически через FlagmanRouter.

---

## DEEPSEEK — Q9: Незавершённые 40-50% MVP

**Вопрос:** Что именно не реализовано в Этапе 1?

**Ответ:** Незавершено:
- Graphiti-core (реальный, сейчас MockGraph)
- e5-small семантический поиск
- TTL Policy (заглушка)
- Trust Engine (не подключён к pipeline)
- GDrive backup (TODO)
- K_truth метрика (не считается)
- Guardian Hook (не индексирует)
- neva_langgraph_pipeline.py (не реализован)
- self-test backup: SKIP→PASS
- MCP Executor интеграция (DRAFT)

---

## GROK — Q1: Общая архитектура

**Вопрос:** Какова общая архитектура NEVA (модули, слои, ключевые компоненты)?

**Ответ:** См. ответ ChatGPT-Q1. 5 слоёв: Director→Orchestration→Execution→Knowledge→Reliability. Ключевые модули: FlagmanRouter, ThermalGuard, Medic, MCP Server, Kuzu, DUMA, Approval Gate.

---

## GROK — Q2: Оркестрация AI-агентов

**Вопрос:** Как NEVA управляет оркестрацией AI-агентов на Mac M1?

**Ответ:** Оркестрация через MCP Server (JSON-RPC :9000). Claude Desktop — архитектор, получает задачи от Директора. FlagmanRouter выбирает провайдера для каждого запроса. Медик следит за процессами. Все агенты управляются через launchd plist — OS-level supervision.

---

## GROK — Q3: Межмодульное взаимодействие

**Вопрос:** Какие механизмы для межмодульного взаимодействия?

**Ответ:** HTTP (FastAPI :8000 + MCP :9000+9001 + Approval :8766), asyncio.Queue для внутренних сообщений, SQLite для координации (Topic Lock), Kuzu для обмена знаниями между агентами, файловая система (governance/, state/) для документов и конфигов.

---

## GROK — Q4: Обработка задач и ресурсы

**Вопрос:** Как реализована обработка задач и распределение ресурсов?

**Ответ:** Task Queue через asyncio + SQLite (надёжность при рестарте). Dispatcher (dispatcher/dispatcher.py) маршрутизирует HTTP→executor. Ресурсы: RAM контролируется через взаимоисключающую активацию моделей. CPU — без явного ограничения (ThermalGuard реагирует на перегрев). Приоритизация: задачи Директора > фоновый аудит.

---

## GROK — Q5: Технологии и фреймворки

**Вопрос:** Какие технологии и фреймворки лежат в основе NEVA?

**Ответ:** Python 3.12 (Homebrew venv), FastAPI, Kuzu (embedded graph DB), SQLite, asyncio, Ollama (Metal backend), Playwright (веб-автоматизация), launchd (process management), GitHub API, macOS Keychain. Планируется: Graphiti-core, e5-small, LangGraph (под вопросом).

---

## GROK — Q6: Безопасность и изоляция

**Вопрос:** Как обеспечивается безопасность и изоляция компонентов?

**Ответ:** SHA256+HMAC integrity check (neva_integrity_checker.py), mcp_gate_server.py whitelist, schema_guard.py, Approval Gate для деструктивных операций, API ключи только в Keychain. Изоляция: DEV sandbox (BASE_DIR) планируется Этап 2A. Сетевой MCP :9000 независим от Claude Desktop.

---

## GROK — Q7: Масштабирование и обработка ошибок

**Вопрос:** Как NEVA масштабируется и обрабатывает ошибки?

**Ответ:** Горизонтальное масштабирование не предусмотрено (single Mac M1). Вертикальное: добавление провайдеров в FlagmanRouter. Ошибки: Medic L1/L2/L3 + exponential backoff + CHRONIC detection. При критических ошибках: Buffer Middleware возвращает 202 (очередь) вместо отказа.

---

## GROK — Q8: Поток данных

**Вопрос:** Поток данных от входа пользователя до результата?

**Ответ:**
1. Директор → Claude Desktop (MCP клиент)
2. Claude Desktop → MCP Server :9000 (JSON-RPC)
3. MCP Server → dispatcher.py (маршрутизация)
4. dispatcher → executor (нужный инструмент)
5. executor → Kuzu/GitHub/shell (исполнение)
6. Если нужен AI → FlagmanRouter → провайдер (Cerebras/Groq/...)
7. Ответ → MCP Server → Claude Desktop → Директор
8. Критические операции: шаг 3→ Approval Gate :8766 → Директор подтверждает → продолжение
