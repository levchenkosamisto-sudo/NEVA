## СТАТУС НА 2026-06-27 11:00 — ПРОДОЛЖИТЬ В НОВОМ ЧАТЕ

ДУМА MCP-MEM-GIT:
- DeepSeek: ЗАКРЫТ. 6.5/10. Файл: DUMA-MCP-MEM-GIT-R1-DEEPSEEK-VERDICT.md
- Gemini: НЕ ЗАКРЫТ. Прочитал ARCH+TASK. Чат: https://gemini.google.com/app/775659b83449e1a3
  Нужно: Документ 3 (PROMPT), вопросы, ответы, open source альтернативы, write_result

ПРИ СТАРТЕ НОВОГО ЧАТА:
1. Открыть Gemini по ссылке выше
2. Написать: Документ 3 из 3 — ПРОМПТ. github_read filepath=audit_responses/DUMA-MCP-MEM-GIT-R1-PROMPT.txt
3. Run -> Insert -> Отправить
4. Получить вопросы -> ответить -> попросить open source альтернативы -> write_result auditor=gemini

# NEVA SESSION BRIEF | 2026-06-26 | АКТУАЛЬНО

---
## ⛔ ЖЁСТКОЕ ПРАВИЛО — MCP SuperAssistant и ДУМА (2026-06-27)

### КАК ПРАВИЛЬНО РАБОТАТЬ С MCP SuperAssistant:
Мировая практика (mcpsuperassistant.ai/docs):

1. СНАЧАЛА: убедиться что все инструменты включены (Enable All в сайдбаре)
2. СНАЧАЛА: включить Auto-Execute + Auto-Submit (кнопка MCP в чате)
3. СНАЧАЛА: нажать "Insert" в сайдбаре — вставить MCP Instructions Prompt в чат
4. ТОЛЬКО ПОТОМ: написать задачу аудитору
5. ЖДАТЬ: ИИ генерирует ответ с tool call карточкой → расширение показывает RUN
6. НАЖАТЬ RUN (или авто если Auto-Execute включён)
7. РЕЗУЛЬТАТ вставляется в чат автоматически

### ⛔ ЗАПРЕЩЕНО:
- Отправлять промпты всем аудиторам одновременно через скрипт
- Переходить к следующему аудитору не получив ответ от текущего
- Работать с ИИ без вставки MCP Instructions Prompt
- Пропускать шаг Enable All Tools

### ✅ ПОРЯДОК ДУМЫ С MCP:
ОТПРАВИЛ → ПОЛУЧИЛ ОТВЕТ → УБЕДИЛСЯ ЧТО ИНСТРУМЕНТ ВЫЗВАН →
НАЖАЛ RUN → РЕЗУЛЬТАТ В ЧАТЕ → ТОЛЬКО ТОГДА ПЕРЕХОД К СЛЕДУЮЩЕМУ

### КАК ЧЕЛОВЕК:
Каждое действие — как будто я сижу за компьютером и делаю руками:
- Открыл вкладку Grok
- Включил All Tools
- Включил Auto-Execute
- Нажал Insert Instructions
- Написал запрос
- Подождал ответ с tool call карточкой
- Убедился что RUN выполнился
- Посмотрел результат
- ТОЛЬКО ПОТОМ перешёл к ChatGPT
---
# CURSOR-001 ЗАКРЫТ (7 кругов, 4/4 ГОТОВ). Pipeline задеплоен. Переход в новый чат.

---

## ИТОГИ СЕССИИ 2026-06-26

### CURSOR-001 — ЗАВЕРШЁН ПОЛНОСТЬЮ:
- 7 кругов ДУМЫ (5 архитектура + 2 пакет документов)
- Финальная архитектура: Claude Desktop ↔ Cursor CLI (4 этапа)
- Пакет задеплоен: tools/pipeline/ (5 файлов, 26 тестов, ruff ✅, smoke ✅)
- Cursor CLI установлен: agent v2026.06.24, логин levchenkosamisto@gmail.com
- Лимит Cursor исчерпан: сброс 1 июля 2026

### ПРОЦЕДУРА ДУМЫ ОБНОВЛЕНА:
Добавлен финальный круг: аудит пакета документов (ARCH + TASK + TESTS)
Аудиторы проверяют: подробность ТЗ, полноту, слепые зоны, качество тестов
Только после 4/4 ПАКЕТ ГОТОВ — передавать в Cursor

