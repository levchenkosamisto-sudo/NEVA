#!/bin/bash
# scripts/index_file.sh — индексация одного файла в память NEVA

NEVA_DIR="/Users/arka/Documents/NEVA"
cd "$NEVA_DIR"

PYTHON="$NEVA_DIR/.venv/bin/python3"
[ -f "$PYTHON" ] || PYTHON="$(which python3)"

# Грузим переменные окружения




FILE="$1"
if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
    echo "[$(date '+%H:%M:%S')] ERROR: файл не найден: $FILE" >> "$NEVA_DIR/logs/indexer.log"
    exit 1
fi

# Пропускаем служебные файлы
case "$FILE" in
    *.pyc|*.pyo|*.db|*.db-wal|*.db-shm|*.log|*.flag) exit 0 ;;
esac


# Загружаем только KEY=VALUE строки из .env
if [ -f "$NEVA_DIR/.env" ]; then
    while IFS='=' read -r key val; do
        [[ "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]] && export "$key=$val"
    done < <(grep -E '^[A-Z_][A-Z0-9_]+=.+' "$NEVA_DIR/.env")
fi

LOGFILE="$NEVA_DIR/logs/indexer.log"
mkdir -p "$NEVA_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ИНДЕКСИРУЮ: $FILE" >> "$LOGFILE"

"$PYTHON" -c "
import sys, os
sys.path.insert(0, '$NEVA_DIR')
from src.memory.db import init_db
from src.memory.indexer import index_document
from pathlib import Path

init_db()
path = '$FILE'
rel = os.path.relpath(path, '$NEVA_DIR')
text = Path(path).read_text(encoding='utf-8', errors='ignore')
n = index_document(rel, text)
print(f'[INDEXER] {rel}: {n} фактов')
" >> "$LOGFILE" 2>&1

STATUS=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ГОТОВО: $FILE (exit=$STATUS)" >> "$LOGFILE"
exit $STATUS
