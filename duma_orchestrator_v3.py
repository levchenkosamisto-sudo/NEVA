#!/usr/bin/env python3
"""
DUMA Orchestrator v3.1
Ollama = оркестратор и синтезатор. Claude Desktop вне цепочки передачи.
Схема:
  1. Ollama читает промпт из GitHub
  2. Ollama генерирует финальный промпт для каждого аудитора
  3. duma_playwright.py отправляет через браузер, получает ответы
  4. Ollama синтезирует ответы → заливает сводку в GitHub
"""
import json, base64, os, subprocess, urllib.request, time
from pathlib import Path
from datetime import datetime

# ── Конфиг ────────────────────────────────────────────────────────────────────
ENV = {l.split('=',1)[0]: l.split('=',1)[1].strip()
       for l in open(Path.home()/'Documents/NEVA/.env')
       if '=' in l and not l.startswith('#')}

GITHUB_TOKEN = ENV.get('GITHUB_TOKEN', '')
GITHUB_REPO  = 'levchenkosamisto-sudo/NEVA'
OLLAMA_MODEL = 'qwen2.5:7b'
NEVA_DIR     = Path.home() / 'Documents/NEVA'
PYTHON       = str(NEVA_DIR / '.venv/bin/python3')

# ── GitHub ─────────────────────────────────────────────────────────────────────

def gh_read(path: str) -> str:
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    req = urllib.request.Request(url, headers={
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'})
    with urllib.request.urlopen(req) as r:
        return base64.b64decode(json.loads(r.read())['content']).decode()


def gh_write(path: str, content: str, message: str):
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
                                  headers={'Authorization': f'token {GITHUB_TOKEN}',
                                           'Content-Type': 'application/json'}, method='PUT')
    with urllib.request.urlopen(req):
        pass
    print(f'  [GitHub] ✅ {path}')

# ── Ollama ─────────────────────────────────────────────────────────────────────

def ollama(system: str, user: str) -> str:
    body = {'model': OLLAMA_MODEL, 'stream': False,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': user}]}
    req = urllib.request.Request('http://localhost:11434/api/chat',
                                  data=json.dumps(body).encode(),
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())['message']['content']

# ── Playwright (отдельный процесс, без Claude) ────────────────────────────────

def run_playwright(prompt: str) -> dict:
    """Запускает duma_playwright.py с промптом, возвращает ответы."""
    # Сохраняем промпт во временный файл
    prompt_file = NEVA_DIR / 'audit_responses' / 'AUDIT-001-R2-PROMPT.md'
    prompt_file.write_text(prompt)

    print('  [Playwright] Запускаю браузер...')
    result = subprocess.run(
        [PYTHON, str(NEVA_DIR / 'duma_playwright.py')],
        cwd=str(NEVA_DIR),
        capture_output=True, text=True, timeout=600
    )
    print(result.stdout[-2000:] if result.stdout else '(no output)')
    if result.returncode != 0:
        print(f'  STDERR: {result.stderr[-500:]}')

    # Читаем ответы из файлов
    responses = {}
    for ai_id in ['CHATGPT', 'GEMINI', 'DEEPSEEK', 'GROK']:
        f = NEVA_DIR / 'audit_responses' / f'AUDIT-001-R2-{ai_id}.md'
        if f.exists():
            responses[ai_id] = f.read_text()
        else:
            responses[ai_id] = 'NO RESPONSE'
    return responses

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'\n=== DUMA Orchestrator v3.1 (Ollama→Playwright→GitHub) | {ts} ===')
    print('Claude Desktop исключён из цепочки передачи.')

    # 1. Ollama читает базовый промпт из GitHub и улучшает его
    print('\n[1] Ollama читает промпт из GitHub...')
    try:
        base_prompt = gh_read('audit_responses/AUDIT-001-R2-PROMPT.md')
        print(f'  ✅ {len(base_prompt)} chars')
    except Exception as e:
        print(f'  ❌ {e}'); return

    # 2. Ollama адаптирует промпт для веб-аудиторов
    print('\n[2] Ollama адаптирует промпт...')
    final_prompt = ollama(
        system='Ты оркестратор аудита. Получи промпт и сделай его максимально понятным для веб-ИИ аудиторов. Сохрани все ссылки и форму ответа.',
        user=f'Адаптируй этот промпт для отправки через браузер аудиторам ChatGPT, Gemini, DeepSeek и Grok:\n\n{base_prompt}'
    )
    print(f'  ✅ Ollama адаптировал: {len(final_prompt)} chars')

    # 3. Playwright рассылает промпт через браузер (без Claude)
    print('\n[3] Playwright рассылает аудиторам через браузер...')
    responses = run_playwright(final_prompt)

    # 4. Ollama синтезирует ответы
    print('\n[4] Ollama синтезирует ответы...')
    all_responses = '\n\n'.join(f'=== {k} ===\n{v[:2000]}' for k, v in responses.items())
    synthesis = ollama(
        system='Ты аналитик. Синтезируй ответы аудиторов в единый структурированный отчёт. Выдели общие риски, консенсус и противоречия.',
        user=f'Синтезируй ответы аудиторов NEVA:\n\n{all_responses}'
    )
    print(f'  ✅ Синтез: {len(synthesis)} chars')

    # 5. Заливаем всё в GitHub
    print('\n[5] Заливаю в GitHub...')
    summary = f'# DUMA AUDIT-001 R2 — Синтез\nДата: {ts}\nОркестратор: Ollama {OLLAMA_MODEL}\n\n{synthesis}'
    gh_write('audit_responses/AUDIT-001-R2-SYNTHESIS.md', summary, 'DUMA R2: Ollama synthesis')

    for ai_id, text in responses.items():
        gh_write(f'audit_responses/AUDIT-001-R2-{ai_id}.md',
                 f'# {ai_id}\nДата: {ts}\n\n{text}',
                 f'DUMA R2: {ai_id}')

    print(f'\n=== DONE ===')
    print('Следующий шаг для Claude: читать audit_responses/AUDIT-001-R2-SYNTHESIS.md')


if __name__ == '__main__':
    main()