### ПАМЯТЬ MAC M1 — ПРАВИЛА:
- Brave: закрыт навсегда (pkill -f "Brave Browser")
- Claude VM (claudevm): НЕ ТРОГАТЬ — это основа работы Claude
- Ollama: НЕ ТРОГАТЬ — Inspector мониторит
- Node: НЕ ТРОГАТЬ — Desktop Commander
- При ДУМЕ: закрыть Cursor (pkill -f "Cursor.app")
- Chrome CDP: ~/.chrome-neva-debug профиль (аудиторы залогинены там)

### НАСТРОЙКИ CLAUDE DESKTOP (установлено):
ВКЛЮЧЕНО: Search chats, Memory, Artifacts, Code execution, Inline visualizations
ВЫКЛЮЧЕНО: Network egress, AI-powered artifacts, Switch models when flagged

### MCP SUPERASSISTANT — СТАТУС: ✅ РАБОТАЕТ (2026-06-27)
Все 4 веб-ИИ подключены к NEVA MCP сервер :9000 через расширение Chrome.

**Компоненты:**
- Расширение: MCP SuperAssistant v0.6.0, ID: kngiafgkdnlkgmefdafaibkibegkcaef
- Профиль: ~/.chrome-neva-debug (там установлено расширение)
- Прокси: ~/Documents/NEVA/sandbox/mcp-superassistant/ → :3006/sse
- Конфиг: ~/Documents/NEVA/sandbox/mcp-superassistant/mcpconfig.json
- БАГ ИСПРАВЛЕН: configToSse.js — new Server() создаётся per-connection (не singleton)

**Статус по ИИ (Server Connected ✅, 1 of 1 tools enabled):**
- Grok ✅ | ChatGPT ✅ | DeepSeek ✅ | Gemini ✅

**Запуск прокси:**
```bash
pkill -f mcp-superassistant-proxy 2>/dev/null; sleep 2
cd ~/Documents/NEVA/sandbox/mcp-superassistant && \
node node_modules/@srbhptl39/mcp-superassistant-proxy/dist/index.js \
  --config ./mcpconfig.json &
```

**Важно:** Chrome запускать БЕЗ --remote-debugging-port для MCP SuperAssistant.
CDP и расширение совместимы в одном профиле ~/.chrome-neva-debug.

---

### ОТКРЫТЫЕ ЗАДАЧИ:
1. Inspector launchd throttle
2. background_auditor — нужен ли?
3. neva_inspector_monitor.py
4. Telegram двусторонняя связь
5. РАДА — система API-оркестрации 4 веб-ИИ через NEVA MCP (следующий этап)

---



**КАК ДУМА РАБОТАЕТ:**
duma_v2.py + Playwright + CDP порт 9222.
Chrome запускается с флагом --remote-debugging-port=9222 и профилем ~/.chrome-neva-debug.
Аудиторы залогинены в профиле ~/.chrome-neva-debug (куки там сохранены).

**КОМАНДА — выполнить в Terminal перед ДУМОЙ:**
```bash
pkill -f "Google Chrome" 2>/dev/null; sleep 2
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.chrome-neva-debug" \
  --no-first-run &
sleep 5
curl -s http://localhost:9222/json/version | python3 -c "import json,sys; print('CDP OK:', json.load(sys.stdin)['Browser'])"
```

**Если аудиторы разлогинились (только первый раз с новым профилем):**
Открыть в этом же Chrome и войти: chatgpt.com, gemini.google.com, chat.deepseek.com, grok.com

**Claude НЕ задаёт вопросов. Просто выполняет команду выше через start_process.**

---

## ШАГ 1 — ЗАПУСТИТЬ СИСТЕМЫ (сразу при старте чата)

```bash
# Medic
cd /Users/arka/Documents/NEVA_MCP_BRIDGE && \
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u neva_medic.py >> logs/medic.log 2>&1 &

# Inspector
cd /Users/arka/Documents/NEVA && \
nohup .venv/bin/python3 -u neva_inspector.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/inspector.log 2>&1 &

# Проверить
tail -3 /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/medic.log
```

---

