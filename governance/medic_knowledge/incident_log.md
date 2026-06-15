# NEVA Medic Knowledge — Incident Log
# Версия: 1.0 | Дата: 2026-06-15 | Архитектор: Claude | Директор: Серж

## Назначение
incident_log.json — автоматический журнал инцидентов.
Медик пишет запись после каждого heal_success и heal_fail.
База растёт автоматически без участия Директора или Claude.
Хранит последние 500 инцидентов. Путь: STATE/incident_log.json

## Структура записи
{
  "ts":          "2026-06-15T10:15:06",   -- время инцидента
  "problem_id":  "auditor_log_stale",     -- ID проблемы
  "severity":    "MEDIUM",               -- HIGH/MEDIUM/LOW
  "description": "...",                  -- описание проблемы
  "playbook":    "restart_auditor",      -- что применяли
  "attempts":    1,                      -- сколько попыток
  "result":      "SUCCESS",             -- SUCCESS / FAIL
  "diagnosis":   "...",                 -- диагноз AI
  "confidence":  0.88,                  -- уверенность AI
  "fail_reason": ""                     -- причина провала (если FAIL)
}

## Как медик использует журнал
Перед ai_diagnose() — вызвать incident_log_search(problem_id, limit=3).
Передать историю в промпт: "Предыдущие случаи этой проблемы: ..."
Эффект: AI видит что уже пробовали → conf растёт, не повторяет провальные playbooks.

## Код использования в медике
```python
# В ai_diagnose() — добавить контекст из журнала:
history = incident_log_search(problem['id'], limit=3)
if history:
    history_text = '\n'.join(
        f"- {e['ts'][:10]}: {e['result']} via {e['playbook']} "
        f"(attempts={e['attempts']}, conf={e['confidence']:.2f})"
        for e in history
    )
    knowledge += f'\n\n## История этой проблемы\n{history_text}'
```

## Диагностика журнала
```bash
# Сколько записей:
python3 -c "import json; d=json.load(open('/Users/arka/Documents/NEVA_MCP_BRIDGE/state/incident_log.json')); print(f'{len(d)} записей')"

# Последние 3:
python3 -c "import json; [print(e['ts'][:16], e['problem_id'], e['result']) for e in json.load(open('/Users/arka/Documents/NEVA_MCP_BRIDGE/state/incident_log.json'))[-3:]]"

# По problem_id:
python3 -c "import json; pid='auditor_log_stale'; [print(e) for e in json.load(open('/Users/arka/Documents/NEVA_MCP_BRIDGE/state/incident_log.json')) if e['problem_id']==pid]"
```

## Вариант В — Vector Search (планируется после TASK-007 Этап 2)
РЕШЕНИЕ ДИРЕКТОРА (2026-06-15): после подключения graphiti-core + e5-small embedding
заменить incident_log_search() на семантический поиск через Kuzu.
Симптом → embedding → cosine similarity → ближайшие инциденты.
Эффект: находит похожие сбои даже с разными симптомами. conf → 0.95+.
Файл для реализации: governance/FUTURE_VARIANT_V.md

## Правило пополнения
Журнал пополняется АВТОМАТИЧЕСКИ медиком.
После каждого ремонта с участием Claude — архитектор дополняет нужный .md файл
в разделе "История аварий" (сложные случаи которые AUTO не решил).
