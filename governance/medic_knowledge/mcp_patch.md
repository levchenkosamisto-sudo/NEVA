# neva_mcp_patch.py v1.2 — Knowledge Base
# Версия: 1.0 | Дата: 2026-06-15

## НАЗНАЧЕНИЕ
Применение unified diff к файлам с auth + whitelist защитой.
Если сломан — все file_patch операции падают, Claude не может патчить файлы.

## ДИАГНОСТИКА

### patch_module_broken
Симптом: file_patch возвращает ImportError или MODULE_NOT_FOUND
```bash
cd ~/Documents/NEVA_MCP_BRIDGE
python3 -c "from neva_mcp_patch import apply_patch; print('OK')"
```

### patch_auth_fail
Симптом: file_patch возвращает AUTH_FAILED
Причина: NEVA_ADMIN_TOKEN не загружен из .env
```bash
grep NEVA_ADMIN_TOKEN ~/Documents/NEVA/.env
```
Решение: проверить .env, перезапустить сервер

### patch_path_denied
Симптом: file_patch возвращает PATH_DENIED
Причина: путь вне ALLOWED_ROOTS (NEVA_MCP_BRIDGE, NEVA)
Решение: использовать абсолютный путь внутри разрешённых директорий

### patch_context_mismatch
Симптом: "Контекст не совпадает на строке N"
Причина: файл изменился с момента создания diff
Решение: перечитать файл, создать новый diff

## FAILURE MODES
| ID | Симптом | Серьёзность | Действие |
|---|---|---|---|
| patch_module_broken | import fail | HIGH | ASK |
| patch_auth_fail | AUTH_FAILED | MEDIUM | AUTO: перезапустить сервер |
| patch_path_denied | PATH_DENIED | LOW | ASK архитектора |

## SELF-TEST
```bash
python3 /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_mcp_patch.py
# Ожидание: 7/7 PASS
```

## WHITELIST PATHS
- ~/Documents/NEVA_MCP_BRIDGE/ (и все подпапки)
- ~/Documents/NEVA/ (и все подпапки)
