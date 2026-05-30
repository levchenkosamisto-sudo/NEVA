# NEVA — АВАРИЙНЫЙ ПАКЕТ
> Читай этот файл первым при любом сбое

## ЧТО ТАКОЕ NEVA
NEVA — система управления памятью и потоками документов для мульти-агентной разработки.
Проекты: ARKA (разработка), SARJ (медмониторинг).
Архитектор: Серж.

## ИСТОЧНИК ИСТИНЫ
→ governance/ (все правила и решения)
→ Git (история изменений)

## ЕДИНСТВЕННАЯ ЗАПИСЬ В БД
→ core/db_writer.py (только через него)

## ЕДИНСТВЕННАЯ ТОЧКА ВХОДА
→ dispatcher/dispatcher.py

## ПРОМПТЫ АГЕНТОВ
→ prompts/claude.md
→ prompts/chatgpt.md

## КАК ПРОВЕРИТЬ ЧТО СИСТЕМА ЖИВА
```bash
python3 dispatcher/dispatcher.py --health
```

## АГЕНТЫ
- Claude Desktop → через MCP (arka-memory)
- ChatGPT → получает пакет от диспетчера вручную
- API агенты → через dispatcher REST endpoint

## КОНТАКТ
Архитектор: Серж
Регламент: governance/neva_rules.md
