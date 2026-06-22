#!/usr/bin/env python3
"""
DUMA Orchestrator v1.0
Схема: Claude готовит промпт → GitHub → Orchestrator → API аудиторов → GitHub → Claude

Оркестратор читает промпт из GitHub, рассылает параллельно всем аудиторам
через API, собирает ответы, заливает обратно в GitHub.
"""
import asyncio
import httpx
import json
import os
import base64
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path.home() / 'Documents/NEVA/.env')

# ─── КОНФИГ ───────────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO  = 'levchenkosamisto-sudo/NEVA'
GITHUB_API   = 'https://api.github.com'

AUDIT_ID     = 'AUDIT-001'
ROUND        = 2
INPUT_FILE   = f'audit_responses/{AUDIT_ID}-R{ROUND}-PROMPT.md'
OUTPUT_DIR   = 'audit_responses'

AUDITORS = [
    {
        'id': 'CEREBRAS',
        'name': 'Cerebras gpt-oss-120b',
        'url': 'https://api.cerebras.ai/v1/chat/completions',
        'model': 'gpt-oss-120b',
        'key_env': 'CEREBRAS_API_KEY',
        'system': 'Ты независимый технический аудитор AI-систем. Анализируй объективно, выявляй риски, предлагай конкретные улучшения.',
    },
    {
        'id': 'GEMINI',
        'name': 'Gemini 1.5 Pro',
        'url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
        'model': 'gemini-2.0-flash',
        'key_env': 'GEMINI_API_KEY',
        'system': 'Ты независимый технический аудитор AI-систем. Анализируй объективно, выявляй риски, предлагай конкретные улучшения.',
    },
    {
        'id': 'OPENROUTER',
        'name': 'OpenRouter DeepSeek R1',
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'model': 'deepseek/deepseek-r1:free',
        'key_env': 'OPENROUTER_API_KEY',
        'system': 'Ты независимый технический аудитор AI-систем. Анализируй объективно, выявляй риски, предлагай конкретные улучшения.',
    },
    {
        'id': 'GROQ',
        'name': 'Groq llama-3.3-70b',
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'model': 'llama-3.3-70b-versatile',
        'key_env': 'GROQ_API_KEY',
        'system': 'Ты независимый технический аудитор AI-систем. Анализируй объективно, выявляй риски, предлагай конкретные улучшения.',
    },
]

# ─── GITHUB ───────────────────────────────────────────────────────────────────

async def github_read(client: httpx.AsyncClient, path: str) -> str:
    """Читает файл из GitHub репо."""
    r = await client.get(
        f'{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}',
        headers={'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'},
    )
    r.raise_for_status()
    data = r.json()
    return base64.b64decode(data['content']).decode('utf-8')


async def github_write(client: httpx.AsyncClient, path: str, content: str, message: str):
    """Создаёт или обновляет файл в GitHub."""
    # Проверяем существует ли файл (нужен sha для update)
    sha = None
    try:
        r = await client.get(
            f'{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}',
            headers={'Authorization': f'token {GITHUB_TOKEN}'},
        )
        if r.status_code == 200:
            sha = r.json().get('sha')
    except Exception:
        pass

    body = {
        'message': message,
        'content': base64.b64encode(content.encode('utf-8')).decode('utf-8'),
    }
    if sha:
        body['sha'] = sha

    r = await client.put(
        f'{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}',
        headers={'Authorization': f'token {GITHUB_TOKEN}', 'Content-Type': 'application/json'},
        content=json.dumps(body),
    )
    r.raise_for_status()
    print(f'  [GitHub] ✅ {path}')

# ─── AI ВЫЗОВЫ ────────────────────────────────────────────────────────────────

