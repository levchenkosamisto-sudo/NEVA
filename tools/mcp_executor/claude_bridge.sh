#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEVA_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
if [ -f "$NEVA_DIR/.venv/bin/python3" ]; then
    PYTHON="$NEVA_DIR/.venv/bin/python3"
elif [ -f "$NEVA_DIR/venv/bin/python3" ]; then
    PYTHON="$NEVA_DIR/venv/bin/python3"
else
    PYTHON="$(which python3)"
fi
cd "$SCRIPT_DIR"
exec "$PYTHON" mcp_server.py
