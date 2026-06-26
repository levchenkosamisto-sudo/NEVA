#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime

OUT       = Path.home()/'Documents/NEVA/audit_responses/MEDIC-001-R9-CHATGPT.md'
synthesis = (Path.home()/'Documents/NEVA/audit_responses/MEDIC-001-R8-SYNTHESIS.md').read_text()
answers   = (Path.home()/'Documents/NEVA/audit_responses/MEDIC-001-R8-ANSWERS.md').read_text()
now       = datetime.now().strftime('%Y-%m-%d %H:%M')

PAYLOAD = f"""<user_attachments>
  <attachment name="MEDIC-001-R8-SYNTHESIS.md" last_edit="{now}">{synthesis}</attachment>
  <attachment name="MEDIC-001-R8-ANSWERS.md" last_edit="{now}">{answers}</attachment>
</user_attachments>

КРУГ 9 — ПОСЛЕДНИЙ. neva_medic.py прошёл 8 кругов аудита.
Объяснения почему предыдущие замечания отклонены — в ANSWERS выше.

Вопрос один: есть ли блокирующие замечания?
Если не согласен с отклонением замечания — аргументируй конкретно.
Если блокирующих нет — вердикт ГОТОВ.
Отвечай на русском. Максимально коротко."""

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    p = b.contexts[0].new_page()
    p.goto('https://chatgpt.com/', wait_until='domcontentloaded', timeout=30000)
    p.wait_for_timeout(3000)
    el = p.locator('#prompt-textarea').first
    el.click(); p.wait_for_timeout(300)
    p.evaluate("(t) => { const el = document.querySelector('#prompt-textarea'); el.focus(); document.execCommand('insertText', false, t); }", PAYLOAD)
    p.wait_for_timeout(1000)
    for _ in range(30):
        btn = p.query_selector('[data-testid="send-button"]:not([disabled])')
        if btn: btn.click(); break
        p.wait_for_timeout(1000)
    print('[ChatGPT] sent, waiting...')
    p.wait_for_timeout(8000)
    for _ in range(180):
        if not p.query_selector('[data-testid="send-button"][disabled]'): break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(3000)
    msgs = p.locator('[data-message-author-role="assistant"]').all()
    text = '\n\n'.join(m.inner_text() for m in msgs) if msgs else 'NO RESPONSE'
    print(f'[ChatGPT] {len(text)} chars')
    OUT.write_text(f'# ChatGPT Круг 9\nДата: {datetime.now()}\n\n{text}')
    p.close()
