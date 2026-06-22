#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime

PROMPT = open(Path.home()/'Documents/NEVA/audit_responses/AUDIT-001-R2-PROMPT.md').read()
OUT = Path.home()/'Documents/NEVA/audit_responses/AUDIT-001-R2-CHATGPT.md'

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    p = b.contexts[0].new_page()
    p.goto('https://chatgpt.com/', wait_until='domcontentloaded', timeout=30000)
    p.wait_for_timeout(3000)
    el = p.locator('#prompt-textarea').first
    el.click(); p.wait_for_timeout(300); el.fill(PROMPT)
    p.keyboard.press('Enter')
    print('[ChatGPT] sent')
    p.wait_for_timeout(3000)
    p.wait_for_timeout(30000)
    p.wait_for_timeout(2000)
    msgs = p.locator('[data-message-author-role="assistant"]').all()
    text = msgs[-1].inner_text() if msgs else 'NO RESPONSE'
    print(f'[ChatGPT] {len(text)} chars')
    OUT.write_text(f'# ChatGPT\nДата: {datetime.now()}\n\n{text}')
    p.close()
