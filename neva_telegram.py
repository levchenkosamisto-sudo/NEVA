#!/usr/bin/env python3
"""
neva_telegram.py — уведомления Директора в Telegram.
Вызывается Claude в конце каждого ответа И при любой остановке.
"""
import json, os, sys, urllib.request, urllib.parse
from pathlib import Path

TOKEN   = '8577539474:AAFL14KKxZ9GGWOuxb14qGHL1HJpJaIjmq0'
CHAT_ID = '1919255029'

def send(msg: str, silent: bool = False) -> bool:
    try:
        data = urllib.parse.urlencode({
            'chat_id': CHAT_ID, 'text': msg,
            'parse_mode': 'HTML',
            'disable_notification': silent,
        }).encode()
        r = urllib.request.urlopen(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            data, timeout=8
        )
        return json.loads(r.read()).get('ok', False)
    except Exception as e:
        print(f'[tg] err: {e}', file=sys.stderr)
        return False

def done(task: str):
    """✅ Задание выполнено."""
    send(f'✅ <b>NEVA</b>: {task[:200]}')

def stopped(reason: str):
    """⏸ Остановка — нужен ввод или решение Директора."""
    send(f'⏸ <b>NEVA остановлена</b>: {reason[:200]}')

def error(msg: str):
    """❌ Ошибка."""
    send(f'❌ <b>NEVA ошибка</b>: {msg[:200]}')

def progress(msg: str):
    """ℹ️ Промежуточный статус."""
    send(f'ℹ️ <b>NEVA</b>: {msg[:200]}', silent=True)

if __name__ == '__main__':
    # python3 neva_telegram.py "сообщение"
    msg = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'тест'
    print('OK' if send(msg) else 'FAIL')
