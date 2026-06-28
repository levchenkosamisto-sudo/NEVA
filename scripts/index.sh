#!/bin/bash
# scripts/index.sh — переиндексация памяти NEVA
cd "$(dirname "$0")/.."

echo "=== NEVA REINDEX ==="
source .env 2>/dev/null || true

if [ -f "src/memory/indexer.py" ]; then
  python src/memory/indexer.py --full
  echo "✅ Индексация завершена"
else
  echo "⚠️ src/memory/indexer.py не найден — индексатор ещё не реализован"
  echo "REINDEX_NEEDED" > memory/REINDEX_NEEDED.flag
fi
