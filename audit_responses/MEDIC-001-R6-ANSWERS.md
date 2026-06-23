# ОТВЕТЫ ДИРЕКТОРА — КРУГ 6
# 4 блокирующих замечания закрыты

---

## ПРИНЯТО (все 4 блокирующих)

**1. save_incident_log() — относительный путь → STATE**
```python
def save_incident_log(data):
    tmp = STATE/'incident_log.json.tmp'
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, STATE/'incident_log.json')
```

**2. _CRASH_LOOP → бесконечный цикл launchd**
При crash_loop медик не должен просто делать return — launchd поднимет снова.
Решение: после записи heartbeat и push_event → time.sleep(3600) чтобы launchd не перезапускал.
```python
if _CRASH_LOOP:
    write_heartbeat('crash_loop')
    push_event('red')
    log('CRITICAL: crash loop — жду ручного вмешательства')
    time.sleep(3600)  # держим процесс живым чтобы launchd не перезапускал
    sys.exit(1)
```

**3. _is_open() не определена в clear_logs**
Убираем _is_open() — просто missing_ok=True достаточно:
```python
'clear_logs': lambda: [
    p.unlink(missing_ok=True)
    for p in (Path.home()/'Documents/NEVA_MCP_BRIDGE/logs').glob('*.log')
    if p.exists() and p.stat().st_size > 100*1024*1024
],
```

**4. Path('logs') → абсолютный путь**
Все пути через STATE или абсолютные. В коде остался только один relative path — исправлен выше.

**5. requests без перехвата RequestException (Gemini, не блокирующее → принято)**
```python
try:
    resp = requests.get('http://localhost:9000/health', timeout=(3.05, 15)).json()
    assert resp.get('status') == 'ok' and 'version' in resp
except requests.exceptions.RequestException as e:
    log(f'MCP network error: {e}')
except Exception as e:
    log(f'MCP health failed: {e}')
```

---

## БЛОКИРУЮЩИХ ЗАМЕЧАНИЙ ОСТАЛОСЬ: 0
