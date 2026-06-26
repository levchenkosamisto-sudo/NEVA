#!/usr/bin/env python3
"""DUMA Gemini v2 — keyboard.type() + ожидание генерации"""
from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime

BASE = Path.home()/'Documents/NEVA/governance/medic_knowledge'
doc1 = (BASE/'medic_self.md').read_text()
doc2 = (BASE/'neva_medic.md').read_text()
now  = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')

synthesis = (Path.home()/'Documents/NEVA/audit_responses/MEDIC-001-R8-SYNTHESIS.md').read_text()
answers   = (Path.home()/'Documents/NEVA/audit_responses/MEDIC-001-R8-ANSWERS.md').read_text()
OUT    = Path.home()/'Documents/NEVA/audit_responses/MEDIC-001-R9-GEMINI.md'

PROMPT = f"""КРУГ 9 — ПОСЛЕДНИЙ. neva_medic.py (системный watchdog NEVA, НЕ медицинский агент) прошёл 8 кругов аудита.

=== КОД + ОБЪЯСНЕНИЯ ОТКЛОНЁННЫХ ЗАМЕЧАНИЙ ===
{synthesis}

=== ОТВЕТЫ ДИРЕКТОРА ===
{answers}

Есть ли блокирующие замечания?
Если не согласен с отклонением замечания — аргументируй конкретно со ссылкой на строку кода.
ГОТОВ или НЕ ГОТОВ. Отвечай на русском. Коротко."""

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp('http://localhost:9222')
    ctx = b.contexts[0]
    pg = ctx.new_page()
    pg.goto('https://gemini.google.com/app', wait_until='domcontentloaded', timeout=30000)
    pg.wait_for_timeout(4000)

    # Вставляем через execCommand — быстро и надёжно
    pg.locator('.ql-editor').first.click()
    pg.wait_for_timeout(300)
    pg.evaluate("(text) => { document.querySelector('.ql-editor').focus(); document.execCommand('insertText', false, text); }", PROMPT)
    pg.wait_for_timeout(1000)

    # Send через JS по aria-label
    sent = pg.evaluate("""
        (() => {
            const s = Array.from(document.querySelectorAll('button'))
                           .find(b => b.getAttribute('aria-label')?.includes('Отправить'));
            if (s && !s.disabled) { s.click(); return true; }
            return false;
        })()
    """)
    if not sent:
        pg.keyboard.press('Enter')
    print('[Gemini] sent')

    # Ждём завершения
    pg.wait_for_timeout(5000)
    for _ in range(120):
        if not pg.query_selector('[aria-label*="Остановить"], [aria-label*="Stop"]'):
            break
        pg.wait_for_timeout(1000)
    pg.wait_for_timeout(4000)

    msgs = pg.locator('model-response').all()
    text = msgs[-1].inner_text() if msgs else 'NO RESPONSE'
    print(f'[Gemini] {len(text)} chars')
    OUT.write_text(f'# Gemini\nДата: {datetime.now()}\n\n{text}')
    print(f'Saved: {OUT}')
