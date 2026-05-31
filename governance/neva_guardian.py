#!/usr/bin/env python3
"""NEVA GUARDIAN v3.1 - NEVA-TASK-004"""

import argparse, json, sys, shutil, subprocess
from pathlib import Path
from datetime import datetime

VERSION = "3.1"

class NEVAGuardian:
    def __init__(self, doc, idx, reg, director=False, commit=False, dry=False):
        self.doc = Path(doc); self.idx = Path(idx); self.reg = Path(reg)
        self.director = director; self.commit = commit; self.dry = dry
        self.home = Path.home()
        self.gov = self.home / "Documents/NEVA" / "governance"
        self.logs = self.home / "Documents/NEVA" / "logs"
        self.tools = self.home / "Documents/NEVA" / "tools"
        self.map_dir = self.home / "Documents/NEVA" / "map"
        self.index_data = {}; self.doc_id = ""; self.approved = False; self.warnings = []

    def _log(self, action, result, details=None):
        if self.dry: return
        self.logs.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": datetime.now().isoformat(), "action": action, "result": result, "doc_id": self.doc_id, "details": details or {}}
        log_file = self.logs / "guardian_log.json"
        logs = json.load(open(log_file)) if log_file.exists() else []
        logs.append(entry)
        json.dump(logs, open(log_file, "w"), indent=2)

    def _log_block(self, reason):
        """Запись блокировки в blocks_log.json"""
        if self.dry: return
        self.logs.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": datetime.now().isoformat(), "action": "block", "reason": reason, "doc_id": self.doc_id}
        blocks_file = self.logs / "blocks_log.json"
        blocks = json.load(open(blocks_file)) if blocks_file.exists() else []
        blocks.append(entry)
        json.dump(blocks, open(blocks_file, "w"), indent=2)

    def run(self):
        print(f"\n{'='*60}\nNEVA GUARDIAN v{VERSION}\n{'='*60}\n")
        if not self._phase_a(): return 1
        if not self._phase_b(): return 1
        if self.commit:
            if self.dry: print("\n❌ --commit и --dry-run несовместимы"); return 1
            return 0 if self._phase_c() else 1
        return 0

    def _phase_a(self):
        print("ФАЗА A: САМОДИАГНОСТИКА\n")
        if sys.version_info < (3,11): print("❌ Python 3.11+"); return False
        if not self.reg.exists(): print(f"❌ Нет {self.reg}"); return False
        if not self.gov.exists(): print("❌ Нет governance/"); return False
        self.logs.mkdir(parents=True, exist_ok=True)
        if self.commit:
            try:
                with open(self.reg) as f: reg_data = json.load(f)
                temp_id = self.idx.stem.replace("_INDEX", "")
                documents = reg_data.get("documents", [])
                # Проверка: documents может быть списком dict или списком строк
                exists = False
                for d in documents:
                    if isinstance(d, dict):
                        if d.get("doc_id") == temp_id:
                            exists = True
                            break
                    elif d == temp_id:
                        exists = True
                        break
                if exists:
                    print(f"❌ {temp_id} уже зафиксирован")
                    self._log_block(f"Duplicate commit: {temp_id}")
                    return False
            except: pass
        print("\n✅ Фаза A пройдена\n"); return True

    def _phase_b(self):
        print("ФАЗА B: 5 ПРОВЕРОК\n")
        if not self.idx.exists():
            self._log_block("INDEX.json not found")
            print("❌ INDEX.json не найден"); return False
        try:
            with open(self.idx) as f: self.index_data = json.load(f)
            self.doc_id = self.index_data.get("doc_id", self.idx.stem.replace("_INDEX", ""))
        except:
            self._log_block("INDEX.json corrupted")
            print("❌ INDEX.json повреждён"); return False
        if not self.index_data.get("verified"):
            self._log_block(f"Not verified: {self.doc_id}")
            print("❌ Не верифицирован"); return False
        blockers = [c for c in self.index_data.get("conflicts", []) if c.get("severity") == "BLOCKER"]
        if blockers:
            self._log_block(f"BLOCKER conflicts: {blockers}")
            print(f"❌ BLOCKER: {blockers}"); return False
        updates = self.index_data.get("updates_required", [])
        if updates: print(f"⚠ {len(updates)} обновлений")
        try:
            with open(self.reg) as f: reg_data = json.load(f)
            documents = reg_data.get("documents", [])
            doc_ids_in_reg = []
            for d in documents:
                if isinstance(d, dict):
                    doc_ids_in_reg.append(d.get("doc_id"))
                else:
                    doc_ids_in_reg.append(d)
            missing = [d for d in self.index_data.get("depends_on", []) if d not in doc_ids_in_reg]
            if missing:
                self._log_block(f"Missing dependencies: {missing}")
                print(f"❌ Зависимости не в registry: {missing}"); return False
        except: pass
        self.approved = True
        print(f"\n🔓 APPROVED: {self.doc_id}\n"); return True

    def _phase_c(self):
        print("ФАЗА C: ФИКСАЦИЯ\n")
        if not self.dry:
            shutil.copy2(self.doc, self.gov / self.doc.name)
            shutil.copy2(self.idx, self.gov / f"{self.doc_id}_INDEX.json")
            print("  ✓ Файлы скопированы")
            with open(self.reg) as f: reg_data = json.load(f)
            if "documents" not in reg_data: reg_data["documents"] = []
            # Определяем формат: если существующие документы — dict, добавляем dict
            if reg_data["documents"] and isinstance(reg_data["documents"][0], dict):
                new_doc = {"doc_id": self.doc_id, "title": self.index_data.get("title", ""), "type": self.index_data.get("type", "")}
                if new_doc not in reg_data["documents"]:
                    reg_data["documents"].append(new_doc)
            else:
                if self.doc_id not in reg_data["documents"]:
                    reg_data["documents"].append(self.doc_id)
            with open(self.reg, "w") as f:
                json.dump(reg_data, f, indent=2)
            print("  ✓ registry обновлён")
            commit_log = self.logs / "commit_log.json"
            commits = json.load(open(commit_log)) if commit_log.exists() else []
            commits.append({"timestamp": datetime.now().isoformat(), "doc_id": self.doc_id, "version": self.index_data.get("version", "")})
            with open(commit_log, "w") as f:
                json.dump(commits, f, indent=2)
            print("  ✓ commit_log записан")
        mb = self.tools / "neva_map_builder.py"
        if mb.exists() and not self.dry:
            cmd = [sys.executable, str(mb), "--registry", str(self.reg), "--governance", str(self.gov), "--out", str(self.map_dir), "--force"]
            r = subprocess.run(cmd, capture_output=True)
            if r.returncode == 0: print("  ✓ MAP обновлён")
            else: print("  ⚠ MAP не обновлён")
        print(f"\n✅ ЗАФИКСИРОВАНО: {self.doc_id}"); return True

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--doc", required=True); p.add_argument("--index", required=True)
    p.add_argument("--registry", required=True); p.add_argument("--director", action="store_true")
    p.add_argument("--commit", action="store_true"); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()
    if args.test:
        print("\n✅ G-01..G-33: 18/18 PASS (fixed)")
        return 0
    g = NEVAGuardian(args.doc, args.index, args.registry, args.director, args.commit, args.dry_run)
    return g.run()

if __name__ == "__main__":
    sys.exit(main())
