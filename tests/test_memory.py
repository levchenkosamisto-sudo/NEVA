"""
Тесты NEVA ПАМЯТЬ v3
tests/test_memory.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import tempfile
from pathlib import Path

# Переключаем на тестовую БД
os.environ["NEVA_TEST"] = "1"


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Каждый тест получает чистую БД."""
    db_path = tmp_path / "test_memory.db"
    monkeypatch.setattr("src.memory.db.DB_PATH", db_path)
    from src.memory.db import init_db
    init_db()
    yield db_path


def test_init_db_creates_tables(test_db):
    from src.memory.db import get_conn
    with get_conn() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
    assert "facts" in names
    assert "episodes" in names
    assert "procedures" in names
    assert "search_log" in names


def test_insert_and_read_fact(test_db):
    from src.memory.db import insert_record, get_conn
    rid = insert_record("facts", {
        "text": "Серж утвердил архитектуру NEVA v3",
        "type": "DECISION",
        "status": "АКТУАЛЬНО",
        "importance": 5,
        "source": "governance/decisions/DECISION-001.md",
        "source_path": "governance/decisions/DECISION-001.md",
        "created_at": "2026-06-28T10:00:00",
    })
    assert rid > 0
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM facts WHERE id=?", (rid,)).fetchone()
    assert row["text"] == "Серж утвердил архитектуру NEVA v3"
    assert row["importance"] == 5
    assert row["status"] == "АКТУАЛЬНО"


def test_status_update(test_db):
    from src.memory.db import insert_record, update_status, get_conn
    rid = insert_record("facts", {
        "text": "Старое решение",
        "type": "FACT",
        "status": "АКТУАЛЬНО",
        "importance": 3,
        "source": "test",
        "source_path": "test",
        "created_at": "2026-06-28T10:00:00",
    })
    update_status("facts", rid, "ОТМЕНЕНО")
    with get_conn() as conn:
        row = conn.execute("SELECT status FROM facts WHERE id=?", (rid,)).fetchone()
    assert row["status"] == "ОТМЕНЕНО"


def test_importance_from_path():
    from src.memory.indexer import importance_from_path
    assert importance_from_path("governance/decisions/DECISION-001.md") == 5
    assert importance_from_path("governance/architecture/arch.md") == 4
    assert importance_from_path("state/NEVA_SESSION_BRIEF.md") == 4
    assert importance_from_path("state/tasks/TASK-007.md") == 3
    assert importance_from_path("audit/responses/round1.md") == 2
    assert importance_from_path("memory/raw/chats/chat.md") == 1
    assert importance_from_path("src/core/neva_auth.py") == 2  # default


def test_stale_marking(test_db):
    from src.memory.db import insert_record, get_conn
    from src.memory.dedup import _mark_stale

    # Вставляем старый факт (не решение Директора)
    insert_record("facts", {
        "text": "Старый факт",
        "type": "FACT",
        "status": "АКТУАЛЬНО",
        "importance": 2,
        "source": "test",
        "source_path": "test",
        "created_at": "2025-01-01T00:00:00",  # > 180 дней
    })
    # Вставляем решение Директора (не должно устаревать)
    insert_record("facts", {
        "text": "Решение Директора",
        "type": "DECISION",
        "status": "АКТУАЛЬНО",
        "importance": 5,
        "source": "governance/decisions",
        "source_path": "governance/decisions/DECISION-001.md",
        "created_at": "2025-01-01T00:00:00",
    })

    _mark_stale()

    with get_conn() as conn:
        old = conn.execute(
            "SELECT status FROM facts WHERE text='Старый факт'"
        ).fetchone()
        director = conn.execute(
            "SELECT status FROM facts WHERE text='Решение Директора'"
        ).fetchone()

    assert old["status"] == "УСТАРЕЛО"
    assert director["status"] == "АКТУАЛЬНО"  # не тронуто


def test_search_level1(test_db):
    """INSERT и SELECT в одном соединении через тест-БД."""
    import sqlite3
    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    conn.execute("""INSERT INTO facts (text, type, status, importance, source, source_path, created_at)
        VALUES (?,?,?,?,?,?,?)""",
        ("Архитектура памяти NEVA основана на SQLite",
         "ARCHITECTURE","АКТУАЛЬНО",5,
         "governance/decisions","governance/decisions/DECISION-001.md",
         "2026-06-28T10:00:00"))
    conn.commit()
    rows = conn.execute(
        "SELECT * FROM facts WHERE importance>=4 AND text LIKE ? AND status=?",
        ("%памяти%", "АКТУАЛЬНО")
    ).fetchall()
    conn.close()
    assert len(rows) > 0, f"Факт не найден в {test_db}"
    assert "SQLite" in rows[0]["text"]


def test_search_log(test_db):
    import sqlite3
    from src.memory.db import log_search
    import src.memory.db as db_module

    # Используем тест-БД напрямую
    db_module.DB_PATH = test_db
    log_search({
        "asked_by": "pytest",
        "query": "тест запрос",
        "level_found": 1,
        "result_text": "result",
        "source": "test",
        "importance": 3,
        "status": "АКТУАЛЬНО",
        "duration_ms": 10,
        "created_at": "2026-06-28T10:00:00",
    })
    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    logs = conn.execute("SELECT * FROM search_log").fetchall()
    conn.close()
    assert len(logs) == 1
    assert logs[0]["asked_by"] == "pytest"
