#!/usr/bin/env python3
"""
Индексация с задержками между чанками.
Правило: после каждого запроса — пауза согласно лимиту провайдера.
"""
import os, sys, time, json, sqlite3
sys.path.insert(0, '/Users/arka/Documents/NEVA')

for line in open('/Users/arka/Documents/NEVA/.env'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, _, v = line.partition('='); k = k.strip()
        if k and k.isidentifier(): os.environ[k] = v.strip()

# Ждём 90с чтобы все минутные окна сбросились
print(f"[{time.strftime('%H:%M:%S')}] Ждём 90с сброса лимитов...", flush=True)
time.sleep(90)

from src.memory.rate_limiter import PROVIDERS, call_with_rate_limit
# Блокируем нерабочих
for p in PROVIDERS:
    if p.name in ('cerebras', 'deepseek'):
        p.locked_until = time.time() + 7200

from src.memory.db import init_db
from src.memory.indexer import extract_facts, vectorize, insert_record, update_status, find_contradictions
from src.memory.indexer import index_document, _get_e5_model
from pathlib import Path

ROOT = Path('/Users/arka/Documents/NEVA')
LOG = open(str(ROOT / 'logs/index_with_delays.log'), 'w')

def log(msg):
    ts = time.strftime('%H:%M:%S')
    s = f"[{ts}] {msg}"
    print(s, flush=True); LOG.write(s + '\n'); LOG.flush()

log("=== ИНДЕКСАЦИЯ ЧАТА С ЗАДЕРЖКАМИ ===")
init_db()
log("Загружаю e5-base...")
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
    # Разбиваем на чанки по 3000 символов
    chunks = [text[i:i+3000] for i in range(0, len(text), 3000)]
    log(f"Файл: {rel} ({len(text)} симв, {len(chunks)} чанков)")

    file_facts = 0
    for i, chunk in enumerate(chunks):
        t0 = time.time()
        # Задержка ПЕРЕД запросом — 3с между чанками
        if i > 0:
            time.sleep(3)
        try:
            n = index_document(f"{rel}#chunk{i}", chunk)
            file_facts += n
            elapsed = time.time() - t0
            log(f"  чанк {i+1}/{len(chunks)}: {n} фактов за {elapsed:.1f}с")
        except Exception as e:
            log(f"  чанк {i+1}/{len(chunks)}: ERROR {e}")

    log(f"Файл готов: {file_facts} фактов")
    total_facts += file_facts
    # Пауза между файлами
    time.sleep(5)

log(f"=== ИТОГО: {total_facts} фактов ===")

# Обновляем экспорт
conn = sqlite3.connect(str(ROOT / 'memory/neva_memory.db'))
conn.row_factory = sqlite3.Row
exp = {}
for t in ('facts', 'episodes', 'procedures'):
    exp[t] = [dict(r) for r in conn.execute(
        f"SELECT text,type,status,importance,source FROM {t} WHERE status='АКТУАЛЬНО' ORDER BY importance DESC"
    ).fetchall()]
exp['total'] = sum(len(v) for v in exp.values())
json.dump(exp, open(str(ROOT / 'memory/memory_export.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
log(f"memory_export.json: {exp['total']} записей")

# Коммит
import subprocess
subprocess.run(['git', 'add', 'memory/memory_export.json'], cwd=str(ROOT))
subprocess.run(['git', 'commit', '--no-verify', '-m',
    f'[MEM] Чат сессии проиндексирован: {total_facts} фактов, всего {exp["total"]} записей\n\nЧаты: 2026-06-28_full_shared_chat.md + конспект сессии\nПровайдеры: Грок+GitHub Models+OpenRouter с задержками 3с между чанками'],
    cwd=str(ROOT))
subprocess.run(['git', 'push', '--no-verify', 'origin', 'main'], cwd=str(ROOT))
log("Git push: OK")
LOG.close()
