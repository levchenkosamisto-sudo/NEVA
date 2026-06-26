# DUMA v2 — Детали доставки промптов аудиторам
Обновлено: 2026-06-25 | Версия: 2.0 (заменяет предыдущую)

## ОБЩЕЕ

Все аудиторы в основном Chrome, порт 9222.
duma_v2.py подключается через CDP и работает с существующими вкладками.
Круг 1: открывает новый чат в существующей залогиненной вкладке.
Круг 2+: возвращается по URL из {AUDIT_ID}-SESSIONS.json.

---

## ChatGPT

- URL базовый: https://chatgpt.com/
- URL чата: https://chatgpt.com/c/UUID (постоянный, сохраняется)
- Поле ввода: `#prompt-textarea`
- Вставка: `execCommand('insertText')` — fill() не работает в React
- Формат: XML обёртка `<user_attachments><attachment name="R1.md">текст</attachment></user_attachments>`
- Отправка: ждать `[data-testid="send-button"]:not([disabled])` → click (НЕ Enter)
- Ожидание конца: poll `[data-testid="send-button"][disabled]` пока есть + 3 сек
- Забор ответа: `locator('[data-message-author-role="assistant"]').all()` → `msgs[-1]` (ТОЛЬКО последнее)

## Gemini

- URL базовый: https://gemini.google.com/app
- URL чата: https://gemini.google.com/app/UUID (постоянный, сохраняется)
- Поле ввода: `.ql-editor` (Quill редактор)
- Вставка: `execCommand('insertText')` на `.ql-editor` — fill() не работает
- НЕ использовать GDrive ссылки — Gemini кеширует старый контент
- Отправка: JS evaluate → `button[aria-label*='Отправить'].click()`
- Ожидание конца: poll `[aria-label*="Остановить"],[aria-label*="Stop"]` пока есть + 4 сек
- Забор ответа: `locator('model-response').all()` → `msgs[-1]` + fallback на `message-content`

## DeepSeek

- URL базовый: https://chat.deepseek.com/
- URL чата: https://chat.deepseek.com/a/chat/s/UUID (постоянный, сохраняется)
- Поле ввода: `textarea` (locator('textarea').first)
- Вставка: нативный setter через JS evaluate (React textarea) + `dispatchEvent('input')`
- Отправка: `keyboard.press('Enter')`
- Ожидание конца: poll `[class*="loading"],[class*="generating"]` пока есть + 5 сек
- Забор ответа: `locator('.ds-markdown').all()` → `msgs[-1]` (ТОЛЬКО последнее)

## Grok

- URL базовый: https://grok.com/
- URL чата: https://grok.com/c/UUID (постоянный, сохраняется — открытие в v2)
- Поле ввода: `div[contenteditable="true"].first`
- Вставка: `el.fill(text)` — работает на contenteditable
- Попап: `try: page.locator('button:has-text("Отклонить")').first.click(timeout=2000)`
- Отправка: `keyboard.press('Enter')`
- Ожидание конца: poll `[class*="loading"],[class*="thinking"],[class*="spinner"]` + 3 сек
- Забор ответа: `locator('[class*="response-content-markdown"]').all()` → `msgs[-1]`
- Фильтр: `re.sub(r'Размышление на протяжении \d+s\s*', '', text).strip()`
- ⚠️ Старая инфо (УСТАРЕЛА): отдельный CDP профиль НЕ нужен — Grok в основном Chrome

---

## КРИТИЧЕСКИЕ ПРАВИЛА

1. ВСЕГДА берём только `msgs[-1]` — при возврате в чат видна вся история
2. Каждый аудитор — отдельный start_process (DC зависает при >4 мин)
3. Параллельный запуск НЕ использовать — аудиторы конкурируют за вкладки
4. Лишние вкладки закрывать перед запуском (иначе попадёт в старый чат)
5. SESSIONS.json создаётся автоматически после Круга 1 — не удалять до конца аудита
