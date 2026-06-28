"""
NEVA ПАМЯТЬ v3 — Индексатор
src/memory/indexer.py

Цепочка: Церебрас → Грок → qwen (fallback)
Шаги:
  1. Извлечение фактов + важность 1-5
  2. Проверка противоречий (исключение для важность 5)
  3. Запись в SQLite
  4. Векторизация (только когда qwen не активна)
"""
import json
import os
import logging
import time
from pathlib import Path
from datetime import datetime

from .db import get_conn, insert_record, update_status, find_contradictions


log = logging.getLogger("neva.indexer")

# Глобальный кеш e5-base — загружается один раз
_E5_MODEL = None

def _get_e5_model():
    global _E5_MODEL
    if _E5_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _E5_MODEL = SentenceTransformer("intfloat/multilingual-e5-base")
            log.info("[EMBED] e5-base загружена в память")
        except ImportError:
            log.warning("[EMBED] sentence-transformers не установлен")
    return _E5_MODEL

from .rate_limiter import call_with_rate_limit

# Иерархия доверия → важность по пути файла
PATH_IMPORTANCE = {
    "governance/decisions": 5,
    "governance/architecture": 4,
    "state/NEVA_SESSION_BRIEF": 4,
    "state/tasks": 3,
    "audit/responses": 2,
    "memory/raw/chats": 1,
}


def importance_from_path(path: str) -> int:
    for prefix, imp in PATH_IMPORTANCE.items():
        if prefix in path:
            return imp
    return 2


def call_ai(prompt: str, max_tokens: int = 1000) -> str | None:
    """Вызов ИИ с rate limiting и ротацией: Церебрас(1RPM)→Грок(30RPM)→DeepSeek(60RPM)."""
    return call_with_rate_limit(prompt, max_tokens=max_tokens)


def extract_facts(text: str, source_path: str) -> list[dict]:
    """
    Шаг 1: ИИ извлекает факты из документа.
    Возвращает список: [{text, type, importance, table}]
    """
    base_importance = importance_from_path(source_path)

    prompt = f"""Ты — индексатор памяти системы NEVA.
Прочитай документ и извлеки факты. Отвечай ТОЛЬКО JSON-массивом.

Каждый факт:
{{"text": "...", "type": "DECISION|FACT|AUDIT|EVENT|CHAT|PROCEDURE|ARCHITECTURE", "importance": 1-5, "table": "facts|episodes|procedures"}}

Шкала важности:
5 = решение Директора, утверждённая архитектура
4 = результат аудита, зафиксированный факт
3 = предложение принятое к рассмотрению
2 = рабочая гипотеза, обсуждение
1 = шум — НЕ включай в ответ

Базовая важность для этого источника: {base_importance}
Источник: {source_path}

Документ:
{text[:3000]}

Отвечай только JSON-массивом без пояснений."""

    response = call_ai(prompt)
    if not response:
        log.error("[INDEXER] ИИ недоступен для %s", source_path)
        return []

    try:
        # Извлекаем JSON из ответа
        start = response.find("[")
        end = response.rfind("]") + 1
        if start < 0 or end <= start:
            return []
        facts = json.loads(response[start:end])
        # Фильтруем важность 1 — только сырой архив
        return [f for f in facts if f.get("importance", 1) >= 2]
    except json.JSONDecodeError as e:
        log.error("[INDEXER] ошибка парсинга JSON: %s", e)
        return []


def check_contradiction(table: str, new_text: str, new_importance: int, conn) -> list[dict]:
    """
    Шаг 2: Проверка противоречий.
    Исключение: если старый факт важность 5 — не трогаем автоматически.
    """
    candidates = find_contradictions(table, new_text, conn)
    if not candidates:
        return []

    contradictions = []
    for candidate in candidates:
        if candidate["status"] != "АКТУАЛЬНО":
            continue

        prompt = f"""Эти два утверждения противоречат друг другу?
Отвечай только: ДА или НЕТ

Утверждение 1: {candidate['text']}
Утверждение 2: {new_text}"""

        answer = call_ai(prompt)
        if answer and "ДА" in answer.upper():
            contradictions.append(candidate)

    return contradictions


def resolve_contradiction(table: str, old: dict, new_importance: int) -> str:
    """
    Определяем что делать со старым фактом при противоречии.
    Исключение аудиторов: важность 5 не отменяется автоматически.
    """
    if old["importance"] == 5:
        # Решение Директора — только уведомление, не ОТМЕНЕНО
        return "ТРЕБУЕТ_ПРОВЕРКИ_ДИРЕКТОРА"
    return "ОТМЕНЕНО"


def vectorize(text: str) -> bytes | None:
    """Векторизация через e5-base (модель в памяти)."""
    try:
        import numpy as np
        model = _get_e5_model()
        if model is None:
            return None
        vec = model.encode(text, normalize_embeddings=True)
        return vec.astype(np.float32).tobytes()
    except Exception as e:
        log.error("[EMBED] ошибка: %s", e)
        return None

