#!/usr/bin/env python3
import subprocess, json, base64, urllib.request
from pathlib import Path
from datetime import datetime

ENV = {l.split('=',1)[0]: l.split('=',1)[1].strip()
       for l in open(Path.home()/'Documents/NEVA/.env') if '=' in l and not l.startswith('#')}
GITHUB_TOKEN = ENV['GITHUB_TOKEN']
GITHUB_REPO  = 'levchenkosamisto-sudo/NEVA'
PYTHON = str(Path.home()/'Documents/NEVA/.venv/bin/python3')
NEVA   = Path.home()/'Documents/NEVA'

def gh_write(path, content, msg):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    sha = None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})) as r:
            sha = json.loads(r.read()).get('sha')
    except: pass
    body = {'message': msg, 'content': base64.b64encode(content.encode()).decode()}
    if sha: body['sha'] = sha
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
        headers={'Authorization': f'token {GITHUB_TOKEN}', 'Content-Type': 'application/json'}, method='PUT')
    with urllib.request.urlopen(req): pass
    print(f'  ✅ GitHub: {path}')

ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
print(f'\n=== DUMA RUN ALL | {ts} ===')
scripts = ['duma_chatgpt.py','duma_gemini.py','duma_deepseek.py','duma_grok.py']
procs = {s: subprocess.Popen([PYTHON, str(NEVA/s)], cwd=str(NEVA),
         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for s in scripts}
print(f'Запущено: {[p.pid for p in procs.values()]}')
for s, p in procs.items():
    out, _ = p.communicate(timeout=300)
    print(f'  [{s}] exit={p.returncode} | {out.strip()[-100:]}')

ai_ids = ['CHATGPT','GEMINI','DEEPSEEK','GROK']
summary = [f'# DUMA R2 SUMMARY\nДата: {ts}\n']
for ai_id in ai_ids:
    f = NEVA/'audit_responses'/f'AUDIT-001-R2-{ai_id}.md'
    text = f.read_text() if f.exists() else 'NO RESPONSE'
    summary.append(f'\n## {ai_id}\n\n{text[:1000]}\n')
    gh_write(f'audit_responses/AUDIT-001-R2-{ai_id}.md', text, f'DUMA R2: {ai_id}')

s = '\n'.join(summary)
gh_write('audit_responses/AUDIT-001-R2-SUMMARY.md', s, 'DUMA R2: SUMMARY')
print('\n=== DONE ===')
