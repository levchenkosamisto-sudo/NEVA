# DUMA AUDIT TASK-001 | 2026-06-21
# Директор: Серж | Архитектор: Claude
# СТАТУС: ПЛАНИРОВАНИЕ

## ЦЕЛЬ
Провести первый аудит ДУМЫ самой ДУМЫ — 4 независимыми ИИ-аудиторами.
Протокол: neva_audit_protocol_DRAFT.md (7 этапов)

## АУДИТОРЫ
- ChatGPT (Playwright)
- Gemini (Playwright)
- DeepSeek (Claude in Chrome)
- Grok (Claude in Chrome)

## ЧТО НУЖНО СДЕЛАТЬ

### ШАГ 1: Подготовка GitHub
- [ ] Залить всю ДУМУ в neva-audit/duma/
- [ ] Описание как работает DUMA (README.md)
- [ ] neva_audit_protocol_DRAFT.md — правила аудита
- [ ] duma_playwright.py — код ДУМЫ
- [ ] Все промпты governance/duma/prompts/

### ШАГ 2: Система учёта аудитов
Формат ID: AUDIT-001-R1-DEEPSEEK
  - AUDIT-001: номер аудита
  - R1: номер круга
  - DEEPSEEK: аудитор

Файлы: audit_responses/AUDIT-001-R1-DEEPSEEK.yaml
Реестр: audit_responses/AUDIT-001-registry.json

### ШАГ 3: Шаблон YAML ответа
Шаблон не ограничивает аудитора — только задаёт структуру.

```yaml
audit_id: AUDIT-001
round: 1
auditor: deepseek
timestamp: 2026-06-21T00:00:00

questions:
  - id: Q1
    topic: "архитектура"
    text: "ваш вопрос"
    # Дополнительные поля по усмотрению аудитора

notes: |
  Любые дополнительные наблюдения аудитора
```

### ШАГ 4: Промпт аудита (Круг 1)
Содержит:
- Ссылка на ДУМУ в GitHub
- Описание что такое DUMA
- Правила аудита (7 этапов)
- Задание: только вопросы, без оценок
- Шаблон YAML для ответа
- ID: AUDIT-001-R1-[AUDITOR]

### ШАГ 5: Статус по каждому кругу
Claude докладывает Директору:
- кто из 4 аудиторов ответил
- кто нет
- содержимое ответов (кратко)

## ЧТО ДЕЛАЕТ СЛЕДУЮщИЙ ЧАТ
1. Подготовить и залить GitHub (Шаг 1)
2. Создать систему учёта + шаблон YAML
3. Написать промпт Круга 1
4. Запустить: Playwright (ChatGPT+Gemini) + Claude in Chrome (DeepSeek+Grok)
5. Доклад: кто ответил
