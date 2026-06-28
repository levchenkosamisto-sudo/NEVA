"""
NEVA ПАМЯТЬ v3 — Поисковик
src/memory/search.py

Конвейер (6 уровней):
  1. Решения/факты важность 4-5 (точный SQL)
  2. Полнотекстовый поиск FTS5
  3. Граф Kuzu (если доступен)
  4. Смысловой поиск (векторный, e5-base)
  5. Извлечённое из чатов (важность 2-3)
  6. Сырые чаты (крайний случай)
→ Реранжирование по иерархии доверия
→ context_package: Церебрас сжимает топ-3 в ≤500 слов
"""
import json
import os
import logging
import time
from datetime import datetime

from .db import get_conn, log_search
from .ram_manager import qwen_is_active, ensure_e5_available

log = logging.getLogger("neva.search")

MAX_WORDS = 500


def search(query: str, asked_by: str = "unknown", include_obsolete: bool = False) -> dict:
    """
    Основная точка входа поиска.
    Возвращает: {context_package, level_found, sources}
    """
    t0 = time.time()
    results = []
    level_found = None

    # Уровень 1: решения и факты важность 4-5
    r = _search_level1(query, include_obsolete)
    if r:
        results = r
        level_found = 1

    # Уровень 2: полнотекстовый поиск
    if not results:
        r = _search_level2(query, include_obsolete)
        if r:
            results = r
            level_found = 2

    # Уровень 3: граф Kuzu
    if not results:
        r = _search_level3(query)
        if r:
            results = r
            level_found = 3

    # Уровень 4: векторный поиск
    if not results:
        r = _search_level4(query)
        if r:
            results = r
            level_found = 4

    # Уровень 5: извлечённое из чатов
    if not results:
        r = _search_level5(query)
        if r:
            results = r
            level_found = 5

    # Уровень 6: сырые чаты (крайний случай)
    if not results:
        r = _search_level6(query)
        if r:
            results = r
            level_found = 6

    # Реранжирование по иерархии доверия
    results = _rerank(results)

    # Сжатие в context_package
    context_package = _compress(query, results)

    duration_ms = int((time.time() - t0) * 1000)

    # Лог запроса
    top = results[0] if results else {}
    log_search({
        "asked_by": asked_by,
        "query": query,
        "level_found": level_found,
        "result_text": top.get("text", "")[:500] if top else None,
        "source": top.get("source", "") if top else None,
        "importance": top.get("importance") if top else None,
        "status": top.get("status", "") if top else None,
        "duration_ms": duration_ms,
        "created_at": datetime.utcnow().isoformat(),
    })

    return {
        "context_package": context_package,
        "level_found": level_found,
        "results_count": len(results),
        "duration_ms": duration_ms,
        "sources": [r.get("source", "") for r in results[:3]],
    }


def _search_level1(query: str, include_obsolete: bool) -> list:
    """Точный SQL: решения и факты важность 4-5."""
    status_filter = "" if include_obsolete else "AND status='АКТУАЛЬНО'"
    kw = f"%{query}%"
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT *, 'facts' as _table FROM facts "
            f"WHERE importance>=4 AND text LIKE ? {status_filter} "
            f"ORDER BY importance DESC LIMIT 5",
            (kw,)
        ).fetchall()
    return [dict(r) for r in rows]


def _search_level2(query: str, include_obsolete: bool) -> list:
    """Полнотекстовый поиск FTS5 по всем таблицам."""
    results = []
    status_filter = "" if include_obsolete else "AND t.status='АКТУАЛЬНО'"
    with get_conn() as conn:
        for table in ("facts", "episodes", "procedures"):
            try:
                rows = conn.execute(
                    f"SELECT t.*, '{table}' as _table FROM {table}_fts f "
                    f"JOIN {table} t ON t.id=f.rowid "
                    f"WHERE {table}_fts MATCH ? {status_filter} "
                    f"ORDER BY t.importance DESC LIMIT 5",
                    (query,)
                ).fetchall()
                results.extend([dict(r) for r in rows])
            except Exception as e:
                log.debug("[FTS] %s: %s", table, e)
    return results[:10]


def _search_level3(query: str) -> list:
    """Поиск по графу Kuzu (если доступен)."""
    try:
        import kuzu
        db_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "kuzu_data"
        )
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        result = conn.execute(
            "MATCH (n) WHERE n.text CONTAINS $q RETURN n LIMIT 5",
            {"q": query}
        )
        rows = []
        while result.has_next():
            r = result.get_next()
            if r:
                rows.append({"text": str(r[0]), "source": "kuzu_graph", "importance": 3, "status": "АКТУАЛЬНО"})
        return rows
    except Exception:
        return []


