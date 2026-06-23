# ОТВЕТЫ ДИРЕКТОРА — КРУГ 5
# 5 блокирующих замечаний закрыты

---

## ПРИНЯТО (блокирующие)

**1. from pathlib import Path — первой строкой**
Принято. Исправлено в финальном коде.

**2. _CRASH_LOOP — добавить проверку в heal_cycle()**
Принято. DeepSeek прав — флаг устанавливается но heal_cycle его не видит.
```python
def heal_cycle():
    if _CRASH_LOOP:
        push_event('red')
        log('CRITICAL: crash loop — жду ручного вмешательства')
        return
```

**3. Heartbeat — атомарная запись через .tmp + os.replace()**
Принято. ChatGPT прав — status_dot может прочитать файл в момент записи.
```python
def write_heartbeat(status):
    tmp = HEARTBEAT.with_suffix('.tmp')
    tmp.write_text(f'{time.time()}|{os.getpid()}|{status}')
    os.replace(tmp, HEARTBEAT)
```

**4. nohup убрать из всех плейбуков и документации**
Принято. Gemini прав — nohup + launchd KeepAlive = двойной запуск.
Единственный метод запуска: launchctl kickstart -k.
Убираем nohup fallback из status_dot тоже.

**5. Boot-log — try/except на каждую строку**
Принято.
```python
boots = []
for l in BOOT_LOG.read_text().splitlines():
    try:
        boots.append(float(l.strip()))
    except ValueError:
        pass
```

---

## ПРИНЯТО (не блокирующие)

**6. Boot-log ротация — оставлять только последние 24 часа**
```python
recent = [t for t in boots if time.time() - t < 300]
# Ротация: перезаписываем только актуальные записи (< 24 часов)
BOOT_LOG.write_text('\n'.join(str(t) for t in boots if time.time() - t < 86400) + '\n')
```

**7. clear_logs — try/except на unlink**
```python
'clear_logs': lambda: [p.unlink(missing_ok=True) for p in Path('logs').glob('*.log')
                        if p.stat().st_size > 100*1024*1024 and not _is_open(p)],
```

---

## ОТКЛОНЕНО

**restart_medic в белом списке — убрать самоперезапуск из медика**
ChatGPT предложил убрать. Отклонено.
Причина: Медик нужен для recovery сценария когда завис внутри цикла но ещё жив.
status_dot делает pkill в таком случае, но если status_dot тоже завис — нужен плейбук.
Оставляем, но добавляем задержку перед самоперезапуском: `time.sleep(2)`.

**Переписать watchdog на Go/Rust**
Предложил Gemini. Отклонено.
Причина: избыточно. Python watchdog достаточен для задачи, все критические места закрыты.

---

## БЛОКИРУЮЩИХ ЗАМЕЧАНИЙ ОСТАЛОСЬ: 0
Все 5 блокирующих закрыты. Круг 6 — финальная проверка исправленного кода.
