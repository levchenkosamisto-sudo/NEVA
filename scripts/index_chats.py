#!/usr/bin/env python3
"""Индексация чатов сессии через Грок (Церебрас пропускается из-за пустых ответов)."""
import os, sys, time
sys.path.insert(0, '/Users/arka/Documents/NEVA')

for line in open('/Users/arka/Documents/NEVA/.env'):
    line=line.strip()
    if '=' in line and not line.startswith('#'):
        k,_,v=line.partition('='); k=k.strip()
        if k and k.isidentifier(): os.environ[k]=v.strip()

from src.memory.rate_limiter import PROVIDERS
# Блокируем Церебрас — возвращает None на реальных запросах
for p in PROVIDERS:
    if p.name == 'cerebras':
        p.locked_until = time.time() + 7200

from src.memory.db import init_db
from src.memory.indexer import index_document
from pathlib import Path

init_db()
LOG = open('/Users/arka/Documents/NEVA/logs/index_chats.log', 'a')

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG.write(line + '\n')
    LOG.flush()

CHATS = [
    'memory/raw/chats/2026-06-28_full_shared_chat.md',
    'memory/raw/chats/2026-06-28_claude_desktop_session_memory_git.md',
]

ROOT = Path('/Users/arka/Documents/NEVA')
for chat in CHATS:
    path = ROOT / chat
    if not path.exists():
        log(f"НЕТ: {chat}")
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    log(f"Начинаю: {chat} ({len(text)} символов, {len(text)//3000+1} чанков)")
    t0 = time.time()
    n = index_document(chat, text)
    log(f"Готово: {chat} → {n} фактов за {time.time()-t0:.0f}с")

log("=== ВСЕ ЧАТЫ ПРОИНДЕКСИРОВАНЫ ===")
LOG.close()
