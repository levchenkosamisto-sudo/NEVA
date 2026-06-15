# NEVA — ПЛАН РАЗРАБОТКИ
# Директор: Серж | Архитектор: Claude
# Обновлено: 2026-06-15 Сессия 4

---

## ⚡ ПОСЛЕДНЯЯ СЕССИЯ: 2026-06-15 СЕССИЯ 4 — Ч9 ЭТАП B ЗАКРЫТ

### Что сделано:
- neva_mcp_patch.py v1.1: ALLOWED_ROOTS whitelist (NEVA + NEVA_MCP_BRIDGE) ✅
- neva_mcp_patch.py v1.1: auth NEVA_ADMIN_TOKEN + logging ✅
- neva_mcp_server.py v2.1: передача токена в apply_patch, ST-04 whitelist-safe ✅
- medic_knowledge/file_patch.md: создан ✅
- git commit 879a581: file_patch.md в NEVA repo ✅
- launchd kickstart: сервер перезапущен с v2.1 ✅
- Self-test: 6/8 PASS (2 WARN = порты заняты = норма) ✅

### Открыто для следующей сессии:
- Финальный тест 11/11
- Ч6 — Auditor sidecar daemon
- TASK-007 Этап 2 — Intelligence Layer
- Q1: git_commit через MCP — нужен approval token или убрать?
- NEVA_MCP_BRIDGE добавить в git repo (сейчас не отслеживается)

---

## СТАТУС ЭТАПОВ

| Этап | Статус | Покрытие |
|---|---|---|
| Этап 0 — Стек и окружение | ✅ УТВЕРЖДЁН | 100% |
| Этап 1 — Core MVP | ✅ УТВЕРЖДЁН 2026-06-05 | ~60% |
| Thermal Guard v9.4 | ✅ ЗАКРЫТ 2026-06-08 | 32/34 PASS |
| MCP Executor v6.3 | ✅ ЗАКРЫТ 2026-06-11 | 100% |
| MEDIC-V3 (все сессии) | ✅ ЗАКРЫТ 2026-06-14 | 17+8/17+8 PASS |
| Ч4 — Двусторонняя связь | ✅ ЗАКРЫТ 2026-06-14 | 17/17 PASS |
| Ч9 Этап A — MCP-сервер | ✅ ЗАКРЫТ 2026-06-14 | 7/7 PASS |
| **Ч9 Этап B — file_patch production** | **✅ ЗАКРЫТ 2026-06-15** | **6/8 PASS (2 WARN норма)** |
| Ч6 — Auditor sidecar | 📌 ЗАПЛАНИРОВАН | 0% |
| Финальный тест 11/11 | 📌 ЗАПЛАНИРОВАН | 0% |
| NEVA-TASK-DXT | 📌 ЗАПЛАНИРОВАН | низкий приоритет |
| Этап 3 — Cursor под командой Клода | 🔴 после Ч6 | 0% |
| Intelligence Layer (TASK-007 Этап 2) | 📌 ЗАПЛАНИРОВАН | 0% |

---

## ПРОГРАММЫ NEVA (актуально)

| Программа | Версия | Статус | Файл |
|---|---|---|---|
| Thermal Guard | v9.4 | PROD LaunchAgent | ~/Documents/NEVA/neva_thermal_guard.py |
| MCP Executor (stdio) | v6.3 | PROD Claude Desktop | ~/Documents/NEVA_MCP_BRIDGE/mcp_server.py |
| NEVA Server | v1 | PROD порт 8000 | ~/Documents/NEVA/neva_context_api.py |
| NEVA Medic | v3.8 | PROD launchd KeepAlive | ~/Documents/NEVA_MCP_BRIDGE/neva_medic.py |
| Repair Agent | v1.0 | PROD | ~/Documents/NEVA_MCP_BRIDGE/neva_repair_agent.py |
| Control Center | v2.6 | PROD порт 8767 | ~/Documents/NEVA_MCP_BRIDGE/neva_control_center.py |
| **MCP Server (HTTP)** | **v2.1** | **PROD порт 9000+9001** | ~/Documents/NEVA_MCP_BRIDGE/neva_mcp_server.py |
| **MCP Patch** | **v1.1** | **PROD lib** | ~/Documents/NEVA_MCP_BRIDGE/neva_mcp_patch.py |
| medic_knowledge | v6.0+ | PROD 13 файлов | ~/Documents/NEVA/governance/medic_knowledge/ |

---

## СОСТОЯНИЕ ПРОЦЕССОВ

- neva_thermal_guard.py — LaunchAgent ✅ PID 97566
- neva_mcp_server.py v2.1 — launchd KeepAlive :9000/:9001 ✅
- neva_auditor_daemon.py — LaunchAgent ✅ PID 5705
- neva_medic.py v3.8 — launchd KeepAlive ✅
- neva_control_center.py v2.6 — nohup :8767 ✅
- neva_approval_server.py — ~/.zshrc :8766 ✅
- neva_status_dot.py v1.1 — launchd KeepAlive + AnyBar 🟢 ✅
- mcp_server.py v6.3 (stdio) — Claude Desktop ✅

---

## АРХИТЕКТУРА Ч9 (ЗАКРЫТО)

```
Claude → neva_execute(file_patch, path, diff)
  ↓ neva_mcp_server.py v2.1
  ↓ _execute_action: token=ADMIN_TOKEN
  ↓ neva_mcp_patch.py v1.1
     1. AUTH check (NEVA_ADMIN_TOKEN)
     2. PATH resolve
     3. WHITELIST guard (NEVA + NEVA_MCP_BRIDGE)
     4. apply unified diff + .bak
     5. log.info OK / rollback on error
```

---

## ОТКРЫТЫЕ ВОПРОСЫ

| # | Вопрос |
|---|---|
| Q1 | git_commit через MCP: approval token или убрать? |
| Q2 | run_tests: sandbox блокирует fs — убрать sandbox или заменить? |
| Q6 | Cerebras/Groq 403: отладить ключи |
| Q7 | run_command без sandbox: добавить в executor? |
| Q8 | NEVA_MCP_BRIDGE: добавить в git repo? (сейчас вне repo) |

---

*Обновлено: 2026-06-15 Сессия 4 | Архитектор: Claude | Директор: Серж*
