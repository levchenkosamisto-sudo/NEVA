# DUMA v2 — ПОЛНЫЙ ПРОТОКОЛ АУДИТА
Версия: 2.0 | Дата: 2026-06-25
Директор: Серж | Архитектор: Claude
Статус: АКТУАЛЬНО — заменяет все предыдущие версии

---

## 1. ЧТО ТАКОЕ ДУМА

Система независимого аудита через 4 веб-ИИ.
Каждый аудитор работает в ОДНОМ чате на весь аудит (все круги).
Аудитор помнит предыдущие круги из истории чата — в промпт Круга 2+ история НЕ вставляется.

Аудиторы: ChatGPT, Gemini, DeepSeek, Grok.
Все залогинены в основном Chrome на порту 9222.

---

## 2. ФАЙЛЫ И ПАПКИ

### Скрипты (~/Documents/NEVA/)
```
duma_v2.py      — основной движок ДУМЫ v2 (один аудитор, один круг)
duma_run.sh     — обёртка: запускает все 4 аудитора последовательно
```

### Ответы аудиторов (~/Documents/NEVA/audit_responses/)
```
{AUDIT_ID}-SESSIONS.json          — URL чатов (создаётся после Круга 1, нужен для Кругов 2+)
{AUDIT_ID}-R{N}-CHATGPT.md        — ответ ChatGPT Круга N
{AUDIT_ID}-R{N}-GEMINI.md         — ответ Gemini Круга N
{AUDIT_ID}-R{N}-DEEPSEEK.md       — ответ DeepSeek Круга N
{AUDIT_ID}-R{N}-GROK.md           — ответ Grok Круга N
{AUDIT_ID}-R{N}-PROMPT.txt        — промпт который был отправлен в Круге N
{AUDIT_ID}-DECISIONS-v{X}.md      — принятые/отклонённые решения архитектора
```

### Промпты (~/Documents/NEVA/audit_responses/)
Каждый круг — отдельный .txt файл:
```
{AUDIT_ID}-R1-PROMPT.txt   — Круг 1: только вопросы без оценок
{AUDIT_ID}-R2-PROMPT.txt   — Круг 2: только новый вопрос (история уже в чате)
{AUDIT_ID}-R3-PROMPT.txt   — и т.д.
```

---

## 3. КАК ЗАПУСКАЕТ CLAUDE

Claude запускает каждый аудитор отдельным start_process с таймаутом 120с.
НЕ все 4 вместе — DC зависает если суммарное время >4 минут.

### Команда для одного аудитора:
```bash
cd /Users/arka/Documents/NEVA && \
.venv/bin/python3 duma_v2.py \
  --audit {AUDIT_ID} \
  --round {N} \
  --prompt audit_responses/{AUDIT_ID}-R{N}-PROMPT.txt \
  --auditor {chatgpt|gemini|deepseek|grok}
```

### Порядок запуска: chatgpt → gemini → deepseek → grok

---

## 4. ПРОЦЕДУРА АУДИТА ПОШАГОВО

### Шаг 1. Подготовка
1. Присвоить ID аудита: напр. `THERMAL-002`, `MEDIC-002`
2. Создать файл промпта Круга 1: `audit_responses/{ID}-R1-PROMPT.txt`
3. Промпт Круга 1 содержит: описание задачи + ТОЛЬКО вопросы (без оценок)

### Шаг 2. Круг 1 (новые чаты)
Запустить для каждого аудитора:
```bash
.venv/bin/python3 duma_v2.py --audit {ID} --round 1 --prompt ... --auditor chatgpt
.venv/bin/python3 duma_v2.py --audit {ID} --round 1 --prompt ... --auditor gemini
.venv/bin/python3 duma_v2.py --audit {ID} --round 1 --prompt ... --auditor deepseek
.venv/bin/python3 duma_v2.py --audit {ID} --round 1 --prompt ... --auditor grok
```
После: URL чатов сохранены в `{ID}-SESSIONS.json`.
Читаем ответы, выявляем блокирующие замечания.

### Шаг 3. Ответы архитектора
Архитектор отвечает на вопросы Круга 1, дорабатывает решение.
Сохраняет ответы в `{ID}-R1-ANSWERS.md`.
Создаёт промпт Круга 2: `{ID}-R2-PROMPT.txt` (только новый вопрос).

### Шаг 4. Круг 2+ (те же чаты)
duma_v2.py читает `{ID}-SESSIONS.json` и возвращается в каждый чат по URL.
Аудитор видит историю (свои вопросы + ответы архитектора) и отвечает на новый вопрос.
```bash
.venv/bin/python3 duma_v2.py --audit {ID} --round 2 --prompt ... --auditor chatgpt
# ... и т.д.
```

### Шаг 5. Финальный круг
Промпт содержит: "ГОТОВ или НЕ ГОТОВ — одно слово + одна строка объяснения".
Цель: получить ГОТОВ от всех 4 аудиторов.
Если есть НЕ ГОТОВ — доработать и запустить следующий круг.

### Шаг 6. Закрытие аудита
Создать `{ID}-AUDIT-CLOSED.md` с итогами:
- сколько кругов, какие замечания были, что принято/отклонено
- подписи аудиторов (финальные вердикты)

---

## 5. ТЕХНИЧЕСКИЕ ДЕТАЛИ duma_v2.py

### Как открывается чат (Круг 1)
Ищет уже открытую залогиненную вкладку аудитора в Chrome CDP.
Переходит на базовый URL (новый чат).

