# DEPLOY_TARGET: /Users/arka/Documents/NEVA/duma_audit_round1.py
# DEPLOY_MODE: copy
# DEPLOY_ARGS:
import sys
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
import json

PROMPT = """Ты — независимый аудитор системы NEVA (AI-оркестратор на Mac M1).
Твоя задача: провести Круг 1 аудита по протоколу ниже.

## ПРОТОКОЛ АУДИТА NEVA (7 этапов)

**Круг 1 — только вопросы, без оценок:**
- Задавай только вопросы. Без критики, без оценок, без альтернатив.
- Работаешь независимо. Не знаешь вопросов других аудиторов.
- Цель: выявить непонятное, неясное, потенциально проблемное.

**Полный протокол (7 этапов):**
1. ПОДГОТОВКА → snapshot + пакет + роли + промпты
2. КРУГ 1 → вопросы без оценок (независимо)
3. ОТВЕТЫ → исполнитель отвечает + исправляет
4. КРУГ 2 → альтернативы и оценки (независимо)
5. КОНСОЛИДАЦИЯ → согласие / спор → Директор
6. ДОРАБОТКА → до 5 циклов → эскалация Директору
7. ЗАКРЫТИЕ → чеклист + подписи + пакет

**Формат ответа (YAML):**
```yaml
audit_id: AUDIT-001
round: 1
auditor: [твоё имя — ChatGPT / Gemini / DeepSeek]
timestamp: [дата]

questions:
  - id: Q1
    topic: "[тема]"
    text: "[твой вопрос]"
  - id: Q2
    topic: "[тема]"
    text: "[твой вопрос]"
  # ... все вопросы

notes: |
  Любые дополнительные наблюдения
```

## ЧТО НУЖНО ПРОАУДИРОВАТЬ — АРХИТЕКТУРА NEVA

NEVA — система AI-оркестрации на Mac M1. Компоненты:
- **FlagmanRouter**: цепочка AI-провайдеров Cerebras→Groq→GitHub→OpenRouter→qwen→llama
- **ThermalGuard v9.4**: 9-состояний FSM, 32/34 тестов PASS, отдельный launchd агент
- **Medic L1/L2/L3**: авторемонт. L1=restart, L2=AI repair (Cerebras/Groq), L3=Claude
- **MCP Server v2.4**: порт 9000+9001, независим от Claude Desktop
- **Kuzu graph DB**: граф атомов P16 (8 полей)
- **neva_github_watcher**: следит за GitHub output/, Cerebras синтезирует ответы
- **DUMA**: система аудита — веб-ИИ читают input/ GitHub, пишут в output/, watcher синтезирует
- **Approval Gate :8766**: Директор утверждает критические операции
- **Exponential backoff**: 60с→5м→15м→30м→1ч, CHRONIC detection
- **8 API-ключей**: Cerebras, Groq, OpenRouter×2, GitHub Models, OpenAI, Gemini, DeepSeek
- **Хранилища**: Kuzu (граф), GitHub (SSOT 500GB), GDrive (backup+шина), SQLite
- **RAM 16GB**: конфликт qwen2.5:7b (8GB) + e5-small RAG — взаимоисключающая активация

**Текущий статус:** Этап 1 завершён (~50-60% MVP). Идёт планирование Этапа 2.

Задай 5-10 вопросов по архитектуре NEVA в формате YAML выше.
Только вопросы. Без оценок."""

OUT_DIR = Path.home() / 'Documents/NEVA/audit_responses'
OUT_DIR.mkdir(parents=True, exist_ok=True)
BRAVE = Path.home() / 'Library/Application Support/BraveSoftware/Brave-Browser'
BRAVE_EXE = '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser'