def index_document(path: str, text: str) -> int:
    """
    Полный цикл индексации одного документа.
    Возвращает количество записанных фактов.
    """
    log.info("[INDEXER] → %s", path)
    facts = extract_facts(text, path)
    if not facts:
        log.info("[INDEXER] фактов не извлечено из %s", path)
        return 0

    count = 0
    with get_conn() as conn:
        for fact in facts:
            table = fact.get("table", "facts")
            new_text = fact["text"]
            new_importance = fact.get("importance", 2)
            fact_type = fact.get("type", "FACT")

            # Санитизация: проверяем что тип соответствует таблице
            TYPE_TABLE = {
                "facts":      {"DECISION","FACT","ARCHITECTURE","COMPONENT"},
                "episodes":   {"AUDIT","EVENT","CHAT","SESSION"},
                "procedures": {"PROCEDURE","TEMPLATE","RULE"},
            }
            if fact_type not in TYPE_TABLE.get(table, set()):
                # Определяем таблицу по типу
                for tbl, types in TYPE_TABLE.items():
                    if fact_type in types:
                        table = tbl
                        break
                else:
                    # Неизвестный тип → facts/FACT
                    table, fact_type = "facts", "FACT"

            # Шаг 2: проверка противоречий
            contradictions = check_contradiction(table, new_text, new_importance, conn)
            for old in contradictions:
                action = resolve_contradiction(table, old, new_importance)
                if action == "ТРЕБУЕТ_ПРОВЕРКИ_ДИРЕКТОРА":
                    # Не трогаем старый, новый пишем с флагом
                    log.warning(
                        "[INDEXER] противоречие с важность 5 id=%d — уведомление Директору",
                        old["id"]
                    )
                    _notify_director_contradiction(old, new_text)
                    new_status = "ТРЕБУЕТ_ПРОВЕРКИ"
                else:
                    update_status(table, old["id"], "ОТМЕНЕНО")
                    log.info("[INDEXER] старый факт id=%d → ОТМЕНЕНО", old["id"])
                    new_status = "АКТУАЛЬНО"

            if not contradictions:
                new_status = "АКТУАЛЬНО"

            # Шаг 3: векторизация
            embedding = vectorize(new_text)
            status = new_status if embedding else "ОЖИДАЕТ_ВЕКТОРИЗАЦИИ" if new_status == "АКТУАЛЬНО" else new_status

            # Шаг 4: запись
            record = {
                "text": new_text,
                "type": fact_type,
                "status": status,
                "importance": new_importance,
                "source": path,
                "source_path": path,
                "created_at": datetime.utcnow().isoformat(),
            }
            if embedding:
                record["embedding"] = embedding

            insert_record(table, record)
            count += 1

    log.info("[INDEXER] записано %d фактов из %s", count, path)
    return count


def vectorize_pending() -> int:
    """Векторизация отложенных записей (модель в памяти)."""
    import numpy as np
    model = _get_e5_model()
    if model is None:
        log.warning("[EMBED] e5-base недоступна")
        return 0
    count = 0
    with get_conn() as conn:
        for table in ("facts", "episodes", "procedures"):
            rows = conn.execute(
                f"SELECT id, text FROM {table} WHERE status='ОЖИДАЕТ_ВЕКТОРИЗАЦИИ' LIMIT 100"
            ).fetchall()
            for row in rows:
                vec = model.encode(row["text"], normalize_embeddings=True)
                embedding = vec.astype(np.float32).tobytes()
                conn.execute(
                    f"UPDATE {table} SET embedding=?, status='АКТУАЛЬНО' WHERE id=?",
                    (embedding, row["id"])
                )
                count += 1
        conn.commit()

    log.info("[EMBED] векторизовано %d записей", count)
    return count


def _notify_director_contradiction(old: dict, new_text: str) -> None:
    """Уведомление Директора о противоречии с решением важность 5."""
    try:
        import urllib.request
        token = os.environ.get("TELEGRAM_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return
        msg = (
            f"⚠️ NEVA ПАМЯТЬ: противоречие с решением Директора\n"
            f"Старый факт (важность 5): {old['text'][:200]}\n"
            f"Новый факт: {new_text[:200]}\n"
            f"Действие: новый записан как ТРЕБУЕТ_ПРОВЕРКИ"
        )
        payload = json.dumps({"chat_id": chat_id, "text": msg}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.warning("[NOTIFY] Телеграм недоступен: %s", e)


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Переиндексировать всю NEVA")
    parser.add_argument("--file", help="Индексировать один файл")
    parser.add_argument("--pending", action="store_true", help="Векторизовать отложенные")
    args = parser.parse_args()

    from .db import init_db
    init_db()

    if args.pending:
        n = vectorize_pending()
        print(f"Векторизовано: {n}")

    elif args.file:
        text = Path(args.file).read_text(encoding="utf-8")
        n = index_document(args.file, text)
        print(f"Записано фактов: {n}")

    elif args.full:
        root = Path(__file__).parent.parent.parent
        extensions = {".md", ".txt"}
        skip = {"sandbox", ".git", "node_modules", "__pycache__"}
        total = 0
        for p in root.rglob("*"):
            if any(s in p.parts for s in skip):
                continue
            if p.suffix in extensions and p.is_file():
                text = p.read_text(encoding="utf-8", errors="ignore")
                total += index_document(str(p.relative_to(root)), text)
        print(f"Итого записано: {total}")
