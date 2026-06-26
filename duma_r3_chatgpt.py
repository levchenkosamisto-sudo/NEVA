#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
from pathlib import Path; from datetime import datetime
P=Path.home()/'Documents/NEVA/audit_responses'
text=(P/'THERMAL-001-R3-PROMPT.txt').read_text()
xml=f'<user_attachments><attachment name="R3.md">{text}</attachment></user_attachments>'
with sync_playwright() as pw:
    b=pw.chromium.connect_over_cdp('http://localhost:9222')
    p=b.contexts[0].new_page()
    p.goto('https://chatgpt.com/',wait_until='domcontentloaded',timeout=30000)
    p.wait_for_timeout(3000)
    p.locator('#prompt-textarea').first.click(); p.wait_for_timeout(300)
    p.evaluate("(t)=>{const e=document.querySelector('#prompt-textarea');e.focus();document.execCommand('insertText',false,t);}",xml)
    p.wait_for_timeout(1000)
    p.locator('[data-testid="send-button"]:not([disabled])').wait_for(timeout=10000)
    p.locator('[data-testid="send-button"]').click(); print('[ChatGPT] sent')
    p.wait_for_timeout(5000)
    for _ in range(240):
        if not p.query_selector('[data-testid="send-button"][disabled]'): break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(3000)
    msgs=p.locator('[data-message-author-role="assistant"]').all()
    r='\n\n'.join(m.inner_text() for m in msgs) if msgs else 'NO RESPONSE'
    (P/'THERMAL-001-R3-CHATGPT.md').write_text(f'# ChatGPT R3\n{datetime.now()}\n\n{r}')
    print(f'[ChatGPT] {len(r)} chars'); p.close()
