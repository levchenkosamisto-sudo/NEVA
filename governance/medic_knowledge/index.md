# NEVA Medic Knowledge — Индекс
# Версия: 4.0 | Дата: 2026-06-15 | Архитектор: Claude

## Назначение
База знаний для AI-промпта Medic.
Medic читает нужный .md файл перед ai_call() — conf растёт с 0.20 до 0.88+.

## ПРАВИЛО 1: Медик диагностирует СЕБЯ первым
medic_self.md — читать при ЛЮБОЙ проблеме до диагностики других компонентов.

## ПРАВИЛО 2: Проверять историю инцидентов
incident_log.json — вызвать incident_log_search(problem_id) перед ai_diagnose().
Передать историю в промпт — AI не повторяет провальные playbooks.

## Файлы базы знаний

| Файл | Компонент | problem_id |
|---|---|---|
| medic_self.md | Medic самодиагностика | ВСЕ (читать первым) |
| incident_log.md | Журнал инцидентов | ВСЕ (читать вторым) |
| auditor.md | Auditor Daemon v1.0 Т6 | auditor_log_stale, ai_providers_all_down |
| thermal_guard.md | Thermal Guard v9.4 | thermal_log_stale, thermal_critical |
| executor.md | MCP Executor v6.3 | executor_log_spam |
| mcp_server.md | mcp_server.py v3.4 | mcp_not_running |
| mcp_server_net.md v2.0 | neva_mcp_server.py :9000 | mcp_server_net_http, file_read_broken |
| approval_server.md | Approval Server :8766 | approval_not_running, approval_http_fail |

## KNOWLEDGE_MAP
KNOWLEDGE_MAP = {
    'auditor_log_stale':     'auditor.md',
    'ai_providers_all_down': 'auditor.md',
    'thermal_log_stale':     'thermal_guard.md',
    'thermal_critical':      'thermal_guard.md',
    'executor_log_spam':     'executor.md',
    'mcp_not_running':       'mcp_server.md',
    'mcp_server_net_http':   'mcp_server_net.md',
    'file_read_broken':      'mcp_server_net.md',
    'approval_not_running':  'approval_server.md',
    'approval_http_fail':    'approval_server.md',
}
MEDIC_SELF_KNOWLEDGE = 'medic_self.md'
INCIDENT_LOG_SEARCH  = 'incident_log_search(problem_id, limit=3)'

## Правило пополнения
Автоматически: incident_log.json пишется медиком после каждого heal.
Вручную: после сложного ремонта с Claude — архитектор дополняет .md файл
в разделе История аварий. Это фиксирует знания которые AUTO не покрывает.

## История версий
| Дата | Версия | Изменение |
|---|---|---|
| 2026-06-13 | 1.0 | Создана база, 5 файлов |
| 2026-06-15 | 2.0 | medic_self.md, auditor.md v2.0 Т6 |
| 2026-06-15 | 3.0 | incident_log.md, Вариант Б активен, Вариант В зафиксирован |
| 2026-06-15 | 4.0 | mcp_server_net.md v2.0: баг sys.path, дерево диагностики, file_read_broken |
