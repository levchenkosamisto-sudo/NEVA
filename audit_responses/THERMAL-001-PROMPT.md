# NEVA ThermalGuard v9.4 — Документ для аудита

**Система:** NEVA AI-оркестратор | **Mac M1 16GB RAM** | **macOS Sequoia**
**Компонент:** neva_thermal_guard.py
**Статус:** PROD | 32/34 тестов PASS | 2 FAIL (race condition)

## Назначение

ThermalGuard защищает Mac M1 от перегрева при работе NEVA.
Мониторит RAM / CPU / swap каждые 18 секунд.
При перегреве останавливает Ollama (локальные AI модели).

## FSM (9 состояний)

NOMINAL→WARM→HOT→CRITICAL→EMERGENCY→COOLING→RECOVERY→NOMINAL
+ MAINTENANCE (ручное) + UNKNOWN (ошибка)

Пороги: NOMINAL→WARM: RAM>70% или CPU>80% | WARM→HOT: RAM>80% | HOT→CRITICAL: RAM>90% | CRITICAL→EMERGENCY: RAM>95%+swap | COOLING→RECOVERY: RAM<70% за 60с | RECOVERY→NOMINAL: стабильно 120с

## Результаты тестов

32/34 PASS. 2 FAIL: race condition EMERGENCY→RECOVERY при CPU spike + network timeout одновременно.

## Известные проблемы

P1 (ХРОНИЧЕСКАЯ): macOS Sequoia FDA блокирует launchd агентам запись в thermal.log. Workaround: nohup вместо launchd.
P2: race condition в asyncio между мониторингом RAM и таймаутом сети. Открыт.

## Интеграция

Medic L1/L2/L3 мониторит каждые 60с. При stale лога >120с → playbook → 3 попытки → эскалация Claude L3.
Текущий стейт: DEGRADED (thermal_state.json).

## Задание аудитору — Круг 1

Прочитай документ и задай 5-8 вопросов по архитектуре и надёжности ThermalGuard.
Только вопросы. Без оценок и критики. Работаешь независимо.

Формат:
АУДИТОР: [имя]
AUDIT-ID: THERMAL-001
РАУНД: 1
Q1 — [тема]: [вопрос]
Q2 — [тема]: [вопрос]
