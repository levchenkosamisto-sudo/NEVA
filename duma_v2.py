#!/usr/bin/env python3
"""
DUMA v2 — Единый чат на весь аудит.
Архитектура: один чат на аудитора = весь аудит (все круги).
Аудитор помнит свои вопросы и ответы — не нужно вставлять историю в промпт.

Использование:
  python3 duma_v2.py --audit AUDIT_ID --round N --prompt FILE [--auditor all|chatgpt|gemini|deepseek|grok]

Пример:
  # Круг 1 (новые чаты):
  python3 duma_v2.py --audit THERMAL-002 --round 1 --prompt audit_responses/THERMAL-002-R1-PROMPT.txt

  # Круг 2 (те же чаты — URL сохранены после Круга 1):
  python3 duma_v2.py --audit THERMAL-002 --round 2 --prompt audit_responses/THERMAL-002-R2-PROMPT.txt

Состояние (URLs чатов) хранится в: audit_responses/{AUDIT_ID}-SESSIONS.json
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE     = Path.home() / 'Documents/NEVA'
SESSIONS = BASE / 'audit_responses'
SESSIONS.mkdir(exist_ok=True)

CDP_URL      = 'http://localhost:9222'   # основной Chrome — все 4 аудитора
CDP_URL_GROK = 'http://localhost:9222'   # Grok тоже в основном Chrome (залогинен)

# ─── СЕЛЕКТОРЫ ────────────────────────────────────────────────────────────────
SEL = {
    'chatgpt': {
        'input':    '#prompt-textarea',
        'send':     '[data-testid="send-button"]',
        'send_ok':  '[data-testid="send-button"]:not([disabled])',
        'busy':     '[data-testid="send-button"][disabled]',
        'response': '[data-message-author-role="assistant"]',
        'base_url': 'https://chatgpt.com/',
        'insert':   'execCommand',   # React — только execCommand
    },
    'gemini': {
        'input':    '.ql-editor',
        'send':     None,            # через JS aria-label
        'busy':     '[aria-label*="Остановить"],[aria-label*="Stop"]',
        'response': 'model-response',
        'base_url': 'https://gemini.google.com/app',
        'insert':   'execCommand',
    },
    'deepseek': {
        'input':    'textarea',
        'send':     None,            # Enter
        'busy':     '[class*="loading"],[class*="generating"]',
        'response': '.ds-markdown',
        'base_url': 'https://chat.deepseek.com/',
        'insert':   'fill',          # обычный fill()
    },
    'grok': {
        'input':    'div[contenteditable="true"]',
        'send':     None,
        'busy':     '[class*="loading"],[class*="thinking"],[class*="spinner"]',
        'response': '[class*="response-content-markdown"]',
        'base_url': 'https://grok.com/',
        'insert':   'fill',
        'has_url':  False,    # Grok не имеет постоянного URL чата
    },
}

AUDITORS = list(SEL.keys())


# ─── ВСТАВКА ТЕКСТА ───────────────────────────────────────────────────────────

def insert_text(page, auditor: str, text: str):
    s = SEL[auditor]
    if s['insert'] == 'execCommand':
        # ChatGPT, Gemini — React/Quill редакторы
        sel = s['input']
        page.locator(sel).first.click()
        page.wait_for_timeout(300)
        page.evaluate(
            f"(t) => {{ const e = document.querySelector('{sel}'); "
            f"e.focus(); document.execCommand('insertText', false, t); }}",
            text
        )
    elif auditor == 'grok':
        # Grok — contenteditable div, fill() не работает
        el = page.locator(s['input']).first
        el.click()
        page.wait_for_timeout(300)
        el.fill(text)
    else:
        # DeepSeek — textarea с нативным setter
        sel = s['input']
        page.locator(sel).first.click()
        page.wait_for_timeout(300)
        page.evaluate(
            """(args) => {
                const [sel, t] = args;
                const el = document.querySelector(sel);
                const proto = el.tagName === 'TEXTAREA'
                    ? window.HTMLTextAreaElement.prototype
                    : window.HTMLElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value');
                if (setter) {
                    setter.set.call(el, t);
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                } else {
                    el.value = t;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                }
            }""",
            [sel, text]
        )


def send_message(page, auditor: str):
    s = SEL[auditor]
    if auditor == 'chatgpt':
        page.wait_for_timeout(800)
        page.locator(s['send_ok']).wait_for(timeout=10000)
        page.locator(s['send']).click()
    elif auditor == 'gemini':
        page.wait_for_timeout(800)
        sent = page.evaluate("""(() => {
            const b = Array.from(document.querySelectorAll('button'))
                .find(x => x.getAttribute('aria-label')?.includes('Отправить'));
            if (b && !b.disabled) { b.click(); return true; }
            return false;
        })()""")
        if not sent:
            page.keyboard.press('Enter')
    else:
        page.keyboard.press('Enter')


def wait_response(page, auditor: str, timeout_sec: int = 180):
    s = SEL[auditor]
    page.wait_for_timeout(5000)
    for _ in range(timeout_sec):
        if not page.query_selector(s['busy']):
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(3000)


def get_last_response(page, auditor: str) -> str:
    s = SEL[auditor]
    msgs = page.locator(s['response']).all()
    if not msgs:
        return 'NO RESPONSE'

    # Всегда берём только ПОСЛЕДНЕЕ сообщение — не всю историю чата.
    last = msgs[-1]

    if auditor == 'grok':
        text = last.inner_text()
        return re.sub(r'Размышление на протяжении \d+s\s*', '', text).strip()
    elif auditor == 'gemini':
        text = last.inner_text().strip()
        if not text:
            fallback = page.locator('message-content, .response-content').all()
            if fallback:
                text = fallback[-1].inner_text().strip()
        return text or 'NO RESPONSE'
    else:
        return last.inner_text()


# ─── СЕССИИ (хранение URL чатов) ──────────────────────────────────────────────

def sessions_path(audit_id: str) -> Path:
    return SESSIONS / f'{audit_id}-SESSIONS.json'


def load_sessions(audit_id: str) -> dict:
    p = sessions_path(audit_id)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def save_sessions(audit_id: str, sessions: dict):
    sessions_path(audit_id).write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False)
    )


def get_chat_url(page, auditor: str) -> str:
    """Возвращает постоянный URL текущего чата."""
    url = page.url
    # Gemini: иногда редиректит не сразу — ждём
    if auditor == 'gemini':
        for _ in range(10):
            if '/app/' in url and len(url) > 40:
                break
            page.wait_for_timeout(1000)
            url = page.url
    return url


# ─── НАВИГАЦИЯ ────────────────────────────────────────────────────────────────

def open_or_resume(page, auditor: str, sessions: dict, round_num: int):
    """Круг 1 → новый чат. Круг 2+ → возвращаемся в существующий чат."""
    s = SEL[auditor]

    if round_num == 1 or auditor not in sessions:
        # Новый чат
        page.goto(s['base_url'], wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(4000)
        print(f'[{auditor}] новый чат')
    else:
        # Возвращаемся в сохранённый чат
        chat_url = sessions[auditor]
        page.goto(chat_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(4000)
        print(f'[{auditor}] возобновляем чат: {chat_url}')

        # Grok не имеет постоянных URL — нажимаем на последний чат в боковой панели
        if auditor == 'grok' and 'grok.com' in page.url:
            try:
                page.locator('[data-testid="conversation-item"]').first.click()
                page.wait_for_timeout(2000)
            except Exception:
                pass

    # Проверяем что залогинены
    _check_login(page, auditor)


def _check_login(page, auditor: str):
    """Проверяет залогиненность. Разные индикаторы для каждого аудитора."""
    s = SEL[auditor]
    body = page.inner_text('body')[:800].lower()

    # Специфичные признаки незалогиненности
    not_logged_in = False
    if auditor == 'chatgpt':
        not_logged_in = 'log in' in body or 'sign up' in body and 'new chat' not in body
    elif auditor == 'gemini':
        not_logged_in = 'sign in' in body and 'чат' not in body and 'chat' not in body
    elif auditor == 'deepseek':
        not_logged_in = 'new chat' not in body and 'войти' in body
    elif auditor == 'grok':
        not_logged_in = 'войти' in body[:200] and 'grok' not in body[:200]

    if not_logged_in:
        print(f'[{auditor}] ⚠️  НЕ ЗАЛОГИНЕН — требуется ручной вход')
        sys.exit(1)


# ─── ОДИН АУДИТОР ─────────────────────────────────────────────────────────────

def run_auditor(pw, auditor: str, prompt: str, audit_id: str,
                round_num: int, sessions: dict) -> str:
    cdp = CDP_URL_GROK if auditor == 'grok' else CDP_URL
    b = pw.chromium.connect_over_cdp(cdp)
    s = SEL[auditor]

    # Для Круга 2+: возвращаемся в сохранённый чат
    if round_num > 1 and auditor in sessions:
        chat_url = sessions[auditor]

        if auditor == 'grok' and chat_url.startswith('https://grok.com/c/'):
            # Grok имеет постоянный URL — переходим напрямую
            page = b.contexts[0].new_page()
            page.goto(chat_url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)
            print(f'[grok] возобновляем чат: {chat_url[:60]}')
        else:
            # ChatGPT / Gemini / DeepSeek — по сохранённому URL
            page = None
            for ctx in b.contexts:
                for pg in ctx.pages:
                    if chat_url in pg.url or pg.url in chat_url:
                        page = pg
                        break
                if page:
                    break
            if not page:
                page = b.contexts[0].new_page()
            page.goto(chat_url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)
            print(f'[{auditor}] возобновляем чат: {chat_url}')
    else:
        # Круг 1: ищем уже залогиненную страницу этого аудитора
        base = s['base_url'].rstrip('/')
        page = None
        for ctx in b.contexts:
            for pg in ctx.pages:
                if base in pg.url:
                    page = pg
                    break
            if page:
                break
        if page:
            # Переходим на базовый URL (новый чат) в существующей странице
            page.goto(base, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)
            print(f'[{auditor}] новый чат (залогиненная страница)')
        else:
            # Нет открытой страницы — создаём
            page = b.contexts[0].new_page()
            page.goto(base, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(4000)
            print(f'[{auditor}] новый чат (новая страница)')

    # Проверяем что залогинены
    _check_login(page, auditor)

    # Закрываем попапы (Grok)
    if auditor == 'grok':
        try:
            page.locator('button:has-text("Отклонить")').first.click(timeout=2000)
        except Exception:
            pass

    try:
        # Вставляем промпт и отправляем
        insert_text(page, auditor, prompt)
        page.wait_for_timeout(500)
        send_message(page, auditor)
        print(f'[{auditor}] Круг {round_num} отправлен')

        # Ждём ответ
        wait_response(page, auditor)

        # Сохраняем URL чата после первого круга
        if round_num == 1:
            url = get_chat_url(page, auditor)
            if url and url != s['base_url'].rstrip('/') and url != s['base_url']:
                sessions[auditor] = url
                print(f'[{auditor}] сохранён URL: {url}')
            elif auditor == 'grok':
                # Grok иногда не меняет URL — сохраняем маркер что чат начат
                sessions[auditor] = url or 'grok:latest'
                print(f'[{auditor}] чат начат (URL: {sessions[auditor]})')

        # Получаем ответ
        text = get_last_response(page, auditor)
        print(f'[{auditor}] {len(text)} символов')
        return text

    except Exception as e:
        raise


# ─── ГЛАВНАЯ ЛОГИКА ───────────────────────────────────────────────────────────

# ─── ЛИМИТ TOOL_USE ──────────────────────────────────────────────────────────
# Claude имеет лимит на количество tool_use в одном ответе (~25 вызовов).
# ПРАВИЛО: запускать каждого аудитора ОТДЕЛЬНЫМ start_process, не все сразу в цикле.
# Максимум за один ответ Claude: 1 аудитор × 1 круг.
# Для всех 4 — 4 отдельных ответа или один цикл в терминале пользователя.
MAX_TOOL_USE_WARNING = True  # напоминание для Claude

def main():
    ap = argparse.ArgumentParser(description='DUMA v2 — единый чат на весь аудит')
    ap.add_argument('--audit',    required=True, help='ID аудита, напр. THERMAL-002')
    ap.add_argument('--round',    required=True, type=int, help='Номер круга (1, 2, 3...)')
    ap.add_argument('--prompt',   required=True, help='Путь к файлу с промптом')
    ap.add_argument('--auditor',  default='all',
                    help='Аудитор: all | chatgpt | gemini | deepseek | grok')
    ap.add_argument('--out-dir',  default=str(SESSIONS), help='Папка для сохранения ответов')
    args = ap.parse_args()

    prompt_path = Path(args.prompt)
    if not prompt_path.exists():
        print(f'Файл промпта не найден: {prompt_path}')
        sys.exit(1)

    prompt = prompt_path.read_text(encoding='utf-8')
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    # Загружаем сохранённые URL сессий
    sessions = load_sessions(args.audit)

    # Определяем список аудиторов
    if args.auditor == 'all':
        targets = AUDITORS
    else:
        targets = [args.auditor]

    # Для Круга 1 — ChatGPT оборачиваем в XML (React-поле)
    prompts = {}
    for a in targets:
        if a == 'chatgpt':
            prompts[a] = (
                f'<user_attachments><attachment name="R{args.round}.md">'
                f'{prompt}</attachment></user_attachments>'
            )
        else:
            prompts[a] = prompt

    results = {}
    with sync_playwright() as pw:
        for auditor in targets:
            try:
                text = run_auditor(
                    pw, auditor, prompts[auditor],
                    args.audit, args.round, sessions
                )
                results[auditor] = text

                # Сохраняем ответ
                out_file = out_dir / f'{args.audit}-R{args.round}-{auditor.upper()}.md'
                out_file.write_text(
                    f'# {auditor.title()} — {args.audit} Круг {args.round}\n'
                    f'Дата: {datetime.now()}\n\n{text}',
                    encoding='utf-8'
                )
                print(f'[{auditor}] сохранён → {out_file.name}')

            except Exception as e:
                print(f'[{auditor}] ОШИБКА: {e}')
                results[auditor] = f'ERROR: {e}'

    # Сохраняем сессии (URLs) для следующего круга
    save_sessions(args.audit, sessions)
    print(f'\n✅ Круг {args.round} завершён. Сессии: {sessions_path(args.audit).name}')
    print(f'Аудиторы: {list(results.keys())}')

    # Итог
    for a, text in results.items():
        status = 'OK' if not text.startswith('ERROR') else '❌'
        print(f'  {status} {a}: {len(text)} символов')


if __name__ == '__main__':
    main()
