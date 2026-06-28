"""
NEVA ПАМЯТЬ v3 — Ночной процесс дедупликации
src/memory/dedup.py

Запуск: launchd 03:00
Алгоритм:
  1. Косинусное сходство векторов ≥ 0.92 → кандидаты
  2. Церебрас/Грок проверяет смысл пары
  3. Объединяет → старые ОБЪЕДИНЕНО
  4. Устаревание: 90д → ТРЕБУЕТ_ПРОВЕРКИ, 180д → УСТАРЕЛО
"""
import logging
import json
from datetime import datetime, timedelta

from .db import get_conn, update_status
from .ram_manager import ensure_e5_available, qwen_is_active
from .indexer import call_ai

log = logging.getLogger("neva.dedup")

SIMILARITY_THRESHOLD = 0.92
STALE_CHECK_DAYS = 90
STALE_OBSOLETE_DAYS = 180


def run_dedup() -> dict:
    """Основная точка входа ночного процесса."""
    if qwen_is_active():
        log.info("[DEDUP] qwen активна — откладываем на 30 минут")
        return {"status": "postponed", "reason": "qwen_active"}

    ok = ensure_e5_available()
    if not ok:
        log.warning("[DEDUP] e5 недоступна — пропускаем векторную дедупликацию")
        merged = 0
    else:
        merged = _dedup_by_vector()

    stale_count = _mark_stale()

    log.info("[DEDUP] завершено: объединено=%d устарело=%d", merged, stale_count)
    return {"status": "ok", "merged": merged, "stale_marked": stale_count}


def _dedup_by_vector() -> int:
    """Поиск и объединение дублей через векторное сходство + ИИ-верификация."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer("intfloat/multilingual-e5-base")
    except ImportError:
        log.warning("[DEDUP] sentence-transformers не установлен")
        return 0

    total_merged = 0

    with get_conn() as conn:
        for table in ("facts", "episodes", "procedures"):
            rows = conn.execute(
                f"SELECT id, text, embedding, importance FROM {table} "
                f"WHERE embedding IS NOT NULL AND status='АКТУАЛЬНО' "
                f"ORDER BY importance DESC"
            ).fetchall()

            if len(rows) < 2:
                continue

            import numpy as np
            ids = [r["id"] for r in rows]
            texts = [r["text"] for r in rows]
            importances = [r["importance"] for r in rows]
            vecs = [
                np.frombuffer(r["embedding"], dtype=np.float32)
                for r in rows
            ]

            merged_ids = set()
            for i in range(len(vecs)):
                if ids[i] in merged_ids:
                    continue
                for j in range(i + 1, len(vecs)):
                    if ids[j] in merged_ids:
                        continue
                    score = float(np.dot(vecs[i], vecs[j]))
                    if score < SIMILARITY_THRESHOLD:
                        continue

                    # ИИ-верификация
                    if not _ai_confirm_duplicate(texts[i], texts[j]):
                        continue

                    # Объединяем: сохраняем с большей важностью
                    if importances[j] >= importances[i]:
                        # оставляем j, объединяем i
                        update_status(table, ids[i], "ОБЪЕДИНЕНО")
                        conn.execute(
                            f"UPDATE {table} SET merged_into=? WHERE id=?",
                            (ids[j], ids[i])
                        )
                        merged_ids.add(ids[i])
                    else:
                        update_status(table, ids[j], "ОБЪЕДИНЕНО")
                        conn.execute(
                            f"UPDATE {table} SET merged_into=? WHERE id=?",
                            (ids[i], ids[j])
                        )
                        merged_ids.add(ids[j])

                    total_merged += 1
                    log.info(
                        "[DEDUP] объединены id=%d и id=%d (score=%.3f)",
                        ids[i], ids[j], score
                    )

        conn.commit()

    return total_merged


def _ai_confirm_duplicate(text1: str, text2: str) -> bool:
    """Церебрас/Грок проверяет: это одно и то же?"""
    prompt = f"""Эти два утверждения описывают одно и то же?
Отвечай только: ДА или НЕТ

Утверждение 1: {text1[:300]}
Утверждение 2: {text2[:300]}"""

    answer = call_ai(prompt)
    if not answer:
        # Если ИИ недоступен — не объединяем (безопасный выбор)
        return False
    return "ДА" in answer.upper()


def _mark_stale() -> int:
    """Отмечаем устаревшие записи (90д → ТРЕБУЕТ_ПРОВЕРКИ, 180д → УСТАРЕЛО)."""
    count = 0
    now = datetime.utcnow()
    threshold_check = (now - timedelta(days=STALE_CHECK_DAYS)).isoformat()
    threshold_obsolete = (now - timedelta(days=STALE_OBSOLETE_DAYS)).isoformat()

    with get_conn() as conn:
        for table in ("facts", "episodes", "procedures"):
            # Исключаем решения Директора (importance=5) из автоустаревания
            conn.execute(
                f"UPDATE {table} SET status='УСТАРЕЛО' "
                f"WHERE status='АКТУАЛЬНО' AND importance < 5 "
                f"AND created_at < ?",
                (threshold_obsolete,)
            )
            conn.execute(
                f"UPDATE {table} SET status='ТРЕБУЕТ_ПРОВЕРКИ' "
                f"WHERE status='АКТУАЛЬНО' AND importance < 5 "
                f"AND created_at < ? AND created_at >= ?",
                (threshold_check, threshold_obsolete)
            )
            # Считаем затронутые
            n = conn.execute(
                f"SELECT changes()"
            ).fetchone()[0]
            count += n
        conn.commit()

    return count


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    from .db import init_db
    init_db()
    result = run_dedup()
    print(json.dumps(result, ensure_ascii=False, indent=2))
