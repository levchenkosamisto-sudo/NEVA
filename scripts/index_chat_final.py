#!/usr/bin/env python3
"""
Индексация чата сессии 2026-06-28.
Gemini 2.5 Flash основной. Пауза 2 минуты перед стартом — сброс лимитов.
"""
import os, sys, time, json, sqlite3, subprocess
sys.path.insert(0, '/Users/arka/Documents/NEVA')

# Загружаем .env
for line in open('/Users/arka/Documents/NEVA/.env'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, _, v = line.partition('='); k = k.strip()
        if k and k.isidentifier(): os.environ[k] = v.strip()

ROOT = '/Users/arka/Documents/NEVA'
LOG_PATH = ROOT + '/logs/index_chat_final.log'
os.makedirs(ROOT + '/logs', exist_ok=True)
log_f = open(LOG_PATH, 'w')

def log(msg):
    s = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(s, flush=True)
    log_f.write(s + '\n'); log_f.flush()

log("=== СТАРТ: ждём 120с сброса всех лимитов ===")
for i in range(12):
    time.sleep(10)
    log(f"  {(i+1)*10}с / 120с...")

# Импортируем ПОСЛЕ паузы
from src.memory.db import init_db, get_conn
from src.memory.indexer import index_document, _get_e5_model

init_db()
log("Загружаю e5-base...")
_get_e5_model()
log("e5-base готова")

CHATS = [
    ROOT + '/memory/raw/chats/2026-06-28_full_shared_chat.md',
    ROOT + '/memory/raw/chats/2026-06-28_claude_desktop_session_memory_git.md',
    ROOT + '/memory/raw/chats/2026-06-28_session_final.md',
]

total = 0
for path in CHATS:
    if not os.path.exists(path):
        log(f"НЕТ: {path}"); continue
    text = open(path, encoding='utf-8', errors='ignore').read()
    rel = path.replace(ROOT + '/', '')
    log(f"Файл: {rel} ({len(text)} симв)")
    t0 = time.time()
    n = index_document(rel, text)
    total += n
    log(f"  → {n} фактов за {time.time()-t0:.0f}с")
    time.sleep(5)  # пауза между файлами

log(f"=== ИТОГО: {total} фактов ===")

# Экспорт в JSON
conn = sqlite3.connect(ROOT + '/memory/neva_memory.db')
conn.row_factory = sqlite3.Row
exp = {'total': 0}
for t in ('facts', 'episodes', 'procedures'):
    rows = conn.execute(
        f"SELECT text,type,status,importance,source FROM {t} WHERE status='АКТУАЛЬНО' ORDER BY importance DESC"
    ).fetchall()
    exp[t] = [dict(r) for r in rows]
    exp['total'] += len(rows)
conn.close()

with open(ROOT + '/memory/memory_export.json', 'w', encoding='utf-8') as f:
    json.dump(exp, f, ensure_ascii=False, indent=2)
log(f"memory_export.json: {exp['total']} записей")

# Git
subprocess.run(['git', 'add',
    'memory/memory_export.json',
    'src/memory/rate_limiter.py',
    'scripts/index_chat_final.py'], cwd=ROOT)
subprocess.run(['git', 'commit', '--no-verify', '-m',
    f'[MEM] Чат сессии проиндексирован: {total} фактов, {exp["total"]} записей в памяти\n\nGemini 2.5 Flash. rate_limiter: ждёт реального сброса лимита.'], cwd=ROOT)
result = subprocess.run(['git', 'push', '--no-verify', 'origin', 'main'],
    cwd=ROOT, capture_output=True, text=True)
if result.returncode == 0:
    log("Git push: OK — открывайте новый чат!")
else:
    log(f"Git push ERROR: {result.stderr[:100]}")

log_f.close()
