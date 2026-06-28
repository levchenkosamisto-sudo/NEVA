def test_search_level1(test_db):
    from src.memory.db import insert_record, get_conn

    insert_record("facts", {
        "text": "Архитектура памяти NEVA основана на SQLite",
        "type": "ARCHITECTURE",
        "status": "АКТУАЛЬНО",
        "importance": 5,
        "source": "governance/decisions",
        "source_path": "governance/decisions/DECISION-001.md",
        "created_at": "2026-06-28T10:00:00",
    })

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM facts WHERE importance>=4 AND text LIKE ? AND status='АКТУАЛЬНО'",
            ("%архитектура%",)
        ).fetchall()
    assert len(rows) > 0
    assert "SQLite" in rows[0]["text"]


def test_search_log(test_db, monkeypatch):
    import src.memory.search as search_module
    from src.memory.db import get_conn
    monkeypatch.setattr(search_module, "_compress", lambda q, r: "test result")
    search_module.search("тест запрос", asked_by="pytest")
    with get_conn() as conn:
        logs = conn.execute("SELECT * FROM search_log").fetchall()
    assert len(logs) == 1
    assert logs[0]["asked_by"] == "pytest"
    assert logs[0]["query"] == "тест запрос"
