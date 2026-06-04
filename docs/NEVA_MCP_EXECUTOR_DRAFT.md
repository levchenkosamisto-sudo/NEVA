# NEVA MCP EXECUTOR — ИНТЕГРАЦИЯ С CLAUDE DESKTOP
# Статус: DRAFT
# Дата: 2026-06-04
# Автор: GPT (предложено), Claude (архитектор, зафиксировал)
# Приоритет: ПОСЛЕ завершения NEVA-TASK-007

---

## СТАТУС ДОКУМЕНТА

DRAFT — не является источником истины.
Реализация ЗАБЛОКИРОВАНА до:
- [ ] ТЗ-1 принят (DeepSeek)
- [ ] ТЗ-2 принят (Gemini)
- [ ] ТЗ-3 принят (GPT)
- [ ] mcp_executor прошёл аудит
- [ ] Директор утвердил

---

## ЦЕЛЬ

Подключить локальный MCP сервер NEVA MCP Executor (stdin/stdout bridge)
к Claude Desktop как tool backend.

---

## АРХИТЕКТУРНЫЙ ПРИНЦИП

Claude = мышление (reasoning, анализ, архитектура)
Executor = исполнение (файлы, CLI, система, IO)

```
IF task ∈ deterministic/system/file/CLI:
    → MCP Executor

ELSE:
    → Claude reasoning layer
```

---

## КОНФИГУРАЦИЯ MCP (DRAFT)

Файл: ~/Library/Application Support/Claude/claude_desktop_config.json

ВНИМАНИЕ: путь должен быть динамическим — НЕ захардкоживать /Users/arka/

```json
{
  "mcpServers": {
    "neva_executor": {
      "command": "$HOME/Documents/NEVA/tools/mcp_executor/claude_bridge.sh"
    }
  }
}
```

---

## ЧТО УХОДИТ В EXECUTOR

Файлы:
- file_read
- file_tree
- search_files

Система:
- git_status
- system_info
- diagnostics

Локальные LLM:
- ollama_list
- ollama_run (требует подтверждения Директора)

Playbooks:
- run_playbook
- run_tests

---

## ЧТО ОСТАЁТСЯ CLAUDE

- Архитектурные решения
- Анализ и планирование
- Интерпретация графа
- Reasoning
- Аудит

---

## КРИТЕРИИ УСПЕХА (для будущей реализации)

- git_status выполняется через MCP
- file_tree возвращается через executor
- file_read работает в sandbox
- ollama_list вызывается через bridge

---

## ОТКРЫТЫЕ ВОПРОСЫ (решить перед реализацией)

- [ ] Аудит tools/mcp_executor/ (попал в репо без ТЗ и двойного ревью)
- [ ] Динамический путь в конфиге (не /Users/arka/)
- [ ] ollama_run требует подтверждения Директора — механизм?
- [ ] Интеграция с dispatcher/ (IMMUTABLE RULE №8)
- [ ] Тесты интеграции Claude Desktop ↔ Executor
