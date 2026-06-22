#!/usr/bin/env python3
"""
DUMA Playwright v2.0
Читает промпт из GitHub → вставляет в веб-ИИ → сохраняет ответы → заливает в GitHub
"""
import sys, json, base64, time
from pathlib import Path
from datetime import datetime
import urllib.request
from playwright.sync_api import sync_playwright

# ── Конфиг ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = open(Path.home() / 'Documents/NEVA/.env').read()
GITHUB_TOKEN = [l.split('=',1)[1].strip() for l in GITHUB_TOKEN.splitlines() if l.startswith('GITHUB_TOKEN=')][0]

GITHUB_REPO  = 'levchenkosamisto-sudo/NEVA'
PROMPT_PATH  = 'audit_responses/AUDIT-001-R2-PROMPT.md'
OUTPUT_DIR   = Path.home() / 'Documents/NEVA/audit_responses'
OUTPUT_DIR.mkdir(exist_ok=True)

CHROME_EXE   = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
CHROME_DATA  = str(Path.home() / 'Library/Application Support/Google/Chrome')

AIS = [
    {
        'name': 'ChatGPT',
        'id':   'CHATGPT',
        'url':  'https://chatgpt.com/',
        'input':    ['div#prompt-textarea', 'div[contenteditable="true"]'],
        'send':     ['[data-testid="send-button"]', 'button[aria-label*="Send"]'],
        'response': ['[data-message-author-role="assistant"] .markdown',
                     '[data-message-author-role="assistant"]'],
        'wait_gone': '.result-streaming',
    },
    {
        'name': 'Gemini',
        'id':   'GEMINI',
        'url':  'https://gemini.google.com/',
        'input':    ['rich-textarea div[contenteditable]', 'div[contenteditable="true"]'],
        'send':     ['button[aria-label*="Send"]', 'button[mattooltip*="Send"]'],
        'response': ['model-response .markdown', 'message-content', '.response-container'],
        'wait_gone': '.loading',
    },
    {
        'name': 'DeepSeek',
        'id':   'DEEPSEEK',
        'url':  'https://chat.deepseek.com/',
        'input':    ['textarea[placeholder*="DeepSeek"]', 'div[contenteditable="true"]',
                     'textarea'],
        'send':     ['button[aria-label*="Send"]', 'button[type="submit"]'],
        'response': ['.ds-markdown', '[class*="assistant"] .markdown'],
        'wait_gone': '[class*="loading"]',
    },
    {
        'name': 'Grok',
        'id':   'GROK',
        'url':  'https://grok.com/',
        'input':    ['div[contenteditable][aria-label*="Ask"]', 'textarea',
                     'div[contenteditable="true"]'],
        'send':     ['button[aria-label*="Send"]', 'button[type="submit"]'],
        'response': ['[class*="message"] .markdown', '[class*="response"]'],
        'wait_gone': '[class*="loading"]',
    },
]

# ── GitHub ─────────────────────────────────────────────────────────────────────

def gh_read(path: str) -> str:
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    req = urllib.request.Request(url, headers={
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
    })
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
    return base64.b64decode(data['content']).decode('utf-8')


def gh_write(path: str, content: str, message: str):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    # Получаем sha если файл есть
    sha = None
    try:
        req = urllib.request.Request(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get('sha')
    except Exception:
        pass
    body = {'message': message, 'content': base64.b64encode(content.encode()).decode()}
    if sha:
        body['sha'] = sha
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                  headers={'Authorization': f'token {GITHUB_TOKEN}',
                                           'Content-Type': 'application/json'},
                                  method='PUT')
    with urllib.request.urlopen(req):
        pass
    print(f'  [GitHub] ✅ {path}')

# ── Playwright helpers ─────────────────────────────────────────────────────────

def try_fill(page, selectors, text, timeout=8000):
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout)
            if el and el.is_visible():
                el.click(); page.wait_for_timeout(400)
                el.type(text, delay=8)
                return True
        except Exception:
            continue
    return False


def try_click(page, selectors, timeout=5000):
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout)
            if el and el.is_visible():
                el.click(); return True
        except Exception:
            continue
    return False


def wait_done(page, wait_gone_sel, max_sec=120):
    """Ждём пока исчезнет индикатор генерации."""
    for _ in range(max_sec):
        if not page.query_selector(wait_gone_sel):
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(3000)


def get_response(page, selectors, timeout=10000):
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout)
            if el:
                return el.inner_text()
        except Exception:
            continue
    return None

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'\n=== DUMA Playwright v2.0 | {ts} ===')

    # 1. Читаем промпт из GitHub
    print(f'\n[1] Читаю промпт из GitHub...')
    try:
        prompt = gh_read(PROMPT_PATH)
        print(f'  ✅ {len(prompt)} chars')
    except Exception as e:
        print(f'  ❌ {e}')
        sys.exit(1)

    results = {}

    # 2. Запускаем браузер и обходим всех ИИ
    print(f'\n[2] Запускаю браузер...')
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=CHROME_DATA,
            executable_path=CHROME_EXE,
            headless=False,
            args=['--no-first-run', '--no-default-browser-check'],
        )

        for ai in AIS:
            print(f'\n  → {ai["name"]}')
            try:
                page = ctx.new_page()
                page.goto(ai['url'], wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(4000)

                ok = try_fill(page, ai['input'], prompt)
                if not ok:
                    print(f'    ❌ input not found')
                    results[ai['name']] = 'ERROR: input not found'
                    page.close(); continue

                page.wait_for_timeout(500)
                sent = try_click(page, ai['send'])
                if not sent:
                    page.keyboard.press('Enter')
                print(f'    sent, waiting...')

                wait_done(page, ai.get('wait_gone', '.none_xyz'))
                text = get_response(page, ai['response'])

                if text:
                    results[ai['name']] = text.strip()
                    print(f'    ✅ {len(text)} chars')
                else:
                    results[ai['name']] = 'ERROR: no response captured'
                    print(f'    ❌ no response')
                page.close()
            except Exception as e:
                results[ai['name']] = f'ERROR: {e}'
                print(f'    ❌ {e}')

        ctx.close()

    # 3. Заливаем ответы в GitHub
    print(f'\n[3] Заливаю ответы в GitHub...')
    summary = [f'# DUMA AUDIT-001 Круг 2 — Ответы аудиторов\nДата: {ts}\n']

    for ai in AIS:
        name = ai['name']
        ai_id = ai['id']
        text = results.get(name, 'NOT RUN')
        status = 'received' if text and not text.startswith('ERROR') else 'error'

        # Сохраняем локально
        local = OUTPUT_DIR / f'AUDIT-001-R2-{ai_id}.md'
        local.write_text(f'# AUDIT-001 Round 2 — {name}\nДата: {ts}\n\n{text}')

        # Заливаем в GitHub
        gh_write(
            f'audit_responses/AUDIT-001-R2-{ai_id}.md',
            f'# AUDIT-001 Round 2 — {name}\nДата: {ts}\n\n{text}',
            f'DUMA R2: ответ {ai_id}'
        )
        summary.append(f'\n## {name} [{status.upper()}]\n\n{text[:800]}...\n')

    # Сводный файл
    summary_text = '\n'.join(summary)
    (OUTPUT_DIR / 'AUDIT-001-R2-SUMMARY.md').write_text(summary_text)
    gh_write('audit_responses/AUDIT-001-R2-SUMMARY.md', summary_text, 'DUMA R2: SUMMARY')

    print(f'\n=== DONE ===')
    print(f'Ответы: audit_responses/AUDIT-001-R2-*.md')


if __name__ == '__main__':
    main()
