#!/usr/bin/env python3
"""
NEVA Indexer Daemon — ночной индексатор.
Работает до тех пор пока не проиндексирует всё.
При исчерпании лимита любого провайдера — ждёт retry_delay из ответа API и пробует другого.
Проверяет каждые 5 минут есть ли что индексировать.
"""
import os, sys, time, json, sqlite3, subprocess, re
sys.path.insert(0, '/Users/arka/Documents/NEVA')

ROOT = '/Users/arka/Documents/NEVA'
LOG = open(ROOT+'/logs/neva_indexer_daemon.log', 'a')

def log(msg):
    s = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(s, flush=True); LOG.write(s+'\n'); LOG.flush()

# Загружаем .env
for line in open(ROOT+'/.env'):
    line=line.strip()
    if '=' in line and not line.startswith('#'):
        k,_,v=line.partition('='); k=k.strip()
        if k and k.isidentifier(): os.environ[k]=v.strip()

log("=== NEVA INDEXER DAEMON ЗАПУЩЕН ===")

# Состояние провайдеров — когда можно снова использовать
provider_available_at = {}

# ──────────────────────────────────────────
# ВЫЗОВЫ ПРОВАЙДЕРОВ
# ──────────────────────────────────────────
def call_provider(name, prompt, max_tokens=1000):
    """Прямой вызов провайдера. Возвращает (text, retry_after_secs)."""
    import urllib.request, json as _j

    if name == 'gemini':
        from google import genai
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY',''))
        try:
            r = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            return r.text, 0
        except Exception as e:
            retry = _parse_retry(str(e))
            return None, retry

    if name == 'groq':
        from groq import Groq
        try:
            r = Groq(api_key=os.environ.get('GROQ_API_KEY','')).chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=[{'role':'user','content':prompt}], max_tokens=max_tokens)
            return r.choices[0].message.content, 0
        except Exception as e:
            return None, _parse_retry(str(e))

    if name == 'github':
        payload = _j.dumps({'model':'gpt-4o-mini',
            'messages':[{'role':'user','content':prompt}],'max_tokens':max_tokens}).encode()
        req = urllib.request.Request('https://models.inference.ai.azure.com/chat/completions',
            data=payload, headers={'Content-Type':'application/json',
            'Authorization':f'Bearer {os.environ.get("GITHUB_TOKEN_ADMIN","")}'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = _j.loads(r.read())
                return d['choices'][0]['message']['content'], 0
        except Exception as e:
            return None, _parse_retry(str(e))

    if name.startswith('or_'):
        MODEL_MAP = {
            'or_gpt120':   ('openai/gpt-oss-120b:free',                os.environ.get('OPENROUTER_API_KEY','')),
            'or_nemotron': ('nvidia/nemotron-3-ultra-550b-a55b:free',  os.environ.get('OPENROUTER_API_KEY','')),
            'or_llama_k1': ('meta-llama/llama-3.3-70b-instruct:free',  os.environ.get('OPENROUTER_API_KEY','')),
            'or_llama_k2': ('meta-llama/llama-3.3-70b-instruct:free',  os.environ.get('OPENROUTER_API_KEY_2','')),
        }
        model, key = MODEL_MAP.get(name, ('openai/gpt-oss-120b:free', ''))
        payload = _j.dumps({'model':model,
            'messages':[{'role':'user','content':prompt}],'max_tokens':max_tokens}).encode()
        req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
            data=payload, headers={'Content-Type':'application/json',
            'Authorization':f'Bearer {key}',
            'HTTP-Referer':'https://github.com/levchenkosamisto-sudo/NEVA'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = _j.loads(r.read())
                content = d['choices'][0]['message']['content']
                if not content: return None, 30
                return content, 0
        except Exception as e:
            return None, _parse_retry(str(e))

    return None, 60

def _parse_retry(err):
    # Дневной лимит — блокируем до завтра
    if 'PerDay' in err or 'per_day' in err.lower() or 'daily' in err.lower():
        log(f"  ДНЕВНОЙ ЛИМИТ — блокируем на 8 часов")
        return 28800
    if '402' in err:
        return 86400  # платный — на сутки
    # Извлекаем retry-after из ответа
    for pat in [r'Please retry in ([\d.]+)', r'retry.{0,10}after[:\s]+([\d.]+)', r'Retry-After[:\s]+([\d.]+)']:
        m = re.search(pat, err)
        if m: return min(float(m.group(1)) + 10, 3600)
    if '429' in err: return 70  # стандартная минута + буфер
    return 30

# Приоритет провайдеров
PROVIDERS = ['gemini', 'groq', 'github', 'or_gpt120', 'or_nemotron', 'or_llama_k1', 'or_llama_k2']

def get_provider():
    """Возвращает первого доступного провайдера или None."""
    now = time.time()
    for p in PROVIDERS:
        avail = provider_available_at.get(p, 0)
        if now >= avail:
            return p
    return None
    
def call_ai(prompt):
    """Вызов ИИ с авторотацией. Ждёт если все провайдеры заняты."""
    while True:
        p = get_provider()
        if p is None:
            # Все заняты
            earliest = min(provider_available_at.get(pr, 0) for pr in PROVIDERS)
            wait = max(5, earliest - time.time())
            log(f"  Все провайдеры заняты, ждём {wait:.0f}с...")
            time.sleep(wait)
            continue

        result, retry = call_provider(p, prompt)
        if result:
            return result, p
        else:
            log(f"  [{p}] недоступен, retry={retry}с")
            provider_available_at[p] = time.time() + retry

# ──────────────────────────────────────────
# ИНДЕКСАЦИЯ
# ──────────────────────────────────────────
from src.memory.db import init_db, get_conn
from src.memory.indexer import importance_from_path, _get_e5_model
import numpy as np

init_db()
log("Загружаю e5-base...")
e5 = _get_e5_model()
log("e5-base готова")

TYPE_TABLE = {
    'facts':      {'DECISION','FACT','ARCHITECTURE','COMPONENT'},
    'episodes':   {'AUDIT','EVENT','CHAT','SESSION'},
    'procedures': {'PROCEDURE','TEMPLATE','RULE'},
}

def index_chunk(text, path, chunk_idx):
    """Индексация одного чанка. Возвращает количество фактов."""
    base_imp = importance_from_path(path)
    prompt = f"""Извлеки факты из текста. Отвечай ТОЛЬКО JSON-массивом без пояснений.
Формат: [{{"text":"...","type":"DECISION|FACT|AUDIT|EVENT|CHAT|PROCEDURE","importance":1-5,"table":"facts|episodes|procedures"}}]
Важность: 5=решение директора/утверждённая архитектура, 4=факт аудита, 3=предложение, 2=гипотеза, 1=шум(не включай)
Источник: {path}
Текст:
{text[:2500]}
JSON:"""

    result, provider = call_ai(prompt)
    if not result:
        return 0

    try:
        start = result.find('['); end = result.rfind(']') + 1
        if start < 0 or end <= start: return 0
        facts = json.loads(result[start:end])
    except:
        return 0

    count = 0
    with get_conn() as conn:
        for fact in facts:
            if fact.get('importance', 1) < 2: continue
            table = fact.get('table', 'facts')
            ftype = fact.get('type', 'FACT')
            if ftype not in TYPE_TABLE.get(table, set()):
                for tbl, types in TYPE_TABLE.items():
                    if ftype in types: table = tbl; break
                else: table, ftype = 'facts', 'FACT'

            try:
                vec = e5.encode(fact['text'], normalize_embeddings=True).astype(np.float32).tobytes()
            except: vec = None

            record = {
                'text': fact['text'], 'type': ftype,
                'status': 'АКТУАЛЬНО',
                'importance': fact.get('importance', base_imp),
                'source': path, 'source_path': path,
                'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }
            if vec: record['embedding'] = vec

            try:
                conn.execute(
                    f"INSERT INTO {table} ({','.join(record.keys())}) VALUES ({','.join(['?']*len(record))})",
                    list(record.values())
                )
                count += 1
            except Exception as e:
                if 'UNIQUE' not in str(e):
                    log(f"    DB: {e}")
        conn.commit()

    return count

def get_files_to_index():
    """Все .md файлы которые нужно проиндексировать."""
    import glob
    SKIP = {'.venv','node_modules','sandbox','.git','__pycache__','.pytest_cache','logs','kuzu_data'}
    files = []
    for p in glob.glob(ROOT+'/**/*.md', recursive=True):
        rel = p.replace(ROOT+'/', '')
        if any(s in p for s in SKIP): continue
        if len(open(p, encoding='utf-8', errors='ignore').read().strip()) < 50: continue
        files.append((p, rel))
    return files

def already_indexed(rel):
    """Проверяем есть ли хоть один факт из этого файла."""
    with get_conn() as conn:
        for t in ('facts','episodes','procedures'):
            n = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE source=?", (rel,)).fetchone()[0]
            if n > 0: return True
    return False

def export_and_push(total_new):
    """Экспорт в JSON и git push."""
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
    log(f"Экспорт: {exp['total']} записей")
    subprocess.run(['git','add','memory/memory_export.json'], cwd=ROOT)
    subprocess.run(['git','commit','--no-verify','-m',
        f'[MEM] Ночная индексация: +{total_new} фактов, всего {exp["total"]}'], cwd=ROOT)
    r = subprocess.run(['git','push','--no-verify','origin','main'], cwd=ROOT, capture_output=True, text=True)
    log("Git push: " + ("OK" if r.returncode==0 else f"ERR: {r.stderr[:80]}"))

# ──────────────────────────────────────────
# ГЛАВНЫЙ ЦИКЛ
# ──────────────────────────────────────────
CHUNK_SIZE = 2500
total_indexed = 0
last_push = time.time()

while True:
    files = get_files_to_index()
    pending = [(p, rel) for p, rel in files if not already_indexed(rel)]
    
    if not pending:
        log(f"Все {len(files)} файлов проиндексированы! Итого новых фактов: {total_indexed}")
        export_and_push(total_indexed)
        log("Демон завершён.")
        break

    log(f"Осталось: {len(pending)}/{len(files)} файлов")

    for file_path, rel in pending:
        text = open(file_path, encoding='utf-8', errors='ignore').read()
        chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
        log(f"Файл: {rel} ({len(chunks)} чанков)")

        file_facts = 0
        for i, chunk in enumerate(chunks):
            n = index_chunk(chunk, rel, i)
            file_facts += n
            total_indexed += n
            log(f"  чанк {i+1}/{len(chunks)}: {n} фактов")
            time.sleep(2)  # 2с между чанками

        log(f"  Файл готов: {file_facts} фактов")

        # Пушим каждые 30 минут
        if time.time() - last_push > 1800:
            export_and_push(total_indexed)
            last_push = time.time()

        time.sleep(3)  # 3с между файлами

log("=== ДЕМОН ЗАВЕРШИЛ РАБОТУ ===")
LOG.close()
