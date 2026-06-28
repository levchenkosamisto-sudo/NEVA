#!/bin/bash
# scripts/start.sh — запуск NEVA
cd "$(dirname "$0")/.."

echo "=== NEVA START ==="
source .env 2>/dev/null || true

NEVA_ADMIN_TOKEN=$(grep NEVA_ADMIN_TOKEN .env 2>/dev/null | cut -d'=' -f2)
NEVA_AGENT_TOKEN=$(grep NEVA_AGENT_TOKEN .env 2>/dev/null | cut -d'=' -f2)

export NEVA_ADMIN_TOKEN NEVA_AGENT_TOKEN

python -m uvicorn neva_context_api:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1
