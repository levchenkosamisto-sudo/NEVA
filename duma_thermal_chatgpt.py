#!/usr/bin/env python3
"""THERMAL-AUDIT-001 Round 1 — ChatGPT"""
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime

PROMPT_FILE = Path.home()/'Documents/NEVA/audit_responses/THERMAL-001-R1-PROMPT.txt'
OUT = Path.home()/'Documents/NEVA/audit_responses/THERMAL-001-R1-CHATGPT.md'
PROMPT = PROMPT_FILE.read_text()
XML = f'<user_attachments><attachment name="THERMAL-001-R1.md">{PROMPT}</attachment></user_attachments>'

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    p = b.contexts[0].new_page()
    p.goto('https://chatgpt.com/', wait_until='domcontentloaded', timeout=30000)
    p.wait_for_timeout(3000)
    el = p.locator('#prompt-textarea').first
    el.click(); p.wait_for_timeout(300)
    p.evaluate("(t) => { const e = document.querySelector('#prompt-textarea'); e.focus(); document.execCommand('insertText', false, t); }", XML)
    p.wait_for_timeout(1000)
    p.locator('[data-testid="send-button"]:not([disabled])').wait_for(timeout=10000)
    p.locator('[data-testid="send-button"]').click()
    print('[ChatGPT] sent')
    p.wait_for_timeout(5000)
    for _ in range(180):
        if not p.query_selector('[data-testid="send-button"][disabled]'): break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(3000)
    msgs = p.locator('[data-message-author-role="assistant"]').all()
    text = '\n\n'.join(m.inner_text() for m in msgs) if msgs else 'NO RESPONSE'
    print(f'[ChatGPT] {len(text)} chars')
    OUT.write_text(f'# ChatGPT — THERMAL-001-R1\nДата: {datetime.now()}\n\n{text}')
    print(f'Saved: {OUT}')
    p.close()
