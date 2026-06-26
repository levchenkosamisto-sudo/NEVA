# DeepSeek
Дата: 2026-06-22 23:41:23.133615

ФИНАЛЬНАЯ ВАЛИДАЦИЯ NEVA_MEDIC — КРУГ 5
1. ПРОТИВОРЕЧИЯ МЕЖДУ БЛОКАМИ КОДА
✅ ПРОТИВОРЕЧИЙ НЕТ

Проверка связок:

Связка	Блок A	Блок B	Статус
Heartbeat при старте → status_dot	Пишет starting	Читает ts|pid|status	✅ Совместимо
Boot-счётчик → crash_loop	Устанавливает _CRASH_LOOP = True	В коде не показан push_event	⚠️ См. ниже
Белый список → run_playbook()	Определён PLAYBOOK_COMMANDS	Вызов PLAYBOOK_COMMANDS[playbook_id]()	✅ Тип dict[str, Callable]
os.replace() → импорты	Использует os.replace	import os есть в Блоке 1	✅
Grace period → kill	proc_uptime > 120	Сигнал не отправлен в синтезе	✅ Безопасно

Единственное НЕсоответствие:

python
Copy
Download
# Блок 1 — установка флага
_CRASH_LOOP = True

# Блок 2 — нет проверки _CRASH_LOOP в heal_cycle()
def heal_cycle():
    # ❌ НЕТ: if _CRASH_LOOP: push_event('red'); return

Решение: добавить в начало heal_cycle():

python
Copy
Download
def heal_cycle():
    if _CRASH_LOOP:
        push_event('red', 'crash_loop_detected')
        log('CRITICAL: crash loop detected, waiting for manual intervention')
        # Не выходим, но отправляем сигнал директору
        return
    # ... остальной код
2. ПОРЯДОК ОПЕРАЦИЙ ПРИ СТАРТЕ
ТЕКУЩИЙ ПОРЯДОК В БЛОКЕ 1:
python
Copy
Download
1. import fcntl, sys, os, time
2. HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
3. HEARTBEAT.write_text(f'{time.time()}|{os.getpid()}|starting')   # ← heartbeat
4. LOCK_PATH = ...
5. _LOCK = open(LOCK_PATH, 'w')
6. _acquire_lock()                                                 # ← lock
7. BOOT_LOG = ...
8. with open(BOOT_LOG, 'a') as f: ...
9. boots = [float(l) for l in BOOT_LOG.read_text().splitlines()]   # ← boot-счётчик
10. if len(recent) >= 3: _CRASH_LOOP = True
11. # импорты (requests, json, etc.) — ПОСЛЕ всего
✅ ПОРЯДОК ПРАВИЛЬНЫЙ

Обоснование:

Heartbeat до lock — если процесс упадёт в fcntl.flock(), предыдущий heartbeat останется и status_dot увидит проблему

Lock до boot-счётчика — если второй процесс заблокирован, он не пишет в boot-лог

Boot-счётчик до импортов — если requests или psutil сломаны, crash-loop будет зафиксирован до их загрузки

Импорты в конце — все