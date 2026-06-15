# NEVA — РЕЕСТР ПРОГРАММ И ИНСТРУМЕНТОВ MAC M1
# ОБНОВЛЕНИЕ: 2026-06-15 Сессия 3
# Изменения: neva_mcp_server v2.0 патч sys.path, CC v2.6, medic_knowledge v5.0

## УДАЛЕНО (2026-06-06)
- Pinokio.app, Leonardo.Ai.app, faceswap.app

## /Applications (текущее состояние)
Brave Browser.app, ChatGPT.app, Chatbox.app, Claude.app, Cursor.app,
FB Events.app, Google Docs.app, Google Drive.app, Google Sheets.app,
Google Slides.app, Health Auto Export.app, Keynote.app,
LuLu.app, Meest Shopping.app, Meet+.app, MeetInOne.app,
Messenger.app, NCalc.app, Numbers.app, Obsidian.app,
Ollama.app, OpenVPN Connect, PDF & Document Converter.app,
PDF Reader Pro.app, PDF to Excel by Flyingbee.app, Pages.app,
Perplexity.app, Photoroom.app, Privat24.app, Radio FM.app,
Reaction.app, Safari.app, Telegram.app, Translator X.app,
Twitter.app, VPN Proxy Master.app, Viber.app,
Visual Studio Code.app, Weather Forecast.app, WhatsApp.app,
XLS-Editor.app, Xiaomi Home.app

## ИНСТРУМЕНТЫ РАЗРАБОТЧИКА

| Инструмент | Версия | Статус | Назначение |
|---|---|---|---|
| Python | 3.12.13 | OK | основной язык NEVA |
| Node.js | 26.0.0 | OK | зависимости |
| Git | 2.54.0 | OK | версионирование |
| Ollama | актуальная | OK | локальные LLM |
| uvicorn | 0.49.0 | OK | ASGI сервер |
| Docker | — | не установлен | — |
| venv (.venv) | активен | OK | ~/Documents/NEVA/.venv |
| Cursor | актуальная | OK | IDE + MCP клиент |
| Visual Studio Code | актуальная | OK | редактор |
| Cline (VS Code) | v3.89.0 | OK | MCP клиент в VS Code |

## MCP КЛИЕНТЫ

| Клиент | Статус | Config путь |
|---|---|---|
| Claude Desktop | активен | ~/Library/Application Support/NEVA/mcp_server.py |
| Cursor | установлен | ~/.cursor/mcp.json |
| VS Code+Cline | установлен | ~/.vscode/cline_mcp_settings.json |
| Windsurf | ОТМЕНЁН | платный |

## НЕВА ПРОГРАММЫ — ПОЛНЫЙ РЕЕСТР

| Программа | Версия | Порт | Статус | Кнопка медика | Файл |
|---|---|---|---|---|---|
| Thermal Guard | v9.4 | — | PROD LaunchAgent | thermal_guard.md | ~/Documents/NEVA/neva_thermal_guard.py |
| NEVA Server | v1 | 8000 | PROD | neva_server.md | ~/Documents/NEVA/neva_context_api.py |
| NEVA Medic | v3.8 | — | PROD Login Items | neva_medic.md | ~/Documents/NEVA_MCP_BRIDGE/neva_medic.py |
| MCP Server (HTTP) | v2.0 | 9000/9001 | PROD launchd | mcp_server_net.md | ~/Documents/NEVA_MCP_BRIDGE/neva_mcp_server.py |
| MCP Executor (stdio) | v6.3 | — | PROD Claude Desktop | executor.md | ~/Documents/NEVA_MCP_BRIDGE/mcp_server.py |
| MCP Executor lib | v3.1 | — | PROD lib | executor.md | ~/Documents/NEVA_MCP_BRIDGE/mcp_executor.py |
| MCP Validator | v3.0 | — | PROD lib | executor.md | ~/Documents/NEVA_MCP_BRIDGE/mcp_validator.py |
| Approval Server | v1 | 8766 | PROD .zshrc | approval_server.md | ~/Documents/NEVA_MCP_BRIDGE/neva_approval_server.py |
| Control Center | v2.6 | 8767 | PROD ручной | control_center.md | ~/Documents/NEVA_MCP_BRIDGE/neva_control_center.py |
| Auditor Daemon | v1.0 | — | PROD LaunchAgent Т6 | auditor.md | ~/Documents/NEVA_MCP_BRIDGE/neva_auditor_daemon.py |
| Background Auditor | v6.9 | — | PROD lib | executor.md | ~/Documents/NEVA_MCP_BRIDGE/background_auditor.py |
| MCP Proxy | v1.0 | stdio→9000 | PROD | mcp_server_net.md | ~/Documents/NEVA_MCP_BRIDGE/neva_mcp_proxy.py |
| medic_knowledge | v5.0 | — | PROD 11 md-файлов | index.md | ~/Documents/NEVA/governance/medic_knowledge/ |

