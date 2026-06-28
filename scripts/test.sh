#!/bin/bash
# scripts/test.sh — запуск всех тестов NEVA
cd "$(dirname "$0")/.."

echo "=== NEVA TEST ==="
source .env 2>/dev/null || true

ruff check src/ && echo "✅ ruff OK" || echo "⚠️ ruff: есть замечания"

python -m pytest tests/ -v --tb=short
STATUS=$?

if [ $STATUS -eq 0 ]; then
  echo "✅ Все тесты прошли"
else
  echo "❌ Тесты упали — коммит заблокирован"
fi

exit $STATUS
