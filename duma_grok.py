#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime

PROMPT = open(Path.home()/'Documents/NEVA/audit_responses/AUDIT-001-R2-PROMPT.md').read()
OUT = Path.home()/'Documents/NEVA/audit_responses/AUDIT-001-R2-GROK.md'

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    p = b.contexts[0].new_page()
    p.goto('https://grok.com/', wait_until='domcontentloaded', timeout=30000)
    p.wait_for_timeout(3000)
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
    text = p.inner_text('main')
    print(f'[Grok] {len(text)} chars')
    OUT.write_text(f'# Grok\nДата: {datetime.now()}\n\n{text}')
    p.close()