### Как возвращается в чат (Круг 2+)
Читает URL из `{ID}-SESSIONS.json`.
Открывает новую страницу и переходит по URL.
Аудитор видит всю историю чата.

### Вставка текста
- ChatGPT: `execCommand('insertText')` на `#prompt-textarea` + XML обёртка
- Gemini:   `execCommand('insertText')` на `.ql-editor`
- DeepSeek: нативный setter + `Enter`
- Grok:     `el.fill()` + `Enter`

### Чтение ответа
Всегда берётся ТОЛЬКО ПОСЛЕДНЕЕ сообщение ассистента (`msgs[-1]`).
При возврате в чат видна вся история — нас интересует только свежий ответ.

### Сохранение URL (только Круг 1)
- ChatGPT:  `chatgpt.com/c/UUID`
- Gemini:   `gemini.google.com/app/UUID`
- DeepSeek: `chat.deepseek.com/a/chat/s/UUID`
- Grok:     `grok.com/c/UUID` (тоже постоянный URL)

---

## 6. СТРУКТУРА ПРОМПТОВ

### Круг 1 — только вопросы:
```
АУДИТ {ID} — КРУГ 1

Тема: [описание что аудируется]
Контекст: [краткое описание системы/кода]

[прикладываем документы или код если нужно]

Задай уточняющие вопросы. Только вопросы, без оценок и решений.
```

### Круг 2 — ответ на вопросы + новое задание:
```
АУДИТ {ID} — КРУГ 2

[Твои вопросы из Круга 1 и мои ответы уже в истории этого чата выше.]

[новый вопрос или задание для этого круга]
```

### Финальный круг:
```
АУДИТ {ID} — КРУГ {N} (ФИНАЛЬНЫЙ)

[краткое резюме всех изменений]

Вердикт: ГОТОВ или НЕ ГОТОВ.
Если НЕ ГОТОВ — одно конкретное блокирующее замечание с примером кода.
```

---

## 7. CHROME CDP

Порт: 9222
Все 4 аудитора залогинены в ОСНОВНОМ Chrome (не отдельный профиль).
Grok тоже в основном Chrome — старая информация про ~/.chrome-neva-debug устарела.

Проверить что все залогинены:
```bash
cd /Users/arka/Documents/NEVA && .venv/bin/python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    for p in b.contexts[0].pages:
        print(p.url[:80])
"
```

Нужные вкладки: chatgpt.com, gemini.google.com, chat.deepseek.com, grok.com.
Лишние вкладки закрывать — иначе ДУМА попадает в старый чат.

---

## 8. ЧАСТЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

| Проблема | Причина | Решение |
|---|---|---|
| DC зависает | Playwright >4 мин | Каждый аудитор отдельным start_process |
| Аудитор попал в старый чат | Лишние вкладки в Chrome | Оставить по одной вкладке каждого аудитора |
| get_last_response возвращает историю | Старый баг (исправлен) | duma_v2.py берёт только msgs[-1] |
| Gemini пустой ответ | Неправильный селектор | fallback на message-content |
| Grok не залогинен | Ищет в неправильном профиле | Grok в основном Chrome на 9222 |
| SESSIONS.json не найден в Круге 2 | Круг 1 не завершился | Проверить что R1 дал URL для всех 4 |

---

## 9. ПРИМЕР — ПОЛНЫЙ АУДИТ

```bash
AUDIT="THERMAL-003"
cd /Users/arka/Documents/NEVA

# Круг 1
for a in chatgpt gemini deepseek grok; do
  .venv/bin/python3 duma_v2.py --audit $AUDIT --round 1 \
    --prompt audit_responses/${AUDIT}-R1-PROMPT.txt --auditor $a
done

# Читаем ответы, дорабатываем, пишем R2-PROMPT.txt

# Круг 2
for a in chatgpt gemini deepseek grok; do
  .venv/bin/python3 duma_v2.py --audit $AUDIT --round 2 \
    --prompt audit_responses/${AUDIT}-R2-PROMPT.txt --auditor $a
done

# ... повторяем до 4/4 ГОТОВ
```

---

## 10. СТАТУС (2026-06-25)

- duma_v2.py: ✅ протестирован 3 круга, все 4 аудитора
- ChatGPT: ✅ постоянный URL, возврат работает
- Gemini:  ✅ постоянный URL, возврат работает
- DeepSeek: ✅ постоянный URL, возврат работает
- Grok:    ✅ постоянный URL /c/UUID, возврат работает
- get_last_response: ✅ исправлен (только msgs[-1])

---

## КРИТИЧЕСКОЕ ПРАВИЛО — ЛИМИТ TOOL_USE

Claude имеет лимит ~25 tool_use за один ответ.
Запуск 4 аудиторов подряд в цикле = зависание с ошибкой "Claude reached its tool-use limit".

**ПРАВИЛО:** каждый аудитор — отдельный start_process, отдельный ответ Claude.

Правильный порядок за один аудит:
```
Ответ 1: запуск chatgpt → ждём → читаем
Ответ 2: запуск gemini  → ждём → читаем
Ответ 3: запуск deepseek → ждём → читаем
Ответ 4: запуск grok    → ждём → читаем
Ответ 5: читаем все 4 ответа → синтез → следующий круг
```

Нельзя: for a in chatgpt gemini deepseek grok в одном ответе.
