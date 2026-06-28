#!/usr/bin/env python3
"""
NEVA TASK-MEM-006: Первичная индексация всей NEVA
Запускается фоново, прогресс пишется в logs/full_index.log
"""
import os, sys, time, json
sys.path.insert(0, '/Users/arka/Documents/NEVA')

# Грузим .env
for line in open('/Users/arka/Documents/NEVA/.env'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, _, v = line.partition('=')
        k = k.strip()
        if k and all(c.isalnum() or c=='_' for c in k):
            os.environ[k] = v.strip()

from pathlib import Path
from src.memory.db import init_db
from src.memory.indexer import index_document, _get_e5_model

LOG = Path('/Users/arka/Documents/NEVA/logs/full_index.log')
LOG.parent.mkdir(exist_ok=True)

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

log("=== TASK-MEM-006: ПЕРВИЧНАЯ ИНДЕКСАЦИЯ NEVA ===")

init_db()
log("БД инициализирована")

log("Загружаю e5-base (один раз)...")
t0 = time.time()
_get_e5_model()
log(f"e5-base готова за {time.time()-t0:.1f}с")

ROOT = Path('/Users/arka/Documents/NEVA')
SKIP = {'.venv','node_modules','sandbox','.git','__pycache__','.pytest_cache','logs','kuzu_data'}
EXTS = {'.md', '.txt'}

files = sorted([p for p in ROOT.rglob('*')
    if not any(s in p.parts for s in SKIP)
    and p.suffix in EXTS
    and p.is_file()
    and len(p.read_text(encoding='utf-8', errors='ignore').strip()) >= 50
])

log(f"Файлов для индексации: {len(files)}")

total_facts = 0
errors = 0
t_start = time.time()

for i, p in enumerate(files):
    rel = str(p.relative_to(ROOT))
    try:
        text = p.read_text(encoding='utf-8', errors='ignore')
        t0 = time.time()
        n = index_document(rel, text)
        elapsed = time.time() - t0
        total_facts += n
        log(f"[{i+1}/{len(files)}] {n:2d} фактов  {elapsed:4.1f}с  {rel}")
    except Exception as e:
        errors += 1
        log(f"[{i+1}/{len(files)}] ERROR {rel}: {e}")

total_time = time.time() - t_start

summary = {
    "files": len(files),
    "facts": total_facts,
    "errors": errors,
    "time_sec": round(total_time),
    "time_min": round(total_time/60, 1),
    "speed_per_min": round(len(files)/total_time*60)
}

log("")
log("=== ИТОГ ===")
for k, v in summary.items():
    log(f"  {k}: {v}")

with open('/Users/arka/Documents/NEVA/logs/full_index_result.json', 'w') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

log("Готово. Результат: logs/full_index_result.json")
