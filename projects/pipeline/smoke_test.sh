#!/bin/bash
# smoke_test.sh — интеграционный тест реального запуска

PASS=0
FAIL=0
PYTHON=/Users/arka/Documents/NEVA/.venv/bin/python3

echo "=== SMOKE TEST: NEVA Pipeline Tools ==="

# Тест 1: new_project.py создаёт папку
TMP_PROJ="smoke_test_$$"
NEVA_PROJECTS_DIR="/tmp" "$PYTHON" tools/pipeline/new_project.py "$TMP_PROJ"
if [ -d "/tmp/$TMP_PROJ" ]; then
    echo "✅ new_project.py — OK"
    PASS=$((PASS+1))
    rm -rf "/tmp/$TMP_PROJ"
else
    echo "❌ new_project.py — FAIL"
    FAIL=$((FAIL+1))
fi

# Тест 2: review_checker.py с пустым чеклистом
echo "# test" > /tmp/review_test.md
/Users/arka/Documents/NEVA/.venv/bin/python3 tools/pipeline/review_checker.py /tmp/review_test.md
if [ $? -eq 1 ]; then
    echo "✅ review_checker.py (пустой) — OK"
    PASS=$((PASS+1))
else
    echo "❌ review_checker.py (пустой) — FAIL"
    FAIL=$((FAIL+1))
fi

# Тест 3: review_checker.py с полным чеклистом
echo "- [x] всё готово" > /tmp/review_full.md
/Users/arka/Documents/NEVA/.venv/bin/python3 tools/pipeline/review_checker.py /tmp/review_full.md
if [ $? -eq 0 ]; then
    echo "✅ review_checker.py (полный) — OK"
    PASS=$((PASS+1))
else
    echo "❌ review_checker.py (полный) — FAIL"
    FAIL=$((FAIL+1))
fi

# Тест 4: notify_director.py с несуществующим файлом
/Users/arka/Documents/NEVA/.venv/bin/python3 tools/pipeline/notify_director.py /tmp/nonexistent_questions.md
if [ $? -eq 0 ]; then
    echo "✅ notify_director.py (нет файла) — OK"
    PASS=$((PASS+1))
else
    echo "❌ notify_director.py (нет файла) — FAIL"
    FAIL=$((FAIL+1))
fi

echo ""
echo "=== ИТОГ: $PASS PASS / $FAIL FAIL ==="
[ $FAIL -eq 0 ] && exit 0 || exit 1
