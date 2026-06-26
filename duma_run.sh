#!/bin/bash
# DUMA v2 — запуск одного круга для всех 4 аудиторов последовательно
# Использование: ./duma_run.sh AUDIT_ID ROUND PROMPT_FILE
# Пример:        ./duma_run.sh THERMAL-002 1 audit_responses/THERMAL-002-R1-PROMPT.txt

set -e
cd "$(dirname "$0")"

AUDIT_ID="$1"
ROUND="$2"
PROMPT="$3"

if [ -z "$AUDIT_ID" ] || [ -z "$ROUND" ] || [ -z "$PROMPT" ]; then
  echo "Использование: $0 AUDIT_ID ROUND PROMPT_FILE"
  echo "Пример:        $0 THERMAL-002 1 audit_responses/THERMAL-002-R1-PROMPT.txt"
  exit 1
fi

if [ ! -f "$PROMPT" ]; then
  echo "❌ Файл промпта не найден: $PROMPT"
  exit 1
fi

echo "=== DUMA v2 | Аудит: $AUDIT_ID | Круг: $ROUND ==="
echo "Промпт: $PROMPT"
echo ""

OK=0; FAIL=0

for AUDITOR in chatgpt gemini deepseek grok; do
  echo "▶ $AUDITOR..."
  if .venv/bin/python3 duma_v2.py \
      --audit "$AUDIT_ID" \
      --round "$ROUND" \
      --prompt "$PROMPT" \
      --auditor "$AUDITOR" 2>&1; then
    OK=$((OK+1))
  else
    echo "❌ $AUDITOR завершился с ошибкой"
    FAIL=$((FAIL+1))
  fi
  echo ""
done

echo "=== Итог Круга $ROUND: ✅ $OK  ❌ $FAIL ==="
echo "Ответы: audit_responses/${AUDIT_ID}-R${ROUND}-*.md"
echo "Сессии: audit_responses/${AUDIT_ID}-SESSIONS.json"
