# file_patch — База знаний медика
# Программа: neva_mcp_patch.py v1.1 + neva_mcp_server.py v2.1
# Обновлено: 2026-06-15 (Ч9 Этап B)

## ЧТО ТАКОЕ
`file_patch` — MCP action для применения unified diff к файлу без перезаписи целиком.
Экономит токены: передаём только изменённые строки (не весь файл).

## БЕЗОПАСНОСТЬ (v1.1)

### AUTH
Сервер автоматически подставляет ADMIN_TOKEN из .env.
Внешний клиент может передать `token` явно. Без токена → AUTH_FAILED.

### WHITELIST (BASE_DIR guard)
Разрешённые пути (только эти деревья):
- `~/Documents/NEVA_MCP_BRIDGE/` — все серверы и модули
- `~/Documents/NEVA/` — core, governance, tools

Попытка патчить файл за пределами → PATH_DENIED.

## ПРИМЕР DIFF

```
@@ -3,3 +3,3 @@
 предыдущая строка
-старая строка
+новая строка
 следующая строка
```

Правило использования чисел в `@@`:
- `file_lines` возвращает 1-indexed номера строк
- в `@@` используется тот же номер, но движок от `file_lines` составляет +2
- **Безопасный путь**: использовать контекстные `-` строки, а не полагаться на номер

## РЕЗУЛЬТАТЫ

| Статус | Означает |
|---|---|
| `ok` + `lines_changed` | Патч применён, .bak удалён |
| `AUTH_FAILED` | Неверный токен |
| `PATH_DENIED` | Путь за пределами ALLOWED_ROOTS |
| `Файл не найден` | Неверный путь |
| `Контекст не совпадает` | Строки в diff не совпадают с файлом |
| `Дифф не привёл к изменениям` | Контент уже актуален |

## SELF-TESTS

`neva_mcp_patch.py` — 6/6 PASS (запуск `python neva_mcp_patch.py`)
`neva_mcp_server.py` ST-04 — патчит `state/_patch_selftest.txt` внутри BASE

## ЛОГ

Логи `file_patch` пишутся через `logging.getLogger('neva_mcp_patch')`
В файл: `logs/mcp_server_net.log` (общий лог сервера)
Формат: `file_patch OK: /path/to/file lines_changed=N`

## ОТЛАДКА

```bash
# Проверить что file_patch работает:
cd ~/Documents/NEVA_MCP_BRIDGE
python -c "from neva_mcp_patch import apply_patch; print(apply_patch.__doc__)"

# Запустить self-test patch:
python neva_mcp_patch.py

# Запустить self-test сервера (ST-04 проверяет file_patch):
NEVA_ADMIN_TOKEN=$(grep NEVA_ADMIN_TOKEN ~/Documents/NEVA/.env | cut -d'=' -f2) \
python neva_mcp_server.py --self-test
```

## ОТКАТ
БАК: автоматически (файл + `.bak`), удаляется после успеха.
При ошибке записи — автоматический роллбэк из `.bak`.

*Создано: 2026-06-15 (Ч9 Этап B) | Архитектор: Claude | Директор: Серж*
