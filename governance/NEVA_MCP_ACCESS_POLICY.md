# NEVA MCP ACCESS POLICY
# Дата: 2026-06-05
# Директор: Серж
# Статус: УТВЕРЖДЕНО

---

## ДОСТУП CLAUDE ЧЕРЕЗ MCP EXECUTOR

### РАЗРЕШЁННЫЕ ПАПКИ (NEVA_MCP_BRIDGE)

| Папка | Доступ |
|---|---|
| governance/ | ✅ чтение |
| docs/ | ✅ чтение |
| tools/ | ✅ чтение |
| dispatcher/ | ✅ чтение |
| map/ | ✅ чтение |
| status/ | ✅ чтение |
| chats/ | ✅ чтение |
| prompts/ | ✅ чтение |
| core/ | ✅ чтение |
| agents/ | ✅ чтение |

### ЗАБЛОКИРОВАНО

| Ресурс | Статус |
|---|---|
| .env | ❌ PATH_ESCAPE_BLOCKED |
| kuzu_data | ❌ не в BRIDGE |
| .git | ❌ не в BRIDGE |
| всё вне NEVA_MCP_BRIDGE | ❌ PATH_ESCAPE_BLOCKED |

---

## ПРАВИЛА ОПЕРАЦИЙ

### Без подтверждения (readonly):
- file_read
- file_tree
- git_status
- system_info
- ollama_list
- diagnostics

### Требуют явного "да" от Директора:
- file_write
- git_commit
- git_push
- run_tests

---

## РЕАЛИЗАЦИЯ

- BASE_DIR = ~/Documents/NEVA_MCP_BRIDGE
- safe_path() блокирует любой выход за BASE_DIR
- Audit log: ~/Library/Application Support/NEVA/audit.db
- Python: /Users/arka/Documents/NEVA/.venv/bin/python3
- MCP server: ~/Library/Application Support/NEVA/mcp_server.py

---

## ПОДТВЕРЖДЕНИЕ

Директор Серж утвердил политику доступа 2026-06-05.
Claude подтверждает соблюдение ограничений.
