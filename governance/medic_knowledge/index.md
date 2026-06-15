# NEVA Medic Knowledge — Индекс
# Версия: 2.0 | Дата: 2026-06-15 | Архитектор: Claude

## Назначение
governance/medic_knowledge/ — база знаний для AI-промпта Medic.
Medic читает нужный .md файл перед вызовом ai_call() → conf вырастает с 0.20 до 0.70+.

## ПРАВИЛО №1: Медик диагностирует СЕБЯ первым
Файл: medic_self.md — читать при ЛЮБОЙ проблеме до диагностики других компонентов.

## Файлы

| Файл | Компонент | problem_id покрытые |
|---|---|---|
| medic_self.md | Medic самодиагностика | ВСЕ (читать первым) |
| auditor.md | Auditor Daemon v1.0 (Т6) | auditor_log_stale, ai_providers_all_down |
| thermal_guard.md | Thermal Guard v9.4 | thermal_log_stale, thermal_critical |
| executor.md | MCP Executor v6.3 | executor_log_spam |
| mcp_server.md | mcp_server.py v3.4 | mcp_not_running |
| mcp_server_net.md | neva_mcp_server.py :9000 | mcp_server_net_http |
| approval_server.md | Approval Server :8766 | approval_not_running, approval_http_fail |

## KNOWLEDGE_MAP (для кода медика)
```python
KNOWLEDGE_MAP = {
    'auditor_log_stale':     'auditor.md',
    'ai_providers_all_down': 'auditor.md',
    'thermal_log_stale':     'thermal_guard.md',
    'thermal_critical':      'thermal_guard.md',
    'executor_log_spam':     'executor.md',
    'mcp_not_running':       'mcp_server.md',
    'mcp_server_net_http':   'mcp_server_net.md',
    'approval_not_running':  'approval_server.md',
    'approval_http_fail':    'approval_server.md',
}
MEDIC_SELF_KNOWLEDGE = 'medic_self.md'  # читать первым при любой проблеме
```

## Правило обновления
При каждой новой аварии — дополнить нужный .md файл в разделе "История аварий".
Архитектор обновляет после закрытия эскалации.

## История
| Дата | Изменение |
|---|---|
| 2026-06-13 | v1.0 — создана база, 5 файлов |
| 2026-06-15 | v2.0 — добавлен medic_self.md, auditor.md обновлён до Т6, index обновлён |
