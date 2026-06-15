# Repair Agent — База знаний медика
# Программа: neva_repair_agent.py v1.0
# Обновлено: 2026-06-15 Сессия 4

## НАЗНАЧЕНИЕ
Уровень 2 (L2) автономного ремонта. Запускается Medic через create_escalation() после провала L1.
AI генерирует Python-скрипт ремонта → pre-flight чек → sandbox /tmp/neva_repair/ → результат в ESC JSON.
L3 = архитектор Claude (если L2 провался).

## АРХИТЕКТУРА
```
Medic L1 повторно провался
  ↓ create_escalation(ESC-ID)
  ↓ run_agent(ESC-ID):
     1. маркер (защита от повтора)
     2. читаем ESC JSON
     3. load_knowledge(problem_id) → .md файл
     4. ai_generate_script(esc, knowledge) → Cerebras/Groq/OR
     5. preflight_check() → FORBIDDEN_PATTERNS + SyntaxError
     6. run_script_in_sandbox() → /tmp/neva_repair/ timeout=120s
  ↓ L2_SUCCESS: ESC закрыт, osascript уведомление
  ↓ L2_FAILED: activate_claude_inbox() → ATTENTION.json
```

## БЕЗОПАСНОСТЬ

### FORBIDDEN_PATTERNS (блокируются в любом скрипте):
`rm -rf`, `sudo rm`, `shutil.rmtree`, `.env`, `governance/`, `DROP TABLE`,
`os.remove`, `rmdir`, `format(`, `:(){`, `eval(`, `exec(`, `sudo `,
`__import__`, `open("/etc`, `open("/usr`

### Порог confidence:
- < 0.40 → L2_FAILED (низкая уверенность AI)
- Sandbox: /tmp/neva_repair/, timeout 120s, cwd=/tmp/neva_repair/

## УПРАВЛЕНИЕ
Запуск: вручную Medic'ом:
```bash
python3 neva_repair_agent.py ESC-20260615-XXXXXX
```

Self-test:
```bash
/Users/arka/Documents/NEVA/.venv/bin/python3 neva_repair_agent.py --self-test
# Ожидание: 7/8 PASS (или 8/8 если AI ключи в порядке)
```

Live-test (AI зовет, скрипт не запускается):
```bash
/Users/arka/Documents/NEVA/.venv/bin/python3 neva_repair_agent.py --live-test ESC-ID
```

## ЛОГ
Файл: `logs/repair_agent.log`
Норма: `L2 SUCCESS` или `L2 FAILED` записи с esc_id
Отсутствие новых записей 5+ мин = агент не запускался (Agent запускается только Medic'ом)

## ПРОБЛЕМЫ И РЕШЕНИЯ

### ПРОБЛЕМА repair_agent_l2_failed
Симптом: `L2_FAILED` в ESC JSON + `claude_inbox/ATTENTION.json` создан.
Причины:
- Нет AI ключей (confidence=0.0 — все провайдеры недоступны)
- pre-flight FORBIDDEN паттерн в скрипте
- Sandbox timeout 120s
- confidence < 0.40
Действия Medic: проверить `repair_agent.log`, записать event `repair_agent_l2_failed`.
**ЭТО Л3 — требуется внимание архитектора через claude_inbox.**
Решение: доложить Директору — требуется решение Claude + Серж.

### ПРОБЛЕМА repair_agent_not_launched
Симптом: ESC в статусе OPEN, l2_status отсутствует.
Причина: Medic не запустил subprocess или маркер старый.
Действия: запустить вручную, удалить маркер если нужен перезапуск:
```bash
rm ~/Documents/NEVA_MCP_BRIDGE/escalations/.agent_ran_ESC-ID
python3 neva_repair_agent.py ESC-ID
```

### ПРОБЛЕМА AI провайдеры недоступны
См. Q6 — Cerebras/Groq 403. Проверить .env:
```bash
grep -E 'CEREBRAS|GROQ|OPENROUTER' ~/Documents/NEVA/.env
python3 neva_repair_agent.py --self-test  # ST-08 WARN = нет ключей
```

## PROBLEM_IDs ПОКРыТЫЕ AGENT'OM
```python
'thermal_log_stale', 'thermal_critical',
'executor_log_spam', 'mcp_not_running',
'approval_not_running', 'approval_http_fail',
'auditor_log_stale', 'ai_providers_all_down'
```
При новых problem_id — добавить в KNOWLEDGE_MAP в neva_repair_agent.py.

## ОТКАТ
Нет. L2 Agent не имеет отката. Если скрипт завалился — ESC ставится L2_FAILED.
Роллбэк самого повреждения: sandbox /tmp/ — файлы не попадут в NEVA.

*Создано: 2026-06-15 (Сессия 4) | Архитектор: Claude | Директор: Серж*
