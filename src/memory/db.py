"""
NEVA ПАМЯТЬ v3 — менеджер базы данных
src/memory/db.py
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "memory" / "neva_memory.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

TABLES = ("facts", "episodes", "procedures")


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Инициализация схемы при первом запуске."""
    with get_conn() as conn:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(sql)
    print(f"[DB] Инициализирована: {DB_PATH}")


def insert_record(table: str, data: dict) -> int:
    """Вставить запись в таблицу. Возвращает id."""
    assert table in TABLES, f"Неизвестная таблица: {table}"
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    with get_conn() as conn:
        cur = conn.execute(sql, list(data.values()))
        return cur.lastrowid


def update_status(table: str, record_id: int, status: str) -> None:
    """Обновить статус записи."""
    assert table in TABLES
    with get_conn() as conn:
        conn.execute(
            f"UPDATE {table} SET status=? WHERE id=?",
            (status, record_id)
        )


def find_contradictions(table: str, text: str, conn: sqlite3.Connection) -> list:
    """
    Поиск противоречащих записей через FTS.
    Возвращает список записей кандидатов.
    """
    fts_table = f"{table}_fts"
    # Берём ключевые слова (первые 5)
    keywords = " ".join(text.split()[:5])
    try:
        rows = conn.execute(
            f"SELECT {table}.* FROM {fts_table} "
            f"JOIN {table} ON {table}.id = {fts_table}.rowid "
            f"WHERE {fts_table} MATCH ? AND {table}.status='АКТУАЛЬНО' "
            f"LIMIT 10",
            (keywords,)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def log_search(data: dict) -> None:
    """Записать поисковый запрос в лог."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO search_log ({cols}) VALUES ({placeholders})",
            list(data.values())
        )


if __name__ == "__main__":
    init_db()
