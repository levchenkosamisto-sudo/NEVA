# NEVA Medic Knowledge — Индекс
# Версия: 6.0 | Дата: 2026-06-15 | Архитектор: Claude

## Назначение
База знаний для AI-промпта Medic.
Medic читает нужный .md файл перед ai_call() — conf растёт с 0.20 до 0.88+.

## ПРАВИЛО 1: Медик диагностирует СЕБЯ первым
medic_self.md — читать при ЛЮБОЙ проблеме до диагностики других компонентов.

## ПРАВИЛО 2: Проверять историю инцидентов
incident_log.json — вызвать incident_log_search(problem_id) перед ai_diagnose().
Передать историю в промпт — AI не повторяет провальные playbooks.

## Файлы базы знаний

| Файл | Компонент | problem_id | Версия |
|---|---|---|---|
| medic_self.md | Medic + вся система | ВСЕ (читать первым) | 2.0 |
| incident_log.md | Журнал инцидентов | ВСЕ (читать вторым) | 1.0 |
| auditor.md | Auditor Daemon Т6 | auditor_log_stale, ai_providers_all_down | 2.0 |
| thermal_guard.md | Thermal Guard v9.4 | thermal_log_stale, thermal_critical | 1.0 |
| executor.md | MCP Executor v6.3 | executor_log_spam | 1.0 |
| mcp_server.md | mcp_server.py v3.4 | mcp_not_running | 1.0 |
| mcp_server_net.md | neva_mcp_server.py :9000 | mcp_server_net_http, file_read_broken | 2.1 |
| approval_server.md | Approval Server :8766 | approval_not_running, approval_http_fail | 1.0 |
| control_center.md | Control Center v2.6 :8767 | cc_not_running, cc_port_busy | 1.0 |
| neva_medic.md | Medic сам себя | medic_not_running, medic_ai_all_fail | 2.0 |
| neva_server.md | NEVA Server :8000 Kuzu | neva_server_not_running, neva_server_kuzu_lock | 1.0 |
| status_dot.md | AnyBar + neva_status_dot | status_dot_not_running, anybar_not_running | 1.0 |

## KNOWLEDGE_MAP
```python
KNOWLEDGE_MAP = {
    # Auditor
    'auditor_log_stale':       'auditor.md',
    'ai_providers_all_down':   'auditor.md',
    # Thermal
    'thermal_log_stale':       'thermal_guard.md',
    'thermal_critical':        'thermal_guard.md',
    # Executor
    'executor_log_spam':       'executor.md',
    # MCP stdio
    'mcp_not_running':         'mcp_server.md',
    # MCP HTTP
    'mcp_server_net_http':     'mcp_server_net.md',
    'file_read_broken':        'mcp_server_net.md',
    # Approval
    'approval_not_running':    'approval_server.md',
    'approval_http_fail':      'approval_server.md',
    # Control Center
    'cc_not_running':          'control_center.md',
    'cc_port_busy':            'control_center.md',
    # Medic сам
    'medic_not_running':       'neva_medic.md',
    'medic_ai_all_fail':       'neva_medic.md',
    # NEVA Server
    'neva_server_not_running': 'neva_server.md',
    'neva_server_kuzu_lock':   'neva_server.md',
    # Status Dot
    'status_dot_not_running':  'status_dot.md',
    'anybar_not_running':      'status_dot.md',
}
MEDIC_SELF_KNOWLEDGE = 'medic_self.md'
INCIDENT_LOG_SEARCH  = 'incident_log_search(problem_id, limit=3)'
```

## Правило пополнения
Автоматически: incident_log.json пишется медиком после каждого heal.
Вручную: после сложного ремонта с Claude — архитектор дополняет .md файл.

## История версий
| Дата | Версия | Изменение |
|---|---|---|
| 2026-06-13 | 1.0 | Создана база, 5 файлов |
| 2026-06-15 | 2.0 | medic_self.md, auditor.md v2.0 |
| 2026-06-15 | 3.0 | incident_log.md, Вариант Б |
| 2026-06-15 | 4.0 | mcp_server_net.md v2.0: баг sys.path |
| 2026-06-15 | 5.0 | +control_center.md, +neva_medic.md, +neva_server.md |
| 2026-06-15 | 6.0 | +status_dot.md, medic_self v2.0 (точка AnyBar), neva_medic v2.0 (KeepAlive), 18 problem_id |
