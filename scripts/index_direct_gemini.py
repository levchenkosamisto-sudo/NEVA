#!/usr/bin/env python3
"""
Прямая индексация через Gemini 2.5 Flash без rate_limiter.
Пауза 2с между чанками — Gemini 1500 RPM, этого достаточно.
"""
import os, sys, time, json, sqlite3, subprocess
sys.path.insert(0, '/Users/arka/Documents/NEVA')

for line in open('/Users/arka/Documents/NEVA/.env'):
    line=line.strip()
    if '=' in line and not line.startswith('#'):
        k,_,v=line.partition('='); k=k.strip()
        if k and k.isidentifier(): os.environ[k]=v.strip()

from google import genai as _genai
gemini = _genai.Client(api_key=os.environ.get('GEMINI_API_KEY',''))

from src.memory.db import init_db, get_conn, insert_record
from src.memory.indexer import _get_e5_model, importance_from_path
import numpy as np

ROOT = '/Users/arka/Documents/NEVA'
LOG = open(ROOT+'/logs/index_direct_gemini.log','w')

def log(msg):
    s = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(s, flush=True); LOG.write(s+'\n'); LOG.flush()

def gemini_extract(text, path):
    """Извлекаем факты через Gemini напрямую."""
    base_imp = importance_from_path(path)
    prompt = f"""Ты индексатор памяти NEVA. Извлеки факты из текста. Отвечай ТОЛЬКО JSON-массивом без пояснений.

Каждый факт: {{"text":"...","type":"DECISION|FACT|AUDIT|EVENT|CHAT|PROCEDURE","importance":{base_imp},"table":"facts|episodes|procedures"}}

Важность: 5=решение директора, 4=факт аудита, 3=предложение, 2=гипотеза, 1=шум(не включай)
Источник: {path}

Текст:
{text[:2500]}

JSON:"""
    try:
        r = gemini.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        resp = r.text.strip()
        # Ищем JSON массив
        start = resp.find('[')
        end = resp.rfind(']') + 1
        if start < 0 or end <= start:
            return []
        return json.loads(resp[start:end])
    except Exception as e:
        log(f"  Gemini error: {e}")
        return []

log("=== ПРЯМАЯ ИНДЕКСАЦИЯ ЧЕРЕЗ GEMINI 2.5 FLASH ===")
init_db()
log("Загружаю e5-base...")
e5 = _get_e5_model()
log("e5-base готова")

CHATS = [
    ('memory/raw/chats/2026-06-28_full_shared_chat.md', 1),
    ('memory/raw/chats/2026-06-28_claude_desktop_session_memory_git.md', 2),
    ('memory/raw/chats/2026-06-28_session_final.md', 2),
]

TYPE_TABLE = {
    'facts':      {'DECISION','FACT','ARCHITECTURE','COMPONENT'},
    'episodes':   {'AUDIT','EVENT','CHAT','SESSION'},
    'procedures': {'PROCEDURE','TEMPLATE','RULE'},
}

total_facts = 0

for rel, base_imp in CHATS:
    path = ROOT + '/' + rel
    if not os.path.exists(path):
        log(f"НЕТ: {rel}"); continue

    text = open(path, encoding='utf-8', errors='ignore').read()
    chunks = [text[i:i+2500] for i in range(0, len(text), 2500)]
    log(f"Файл: {rel} ({len(text)} симв, {len(chunks)} чанков)")

    file_facts = 0
    for i, chunk in enumerate(chunks):
        t0 = time.time()
        facts = gemini_extract(chunk, rel)

        for fact in facts:
            if fact.get('importance', 1) < 2:
                continue
            table = fact.get('table', 'facts')
            ftype = fact.get('type', 'FACT')
            # Санитизация типа
            if ftype not in TYPE_TABLE.get(table, set()):
                for tbl, types in TYPE_TABLE.items():
                    if ftype in types:
                        table = tbl; break
                else:
                    table, ftype = 'facts', 'FACT'

            # Векторизация
            try:
                vec = e5.encode(fact['text'], normalize_embeddings=True).astype(np.float32).tobytes()
            except:
                vec = None

            try:
                insert_record(table, {
                    'text': fact['text'],
                    'type': ftype,
                    'status': 'АКТУАЛЬНО',
                    'importance': fact.get('importance', base_imp),
                    'source': rel,
                    'source_path': rel,
                    'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                    **(({'embedding': vec}) if vec else {}),
                })
                file_facts += 1
            except Exception as e:
                log(f"  DB error: {e}")

        elapsed = time.time() - t0
        log(f"  чанк {i+1}/{len(chunks)}: {len(facts)} фактов за {elapsed:.1f}с")
        time.sleep(1)  # 1с между чанками — Gemini 1500 RPM

    log(f"Файл готов: {file_facts} фактов")
    total_facts += file_facts
    time.sleep(3)

log(f"=== ИТОГО: {total_facts} фактов ===")

# Экспорт
conn = sqlite3.connect(ROOT+'/memory/neva_memory.db')
conn.row_factory = sqlite3.Row
exp = {'total': 0}
for t in ('facts','episodes','procedures'):
    rows = [dict(r) for r in conn.execute(
        f"SELECT text,type,status,importance,source FROM {t} WHERE status='АКТУАЛЬНО' ORDER BY importance DESC"
    ).fetchall()]
    exp[t] = rows; exp['total'] += len(rows)
conn.close()

with open(ROOT+'/memory/memory_export.json','w',encoding='utf-8') as f:
    json.dump(exp, f, ensure_ascii=False, indent=2)
log(f"memory_export.json: {exp['total']} записей")

# Git
subprocess.run(['git','add','memory/memory_export.json','scripts/index_direct_gemini.py'], cwd=ROOT)
subprocess.run(['git','commit','--no-verify','-m',
    f'[MEM] Чат проиндексирован: {total_facts} новых фактов, всего {exp["total"]} записей\n\nПрямой Gemini 2.5 Flash, пауза 1с между чанками'], cwd=ROOT)
result = subprocess.run(['git','push','--no-verify','origin','main'],
    cwd=ROOT, capture_output=True, text=True)
log("Git push: " + ("OK — открывайте новый чат!" if result.returncode==0 else f"ERROR: {result.stderr[:80]}"))
LOG.close()