## ШАГ 2 — ЗАДАЧА НОВОГО ЧАТА

**ПЕРЕДАТЬ ПАКЕТ В CURSOR ДЛЯ РЕАЛИЗАЦИИ:**

Пакет документов готов в audit_responses/:
  CURSOR-001-FINAL-ARCH.md   — финальная архитектура (утверждена 7 кругами)
  CURSOR-001-TASK.md         — ТЗ для Cursor (5 файлов, 26 требований)
  CURSOR-001-TESTS.py        — тесты (26 штук, TDD)

Шаги передачи:
1. Создать проект: python3 tools/pipeline/new_project.py pipeline
2. Скопировать CURSOR-001-TASK.md → projects/pipeline/spec.md
3. Скопировать CURSOR-001-TESTS.py → projects/pipeline/tests/test_pipeline.py
4. Открыть projects/pipeline/ в Cursor
5. Cursor реализует код по ТЗ

---

## TELEGRAM — ОБЯЗАТЕЛЬНО В КОНЦЕ КАЖДОГО ОТВЕТА

```bash
cd /Users/arka/Documents/NEVA && python3 -c "from neva_telegram import done; done('текст')"
```
Методы: `done(task)` / `stopped(reason)` / `error(msg)` / `progress(msg)`
Файл: ~/Documents/NEVA/neva_telegram.py
Токен: 8577539474:AAFL14KKxZ9GGWOuxb14qGHL1HJpJaIjmq0
Chat ID: 1919255029

---

## ДУМА v2 — КРИТИЧЕСКИЕ ПРАВИЛА

1. Каждый аудитор = ОТДЕЛЬНЫЙ start_process = ОТДЕЛЬНЫЙ ответ Claude
   (иначе "Claude reached tool-use limit" — DC зависает)
2. Порядок: chatgpt → gemini → deepseek → grok
3. Все 4 залогинены в основном Chrome порт 9222
4. Сессии сохраняются в: audit_responses/[AUDIT_ID]-SESSIONS.json
5. В Круге 2+ аудиторы помнят предыдущие круги (один чат на весь аудит)

Детали: governance/DUMA_PROTOCOL.md

---

## ПРОЦЕДУРА ДУМЫ — ОБНОВЛЕНО 2026-06-26

### СТРУКТУРА КРУГОВ (обязательная последовательность):

Круг 1: ВОПРОСЫ — аудиторы задают вопросы без оценок (независимо)
Круг 2: АЛЬТЕРНАТИВЫ — аудиторы предлагают альтернативы из мировой практики
Круг 3+: ОЦЕНКА РЕШЕНИЯ — архитектор подаёт доработанное решение,
         аудиторы оценивают: ГОТОВ / НЕ ГОТОВ / ДОРАБОТАТЬ
         Повторять пока все 4 не дадут ГОТОВ.

### ФИНАЛЬНЫЙ КРУГ (НОВОЕ — добавлено 2026-06-26):
После получения 4/4 ГОТОВ по архитектуре — архитектор готовит пакет документов:
  ДОКУМЕНТ 1: финальная архитектура (FINAL-ARCH.md)
  ДОКУМЕНТ 2: ТЗ для Cursor (TASK.md) — подробное, с edge cases
  ДОКУМЕНТ 3: тесты (TESTS.py) — TDD, написаны до кода

Пакет отправляется на аудит. Аудиторы оценивают:
  А. Подробность ТЗ — достаточно ли деталей для Cursor?
  Б. Полнота — есть ли пропущенные требования?
  В. Слепые зоны — что может пойти не так?
  Итог: ПАКЕТ ГОТОВ / ДОРАБОТАТЬ

Дорабатывать до 4/4 ПАКЕТ ГОТОВ.
Только после этого — передавать в Cursor.

### КОМАНДА ЗАПУСКА:
```bash
cd /Users/arka/Documents/NEVA && .venv/bin/python3 duma_v2.py \
  --audit [AUDIT_ID] --round [N] \
  --prompt audit_responses/[AUDIT_ID]-R[N]-PROMPT.txt \
  --auditor chatgpt   # потом gemini, deepseek, grok — каждый отдельно
```

---

## АРХИТЕКТУРА CURSOR PIPELINE — УТВЕРЖДЕНА (CURSOR-001)

