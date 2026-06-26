#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
from pathlib import Path; from datetime import datetime
P=Path.home()/'Documents/NEVA/audit_responses'
text=(P/'THERMAL-001-R3-PROMPT.txt').read_text()
with sync_playwright() as pw:
    b=pw.chromium.connect_over_cdp('http://localhost:9222')
    p=b.contexts[0].new_page()
    p.goto('https://chat.deepseek.com/',wait_until='domcontentloaded',timeout=30000)
    p.wait_for_timeout(3000)
    el=p.locator('textarea').first; el.click(); p.wait_for_timeout(300); el.fill(text)
    p.keyboard.press('Enter'); print('[DeepSeek] sent')
    p.wait_for_timeout(5000)
    for _ in range(240):
        if not p.query_selector('[class*="loading"],[class*="generating"]'): break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(5000)
    msgs=p.locator('.ds-markdown').all()
    r='\n\n'.join(m.inner_text() for m in msgs) if msgs else 'NO RESPONSE'
    (P/'THERMAL-001-R3-DEEPSEEK.md').write_text(f'# DeepSeek R3\n{datetime.now()}\n\n{r}')
    print(f'[DeepSeek] {len(r)} chars'); p.close()