AIS = [
    {
        'name': 'ChatGPT',
        'id': 'CHATGPT',
        'url': 'https://chatgpt.com/',
        'input': ['div#prompt-textarea', 'div[contenteditable="true"]', 'textarea'],
        'send': ['[data-testid="send-button"]', 'button[aria-label*="Send"]'],
        'response': ['[data-message-author-role="assistant"] .markdown', '[data-message-author-role="assistant"]'],
        'wait_gone': '.result-streaming',
    },
    {
        'name': 'Gemini',
        'id': 'GEMINI',
        'url': 'https://gemini.google.com/',
        'input': ['rich-textarea div[contenteditable]', 'div[contenteditable="true"]', 'textarea'],
        'send': ['button[aria-label*="Send"]', 'button[mattooltip*="Send"]'],
        'response': ['model-response .markdown', 'message-content', '.response-container'],
        'wait_gone': '.loading',
    },
]


def try_fill(page, selectors, text, timeout=8000):
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout)
            if el and el.is_visible():
                el.click()
                page.wait_for_timeout(300)
                el.type(text, delay=5)
                return True
        except Exception:
            continue
    return False


def try_click(page, selectors, timeout=5000):
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout)
            if el and el.is_visible():
                el.click()
                return True
        except Exception:
            continue
    return False


def try_text(page, selectors, timeout=10000):
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout)
            if el:
                return el.inner_text()
        except Exception:
            continue
    return None


results = {}

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(BRAVE),
        executable_path=BRAVE_EXE,
        headless=False,
        args=['--no-first-run', '--no-default-browser-check'],
    )
    for ai in AIS:
        print(f'-> {ai["name"]}...')
        try:
            page = ctx.new_page()
            page.goto(ai['url'], wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(4000)
            ok = try_fill(page, ai['input'], PROMPT)
            if not ok:
                results[ai['name']] = 'ERROR: input not found'
                print(f'  ERR: input not found')
                page.close()
                continue
            page.wait_for_timeout(500)
            sent = try_click(page, ai['send'])
            if not sent:
                page.keyboard.press('Enter')
            print(f'  sent, waiting response...')
            # Ждём завершения генерации (до 120 сек)
            page.wait_for_timeout(5000)
            for _ in range(120):
                if not page.query_selector(ai.get('wait_gone', '.none_xyz')):
                    break
                page.wait_for_timeout(1000)
            page.wait_for_timeout(3000)
            text = try_text(page, ai['response'], timeout=10000)
            if text:
                results[ai['name']] = text.strip()
                print(f'  ok ({len(text)} chars)')
            else:
                results[ai['name']] = 'ERROR: no response captured'
                print(f'  ERR: no response')
            page.close()
        except Exception as e:
            results[ai['name']] = f'ERROR: {e}'
            print(f'  ERR: {e}')
    ctx.close()

# Сохраняем результаты
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
lines = [f'# DUMA AUDIT-001 Round 1 | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n']
registry = {}

for ai in AIS:
    name = ai['name']
    ai_id = ai['id']
    ans = results.get(name, 'NOT RUN')
    lines.append(f'## {name} (AUDIT-001-R1-{ai_id})\n\n{ans}\n')
    ai_file = OUT_DIR / f'AUDIT-001-R1-{ai_id}.yaml'
    ai_file.write_text(ans, encoding='utf-8')
    print(f'  saved: {ai_file}')
    registry[f'AUDIT-001-R1-{ai_id}'] = {
        'auditor': name,
        'round': 1,
        'status': 'received' if ans and not ans.startswith('ERROR') and ans != 'NOT RUN' else 'error',
        'timestamp': datetime.now().isoformat(),
        'file': f'AUDIT-001-R1-{ai_id}.yaml'
    }

out_file = OUT_DIR / f'AUDIT-001-R1-RAW_{ts}.md'
out_file.write_text('\n'.join(lines), encoding='utf-8')
print(f'SAVED: {out_file}')

registry_path = OUT_DIR / 'AUDIT-001-registry.json'
registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2))
print(f'REGISTRY: {registry_path}')
