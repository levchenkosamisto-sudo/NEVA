#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime

PROMPT = """КРУГ 9 — ПОСЛЕДНИЙ. neva_medic.py прошёл 8 кругов аудита.

Код + объяснения отклонённых замечаний:
https://raw.githubusercontent.com/levchenkosamisto-sudo/NEVA/main/audit_responses/MEDIC-001-R8-SYNTHESIS.md

Ответы директора:
https://raw.githubusercontent.com/levchenkosamisto-sudo/NEVA/main/audit_responses/MEDIC-001-R8-ANSWERS.md

Есть ли блокирующие замечания? Если не согласен с отклонением — аргументируй.
ГОТОВ или НЕ ГОТОВ. Коротко."""
OUT = Path.home()/'Documents/NEVA/audit_responses/MEDIC-001-R9-GROK.md'

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = b.contexts[0]
    # Берём страницу grok с активным чатом, или открываем новый чат
    pages = [pg for pg in ctx.pages if 'grok.com' in pg.url and pg.url != 'https://grok.com/']
    if not pages:
        pages = [pg for pg in ctx.pages if 'grok.com' in pg.url]
    p = pages[0] if pages else ctx.new_page()
    # Открываем новый чат чтобы не засорять существующий
    p.goto('https://grok.com/', wait_until='domcontentloaded', timeout=30000)
    p.wait_for_timeout(3000)
    # Проверяем залогинены ли
    if 'Войти' in (p.inner_text('body')[:200]):
        print('[Grok] НЕ ЗАЛОГИНЕН в этом контексте')
        exit(1)
    try: p.locator('button:has-text("Отклонить")').first.click(timeout=3000)
    except: pass
    el = p.locator('div[contenteditable="true"]').first
    el.click(); p.wait_for_timeout(300); el.fill(PROMPT)
    p.keyboard.press('Enter')
    print('[Grok] sent')
    p.wait_for_timeout(5000)
    for _ in range(120):
        if not p.query_selector('[class*="loading"],[class*="thinking"]'): break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(3000)
    # Ответы Grok всегда в response-content-markdown, промпты — в message-bubble
    msgs2 = p.locator('[class*="response-content-markdown"]').all()
    if msgs2:
        text = msgs2[-1].inner_text()
    else:
        msgs = p.locator('.message-bubble').all()
        text = msgs[-1].inner_text() if msgs else 'NO RESPONSE'
    import re
    text = re.sub(r'Размышление на протяжении \d+s\s*', '', text).strip()
    print(f'[Grok] {len(text)} chars')
    OUT.write_text(f'# Grok\nДата: {datetime.now()}\n\n{text}')
    p.close()
