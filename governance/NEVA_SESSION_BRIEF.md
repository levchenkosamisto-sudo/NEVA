# NEVA SESSION BRIEF | 2026-06-21 | WEB-AI AUTOMATION

## СТАТУС СИСТЕМЫ
- Traffic light: GREEN
- MCP Server: v2.4 (script_deploy + python3 whitelist)
- Desktop Commander: ✅ установлен
- Claude Code: ✅ v2.1.185 (~/.local/bin/claude) — авторизация через браузер нужна

## АРХИТЕКТУРА ВЕБ-ИИ (УТВЕРЖДЕНО)

| Канал | Сервисы | Причина |
|---|---|---|
| duma_playwright.py | ChatGPT ✅ Gemini ✅ | Google аккаунт передаётся |
| Claude in Chrome | DeepSeek ✅ Grok ✅ | OAuth X/Google блокирует Playwright |

## ИНСТРУМЕНТЫ АВТОМАТИЗАЦИИ
- Desktop Commander MCP: кнопка Allow в Claude Desktop — все команды через него
- script_deploy: file_write → script_deploy — без heredoc
- duma_playwright.py: запуск через Desktop Commander
- Claude in Chrome: для DeepSeek и Grok

## ЗАПУСК PLAYWRIGHT
```bash
cd ~/Documents/NEVA && python3 duma_playwright.py --round N --prompt governance/duma/prompts/PROMPT.md
cd ~/Documents/NEVA && python3 duma_playwright.py --round N --prompt ... --services chatgpt
```
Ответы: ~/Documents/NEVA/audit_responses/
GitHub: neva-audit/output/

## CLAUDE IN CHROME — ДЛЯ DeepSeek И Grok
В новом чате: задать вопрос через tabs_context_mcp, читать ответ, сохранять.

## ЗАДАЧА НОВОГО ЧАТА → DUMA_AUDIT_TASK_001 (ПРИОРИТЕТ)
СМ.: governance/duma/DUMA_AUDIT_TASK_001.md

1. Залить ДУМУ в GitHub (neva-audit/duma/) — код + описание как работает
2. Создать систему учёта: AUDIT-001-R1-[AUDITOR].yaml + registry.json
3. Написать промпт Круга 1 (вопросы без оценок, шаблон YAML, ссылка GitHub)
4. Запустить: Playwright (ChatGPT+Gemini) + Claude in Chrome (DeepSeek+Grok)
5. Доклад Директору: кто из 4 ответил / кто нет

## КЛЮЧЕВЫЕ ФАЙЛЫ
- MCP Server: ~/Documents/NEVA_MCP_BRIDGE/neva_mcp_server.py (v2.4)
- Playwright: ~/Documents/NEVA/duma_playwright.py
- Профиль Chrome: ~/Library/Application Support/Google/Chrome
- Ответы: ~/Documents/NEVA/audit_responses/
- GitHub: neva-audit/output/ и neva-audit/duma/
- Промпты: ~/Documents/NEVA/governance/duma/prompts/
- Задание: ~/Documents/NEVA/governance/duma/DUMA_AUDIT_TASK_001.md
- Протокол: ~/Documents/NEVA/neva_audit_protocol_DRAFT.md

## MCP v2.4 — ВАЖНО
При перезапуске медиком — v2.4 сбрасывается. Восстановить:
```bash
launchctl unload ~/Library/LaunchAgents/com.neva.mcp-server.plist
pkill -f neva_mcp_server
cd ~/Documents/NEVA_MCP_BRIDGE && python3 neva_mcp_server.py &
```
