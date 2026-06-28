#!/bin/bash
# scripts/neva_dedup.sh — ночной процесс дедупликации памяти
# Запускается launchd в 00:00

cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null

LOGFILE="logs/dedup_$(date +%Y%m%d).log"
mkdir -p logs

echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEDUP START" >> "$LOGFILE"

# Запускаем дедупликацию
python3 -m src.memory.dedup 2>>"$LOGFILE"
STATUS=$?

# Векторизуем отложенные
python3 -c "
from src.memory.indexer import vectorize_pending
n = vectorize_pending()
print(f'Векторизовано: {n}')
" >> "$LOGFILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEDUP END status=$STATUS" >> "$LOGFILE"

# Уведомление в Телеграм
source .env 2>/dev/null
if [ -n "$TELEGRAM_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    MSG="🌙 NEVA ПАМЯТЬ: ночной процесс завершён $(date '+%Y-%m-%d')"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${MSG}" > /dev/null 2>&1
fi

exit $STATUS
