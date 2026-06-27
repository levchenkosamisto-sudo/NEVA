# АРХИТЕКТУРА — MCP СЕРВЕР, ПАМЯТЬ NEVA, GIT
## ДУМА: ЗАДАНИЕ ДЛЯ АУДИТА
**Дата:** 2026-06-27 | **Директор:** Серж | **Архитектор:** Claude
**Статус:** ПРОЕКТ — ожидает аудита 4 ИИ

---

## БЛОК 1 — MCP СЕРВЕР (порт 9000 + 3006)

### 1.1 Текущая архитектура
```
Claude Desktop
    ↓ MCP Streamable HTTP
neva_mcp_server.py :9000
    ↓ actions
  file_read / file_patch / file_write
  shell_exec / script_deploy
  neva_status / neva_heal / neva_chronic
  medic_events / claude_reply
  approval_request / approval_poll
  ping_director / batch
    ↓
NEVA файловая система (~/Documents/NEVA_MCP_BRIDGE/)

MCP SuperAssistant Proxy :3006/sse
    ↓ SSE
Chrome расширение (профиль ~/.chrome-neva-debug)
    ↓
4 веб-ИИ: Grok / ChatGPT / DeepSeek / Gemini
    ↓ инструменты
neva_audit_tools.py :9100
  mac_read_file / github_read / write_result
```

### 1.2 Что работает
- Claude Desktop → MCP :9000 → все actions ✅
- DeepSeek → MCP SuperAssistant → github_read + write_result ✅
- Grok подключён но отказывает по политике модели
- ChatGPT подключён но tools недоступны на free tier

### 1.3 Что НЕ реализовано
- Нет единого инструмента ask_ai(model, prompt) для оркестрации веб-ИИ через API
- neva_audit_tools.py живёт в sandbox — не интегрирован в основной MCP сервер
- РАДА (система API-оркестрации 4 веб-ИИ) — только концепция
- Нет auth для MCP SuperAssistant — любой может подключиться к :3006
- MCP сервер :9000 принимает запросы без токена от расширения

### 1.4 Риски
- R1: Прокси :3006 падает при двойном SSE соединении (фикс применён вручную, не постоянный)
- R2: neva_audit_tools.py запускается вручную — нет launchd
- R3: shell_exec в MCP :9000 без белого списка — потенциальная дыра
- R4: MCP SuperAssistant несовместим с CDP Chrome — нужен отдельный Chrome или выбор режима

---

## БЛОК 2 — ПАМЯТЬ NEVA

### 2.1 Текущее состояние
```
SSOT (источник истины):
  GitHub: levchenkosamisto-sudo/NEVA (main ветка)
  governance/  — решения, протоколы, бриф
  docs/        — архитектура, карты
  state/       — текущий статус задач
  audit_responses/ — ответы аудиторов ДУМЫ

Локальная база:
  ~/Documents/NEVA/        — основная директория
  ~/Documents/NEVA_MCP_BRIDGE/ — MCP сервер
  neva.db (Kuzu)           — граф знаний (P16 атомы)
  neva_graphiti.py v3.6    — временной граф эпизодов (MockGraph, не реальный)

Поиск:
  e5-small (multilingual)  — в venv, НЕ АКТИВИРОВАН
  текстовый CONTAINS поиск — единственный рабочий
```

### 2.2 Что работает
- Git commit/push/pull ✅
- Чтение файлов через MCP ✅
- Kuzu embedded DB — базовые операции ✅
- NEVA_SESSION_BRIEF.md — живой бриф актуальный ✅

### 2.3 Что НЕ реализовано
- graphiti-core (реальный) — используется MockGraph-заглушка
- e5-small семантический поиск — установлен но не подключён
- K_truth (метрика достоверности) — не считается
- TTL Policy — заглушка
- Trust Engine — частично
- Chat Guardian — создан но не интегрирован
- Автоматическая индексация чатов в память
- Единый Knowledge API для всех ИИ
- Decision Registry / ADR Registry

### 2.4 Риски
- R5: Память фрагментирована — часть в Kuzu, часть в файлах, нет единой точки доступа
- R6: graphiti-core не подключён — нет временных связей между событиями
- R7: e5-small не активен — только keyword поиск, K_repro ≪ 95%
- R8: GDrive backup не работает — TODO в коде

---

## БЛОК 3 — GIT КАК SSOT

### 3.1 Текущая структура
```
Репо: levchenkosamisto-sudo/NEVA (main)
Ветки: только main (нет dev, audit/*, snapshot/*)
.gitignore: sandbox/ исключён — тестовые файлы не версионируются
Коммиты: вручную при необходимости

Что версионируется:
  governance/  ✅
  docs/        ✅
  state/       ✅
  tools/       ✅
  audit_responses/ частично

Что НЕ версионируется:
  sandbox/     — исключён .gitignore
  *.env        — правильно
  neva.db      — правильно
  venv/        — правильно
```

### 3.2 Что работает
- git push/pull через NEVA MCP (shell_exec) ✅
- raw URL для чтения файлов веб-ИИ ✅
- История коммитов как лог решений ✅

### 3.3 Что НЕ реализовано
- Ветки dev / audit/* / snapshot/* — работаем только в main
- pre-commit hook — нет проверки схем перед коммитом
- GitHub Actions — нет CI/CD
- Автоматический коммит после завершения задачи
- Теги версий (v1.0, v2.0) для этапов
- Pull Request процесс для изменений в governance/

### 3.4 Риски
- R9: работа в main — один плохой коммит ломает SSOT
- R10: нет автоматических тестов при коммите
- R11: sandbox/ не версионируется — потеря тестового кода при очистке

---

## ВОПРОСЫ ДЛЯ АУДИТОРОВ

1. **MCP сервер:** Нужна ли РАДА сейчас (Этап 2) или достаточно DeepSeek через MCP SuperAssistant?
2. **MCP сервер:** Как защитить :3006 от несанкционированного доступа?
3. **Память:** Какой приоритет — graphiti-core или e5-small? Что даст больший выигрыш для К_repro?
4. **Память:** GitHub как основная память — достаточно или нужен Qdrant/ChromaDB?
5. **Git:** Нужны ли ветки сейчас или overhead превышает пользу при команде из 1 человека?
6. **Git:** Как автоматизировать git commit после каждой завершённой задачи NEVA?
