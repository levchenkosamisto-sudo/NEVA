# Чат Claude Desktop — Сессия: Память NEVA v3 + Гит структура
Дата: 2026-06-28
Участник: Серж (Директор) + Claude (Архитектор)
Тема: Разработка памяти NEVA v3, организация Гит, отключение Ollama

## КЛЮЧЕВЫЕ РЕШЕНИЯ СЕССИИ

### ГИТ СТРУКТУРА (DECISION-001)
- Репо: levchenkosamisto-sudo/NEVA
- Ветки: main → dev → task/TASK-XXX
- AGENTS.md + CLAUDE.md в корне
- pre-commit хук: защита красной зоны (decisions/, neva_auth.py, schema.sql)
- pre-push хук: запрет прямых пушей в main
- CI: .github/workflows/ci.yml (ruff + pytest + self-test + переиндексация + Телеграм)
- GitHub Branch Protection включён через admin токен

### ПАМЯТЬ NEVA v3
- SQLite три полки: ЧТО ПРОИСХОДИЛО / ЧТО ИЗВЕСТНО / КАК ДЕЛАТЬ
- Каждая запись: текст + тип + статус + важность 1-5 + даты + источник + вектор
- Статусы: АКТУАЛЬНО / ОТМЕНЕНО / УСТАРЕЛО / ОБЪЕДИНЕНО / ТРЕБУЕТ_ПРОВЕРКИ / ОЖИДАЕТ_ВЕКТОРИЗАЦИИ
- Индексатор: Церебрас(1RPM) → Грок(30RPM) → DeepSeek(60RPM) через rate_limiter
- e5-base: multilingual-e5-base, загружается один раз в память
- Ночной процесс 00:00: дедупликация (порог 0.92) + устаревание 90/180 дней
- Поисковый конвейер 6 уровней: решения→FTS→Kuzu→вектор→чаты→сырые чаты
- memory_search добавлен как MCP tool в mcp_server.py

### RATE LIMITER (НОВОЕ)
- src/memory/rate_limiter.py
- Церебрас: 1 RPM (60с между запросами)
- Грок: 30 RPM (2с между запросами)
- DeepSeek: 60 RPM (1с между запросами)
- При 429 → автоблокировка провайдера + переключение на следующего
- При блокировке всех → ожидание и повтор

### OLLAMA ОТКЛЮЧЕНА
- Остановлена: launchctl bootout gui/502/com.ollama.ollama
- Автозапуск отключён: launchctl disable gui/502/com.ollama.ollama
- Из кода удалена: qwen_local убран из AI_PROVIDERS
- RAM освободилась: 171MB → 1635MB

### ДЕМОН НАБЛЮДАТЕЛЬ
- scripts/neva_watcher.sh: fswatch следит за memory/raw/chats/, governance/, state/, audit/
- launchd: com.neva.memory.watcher (KeepAlive=true)
- scripts/index_file.sh: индексация одного файла
- scripts/save_chat.sh: сохранение чата → git commit → фоновая индексация

### LAUNCHD НОЧНОЙ ПРОЦЕСС
- com.neva.memory.dedup: 00:00 ежедневно
- scripts/neva_dedup.sh: дедупликация + векторизация отложенных + Телеграм

## КОММИТЫ СЕССИИ
- bb5c272: [TASK-GIT-001] Структура Гит NEVA внедрена
- cccf92f: [TASK-MEM-001] Память NEVA v3 — ядро реализовано (7/7 тестов)
- 4d1a65d: [TASK-MEM-002] launchd ночной процесс памяти 00:00
- 70409ff: [TASK-MEM-003] memory_search в MCP сервер + save_chat.sh
- 5d9968b: [TASK-MEM-004] fswatch демон-наблюдатель + автоиндексация
- 81b9302: [FIX] Церебрас: модель gpt-oss-120b
- 8a6113e: [TASK-MEM-005] Отключена Ollama из цепочки индексации

## ФАЙЛЫ СОЗДАНЫ
- src/memory/schema.sql, db.py, indexer.py, search.py, dedup.py, api.py, ram_manager.py, rate_limiter.py
- src/memory/__init__.py
- tests/test_memory.py
- scripts/start.sh, test.sh, index.sh, neva_dedup.sh, neva_watcher.sh, index_file.sh, save_chat.sh, run_full_index.py
- AGENTS.md, CLAUDE.md
- governance/decisions/DECISION-001.md
- .github/workflows/ci.yml
- LaunchAgents: com.neva.memory.dedup.plist, com.neva.memory.watcher.plist

## ОТКРЫТЫЕ ЗАДАЧИ
- Первичная индексация всей NEVA (269 файлов) — прервана, нужно перезапустить с rate_limiter
- GitHub Branch Protection настроен, но требует классического PAT для полного контроля
- Снимок системы перед аудитом (scripts/snapshot.sh) — не создан
- Kuzu граф — graphiti-core реальный ещё не подключён (MockGraph)
- ESC по qwen — устаревшие, нужно закрыть
