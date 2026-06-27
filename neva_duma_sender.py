#!/usr/bin/env python3
"""
neva_duma_sender.py — локальный клиент для передачи документов думы АПИ-ИИ.
Решает проблему: веб-ИИ не могут читать файлы через MCP.
Альтернатива по предложению Gemini 2026-06-27.

Использование:
  python3 neva_duma_sender.py --model gemini --auditor DUMA-MEM-GIT-2
"""
import os
import sys
import json
import argparse
import requests
from pathlib import Path

NEVA_DIR = Path.home() / 'Documents' / 'NEVA'
AUDIT_DIR = NEVA_DIR / 'audit_responses'
ENV_FILE = NEVA_DIR / '.env'


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env


def read_docs(audit_id):
    arch = (AUDIT_DIR / f'{audit_id}-ARCH.md').read_text()
    task = (AUDIT_DIR / f'{audit_id}-TASK.md').read_text()
    prompt = (AUDIT_DIR / f'{audit_id}-PROMPT.txt').read_text()
    return arch, task, prompt


def write_result(auditor, content):
    """Сохраняет ответ аудитора на Мак."""
    audit_id = sys.argv[sys.argv.index('--auditor') + 1] if '--auditor' in sys.argv else 'DUMA'
    out_file = AUDIT_DIR / f'{audit_id}-R1-{auditor.upper()}.md'
    out_file.write_text(content)
    print(f'OK: сохранён в {out_file}')


def call_gemini(env, arch, task, prompt):
    api_key = env.get('GEMINI_API_KEY', '')
    if not api_key:
        print('ERROR: GEMINI_API_KEY не найден')
        sys.exit(1)

    context = f"""=== ДОКУМЕНТ 1: АРХИТЕКТУРА ===\n{arch}\n\n=== ДОКУМЕНТ 2: ТЗ ===\n{task}\n\n=== ЗАДАНИЕ ===\n{prompt}"""

    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={api_key}'
    body = {'contents': [{'parts': [{'text': context}]}]}
    resp = requests.post(url, json=body, timeout=60)
    resp.raise_for_status()
    answer = resp.json()['candidates'][0]['content']['parts'][0]['text']
    return answer


def call_deepseek(env, arch, task, prompt):
    api_key = env.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        print('ERROR: DEEPSEEK_API_KEY не найден')
        sys.exit(1)

    context = f"=== АРХИТЕКТУРА ===\n{arch}\n\n=== ТЗ ===\n{task}\n\n=== ЗАДАНИЕ ===\n{prompt}"
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    body = {'model': 'deepseek-reasoner', 'messages': [{'role': 'user', 'content': context}], 'max_tokens': 4000}
    resp = requests.post('https://api.deepseek.com/chat/completions', headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']


def call_chatgpt(env, arch, task, prompt):
    api_key = env.get('OPENAI_API_KEY', '')
    if not api_key:
        print('ERROR: OPENAI_API_KEY не найден')
        sys.exit(1)

    context = f"=== АРХИТЕКТУРА ===\n{arch}\n\n=== ТЗ ===\n{task}\n\n=== ЗАДАНИЕ ===\n{prompt}"
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    body = {'model': 'gpt-4o', 'messages': [{'role': 'user', 'content': context}], 'max_tokens': 4000}
    resp = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['gemini', 'deepseek', 'chatgpt', 'all'], required=True)
    parser.add_argument('--auditor', default='DUMA-MEM-GIT-2')
    args = parser.parse_args()

    env = load_env()
    arch, task, prompt = read_docs(args.auditor)
    print(f'Документы загружены: ARCH {len(arch)} симв., TASK {len(task)} симв.')

    models = ['gemini', 'deepseek', 'chatgpt'] if args.model == 'all' else [args.model]

    for model in models:
        print(f'\nОтправляю в {model}...')
        try:
            if model == 'gemini':
                answer = call_gemini(env, arch, task, prompt)
            elif model == 'deepseek':
                answer = call_deepseek(env, arch, task, prompt)
            else:
                answer = call_chatgpt(env, arch, task, prompt)
            write_result(model, f'AUDITOR: {model}\nDATE: 2026-06-27\n\n{answer}')
        except Exception as e:
            print(f'ERROR {model}: {e}')


if __name__ == '__main__':
    main()
