#!/bin/bash
# new_project.sh — обёртка для обратной совместимости
exec python3 "$(dirname "$0")/new_project.py" "$@"