def _search_level4(query: str) -> list:
    """Векторный поиск e5-base. Только когда qwen не активна."""
    if qwen_is_active():
        return []

    ok = ensure_e5_available()
    if not ok:
        return []

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer("intfloat/multilingual-e5-base")
        q_vec = model.encode(query, normalize_embeddings=True).astype(np.float32)

        results = []
        with get_conn() as conn:
            for table in ("facts", "episodes", "procedures"):
                rows = conn.execute(
                    f"SELECT id, text, source, importance, status, embedding FROM {table} "
                    f"WHERE embedding IS NOT NULL AND status='АКТУАЛЬНО' LIMIT 500"
                ).fetchall()
                for row in rows:
                    vec = np.frombuffer(row["embedding"], dtype=np.float32)
                    score = float(np.dot(q_vec, vec))
                    if score > 0.75:
                        d = dict(row)
                        d["_score"] = score
                        d["_table"] = table
                        results.append(d)

        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:5]
    except ImportError:
        log.warning("[EMBED] sentence-transformers не установлен")
        return []
    except Exception as e:
        log.error("[EMBED] ошибка поиска: %s", e)
        return []


def _search_level5(query: str) -> list:
    """Извлечённое из чатов (важность 2-3, тип CHAT)."""
    kw = f"%{query}%"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT *, 'episodes' as _table FROM episodes "
            "WHERE type='CHAT' AND importance BETWEEN 2 AND 3 "
            "AND text LIKE ? AND status='АКТУАЛЬНО' "
            "ORDER BY importance DESC LIMIT 5",
            (kw,)
        ).fetchall()
    return [dict(r) for r in rows]


def _search_level6(query: str) -> list:
    """Сырые чаты — крайний случай."""
    import glob
    raw_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "memory", "raw", "chats"
    )
    results = []
    kw = query.lower()
    for filepath in sorted(glob.glob(f"{raw_dir}/*.md"), reverse=True)[:20]:
        try:
            text = open(filepath, encoding="utf-8").read()
            if kw in text.lower():
                # Берём 300 символов вокруг совпадения
                idx = text.lower().find(kw)
                snippet = text[max(0, idx-100):idx+200]
                results.append({
                    "text": snippet,
                    "source": os.path.basename(filepath),
                    "importance": 1,
                    "status": "АКТУАЛЬНО",
                    "_table": "raw_chats"
                })
                if len(results) >= 3:
                    break
        except Exception:
            pass
    return results


# Иерархия доверия: источник → вес
TRUST_WEIGHTS = {
    "governance/decisions": 1.0,
    "governance/architecture": 0.9,
    "state/": 0.8,
    "audit/": 0.6,
    "kuzu_graph": 0.5,
    "episodes": 0.4,
    "raw_chats": 0.2,
}


def _rerank(results: list) -> list:
    """Реранжирование по иерархии доверия."""
    def trust_score(r):
        source = r.get("source", "") or ""
        for prefix, weight in TRUST_WEIGHTS.items():
            if prefix in source:
                return weight * r.get("importance", 1)
        return 0.3 * r.get("importance", 1)

    return sorted(results, key=trust_score, reverse=True)


def _compress(query: str, results: list) -> str:
    """
    Сжатие топ-3 результатов в ≤500 слов через Церебрас.
    Если ИИ недоступен — возвращаем топ-3 как есть с усечением.
    """
    if not results:
        return "Информация по запросу не найдена."

    top3 = results[:3]
    combined = "\n\n".join(
        f"[{i+1}] (важность {r.get('importance','?')}, источник: {r.get('source','?')})\n{r['text']}"
        for i, r in enumerate(top3)
    )

    prompt = f"""Сожми следующую информацию в ответ на запрос. Максимум 500 слов. Только факты.

Запрос: {query}

Информация:
{combined}

Ответ (не более 500 слов):"""

    try:
        from .indexer import call_ai
        result = call_ai(prompt)
        if result:
            return result.strip()
    except Exception as e:
        log.warning("[COMPRESS] ИИ недоступен: %s", e)

    # Fallback: усечение
    words = combined.split()
    return " ".join(words[:MAX_WORDS])
