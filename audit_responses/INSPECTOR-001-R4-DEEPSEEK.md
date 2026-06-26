# Deepseek — INSPECTOR-001 Круг 4
Дата: 2026-06-25 21:53:17.397909

ФИНАЛЬНАЯ ВАЛИДАЦИЯ АРХИТЕКТУРЫ v3
1. STATE MACHINE — КОРРЕКТНОСТЬ ПЕРЕХОДОВ

Обнаружены две проблемы:

Проблема 1: Переход STARTING → DEAD

text
Copy
Download
STARTING → DEAD : grace period истёк, PID уже нет

Если grace period = 30 секунд, а процесс стартанул, но упал через 1 секунду — Inspector увидит STARTING, подождёт 30 секунд, и только потом переведёт в DEAD. Это означает, что реальное падение будет обнаружено с задержкой 30 секунд + 2 цикла (60 секунд) для подтверждения = 90 секунд. Слишком долго для процесса, который должен быть живым.

Проблема 2: Переход ALIVE → STALE при отсутствии HTTP/лог
Для процессов без HTTP/лог (background_auditor) используется cpu_percent = 0. Но cpu_percent — это среднее за интервал, и для процессов которые спят (ждут события) это нормально. Процесс может быть жив, но не потреблять CPU >1 минуты. Это приведёт к ложному STALE.

Рекомендация:

STARTING → DEAD проверять сразу, без ожидания grace period: если PID нет и grace period не истёк → DEAD (не ждать)

Для background_auditor убрать проверку CPU, оставить только наличие PID

2. STALE→DEAD ЧЕРЕЗ PKILL -9 — РИСКИ

Риски:

Риск 1: pkill -9 по совпадению имени
pkill -9 -f "desktop-commander" может убить процесс, который не является desktop-commander, если его путь содержит эти символы (например, ~/projects/desktop-commander-backup). В psutil мы знаем точный PID — нужно убивать по PID, а не по имени.

Риск 2: Убийство процесса в момент записи данных
pkill -9 — это SIGKILL, процесс не успевает сохранить состояние. Для сервисов с состоянием (MCP сервер, approval_srv) это риск коррупции данных. Лучше сначала SIGTERM (pkill без -9), подождать 5 секунд, и только потом SIGKILL.

Рекомендация:

python
Copy
Download
def kill_process(pid, timeout=5):
    proc = psutil.Process(pid)
    proc.terminate()  # SIGTERM
    proc.wait(timeout=timeout)
    if proc.is_running():
        proc.kill()  # SIGKILL
3. ВЗАИМНЫЙ КОНТРОЛЬ INSPECTOR↔MEDIC — ДЕДЛОК?

Сценарий 1: Inspector упал → Medic поднимает через launchctl
Medic проверяет heartbeat. Если Inspector мёртв, Medic делает launchctl kickstart com.neva.inspector. Это не deadlock, это работает.