# Grok — INSPECTOR-001 Круг 2
Дата: 2026-06-25 21:30:55.983700

1. Готовые бесплатные решения:

Monit: Лёгкий open-source watchdog. Мониторит процессы, HTTP, логи, рестартует, алертит. Подходит: лёгкий, offline, macOS. Не подходит: не native launchd, чуть больше deps.⁠Mmonit
launchd + plist (native): Встроенный в macOS. KeepAlive, WatchPaths, Throttle. Полностью покрывает рестарт. Идеально для Mac M1/offline/min deps. Не покрывает сложные health-checks и дашборд.⁠Medium
osquery: Мониторинг процессов, health, SQL-запросы. Отлично для Mac. Не подходит: тяжеловат, нет авто-рестарта.⁠Dropbox

2. Взять в v1:

launchd KeepAlive + heartbeat для контроля Inspector.
Monit-подобную логику health + restart (pgrep + HTTP + log) вместо полного самописного.

3. Изменения в v1:

Усилить launchd.plist (KeepAlive, ThrottleInterval).
Добавить maintenance flag и suppress-файлы как есть.
Минимизировать Python: core на bash + launchd, rich только в мониторе.
Убрать qwen-диагноз если не критично (экономия ресурсов).