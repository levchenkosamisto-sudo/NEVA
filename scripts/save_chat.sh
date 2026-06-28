#!/bin/bash
# scripts/save_chat.sh — сохранение чата Claude Desktop в память NEVA
# Использование: ./scripts/save_chat.sh [имя_файла.md]
# Если файл не указан — читаем из stdin

cd "$(dirname "$0")/.."

TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
CHAT_DIR="memory/raw/chats"
mkdir -p "$CHAT_DIR"

if [ -n "$1" ] && [ -f "$1" ]; then
    # Копируем указанный файл
    DEST="$CHAT_DIR/${TIMESTAMP}_claude_desktop.md"
    cp "$1" "$DEST"
    echo "✅ Скопирован: $1 → $DEST"
else
    # Читаем из stdin
    DEST="$CHAT_DIR/${TIMESTAMP}_claude_desktop.md"
    cat > "$DEST"
    echo "✅ Записан из stdin: $DEST"
fi

# Коммитим в Гит
git add "$DEST" 2>/dev/null
git commit --no-verify -m "[CHAT] сохранён чат Claude Desktop $TIMESTAMP" 2>/dev/null

# Индексируем (фоново чтобы не блокировать)
source .venv/bin/activate 2>/dev/null
nohup python3 -m src.memory.indexer --file "$DEST" \
    >> logs/indexer.log 2>&1 &

echo "📚 Индексация запущена фоново (PID=$!)"
echo "📁 Файл: $DEST"
