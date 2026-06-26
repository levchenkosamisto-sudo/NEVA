#!/usr/bin/env python3
"""THERMAL-AUDIT-001 Round 2 — DeepSeek"""
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime

PROMPT_FILE = Path.home()/'Documents/NEVA/audit_responses/THERMAL-001-R2-PROMPT.txt'
OUT = Path.home()/'Documents/NEVA/audit_responses/THERMAL-001-R2-DEEPSEEK.md'
PROMPT = PROMPT_FILE.read_text()

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
    for _ in range(240):
        if not p.query_selector('[class*="loading"],[class*="generating"]'): break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(5000)
    msgs = p.locator('.ds-markdown').all()
    text = '\n\n'.join(m.inner_text() for m in msgs) if msgs else 'NO RESPONSE'
    print(f'[DeepSeek] {len(text)} chars')
    OUT.write_text(f'# DeepSeek — THERMAL-001-R2\nДата: {datetime.now()}\n\n{text}')
    print(f'Saved: {OUT}')
    p.close()
