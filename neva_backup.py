import json
import random
import sqlite3
from datetime import datetime
from pathlib import Path

class BackupManager:
    def __init__(self):
        self.backup_dir = Path.home() / ".neva" / "backups" / "jsonl"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_db = Path.home() / ".neva" / "neva_metrics.db"
        self.metrics_db.parent.mkdir(exist_ok=True)
    
    async def run_jsonl_backup(self, atoms):
        seq = len(list(self.backup_dir.glob("backup_*.jsonl"))) + 1
        backup_file = self.backup_dir / f"backup_{seq:06d}.jsonl"
        with open(backup_file, 'w') as f:
            for atom in atoms:
                f.write(json.dumps(atom, ensure_ascii=False) + '\n')
        return {"sequence": seq, "path": str(backup_file), "status": "success"}
    
    async def test_restore(self, num_samples=5):
        backups = sorted(self.backup_dir.glob("backup_*.jsonl"))
        if not backups:
            return {"status": "failed", "error": "No backups"}
        latest = backups[-1]
        atoms = []
        with open(latest) as f:
            for line in f:
                if line.strip():
                    atoms.append(json.loads(line))
        samples = random.sample(atoms, min(num_samples, len(atoms)))
        valid = sum(1 for a in samples if a.get("content") and a.get("author_ai"))
        return {"status": "success" if valid == len(samples) else "partial", "successful": valid, "total_tested": len(samples)}
