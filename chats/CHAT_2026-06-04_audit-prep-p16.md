# ИТОГ ЧАТА: 2026-06-04 — Подготовка аудита v3.5 + P16
## Файл: chats/CHAT_2026-06-04_audit-prep-p16.md

### УЧАСТНИКИ
- Серж (Директор)
- Claude (Архитектор, Opus 4.8)

### ЧТО СДЕЛАНО

1. **Получен полный манифест NEVA-TASK-007 v3.5** из предыдущего чата
2. **Добавлен принцип P16** — индексация всех документов NEVA одной моделью:
   - Graphiti + multilingual-e5-small + Kuzu
   - RAW файл = ИСТИНА 100%, индекс = УКАЗАТЕЛЬ через source_path
   - Каждый атом: source_path, doc_id, doc_version, sha256
   - Цель K_repro: 95%, реально e5-small: 0.76–0.84
   - Старый neva_indexer.py (Mistral) → удалить после переиндексации
3. **Созданы 3 аудит-пакета** (Gemini, GPT, DeepSeek) с P16
4. **Созданы 3 ТЗ** (DeepSeek, Gemini, GPT) с правками по P16:
   - ТЗ-1: neva_init.py → --import-all, --reindex, source_path+sha256
   - ТЗ-2: /api/v1/search и /api/v1/document/{doc_id}
   - ТЗ-3: self-test №8 → проверка P16
5. **Все 7 файлов разложены** по governance/, tz/, audits/
6. **Git commit d96ab83** — зафиксировано

### РЕШЕНИЯ ПРИНЯТЫЕ В ЭТОМ ЧАТЕ

| Решение | Обоснование |
|---|---|
| P16: одна модель индексации | Принцип стандартизации (Директор) |
| RAW = истина 100%, индекс = указатель | Не нарушает P15, перестраивается из RAW |
| Целевой K_repro 95% | Директор: к чему стремиться |
| Реальный K_repro 0.76–0.84 | MTEB multilingual-e5-small RU |
| НЕ устанавливать Chrome | M1 8GB, +500MB RAM, только Haiku — не стоит |
| Opus 4.8 для архитектуры | Глубина, логика, не пропускает дыры |
| Sonnet 4.6 для рутины | Лимит в 5-6x больше |
| Гигиена чатов | Утверждён → обновить KB → новый чат |
| Два новых чата | 1: аудит v3.5, 2: память/организация |

### ОТКРЫТЫЕ ЗАДАЧИ (перенесены в новые чаты)

- [ ] Финальный аудит v3.5 + P16 (Gemini, GPT, DeepSeek) → Чат 1
- [ ] Обновить arka-memory (устарел: ARKA CORE v4) → Чат 2
- [ ] Создать Project в claude.ai + загрузить KB → Чат 2
- [ ] Доработать NEVA_PROJECT_INSTRUCTION.md → Чат 2
- [ ] Обновить/удалить NEVA_PROJECT_KNOWLEDGE.md (устарел) → Чат 2

### ФАЙЛЫ СОЗДАННЫЕ В ЭТОМ ЧАТЕ

| Файл | Куда сохранён | Статус |
|---|---|---|
| NEVA-TASK-007-v3.5.md | governance/ | ✅ Git |
| NEVA_TZ1_DEEPSEEK.md | tz/ | ✅ Git |
| NEVA_TZ2_GEMINI.md | tz/ | ✅ Git |
| NEVA_TZ3_GPT.md | tz/ | ✅ Git |
| NEVA_AUDIT_GEMINI.md | audits/ | ✅ Git |
| NEVA_AUDIT_GPT.md | audits/ | ✅ Git |
| NEVA_AUDIT_DEEPSEEK.md | audits/ | ✅ Git |
| NEVA_PROJECT_INSTRUCTION.md | НЕ на диске | ⏳ загрузить в KB |
