# mcp_server_net knowledge
# Версия: 2.0 | Обновлено: 2026-06-15 | Архитектор: Claude

---

## КОМПОНЕНТ: neva_mcp_server.py v2.0
Файл:   ~/Documents/NEVA_MCP_BRIDGE/neva_mcp_server.py
Порты:  :9000 (MCP API) / :9001 (Dashboard)
venv:   /Users/arka/Documents/NEVA/.venv/bin/python3  ← ПРАВИЛЬНЫЙ
Лог:    ~/Documents/NEVA_MCP_BRIDGE/logs/mcp_server_net.log
BASE:   ~/Documents/NEVA_MCP_BRIDGE/

---

## АРХИТЕКТУРА — КАК РАБОТАЕТ

```
Claude Desktop
  └─ neva_mcp_proxy.py (stdio)
       └─ HTTP POST → :9000/mcp
            └─ neva_mcp_server.py _execute_action()
                 ├─ neva_status, neva_heal, neva_chronic  ← встроены в server
                 ├─ file_read, file_tree, git_status ...  ← через mcp_executor
                 └─ _executor_run(validated)              ← mcp_executor.run()

mcp_executor.py  ← загружается из NEVA_MCP_BRIDGE/ (ВАЖНО: не из NEVA/tools/)
mcp_validator.py ← загружается из NEVA_MCP_BRIDGE/
```

### КРИТИЧЕСКИЙ ФАКТ (баг 2026-06-15):
В neva_mcp_server.py sys.path должен иметь NEVA_MCP_BRIDGE ПЕРВЫМ.
Если NEVA/tools попадает в path раньше — загружается СТАРЫЙ mcp_executor
из NEVA/tools/mcp_executor/ без file_read/tree/git_status.
Результат: все файловые actions → "Неизвестное action: file_read"

---

## ДИАГНОСТИКА — ДЕРЕВО РЕШЕНИЙ

### Шаг 1 — Сервер жив?
```bash
curl -s http://127.0.0.1:9000/health
# Ожидание: {"status": "ok", "version": "2.0"}
```
Если нет ответа → Шаг 2 (запустить)
Если ответ есть → Шаг 3 (проверить actions)

### Шаг 2 — Запуск сервера
```bash
# Проверить занятость порта:
lsof -i :9000
# Если занят — kill старый процесс:
kill $(lsof -ti :9000)
sleep 2
# Запустить:
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_mcp_server.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/mcp_server_net.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:9000/health
```

### Шаг 3 — file_read работает?
```bash
curl -s -X POST http://127.0.0.1:9000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"neva_execute","arguments":{"action":"file_read","params":{"path":"/Users/arka/Documents/NEVA/governance/index.md"}}}}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); t=json.loads(d['result']['content'][0]['text']); print('STATUS:', t.get('status'))"
# Ожидание: STATUS: ok
```
Если STATUS: error, reason: "Неизвестное action" → Шаг 4 (баг sys.path)
Если STATUS: ok → сервер исправен

### Шаг 4 — Диагностика sys.path бага
```bash
# Проверить что загружается:
python3 -c "
import sys
sys.path.insert(0, '/Users/arka/Documents/NEVA_MCP_BRIDGE')
from mcp_executor import run
import mcp_executor, os
print('executor path:', os.path.abspath(mcp_executor.__file__))
"
# ПРАВИЛЬНО: .../NEVA_MCP_BRIDGE/mcp_executor.py
# НЕПРАВИЛЬНО: .../NEVA/tools/mcp_executor/mcp_executor.py
```
Если путь неправильный → Шаг 5 (патч файла)

### Шаг 5 — Патч sys.path в neva_mcp_server.py
```bash
cd /Users/arka/Documents/NEVA_MCP_BRIDGE
cp neva_mcp_server.py neva_mcp_server.py.bak
python3 - << 'PYEOF'
content = open('neva_mcp_server.py').read()
old = """try:\n    from mcp_executor import run as _executor_run\n    from mcp_validator import validate as _executor_validate\n    _EXECUTOR_OK = True\nexcept ImportError:\n    _EXECUTOR_OK = False"""
new = """# FIX: явно ставим BASE первым чтобы не загрузить tools/mcp_executor\nimport sys as _sys\nif str(BASE) not in _sys.path:\n    _sys.path.insert(0, str(BASE))\ntry:\n    from mcp_executor import run as _executor_run\n    from mcp_validator import validate as _executor_validate\n    _EXECUTOR_OK = True\nexcept ImportError as _e:\n    _EXECUTOR_OK = False\n    import logging as _l; _l.getLogger('neva_mcp_server').error(f'EXECUTOR IMPORT FAILED: {_e}')"""
if old in content:\n    content = content.replace(old, new)\n    open('neva_mcp_server.py', 'w').write(content)\n    print('PATCH OK')\nelse:\n    print('PATTERN NOT FOUND — патч уже применён или файл изменился')
PYEOF
```
После патча → перезапустить сервер (Шаг 2) → проверить (Шаг 3)

