#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
from pathlib import Path; from datetime import datetime
P=Path.home()/'Documents/NEVA/audit_responses'
text=(P/'THERMAL-001-R3-PROMPT.txt').read_text()
with sync_playwright() as pw:
    b=pw.chromium.connect_over_cdp('http://localhost:9222')
    pg=b.contexts[0].new_page()
    pg.goto('https://gemini.google.com/app',wait_until='domcontentloaded',timeout=30000)
    pg.wait_for_timeout(4000)
    pg.locator('.ql-editor').first.click(); pg.wait_for_timeout(300)
    pg.evaluate("(t)=>{document.querySelector('.ql-editor').focus();document.execCommand('insertText',false,t);}",text)
    pg.wait_for_timeout(1000)
    sent=pg.evaluate("(()=>{const s=Array.from(document.querySelectorAll('button')).find(b=>b.getAttribute('aria-label')?.includes('Отправить'));if(s&&!s.disabled){s.click();return true;}return false;})()")
    if not sent: pg.keyboard.press('Enter')
    print('[Gemini] sent')
    pg.wait_for_timeout(5000)
    for _ in range(240):
        if not pg.query_selector('[aria-label*="Остановить"],[aria-label*="Stop"]'): break
        pg.wait_for_timeout(1000)
    pg.wait_for_timeout(4000)
    msgs=pg.locator('model-response').all()
    r=msgs[-1].inner_text() if msgs else 'NO RESPONSE'
    (P/'THERMAL-001-R3-GEMINI.md').write_text(f'# Gemini R3\n{datetime.now()}\n\n{r}')
    print(f'[Gemini] {len(r)} chars'); pg.close()
