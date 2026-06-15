# NEVA TASK — ОПТИМИЗАЦИЯ СКОРОСТИ
# Для нового чата | Приоритет: ВЫСОКИЙ
# Создано: 2026-06-15 Сессия 4

## ПРОБЛЕМА
Текущая работа Claude медленная из-за:
1. Каждый neva_execute = отдельный HTTP round-trip (2-5 сек)
2. Нет параллельности — всё последовательно
3. Чтение целых файлов когда нужно 20 строк = лишние токены
4. off-by-one баг в file_patch = retry loops
5. Говернанс файлы: читаются по 1 каждый старт чата (холостой проход)

## ЦЕЛЬ
Сократить время работы Claude в 2-3 раза за счёт batch + token economy.

## ЗАДАНИЯ ДЛЯ АРХИТЕКТОРА (по приоритету)

### TASK-1: batch_actions в neva_mcp_server.py — ПРИОРИТЕТ 1
Сейчас:
  neva_execute(file_read A) → 3с
  neva_execute(file_read B) → 3с
  neva_execute(file_read C) → 3с
  Итого: 9 секунд

После:
  neva_execute(batch: [file_read A, file_read B, file_read C]) → 4с
  Итого: 4 секунд

Реализация:
  В neva_mcp_server.py добавить action='batch':
  params = {'actions': [{action, params}, {action, params}, ...]}
  запускает threading.Thread для независимых (read-only)
  последовательно для write (order matters)
  возвращает {'results': [result1, result2, result3]}

### TASK-2: file_patch off-by-one FIX — ПРИОРИТЕТ 2
  Баг: src_start в @@ не совпадает с file_lines (1-indexed)
  Диагностика: написать unit test который покажет смещение
  Исправить: в _apply_unified_diff()
  После фикса: self-test 8/8 PASS без retry loops

### TASK-3: token economy — ПРИОРИТЕТ 3
  3a. governance файлы — читать только summary (не полный текст)
      Добавить в каждый governance файл:
      ## SUMMARY (10 строк макс) — Claude читает только это при старте
      детали читает только по запросу
  
  3b. file_read с ограничением вывода
      Добавить params: max_lines=50 (default), summary_only=True
  
  3c. CHAT_CONTEXT_BUDGET — компактный словарь в начале чата
      вместо 5 полных governance файлов — 1 файл NEVA_SESSION_BRIEF.md

### TASK-4: NEVA_SESSION_BRIEF.md — ПРИОРИТЕТ 4
  Автогенерируемый файл (обновляется в конце каждой сессии):
  - Текущий статус (1 строка)
  - Версии программ (1 строка)
  - Открытые задачи (список)
  - Топ-3 приоритета
  Объём: макс 40 строк. Claude читает только это при старте.
  Экономия: 5 чтений файлов → 1 чтение = -80% токенов на старте

## ОЖИДАЕМЫЙ ЭФФЕКТ

| Таск | Ускорение |
|---|---|
| batch_actions | -50% round-trips → ~3-4 мин вместо 7 |
| file_patch fix | -15% retry loops → чистый патчинг |
| token economy | -60% токенов на старте чата |
| SESSION_BRIEF | -80% стартовых чтений |
| ВСЕГО | ~2-3x быстрее в сессии |

## СТАРТ СЛЕДУЮЩегО ЧАТА
Написать в начале: "читай SPEED_TASK.md и начинаем"

*2026-06-15 Сессия 4 | Написал: Claude*