### Шаг 6 — Проверка EXECUTOR_OK при старте
```bash
# Симуляция импорта как делает сервер:
cd /Users/arka/Documents/NEVA_MCP_BRIDGE && python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from mcp_executor import run as r
    from mcp_validator import validate as v
    print('EXECUTOR_OK=True')
except ImportError as e:
    print('EXECUTOR_OK=False —', e)
"
# Ожидание: EXECUTOR_OK=True
```

---

## ИЗВЕСТНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### mcp_server_net_http — сервер не отвечает на :9000
Причина A: процесс упал
Причина B: порт занят старым процессом
Причина C: launchd не запустил (exit 78 — неправильный venv в plist)
Решение: Шаг 1 → Шаг 2 выше

### file_read / file_tree / git_status → "Неизвестное action"
Причина: EXECUTOR_OK=False или загружен неправильный mcp_executor
Диагностика: Шаг 3 → Шаг 4
Решение: Шаг 5 (патч) + Шаг 2 (перезапуск)
Эталонный патч: governance/neva_mcp_server_patched_2026-06-15.py

### exit 78 в launchd
Причина: plist указывает на несуществующий venv
НЕПРАВИЛЬНО: ~/Documents/NEVA_MCP_BRIDGE/.venv/bin/python3 (не существует)
ПРАВИЛЬНО:  /Users/arka/Documents/NEVA/.venv/bin/python3
Диагностика: launchctl list | grep mcp
Решение: исправить plist, launchctl unload/load
Временное решение: nohup запуск (Шаг 2)

### mcp_approval_hang — executor принял токен, завис >90с
Причина: approval_store не получил decision
Playbook: restart_mcp_server_net

### mcp_proxy_fallback_stuck — proxy не передаёт на :9000
Причина: neva_mcp_proxy.py завис
Playbook: restart_mcp_server_net

---

## PLAYBOOK: restart_mcp_server_net
```bash
# 1. Найти и убить процесс
PID=$(lsof -ti :9000)
[ -n "$PID" ] && kill $PID && sleep 2
# 2. Запустить
nohup /Users/arka/Documents/NEVA/.venv/bin/python3 -u \
  /Users/arka/Documents/NEVA_MCP_BRIDGE/neva_mcp_server.py \
  >> /Users/arka/Documents/NEVA_MCP_BRIDGE/logs/mcp_server_net.log 2>&1 &
sleep 3
# 3. Проверить
curl -s http://127.0.0.1:9000/health | python3 -c "import json,sys; print(json.load(sys.stdin).get('status'))"
```

---

## ИСТОРИЯ АВАРИЙ

### 2026-06-15 — EXECUTOR_OK=False, все file_* actions сломаны
Симптом: file_read/tree/git_status → "Неизвестное action: file_read"
Причина: sys.path в neva_mcp_server.py не гарантировал NEVA_MCP_BRIDGE первым.
  mcp_executor.py из NEVA/tools/mcp_executor/ (старый, без file_read)
  загружался вместо NEVA_MCP_BRIDGE/mcp_executor.py (v3.1, полный).
Диагностика: 6 шагов (curl health → curl file_read → python path check)
Патч: sys.path.insert(0, str(BASE)) перед блоком try/import executor
Перезапуск: kill 98615, новый PID 11731
Результат: file_read/tree/git_status/system_info — все ok
Коммит: 7d22342 (governance/neva_mcp_server_patched_2026-06-15.py)

### 2026-06-15 — launchd exit 78 (backoff), kickstart решение
Симптом: launchctl list | grep mcp → "- 78 com.neva.mcp-server", нет PID
Причина: НЕ неправильный plist (он правильный: NEVA/.venv/bin/python3).
  Реальная причина: многократные ручные запуски занимали порт 9000/9001.
  launchd пытался запустить → сервер видел занятый порт → sys.exit(1).
  После N падений launchd входил в backoff и переставал пытаться.
Диагностика:
  launchctl list com.neva.mcp-server → LastExitStatus=19968 (78*256), нет PID
  lsof -i :9000 → занят ручным процессом
Решение:
  kill $(lsof -ti :9000 :9001 2>/dev/null)
  launchctl kickstart -k gui/$(id -u)/com.neva.mcp-server
  curl -s http://127.0.0.1:9000/health → {"status":"ok"}
Правило: НЕ запускать ручные процессы на :9000/:9001 пока launchd агент загружен.
  Либо: launchctl unload plist перед ручным запуском.
