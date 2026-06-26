#!/usr/bin/env python3
"""THERMAL-AUDIT-001 Round 1 — Grok (CDP профиль ~/.chrome-neva-debug)"""
import re
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime

PROMPT_FILE = Path.home()/'Documents/NEVA/audit_responses/THERMAL-001-R1-PROMPT.txt'
OUT = Path.home()/'Documents/NEVA/audit_responses/THERMAL-001-R1-GROK.md'
PROMPT = PROMPT_FILE.read_text()

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = b.contexts[0]
    pages = [pg for pg in ctx.pages if 'grok.com' in pg.url]
    p = pages[0] if pages else ctx.new_page()
    p.goto('https://grok.com/', wait_until='domcontentloaded', timeout=30000)
    p.wait_for_timeout(3000)
    if 'Войти' in (p.inner_text('body')[:300]):
        print('[Grok] НЕ ЗАЛОГИНЕН — нужен CDP профиль ~/.chrome-neva-debug на порту 9222')
        exit(1)
    try: p.locator('button:has-text("Отклонить")').first.click(timeout=3000)
    except: pass
    el = p.locator('div[contenteditable="true"]').first
    el.click(); p.wait_for_timeout(300); el.fill(PROMPT)
    p.keyboard.press('Enter')
    print('[Grok] sent')
    p.wait_for_timeout(5000)
    for _ in range(180):
        if not p.query_selector('[class*="loading"],[class*="thinking"]'): break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(3000)
    msgs = p.locator('[class*="response-content-markdown"]').all()
    if msgs:
        text = msgs[-1].inner_text()
    else:
        msgs = p.locator('.message-bubble').all()
        text = msgs[-1].inner_text() if msgs else 'NO RESPONSE'
    text = re.sub(r'Размышление на протяжении \d+s\s*', '', text).strip()
    print(f'[Grok] {len(text)} chars')
    OUT.write_text(f'# Grok — THERMAL-001-R1\nДата: {datetime.now()}\n\n{text}')
    print(f'Saved: {OUT}')
    p.close()