## ПРОЦЕССЫ И АВТОЗАПУСК

| Процесс | Механизм | Состояние |
|---|---|---|
| neva_thermal_guard.py | LaunchAgent com.neva.thermal-guard | ✅ PID 97566 |
| neva_mcp_server.py | LaunchAgent com.neva.mcp-server :9000 | ✅ PID 13400 |
| neva_auditor_daemon.py | LaunchAgent com.neva.auditor Т6 | ✅ PID 5705 |
| neva_medic.py | Login Items / вручной nohup | ✅ PID 13924 |
| neva_control_center.py | вручной nohup (нет LaunchAgent) | ✅ PID 13759 |
| neva_approval_server.py | ~/.zshrc автозапуск | ✅ :8766 |
| mcp_server.py (stdio) | Claude Desktop MCP config | ✅ авто |

## API КЛЮЧИ (~/Documents/NEVA/.env)

| # | Переменная | Провайдер | Назначение |
|---|---|---|---|
| 1 | CEREBRAS_API_KEY | Cerebras | FlagmanRouter #1 |
| 2 | GROQ_API_KEY | Groq | FlagmanRouter #2 |
| 3 | OPENROUTER_API_KEY | OpenRouter | FlagmanRouter #3 |
| 4 | OPENROUTER_API_KEY_2 | OpenRouter #2 | резерв |
| 5 | DEEPSEEK_API_KEY | DeepSeek | аудит / резерв |
| 6 | MISTRAL_API_KEY | Mistral | аудит / резерв |
| 7 | COHERE_API_KEY | Cohere | аудит / резерв |
| 8 | GEMINI_API_KEY | Gemini | аудит / резерв |
| 9 | GITHUB_TOKEN | GitHub | git операции |
| 10 | NEVA_ADMIN_TOKEN | NEVA internal | auth сервера |
| 11 | NEVA_AGENT_TOKEN | NEVA internal | auth агентов |

## OLLAMA МОДЕЛИ

| Модель | Размер | Назначение |
|---|---|---|
| llama3.2:3b | 2.0 GB | архитектурный аудитор |
| qwen2.5:7b | 4.7 GB | code review / общие |

## ОТДЕЛЬНЫЕ ПРОЕКТЫ (не NEVA)

| Проект | Путь | MCP сервер |
|---|---|---|
| ARKA | ~/Documents/ARKA_SANDBOX/ | scripts/mcp_server.py |
| ARKA | ~/Documents/ARKA/ | отдельный venv |

## ИСТОРИЯ ИЗМЕНЕНИЙ
| Дата | Изменение |
|---|---|
| 2026-06-08 | Thermal Guard v9.4 — закрыт |
| 2026-06-11 | MCP Executor v6.3 — закрыт |
| 2026-06-13 | Medic v3.3 + CC v2.3 + medic_knowledge v1.0 |
| 2026-06-14 | Medic v3.6 + MCP Server v2.0 + Ч4+Ч9A закрыты |
| 2026-06-15 | Auditor Daemon v1.0 Т6, knowledge v3.0, Вариант Б |
| 2026-06-15 | Сессия 3: MCP file_read патч, launchd kickstart, CC v2.6, knowledge v5.0 |

*Обновлено: 2026-06-15 Сессия 3 | Архитектор: Claude | Директор: Серж*
*Красная зона governance — изменения только через CR + утверждение Директора*
