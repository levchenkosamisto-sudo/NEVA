#!/bin/bash
# scripts/neva_watcher.sh — демон-наблюдатель файловой системы
# Следит за папками и автоматически индексирует новые/изменённые файлы
#
# Наблюдаемые папки:
#   memory/raw/chats/     — чаты Claude Desktop и аудиторов
#   governance/decisions/ — решения Директора (важность 5)
#   governance/architecture/ — архитектурные документы
#   state/tasks/          — задачи
#   audit/responses/      — ответы аудиторов

NEVA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$NEVA_DIR"

LOGFILE="$NEVA_DIR/logs/watcher.log"
mkdir -p "$NEVA_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] WATCHER START PID=$$" >> "$LOGFILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Наблюдаю: memory/raw/chats/, governance/, state/tasks/, audit/responses/" >> "$LOGFILE"

# Папки для наблюдения
WATCH_DIRS=(
    "$NEVA_DIR/memory/raw/chats"
    "$NEVA_DIR/governance/decisions"
    "$NEVA_DIR/governance/architecture"
    "$NEVA_DIR/state/tasks"
    "$NEVA_DIR/audit/responses"
)

# Создаём папки если не существуют
for dir in "${WATCH_DIRS[@]}"; do
    mkdir -p "$dir"
done

# Запускаем fswatch
# -0: null-разделитель между именами файлов
# -r: рекурсивно
# --event Created --event Updated: только создание и обновление
# --latency 2: ждать 2 секунды перед уведомлением (batch)
# --exclude: игнорируем служебные файлы

fswatch \
    --recursive \
    --latency 2 \
    --event Created \
    --event Updated \
    --exclude "\.pyc$" \
    --exclude "\.db$" \
    --exclude "\.log$" \
    --exclude "\.flag$" \
    --exclude "__pycache__" \
    --exclude "\.git/" \
    --include "\.(md|txt|json)$" \
    "${WATCH_DIRS[@]}" \
    | while read -r CHANGED_FILE; do
        echo "[$(date '+%H:%M:%S')] ИЗМЕНЁН: $CHANGED_FILE" >> "$LOGFILE"

        # Запускаем индексацию в фоне (не блокируем поток)
        "$NEVA_DIR/scripts/index_file.sh" "$CHANGED_FILE" &

    done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] WATCHER STOP" >> "$LOGFILE"
