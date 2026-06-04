import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

class MetricsCollector:
    def __init__(self):
        self.db_path = Path.home() / ".neva" / "neva_metrics.db"
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE IF NOT EXISTS k_truth_history (id INTEGER PRIMARY KEY, value REAL, author_ai TEXT, session_id TEXT, recorded_at TEXT)")
            conn.commit()
    
    def record_k_truth(self, value, author_ai, session_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO k_truth_history (value, author_ai, session_id, recorded_at) VALUES (?,?,?,?)",
                        (value, author_ai, session_id, datetime.utcnow().isoformat()))
            conn.commit()
    
    def get_k_truth_trend(self, hours=24):
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        with sqlite3.connect(self.db_path) as conn:
            c = conn.execute("SELECT value FROM k_truth_history WHERE recorded_at > ?", (cutoff.isoformat(),))
            values = [row[0] for row in c.fetchall()]
            if not values:
                return {"average": 0.0, "count": 0}
            return {"average": sum(values)/len(values), "count": len(values)}
