#!/usr/bin/env python3
"""Индексация полного текста чата через GitHub Models GPT-4o-mini."""
import os, sys, time
sys.path.insert(0, '/Users/arka/Documents/NEVA')

for line in open('/Users/arka/Documents/NEVA/.env'):
    line=line.strip()
    if '=' in line and not line.startswith('#'):
        k,_,v=line.partition('='); k=k.strip()
        if k and k.isidentifier(): os.environ[k]=v.strip()

# Только GitHub Models — остальные в лимите
from src.memory.rate_limiter import PROVIDERS
for p in PROVIDERS:
    if p.name in ('cerebras','groq','deepseek'):
        p.locked_until = time.time() + 7200

from src.memory.db import init_db
from src.memory.indexer import index_document
from pathlib import Path

init_db()
LOG = open('/Users/arka/Documents/NEVA/logs/index_full_chat.log', 'a')

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG.write(line + '\n'); LOG.flush()

files = [
    'memory/raw/chats/2026-06-28_full_shared_chat.md',
    'memory/raw/chats/2026-06-28_claude_desktop_session_memory_git.md',
]

ROOT = Path('/Users/arka/Documents/NEVA')
for rel in files:
    p = ROOT / rel
    if not p.exists():
        log(f"НЕТ: {rel}"); continue
    text = p.read_text(encoding='utf-8', errors='ignore')
    chunks = len(text) // 3000 + 1
    log(f"Начинаю: {rel} ({len(text)} символов, ~{chunks} чанков)")
    t0 = time.time()
    n = index_document(rel, text)
    log(f"Готово: {n} фактов за {time.time()-t0:.0f}с")

# Обновляем экспорт
import sqlite3, json
conn = sqlite3.connect(str(ROOT / 'memory/neva_memory.db'))
conn.row_factory = sqlite3.Row
tables = {'facts': [], 'episodes': [], 'procedures': []}
for t in tables:
    tables[t] = [dict(r) for r in conn.execute(
        f"SELECT text,type,status,importance,source FROM {t} WHERE status='АКТУАЛЬНО' ORDER BY importance DESC"
    ).fetchall()]
total = sum(len(v) for v in tables.values())
tables['total'] = total
json.dump(tables, open(str(ROOT / 'memory/memory_export.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
log(f"memory_export.json обновлён: {total} записей")
log("=== ГОТОВО ===")
LOG.close()
