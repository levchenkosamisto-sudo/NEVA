# ТЗ — ЭТАП 2: MCP СЕРВЕР + ПАМЯТЬ + GIT
## Задание для реализации после аудита ДУМЫ
**Дата:** 2026-06-27 | **Директор:** Серж | **Статус:** ЧЕРНОВИК — на аудит

---

## ЗАДАЧА 1 — MCP СЕРВЕР: ИНТЕГРАЦИЯ neva_audit_tools

### Цель
Перенести инструменты из sandbox/neva_audit_tools.py в основной MCP сервер :9000.
Все 4 веб-ИИ и Claude Desktop используют одни и те же инструменты.

### Требования
1. Добавить в neva_mcp_server.py три новых action:
   - `github_read` — читать файл из repo levchenkosamisto-sudo/NEVA по filepath
   - `write_result` — записывать результат аудитора в audit_responses/mcp_test/{auditor}.md
   - `ask_ai` (опционально) — вызывать API одного из 4 ИИ по имени

2. Добавить prompts/list + prompts/get endpoint для MCP SuperAssistant
   - Prompt "neva_instructions" — системный промпт для аудиторов

3. Запустить neva_audit_tools через launchd (постоянно)
   - Файл: ~/Library/LaunchAgents/com.neva.audit_tools.plist
   - Порт: 9100
   - KeepAlive: true

4. Обновить mcpconfig.json — добавить neva_audit_tools как постоянный сервер

### Критерии готовности
- [ ] DeepSeek успешно читает любой файл из GitHub через MCP
- [ ] DeepSeek успешно записывает ответ в audit_responses/
- [ ] Результат доступен через Claude Desktop через тот же action
- [ ] launchd запускает neva_audit_tools при старте системы

---

## ЗАДАЧА 2 — ПАМЯТЬ: ПОДКЛЮЧИТЬ e5-SMALL

### Цель
Активировать семантический поиск через уже установленную модель e5-small.
Текущий keyword-поиск заменить на векторный.

### Требования
1. Создать neva_semantic_search.py:
   - Загружать multilingual-e5-small из venv
   - Индексировать файлы из governance/ и docs/ в ChromaDB (embedded)
   - Метод search(query, top_k=5) → список файлов с релевантностью

2. Добавить action semantic_search в neva_mcp_server.py
   - Принимает: query (str), top_k (int, default=5)
   - Возвращает: [{path, score, snippet}]

3. Индексировать при запуске (или при изменении файла):
   - Все .md файлы из governance/ docs/ state/
   - Обновлять при git pull

4. RAM-ограничение M1 8GB:
   - e5-small ≈ 120MB — безопасно
   - НЕ запускать одновременно с qwen2.5:7b (4.7GB)

### Критерии готовности
- [ ] semantic_search("MCP сервер") возвращает релевантные документы
- [ ] Precision@5 ≥ 0.7 на тестовых запросах
- [ ] Индекс строится за < 30 сек
- [ ] Поиск отвечает за < 500ms

---

## ЗАДАЧА 3 — GIT: АВТОМАТИЗАЦИЯ КОММИТОВ

### Цель
После каждой завершённой задачи NEVA автоматически создавать git коммит.
Ветки для изоляции аудитов.

### Требования
1. Добавить action git_commit в neva_mcp_server.py:
   - Параметры: message (str), files (list, default=all changed)
   - git add → git commit → опционально git push

2. Добавить action git_branch:
   - create(name) — создать ветку
   - merge(name, into="main") — смержить
   - list() — список веток

3. Pre-commit hook:
   - Проверять что *.py файлы в governance/ нет
   - Проверять что .env не попал
   - Запускать ruff check если изменились .py файлы

4. Структура веток:
   - main — только утверждённое Директором
   - dev — текущая разработка
   - audit/TASK-XXX — ветка на время аудита
   - snapshot/TASK-XXX — снапшот перед аудитом

### Критерии готовности
- [ ] git_commit("TASK-008: добавлен semantic search") создаёт коммит
- [ ] pre-commit hook блокирует .env файлы
- [ ] audit/TASK-008 создаётся и мержится в dev после закрытия аудита
- [ ] git push выполняется автоматически после утверждения Директора

---

## ЗАДАЧА 4 — РАДА: API-ОРКЕСТРАЦИЯ ВЕБ-ИИ (опционально Этап 2)

### Цель
Claude Desktop через MCP вызывает любого из 4 веб-ИИ по API — без браузера.

### Требования
1. Создать neva_rada.py:
   - ask(model, prompt, max_tokens=1000) → str
   - Поддерживаемые модели: chatgpt / gemini / deepseek / grok
   - API ключи из ~/.env через keychain

2. Добавить action ask_ai в MCP :9000:
   - Параметры: model, prompt, context (опционально)
   - Возвращает: response (str), tokens_used (int)

3. Параллельный вызов для ДУМЫ:
   - ask_ai_duma(prompt) → вызывает все 4 модели параллельно
   - Возвращает dict {model: response}

### Критерии готовности
- [ ] ask_ai("deepseek", "что такое MCP?") возвращает ответ за < 10 сек
- [ ] ask_ai_duma(prompt) возвращает ответы всех 4 моделей
- [ ] Нет утечки API ключей в логи

---

## ПРИОРИТЕТЫ (предложение архитектора)

| Приоритет | Задача | Обоснование |
|---|---|---|
| P0 | Задача 1 (neva_audit_tools в MCP) | Без этого ДУМА через MCP не работает |
| P0 | Задача 3 (git_commit в MCP) | SSOT требует дисциплины коммитов |
| P1 | Задача 2 (e5-small) | Улучшает память, K_repro 55%→75% |
| P2 | Задача 4 (РАДА) | Нужна но не блокирует текущую работу |
