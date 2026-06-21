# NEVA Medic Knowledge — Индекс
# Версия: 8.0 | Дата: 2026-06-15 Сессия 4 | Архитектор: Claude

## Назначение
База знаний для AI-промпта Medic.
Medic читает нужный .md файл перед ai_call() — conf растёт с 0.20 до 0.88+.

## ПРАВИЛО 1: Медик диагностирует СЕБЯ первым
medic_self.md — читать при ЛЮБОЙ проблеме до диагностики других компонентов.

## ПРАВИЛО 2: Проверять историю инцидентов
incident_log.json — вызвать incident_log_search(problem_id) перед ai_diagnose().

## ПРАВИЛО 3: L2 Repair Agent — всегда читать repair_agent.md
При любом L2_FAILED в ESC JSON.

---

## ФАЙЛЫ БАЗЫ ЗНАНИЙ

| Файл | Компонент | problem_id | Версия |
|---|---|---|---|
| medic_self.md | Medic + вся система | ВСЕ (читать первым) | 2.0 |
| incident_log.md | Журнал инцидентов | ВСЕ (читать вторым) | 1.0 |
| auditor.md | Auditor Daemon | auditor_log_stale, ai_providers_all_down | 2.0 |
| thermal_guard.md | Thermal Guard | thermal_log_stale, thermal_critical | 1.0 |
| executor.md | MCP Executor | executor_log_spam | 1.0 |
| mcp_server.md | mcp_server.py stdio | mcp_not_running | 1.0 |
| mcp_server_net.md | neva_mcp_server.py :9000 | mcp_server_net_down, mcp_server_net_http, dashboard_http | 2.2 |
| approval_server.md | Approval Server :8766 | approval_not_running, approval_http_fail | 1.0 |
| control_center.md | Control Center :8767 | cc_not_running, cc_port_busy | 1.0 |
| neva_medic.md | Medic сам себя | medic_not_running, medic_ai_all_fail | 2.0 |
| neva_server.md | NEVA Server :8000 Kuzu | neva_server_not_running, neva_server_kuzu_lock | 1.0 |
| status_dot.md | AnyBar + neva_status_dot | status_dot_not_running, anybar_not_running | 1.0 |
| file_patch.md | neva_mcp_patch.py v1.1 | file_patch_auth_fail, file_patch_path_denied | 1.1 |
| repair_agent.md | neva_repair_agent.py | repair_agent_l2_failed, repair_agent_not_launched | 1.0 |
| mcp_proxy.md | neva_mcp_proxy.py | proxy_fallback_mode, proxy_import_error | 1.0 |
| mcp_validator.md | mcp_validator.py | validator_import_error, validator_desync | 1.0 |
| **mcp_events.md** | **neva_mcp_events.py v1.1** | **events_module_broken, events_ring_empty** | **1.0** |
| **mcp_patch.md** | **neva_mcp_patch.py v1.2** | **patch_module_broken, patch_auth_fail, patch_path_denied** | **1.0** |
| **session_brief.md** | **neva_session_brief.py** | **session_brief_stale, session_brief_missing** | **1.0** |

---

## KNOWLEDGE_MAP (полный)
```python
KNOWLEDGE_MAP = {
    'auditor_log_stale':           'auditor.md',
    'ai_providers_all_down':       'auditor.md',
    'thermal_log_stale':           'thermal_guard.md',
    'thermal_critical':            'thermal_guard.md',
    'executor_log_spam':           'executor.md',
    'mcp_not_running':             'mcp_server.md',
    'mcp_server_net_down':         'mcp_server_net.md',
    'mcp_approval_hang':           'mcp_server_net.md',
    'mcp_proxy_fallback_stuck':    'mcp_server_net.md',
    'approval_not_running':        'approval_server.md',
    'approval_http_fail':          'approval_server.md',
    'cc_not_running':              'control_center.md',
    'cc_port_busy':                'control_center.md',
    'medic_not_running':           'neva_medic.md',
    'medic_ai_all_fail':           'neva_medic.md',
    'neva_server_not_running':     'neva_server.md',
    'neva_server_kuzu_lock':       'neva_server.md',
    'status_dot_not_running':      'status_dot.md',
    'anybar_not_running':          'status_dot.md',
    'file_patch_auth_fail':        'file_patch.md',
    'file_patch_path_denied':      'file_patch.md',
    'repair_agent_l2_failed':      'repair_agent.md',
    'repair_agent_not_launched':   'repair_agent.md',
    'proxy_fallback_mode':         'mcp_proxy.md',
    'proxy_import_error':          'mcp_proxy.md',
    'validator_import_error':      'mcp_validator.md',
    'validator_desync':            'mcp_validator.md',
    # Новые (2026-06-15 Сессия 4)
    'events_module_broken':        'mcp_events.md',
    'events_ring_empty':           'mcp_events.md',
    'patch_module_broken':         'mcp_patch.md',
    'patch_auth_fail':             'mcp_patch.md',
    'session_brief_stale':         'session_brief.md',
    'session_brief_missing':       'session_brief.md',
}
```

---

## ИСТОРИЯ ВЕРСИЙ
| Дата | Версия | Изменение |
|---|---|---|
| 2026-06-13 | 1.0 | Создана база, 5 файлов |
| 2026-06-15 | 7.0 | +file_patch.md, +repair_agent.md, +mcp_proxy.md, +mcp_validator.md |
| **2026-06-15** | **8.0** | **+mcp_events.md, +mcp_patch.md, +session_brief.md. Итого: 19 файлов, 34 problem_id** |
