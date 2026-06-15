# NEVA — Вариант В: Vector Search для базы знаний медика
# Решение Директора: Серж | Дата: 2026-06-15 | Архитектор: Claude

## СТАТУС: ОТЛОЖЕНО — после TASK-007 Этап 2

## Условие запуска
- graphiti-core подключён (TASK-007 Этап 2)
- e5-small embedding работает
- Kuzu БД активна с семантическим поиском

## Что реализовать
1. При heal_success/fail — писать embedding симптома в Kuzu
2. В ai_diagnose() — cosine similarity поиск по симптому
3. Возвращать TOP-3 похожих инцидента с resolution
4. Передавать в AI промпт как контекст

## Ожидаемый эффект
- conf медика: 0.88 → 0.95+
- Находит похожие сбои с разными symptom strings
- База знаний растёт семантически, не только по exact problem_id

## Текущее решение (Вариант Б)
incident_log.json + incident_log_search() по exact problem_id match.
Работает с 2026-06-15. conf: 0.75 → 0.88.
