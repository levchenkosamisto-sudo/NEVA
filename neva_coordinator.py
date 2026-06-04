import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

class TopicCoordinator:
    def __init__(self, db_path="test_locks.db"):
        self.db_path = db_path
        self._init_db()
    
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    
    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topic_locks (
                    topic TEXT PRIMARY KEY,
                    locked_by TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    locked_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            conn.commit()
    
    async def acquire(self, topic, locked_by, session_id, ttl=30):
        with self._get_conn() as conn:
            conn.execute("BEGIN EXCLUSIVE")
            now = datetime.utcnow()
            expires = now + timedelta(seconds=ttl)
            conn.execute("DELETE FROM topic_locks WHERE expires_at < ?", (now.isoformat(),))
            try:
                conn.execute(
                    "INSERT INTO topic_locks VALUES (?, ?, ?, ?, ?)",
                    (topic, locked_by, session_id, now.isoformat(), expires.isoformat())
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                conn.rollback()
                return False
    
    async def release(self, topic):
        with self._get_conn() as conn:
            result = conn.execute("DELETE FROM topic_locks WHERE topic = ?", (topic,))
            conn.commit()
            return result.rowcount > 0

print("✅ neva_coordinator.py created")