### Пайплайн 4 этапа:

ЭТАП 1: СПЕЦИФИКАЦИЯ (Claude Desktop)
  Claude создаёт: spec.md + AGENTS.md + tests_spec.py + smoke_test.sh
  Директор утверждает → Этап 2. Токены: ~500

ЭТАП 2: РЕАЛИЗАЦИЯ (Cursor)
  Cursor: пишет код → ruff → mypy(опц) → pytest → smoke_test.sh
  При блокировке: questions.md (STATUS: BLOCKED) → fswatch → Telegram
  Inspector poll каждые 3 мин (резерв)
  После ответа Claude: STATUS: RESOLVED
  Лимит: 3 итерации → эскалация Директору. Токены: 0

ЭТАП 3: РЕВЬЮ (Claude Desktop)
  Claude: git diff + test_report.md + smoke_report.md → review.md
  Чеклист 6 пунктов. ГОТОВ / НЕ ГОТОВ. Токены: ~400-600

ЭТАП 4: УТВЕРЖДЕНИЕ (Директор)
  Директор: review.md → утверждает → деплой. Токены: 0

Экономия токенов Claude Desktop: 84%

### Структура папки:
~/Documents/NEVA/projects/[ИМЯ]/
  spec.md / AGENTS.md / tests_spec.py / smoke_test.sh
  src/ / test_report.md / smoke_report.md
  questions.md / answers.md / review.md / logs/

### Триггер блокировок:
fswatch --event Modified --exclude '\.swp$' | grep questions.md
  | xargs grep -l BLOCKED | xargs python3 notify_director.py
+ Inspector poll каждые 3 мин

---

## СТАТУС СИСТЕМ

### ThermalGuard v11 ✅
### Medic v3.10 ✅
### Inspector v6 ✅
### DUMA v2 ✅

### NEVA API :8000 — проверить после перезагрузки:
```bash
cd /Users/arka/Documents/NEVA
NEVA_ADMIN_TOKEN=$(grep NEVA_ADMIN_TOKEN .env | cut -d'=' -f2) \
NEVA_AGENT_TOKEN=$(grep NEVA_AGENT_TOKEN .env | cut -d'=' -f2) \
.venv/bin/python3 -m uvicorn neva_context_api:app \
  --host 127.0.0.1 --port 8000 --workers 1 &
```

---

## CURSOR CLI — ЭКОНОМИЯ ЛИМИТОВ (ВАЖНО)

### Лимиты бесплатного плана Cursor (Hobby):
- Cursor Tab автокомплит: ~2000 завершений/мес
- Премиум-запросы (Agent/Chat/Composer): ~50/мес
- Сброс: 1-го числа каждого месяца
- Dashboard: cursor.com/dashboard

### ПРАВИЛА ЭКОНОМИИ (обязательные):

1. ОДИН АТОМАРНЫЙ ПРОМПТ — не несколько сессий
   Плохо: 3 сессии (реализация → тесты → исправление)
   Хорошо: 1 сессия со всем заданием сразу (экономия 3x)

2. ВСЕГДА --model auto
   agent --trust --model auto -p "полное задание одним промптом..."

3. ПРОМПТ ГОТОВИТЬ ЗАРАНЕЕ до запуска agent
   Включить: все файлы, требования, запуск тестов, ожидаемый результат
   Cursor должен выполнить всё за одну сессию без уточнений

4. НЕ использовать Composer — скрытые фоновые запросы сжигают квоту
   Использовать только agent CLI

5. При лимите Cursor → Claude пишет код сам (резервная схема ниже)

### РЕЗЕРВНАЯ СХЕМА (когда Cursor исчерпан):
Claude Desktop пишет код напрямую через Desktop Commander:
bash_tool / create_file / str_replace — те же тесты, тот же стандарт

---

## СХЕМА CLAUDE DESKTOP ↔ CURSOR (зафиксировано 2026-06-26)

### Полный пайплайн:
  1. ДУМА утверждает архитектуру (4/4 ГОТОВ)
  2. ДУМА утверждает пакет документов (ARCH + TASK + TESTS)
  3. Claude запускает Cursor CLI одним атомарным промптом:
     cd ~/Documents/NEVA/projects/[ИМЯ]
     agent --trust --model auto -p "$(cat TASK.md)"
  4. Cursor пишет код → ruff → pytest
  5. При блокировке: questions.md STATUS:BLOCKED → fswatch → Telegram
     Claude → answers.md → Cursor продолжает
  6. Claude: git diff + test_report.md → review.md (чеклист 6 пунктов)
  7. Директор утверждает → деплой

