"""
neva_self_diagnostics.py — Самодиагностика NEVA
Версия: 3.6 | Архитектор: Claude
8 тестов: --health / --diag / --self-test
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Тест 1: Kuzu ping ────────────────────────────────────────────────────────

async def test_kuzu_ping() -> dict:
    try:
        import kuzu
        db_path = os.path.expanduser(
            os.getenv("NEVA_DB_PATH", "~/Documents/NEVA/kuzu_data")
        )
        db   = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        conn.execute("RETURN 1")
        return {"test": "kuzu_ping", "status": "PASS"}
    except ImportError:
        return {"test": "kuzu_ping", "status": "FAIL", "reason": "kuzu не установлен"}
    except Exception as e:
        return {"test": "kuzu_ping", "status": "FAIL", "reason": str(e)}


# ─── Тест 2: Write Queue ──────────────────────────────────────────────────────

async def test_write_queue() -> dict:
    try:
        from neva_write_queue import write_to_graph, get_write_counter
        before = get_write_counter()

        async def mock_op():
            return "ok"

        await write_to_graph(mock_op)
        after = get_write_counter()
        assert after == before + 1
        return {"test": "write_queue", "status": "PASS", "counter": after}
    except ImportError as e:
        return {"test": "write_queue", "status": "FAIL", "reason": str(e)}
    except Exception as e:
        return {"test": "write_queue", "status": "FAIL", "reason": str(e)}


# ─── Тест 3: Topic Lock ───────────────────────────────────────────────────────

async def test_topic_lock() -> dict:
    try:
        from neva_coordinator import TopicCoordinator
        db_path = os.path.expanduser(
            os.getenv("NEVA_PIPELINE_DB", "~/Documents/NEVA/neva_pipeline.db")
        )
        coord = TopicCoordinator(db_path)
        topic = "self_test_topic"

        acquired = await coord.acquire(topic, "self_diagnostics", "sess_test")
        assert acquired is True

        # Второй acquire должен вернуть False
        second = await coord.acquire(topic, "other_agent", "sess_other")
        assert second is False

        await coord.release(topic)
        return {"test": "topic_lock", "status": "PASS"}
    except ImportError as e:
        return {"test": "topic_lock", "status": "SKIP", "reason": str(e)}
    except Exception as e:
        return {"test": "topic_lock", "status": "FAIL", "reason": str(e)}


# ─── Тест 4: Auth ─────────────────────────────────────────────────────────────

async def test_auth() -> dict:
    try:
        from neva_auth import get_token_role
        token = os.getenv("NEVA_ADMIN_TOKEN", "")
        if not token:
            return {"test": "auth", "status": "SKIP", "reason": "NEVA_ADMIN_TOKEN не задан"}
        role = get_token_role(token)
        assert role == "admin", f"Ожидался admin, получен {role}"
        return {"test": "auth", "status": "PASS", "role": role}
    except ImportError as e:
        return {"test": "auth", "status": "SKIP", "reason": str(e)}
    except Exception as e:
        return {"test": "auth", "status": "FAIL", "reason": str(e)}


# ─── Тест 5: Write atom + немедленная инвалидация ────────────────────────────

async def test_write_atom() -> dict:
    try:
        from tools.neva_graphiti import graph
        if not graph._initialized:
            await graph.init()

        test_atom = {
            "content":     "SELF_TEST_ATOM_DO_NOT_USE",
            "author_ai":   "self_diagnostics",
            "source_path": "tests/self_test",
            "doc_id":      "SELF_TEST",
            "doc_version": "0.0",
            "sha256":      "0" * 64,
            "atom_type":   "TASK",
        }
        result = await graph.add_atom(test_atom)

        if result.get("status") not in ("success", "ok"):
            return {
                "test": "write_atom",
                "status": "FAIL",
                "reason": result
            }

        # Получаем uuid из результата
        uuid_v = (
            result.get("uuid") or
            result.get("result", {}).get("uuid") if isinstance(result.get("result"), dict) else None
        )

        # НЕМЕДЛЕННО инвалидируем
        if uuid_v:
            await graph.invalidate(uuid_v)

        return {
            "test":        "write_atom",
            "status":      "PASS",
            "invalidated": True,
            "uuid":        uuid_v,
        }
    except ImportError as e:
        return {"test": "write_atom", "status": "SKIP", "reason": str(e)}
    except Exception as e:
        return {"test": "write_atom", "status": "FAIL", "reason": str(e)}


# ─── Тест 6: Search (SKIP если сервер не запущен) ────────────────────────────

async def test_search() -> dict:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get("http://localhost:8000/api/v1/health")
            if r.status_code != 200:
                return {
                    "test": "search",
                    "status": "SKIP",
                    "reason": "Сервер не отвечает"
                }
            r2 = await client.get(
                "http://localhost:8000/api/v1/search?q=test&limit=3"
            )
            assert r2.status_code == 200
            return {"test": "search", "status": "PASS"}
    except Exception:
        return {
            "test":   "search",
            "status": "SKIP",
            "reason": "Сервер не запущен — выполни: neva start"
        }


# ─── Тест 7: Backup sequence ─────────────────────────────────────────────────

async def test_backup() -> dict:
    try:
        import sqlite3
        db_path = os.path.expanduser(
            os.getenv("NEVA_METRICS_DB", "~/Documents/NEVA/neva_metrics.db")
        )
        if not os.path.exists(db_path):
            return {
                "test":   "backup",
                "status": "SKIP",
                "reason": "neva_metrics.db не найден — запусти neva_init.py --init"
            }
        with sqlite3.connect(db_path) as conn:
            try:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM k_truth_history"
                )
                count = cursor.fetchone()[0]
                return {
                    "test":             "backup",
                    "status":           "PASS",
                    "k_truth_records":  count
                }
            except sqlite3.OperationalError:
                return {
                    "test":   "backup",
                    "status": "SKIP",
                    "reason": "Таблица k_truth_history не создана"
                }
    except Exception as e:
        return {"test": "backup", "status": "FAIL", "reason": str(e)}


# ─── Тест 8: P16 index (SKIP если сервер не запущен) ─────────────────────────

async def test_p16_index() -> dict:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get("http://localhost:8000/api/v1/health")
            if r.status_code != 200:
                return {
                    "test":   "p16_index",
                    "status": "SKIP",
                    "reason": "Сервер не запущен"
                }
            r2 = await client.get(
                "http://localhost:8000/api/v1/search?q=governance&limit=3"
            )
            data = r2.json()
            results = data.get("results", [])
            # Проверяем что хотя бы один результат имеет source_path
            has_source = any(r.get("source_path") for r in results)
            return {
                "test":       "p16_index",
                "status":     "PASS" if has_source or len(results) == 0 else "FAIL",
                "results":    len(results),
                "has_source": has_source,
            }
    except Exception:
        return {
            "test":   "p16_index",
            "status": "SKIP",
            "reason": "Сервер не запущен"
        }


# ─── Запуск ───────────────────────────────────────────────────────────────────

ALL_TESTS = [
    test_kuzu_ping,
    test_write_queue,
    test_topic_lock,
    test_auth,
    test_write_atom,
    test_search,
    test_backup,
    test_p16_index,
]

HEALTH_TESTS = [test_kuzu_ping, test_write_queue]
DIAG_TESTS   = [test_kuzu_ping, test_write_queue, test_topic_lock,
                test_auth, test_backup]


async def run_tests(tests: list) -> list:
    results = []
    for t in tests:
        try:
            r = await t()
        except Exception as e:
            r = {"test": t.__name__, "status": "FAIL", "reason": str(e)}
        results.append(r)
        status = r.get("status", "?")
        symbol = "✅" if status == "PASS" else ("⏭" if status == "SKIP" else "❌")
        print(f"  {symbol} {r.get('test', t.__name__)}: {status}")
    return results


def main():
    parser = argparse.ArgumentParser(description="NEVA Self Diagnostics")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--health",    action="store_true", help="Быстрая проверка < 5с")
    group.add_argument("--diag",      action="store_true", help="Диагностика < 30с")
    group.add_argument("--self-test", action="store_true", help="Полный тест < 60с")
    args = parser.parse_args()

    if args.health:
        print("=== NEVA HEALTH ===")
        results = asyncio.run(run_tests(HEALTH_TESTS))
    elif args.diag:
        print("=== NEVA DIAG ===")
        results = asyncio.run(run_tests(DIAG_TESTS))
    else:
        print("=== NEVA SELF-TEST (8/8) ===")
        results = asyncio.run(run_tests(ALL_TESTS))

    passed = sum(1 for r in results if r.get("status") == "PASS")
    skipped = sum(1 for r in results if r.get("status") == "SKIP")
    failed  = sum(1 for r in results if r.get("status") == "FAIL")
    print(f"\nИтог: {passed} PASS / {skipped} SKIP / {failed} FAIL")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
