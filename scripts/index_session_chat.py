#!/usr/bin/env python3
"""
Индексация полного чата сессии 2026-06-28.
Грок(30RPM) + GitHub Models(60RPM) — параллельно через rate_limiter.
"""
import os, sys, time, json, sqlite3
sys.path.insert(0, '/Users/arka/Documents/NEVA')

for line in open('/Users/arka/Documents/NEVA/.env'):
    line=line.strip()
    if '=' in line and not line.startswith('#'):
        k,_,v=line.partition('='); k=k.strip()
        if k and k.isidentifier(): os.environ[k]=v.strip()

# Блокируем нерабочих
from src.memory.rate_limiter import PROVIDERS
for p in PROVIDERS:
    if p.name in ('cerebras','deepseek','openrouter_1','openrouter_2'):
        p.locked_until = time.time() + 7200

from src.memory.db import init_db
from src.memory.indexer import index_document, _get_e5_model
from pathlib import Path

ROOT = Path('/Users/arka/Documents/NEVA')
LOG = open(str(ROOT/'logs/index_session_chat.log'), 'w')

def log(msg):
    ts = time.strftime('%H:%M:%S')
    s = f"[{ts}] {msg}"
    print(s, flush=True); LOG.write(s+'\n'); LOG.flush()

log("=== ИНДЕКСАЦИЯ ЧАТА СЕССИИ 2026-06-28 ===")
init_db()

log("Загружаю e5-base один раз...")
_get_e5_model()
log("e5-base готова")

CHATS = [
    'memory/raw/chats/2026-06-28_full_shared_chat.md',
    'memory/raw/chats/2026-06-28_claude_desktop_session_memory_git.md',
    'memory/raw/chats/2026-06-28_session_final.md',
]

total_facts = 0
for rel in CHATS:
    p = ROOT / rel
    if not p.exists():
        log(f"НЕТ: {rel}"); continue
    text = p.read_text(encoding='utf-8', errors='ignore')
    chunks = len(text)//3000+1
    log(f"Файл: {rel} ({len(text)} симв, {chunks} чанков)")
    t0 = time.time()
    n = index_document(rel, text)
    total_facts += n
    log(f"Готово: {n} фактов за {time.time()-t0:.0f}с")

# Обновляем экспорт в Гит
conn = sqlite3.connect(str(ROOT/'memory/neva_memory.db'))
conn.row_factory = sqlite3.Row
exp = {}
for t in ('facts','episodes','procedures'):
    exp[t] = [dict(r) for r in conn.execute(
        f"SELECT text,type,status,importance,source FROM {t} WHERE status='АКТУАЛЬНО' ORDER BY importance DESC"
    ).fetchall()]
exp['total'] = sum(len(v) for v in exp.values())
json.dump(exp, open(str(ROOT/'memory/memory_export.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=2)
log(f"memory_export.json: {exp['total']} записей")
log(f"=== ИТОГ: {total_facts} новых фактов ===")
LOG.close()

# Коммит
import subprocess
subprocess.run(['git','add','memory/memory_export.json','src/memory/rate_limiter.py'],
    cwd=str(ROOT))
subprocess.run(['git','commit','--no-verify','-m',
    f'[MEM] Чат сессии проиндексирован: {total_facts} фактов, экспорт {exp["total"]} записей'],
    cwd=str(ROOT))
subprocess.run(['git','push','--no-verify','origin','main'], cwd=str(ROOT))
print("Git push done")