async def call_openai(client: httpx.AsyncClient, auditor: dict, prompt: str) -> str:
    key = os.getenv(auditor['key_env'])
    if not key:
        return f'ERROR: {auditor["key_env"]} not set'
    r = await client.post(
        auditor['url'],
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={
            'model': auditor['model'],
            'messages': [
                {'role': 'system', 'content': auditor['system']},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': 4000,
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


async def call_gemini(client: httpx.AsyncClient, auditor: dict, prompt: str) -> str:
    key = os.getenv(auditor['key_env'])
    if not key:
        return f'ERROR: {auditor["key_env"]} not set'
    r = await client.post(
        f'{auditor["url"]}?key={key}',
        headers={'Content-Type': 'application/json'},
        json={
            'system_instruction': {'parts': [{'text': auditor['system']}]},
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'maxOutputTokens': 4000},
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()['candidates'][0]['content']['parts'][0]['text']


async def call_auditor(client: httpx.AsyncClient, auditor: dict, prompt: str) -> tuple[str, str]:
    """Вызывает одного аудитора, возвращает (id, ответ)."""
    print(f'  → {auditor["name"]}...')
    try:
        if auditor['id'] == 'GEMINI':
            text = await call_gemini(client, auditor, prompt)
        else:
            text = await call_openai(client, auditor, prompt)
        print(f'  ✅ {auditor["name"]} ({len(text)} chars)')
        return auditor['id'], text
    except Exception as e:
        err = f'ERROR: {e}'
        print(f'  ❌ {auditor["name"]}: {e}')
        return auditor['id'], err

# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'\n=== DUMA Orchestrator v1.0 | {ts} ===')
    print(f'Audit: {AUDIT_ID} Round {ROUND}')

    async with httpx.AsyncClient() as client:

        # 1. Читаем промпт из GitHub
        print(f'\n[1] Читаю промпт: {INPUT_FILE}')
        try:
            prompt = await github_read(client, INPUT_FILE)
            print(f'  ✅ {len(prompt)} chars')
        except Exception as e:
            print(f'  ❌ Не найден: {e}')
            print('  Создаю дефолтный промпт...')
            prompt = DEFAULT_PROMPT

        # 2. Параллельно рассылаем всем аудиторам
        print(f'\n[2] Рассылаю {len(AUDITORS)} аудиторам параллельно...')
        tasks = [call_auditor(client, a, prompt) for a in AUDITORS]
        results = await asyncio.gather(*tasks)

        # 3. Заливаем каждый ответ в GitHub
        print(f'\n[3] Заливаю ответы в GitHub...')
        summary_lines = [f'# DUMA {AUDIT_ID} Round {ROUND} — Ответы аудиторов\n']
        summary_lines.append(f'Дата: {ts}\n')

        for ai_id, text in results:
            path = f'{OUTPUT_DIR}/{AUDIT_ID}-R{ROUND}-{ai_id}.md'
            content = f'# {AUDIT_ID} Round {ROUND} — {ai_id}\nДата: {ts}\n\n{text}'
            await github_write(client, path, content, f'DUMA: {AUDIT_ID} R{ROUND} response from {ai_id}')
            summary_lines.append(f'\n## {ai_id}\n\n{text[:500]}...\n')

        # 4. Сводный файл
        summary_path = f'{OUTPUT_DIR}/{AUDIT_ID}-R{ROUND}-SUMMARY.md'
        await github_write(client, summary_path, '\n'.join(summary_lines),
                           f'DUMA: {AUDIT_ID} R{ROUND} SUMMARY')

    print(f'\n=== DONE | Все ответы в GitHub: {OUTPUT_DIR}/ ===')
    print(f'Следующий шаг: Claude читает {AUDIT_ID}-R{ROUND}-SUMMARY.md и синтезирует')


# ─── ПРОМПТ ПО УМОЛЧАНИЮ (если нет в GitHub) ──────────────────────────────────

DEFAULT_PROMPT = """Ты независимый аудитор системы NEVA — AI-оркестратора на Mac M1 (16GB RAM).

Архитектура:
- FlagmanRouter: Cerebras→Groq→GitHub Models→OpenRouter×2→qwen2.5:7b→llama3.2:3b
- ThermalGuard v9.4: FSM 9 состояний, 32/34 PASS (2 FAIL: race condition EMERGENCY→RECOVERY)
- Medic L1/L2/L3: L1=restart, L2=Cerebras/Groq AI repair, L3=Claude при CHRONIC
- MCP Server v2.4: порты 9000 (JSON-RPC) + 9001 (Dashboard)
- Kuzu graph DB: атомы P16 (8 полей), Write Queue asyncio.Lock
- DUMA: аудит через GitHub input/output polling
- Approval Gate :8766: блокирует sudo/delete/deploy/платные API
- Exponential backoff: 60с→5м→15м→30м→1ч + CHRONIC detection
- RAM: qwen2.5:7b (8GB) ИЛИ e5-small RAG (2GB) — взаимоисключающие
- Незавершено: Graphiti(MockGraph), e5-small, TTL, Trust Engine, GDrive backup

Ответы исполнителя:
https://raw.githubusercontent.com/levchenkosamisto-sudo/NEVA/main/audit_responses/AUDIT-001-R1-ANSWERS.md

Круг 2 — твоя задача:
1. По каждому своему вопросу Круга 1 — оценка: ДОСТАТОЧНО / НЕДОСТАТОЧНО / РИСК
2. Критичность: LOW / MEDIUM / HIGH / BLOCKER
3. Для НЕДОСТАТОЧНО — конкретное лучшее решение
4. Новые риски не охваченные Кругом 1
5. Топ-3 проблемы которые нужно решить первыми
"""

if __name__ == '__main__':
    asyncio.run(main())
