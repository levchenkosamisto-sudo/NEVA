#!/usr/bin/env python3
"""
DUMA v4.1 — browser-use + CDP + Gemini API
Схема: GitHub(промпт) → Gemini управляет Chrome через CDP → веб-ИИ → GitHub(ответы)
Claude Desktop полностью исключён из цепочки.
"""
import asyncio, json, base64, urllib.request, os
from pathlib import Path
from datetime import datetime

from browser_use import Agent
from browser_use.browser.session import BrowserSession
from browser_use.llm.openrouter.chat import ChatOpenRouter

# ── Конфиг ────────────────────────────────────────────────────────────────────
ENV = {l.split('=',1)[0]: l.split('=',1)[1].strip()
       for l in open(Path.home()/'Documents/NEVA/.env')
       if '=' in l and not l.startswith('#')}

GITHUB_TOKEN = ENV['GITHUB_TOKEN']
GITHUB_REPO  = 'levchenkosamisto-sudo/NEVA'
PROMPT_PATH  = 'audit_responses/AUDIT-001-R2-PROMPT.md'
OUTPUT_DIR   = Path.home() / 'Documents/NEVA/audit_responses'
CDP_URL      = 'http://localhost:9222'

AIS = [
    {'name': 'ChatGPT',  'id': 'CHATGPT',  'url': 'https://chatgpt.com/'},
    {'name': 'Gemini',   'id': 'GEMINI',   'url': 'https://gemini.google.com/'},
    {'name': 'DeepSeek', 'id': 'DEEPSEEK', 'url': 'https://chat.deepseek.com/'},
    {'name': 'Grok',     'id': 'GROK',     'url': 'https://grok.com/'},
]

# ── GitHub ─────────────────────────────────────────────────────────────────────

def gh_read(path):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    req = urllib.request.Request(url, headers={
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'})
    with urllib.request.urlopen(req) as r:
        return base64.b64decode(json.loads(r.read())['content']).decode()

def gh_write(path, content, message):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
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
        headers={'Authorization': f'token {GITHUB_TOKEN}', 'Content-Type': 'application/json'},
        method='PUT')
    with urllib.request.urlopen(req): pass
    print(f'  [GitHub] ✅ {path}')

# ── browser-use агент ──────────────────────────────────────────────────────────

async def send_to_ai(ai, prompt):
    print(f'\n  → {ai["name"]}...')

    llm = ChatOpenRouter(
        model='meta-llama/llama-3.3-70b-instruct:free',
        api_key=ENV.get('OPENROUTER_API_KEY', ENV.get('OPENROUTER_API_KEY_2', '')),
    )

    task = f"""Открой {ai['url']}.
Найди поле ввода для сообщений.
Вставь в него ВЕСЬ следующий текст:

{prompt}

Нажми кнопку отправки или Enter.
Дождись полного ответа (подожди пока перестанет генерироваться).
Верни ПОЛНЫЙ текст ответа."""

    try:
        session = BrowserSession(cdp_url=CDP_URL)
        agent = Agent(
            task=task,
            llm=llm,
            browser_session=session,
            use_vision=False,  # DOM-only, без скриншотов
        )
        history = await agent.run(max_steps=25)
        result = history.final_result() or 'NO RESULT'
        print(f'  ✅ {ai["name"]}: {len(result)} chars')
        return result
    except Exception as e:
        print(f'  ❌ {ai["name"]}: {e}')
        return f'ERROR: {e}'

# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'\n=== DUMA v4.1 | {ts} ===')
    print('Оркестратор: Gemini 2.0 Flash | Браузер: Chrome CDP | Claude: не участвует')

    # 1. Читаем промпт из GitHub
    print('\n[1] Читаю промпт из GitHub...')
    try:
        prompt = gh_read(PROMPT_PATH)
        print(f'  ✅ {len(prompt)} chars')
    except Exception as e:
        print(f'  ❌ {e}'); return

    # 2. Проверяем CDP
    print(f'\n[2] Проверяю Chrome CDP на {CDP_URL}...')
    try:
        req = urllib.request.Request(f'{CDP_URL}/json/version')
        with urllib.request.urlopen(req, timeout=3) as r:
            ver = json.loads(r.read())
        print(f'  ✅ {ver["Browser"]}')
    except Exception as e:
        print(f'  ❌ Chrome не запущен с CDP: {e}')
        return

    # 3. Обходим аудиторов последовательно
    print('\n[3] Рассылаю промпт аудиторам...')
    results = {}
    for ai in AIS:
        result = await send_to_ai(ai, prompt)
        results[ai['id']] = result
        await asyncio.sleep(2)

    # 4. Заливаем в GitHub
    print('\n[4] Заливаю ответы в GitHub...')
    summary = [f'# DUMA AUDIT-001 R2\nДата: {ts}\nОркестратор: Gemini 2.0 Flash + Chrome CDP\n']
    for ai in AIS:
        text = results.get(ai['id'], 'NOT RUN')
        path = f'audit_responses/AUDIT-001-R2-{ai["id"]}.md'
        content = f'# {ai["name"]}\nДата: {ts}\n\n{text}'
        (OUTPUT_DIR / f'AUDIT-001-R2-{ai["id"]}.md').write_text(content)
        gh_write(path, content, f'DUMA R2: {ai["id"]}')
        summary.append(f'\n## {ai["name"]}\n\n{text[:800]}\n')

    s = '\n'.join(summary)
    (OUTPUT_DIR / 'AUDIT-001-R2-SUMMARY.md').write_text(s)
    gh_write('audit_responses/AUDIT-001-R2-SUMMARY.md', s, 'DUMA R2: SUMMARY')

    print('\n=== DONE ===')


if __name__ == '__main__':
    asyncio.run(main())
