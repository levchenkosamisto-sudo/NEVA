# NEVA RESOURCES MAP
Версия: 1.0 | Дата: 2026-05-30
Статус: ЗАФИКСИРОВАНО

## ЖЕЛЕЗО
- MacBook Air M1, 8GB RAM, 228GB диск
- THERMAL-SAFE: тяжёлые задачи только 00:00-07:00
- RESOURCE_CLASS: LOW / MEDIUM / HEAVY

## AI МОДЕЛИ

### Локальные (Ollama)
| Модель | Размер | Класс | Роль |
|--------|--------|-------|------|
| arka-dispatcher:latest | 2.0 GB | MEDIUM | диспетчер ARKA |
| llama3.2:3b | 2.0 GB | LOW | рабочая лошадка NEVA |
| qwen2.5:7b | 4.7 GB | HEAVY | только ночью |

### Облачные API (бесплатные тиры)
| Ключ | Env var | Лимит | Роль |
|------|---------|-------|------|
| OpenRouter #1 | OPENROUTER_API_KEY | 1000 req | сложные задачи |
| OpenRouter #2 | OPENROUTER_API_KEY_2 | 1000 req | резерв |
| GROQ | GROQ_API_KEY | без лимита | скорость |
| GEMINI | GEMINI_API_KEY | без лимита | большой контекст |
| MISTRAL | MISTRAL_API_KEY | без лимита | приватность |
| COHERE | COHERE_API_KEY | без лимита | embeddings |
| GitHub Models | GITHUB_TOKEN | 100 req/день | АУДИТОРЫ только |

### Архитектор (с памятью)
- Claude Desktop + MCP arka-memory = преемственность между чатами

## РОУТИНГ INFERENCE
- LOW    -> llama3.2:3b (локально)
- MEDIUM -> GROQ или MISTRAL (облако)
- HIGH   -> OpenRouter KEY_1 -> KEY_2 (резерв)
- AUDIT  -> GitHub Models (флагманы, 100 req/день)
- HEAVY  -> qwen2.5:7b (только ночью, локально)

## ХРАНИЛИЩА
| Хранилище | Объём | Роль | Статус |
|-----------|-------|------|--------|
| Mac локально | 228 GB | активная БД, memory | ready |
| GitHub | без лимита | код, конфиги, governance | ready |
| Google Drive | 15 GB | бэкап памяти | ready |
| MEGA | 5 GB | второй бэкап | pending |
| Cloudflare R2 | 10 GB/мес | снапшоты, логи | pending |

## ПРАВИЛА
1. GitHub — только код и конфиги, НЕ транзакционные данные
2. OPENROUTER_API_KEY_2 добавить в .zshenv
3. qwen2.5:7b — только ночью + ревью
4. GitHub Models — только аудит, не рабочий поток

## PENDING
- [ ] Зарегистрировать Cloudflare R2
- [ ] Подключить MEGA
- [ ] Добавить OPENROUTER_API_KEY_2 в .zshenv
