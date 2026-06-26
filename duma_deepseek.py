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
OUT = Path.home()/'Documents/NEVA/audit_responses/MEDIC-001-R9-DEEPSEEK.md'

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    p = b.contexts[0].new_page()
    p.goto('https://chat.deepseek.com/', wait_until='domcontentloaded', timeout=30000)
    p.wait_for_timeout(3000)
    el = p.locator('textarea').first
    el.click(); p.wait_for_timeout(300); el.fill(PROMPT)
    p.keyboard.press('Enter')
    print('[DeepSeek] sent')
    p.wait_for_timeout(5000)
    for _ in range(120):
        if not p.query_selector('[class*="loading"],[class*="generating"]'): break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(5000)
    msgs = p.locator('.ds-markdown').all()
    text = '\n\n'.join(m.inner_text() for m in msgs) if msgs else 'NO RESPONSE'
    print(f'[DeepSeek] {len(text)} chars')
    OUT.write_text(f'# DeepSeek\nДата: {datetime.now()}\n\n{text}')
    p.close()