### Cursor CLI:
  Установка: curl https://cursor.com/install -fsS | bash
  Логин: agent login (levchenkosamisto@gmail.com)
  Проверка: agent --version

### Уже реализовано (CURSOR-001):
  ~/Documents/NEVA/projects/pipeline/tools/pipeline/
  utils.py / notify_director.py / inspector_poll.py
  new_project.py / review_checker.py
  26 тестов PASS ✅ ruff ✅ smoke 4/4 ✅ ЗАДЕПЛОЕНО ✅

---

## ЗАЩИТА ПАМЯТИ — ВАЖНО

Своп на SSD изнашивает NAND ячейки.
Правила:
- STALE_KILL_SEC=900 (15 мин, не 5)
- Лимит pkill 3/3ч
- Swap >6GB → Inspector морозит действия
- Проверять: `sysctl vm.swapusage`

### УПРАВЛЕНИЕ ПРИЛОЖЕНИЯМИ (Mac M1 8GB):
- ДУМА: держать только Chrome + Claude Desktop. Cursor и Brave закрыть.
- Cursor: открывать ТОЛЬКО когда даёшь задачу на код, после — закрыть.
- Brave: не нужен, закрывать всегда. pkill -f "Brave Browser"
- Ollama: НЕ ТРОГАТЬ — Inspector мониторит её как один из 10 процессов.
- Node (Desktop Commander): НЕ ТРОГАТЬ — через него работает Claude Desktop.
- Три Electron-приложения одновременно (Chrome + Claude + Cursor) = предел памяти.

### ГЛАВНЫЙ ПОЖИРАТЕЛЬ ПАМЯТИ — Claude Desktop VM:
Claude Desktop запускает встроенную Linux VM (claudevm.bundle) для Code Execution.
На Mac M1 8GB это съедает 5GB (1.9GB физически + 3.1GB compressor).
НЕ ОТКЛЮЧАТЬ — это основа работы Claude: bash_tool, create_file, Desktop Commander.
Единственный способ снизить нагрузку — закрыть Chrome и Cursor когда не нужны.

---

## ОТКРЫТЫЕ ЗАДАЧИ (в порядке приоритета)

1. Inspector launchd throttle — bootout/bootstrap для стабильного KeepAlive
2. background_auditor — не запущен, разобраться нужен ли
3. neva_inspector_monitor.py — проверить в терминале
4. Telegram двусторонняя связь — низкий приоритет

---

## ФАЙЛОВАЯ СТРУКТУРА NEVA

```
~/Documents/NEVA/
  neva_inspector.py            Inspector v6
  neva_inspector_monitor.py    Монитор (rich, вручную)
  neva_telegram.py             Telegram уведомления
  duma_v2.py                   ДУМА движок
  governance/
    NEVA_SESSION_BRIEF.md      этот файл
    DUMA_PROTOCOL.md           полный протокол ДУМЫ
    medic_knowledge/
      duma_delivery.md         детали вставки текста в браузер
  audit_responses/
    CURSOR-001-FINAL-ARCH.md   финальная архитектура pipeline
    CURSOR-001-TASK.md         ТЗ для Cursor
    CURSOR-001-TESTS.py        тесты (26 штук)
    CURSOR-001-AUDIT-CLOSED.md статистика аудита архитектуры
    CURSOR-001-PACKAGE-CLOSED.md статистика аудита пакета
    INSPECTOR-001-*            закрытый аудит (7 кругов, 4/4 ГОТОВ)
  projects/                    ← папка проектов (создать)
    [ИМЯ]/                     ← папка каждого проекта
      spec.md / AGENTS.md / tests_spec.py / smoke_test.sh
      src/ / tests/ / logs/

~/Documents/NEVA_MCP_BRIDGE/
  neva_medic.py                Medic v3.10
  state/
    inspector_status.json
    inspector_heartbeat
    pending_decisions.json
  logs/
    medic.log
    inspector.log
```
