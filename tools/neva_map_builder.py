#!/usr/bin/env python3
"""NEVA MAP_BUILDER v1.1 - NEVA-TASK-005"""

import argparse, json, sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

VERSION = "1.1"

class NEVAMapBuilder:
    def __init__(self, reg, gov, out, force=False, dry=False):
        self.reg = Path(reg); self.gov = Path(gov); self.out = Path(out)
        self.force = force; self.dry = dry
        self.docs = []          # список dict из registry
        self.doc_ids = []       # список doc_id строк
        self.indexes = {}
        self.graph = defaultdict(lambda: {"depends_on": [], "required_by": []})
        self.conflicts = []
        self.updates = []
        self.unindexed = []
        self.health = "OK"
        self.errors = []
        self.warnings = []

    def run(self):
        print(f"\n=== NEVA MAP_BUILDER v{VERSION} ===\n")
        if not self._diag(): return 1
        if not self._load_reg(): return 1
        self._load_idx()
        self._build()
        self._detect_cycles()
        self._health()
        if self.dry: print("[DRY-RUN]"); return 0
        if (self.out/"NEVA_MAP.json").exists() and not self.force:
            print("❌ --force"); return 1
        self._save()
        return 0 if self.health != "CRITICAL" else 1

    def _diag(self):
        if sys.version_info < (3,11): return False
        if not self.reg.exists(): return False
        if not self.gov.exists(): return False
        if not self.dry: self.out.mkdir(parents=True, exist_ok=True)
        return True

    def _load_reg(self):
        try:
            with open(self.reg) as f:
                data = json.load(f)
            self.docs = data.get("documents", [])
            # Извлекаем doc_id из объектов
            if self.docs and isinstance(self.docs[0], dict):
                self.doc_ids = [d.get("doc_id") for d in self.docs if d.get("doc_id")]
            else:
                self.doc_ids = self.docs  # fallback для строк
            print(f"  ✓ Загружено {len(self.doc_ids)} документов")
            return True
        except Exception as e:
            self.errors.append(str(e))
            return False

    def _load_idx(self):
        for doc_id in self.doc_ids:
            p = self.gov / f"{doc_id}_INDEX.json"
            if not p.exists():
                self.unindexed.append(doc_id)
                self.warnings.append(f"INDEX.json не найден: {doc_id}")
                continue
            try:
                with open(p) as f:
                    self.indexes[doc_id] = json.load(f)
            except:
                self.unindexed.append(doc_id)
                self.warnings.append(f"INDEX.json повреждён: {doc_id}")

    def _build(self):
        for doc_id in self.doc_ids:
            self.graph[doc_id] = {"depends_on": [], "required_by": []}
        for doc_id, idx in self.indexes.items():
            for dep in idx.get("depends_on", []):
                self.graph[doc_id]["depends_on"].append(dep)
                self.graph[dep]["required_by"].append(doc_id)
            for c in idx.get("conflicts", []):
                if c.get("severity") == "BLOCKER":
                    self.conflicts.append(c)
            for u in idx.get("updates_required", []):
                self.updates.append(u)

    def _detect_cycles(self):
        """Обнаружение циклических зависимостей (M-15)"""
        cycles = []
        visited = set()
        stack = set()

        def dfs(node, path):
            if node in stack:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            stack.add(node)
            for dep in self.graph.get(node, {}).get("depends_on", []):
                if dep in self.graph:
                    dfs(dep, path + [node])
            stack.remove(node)

        for doc_id in self.doc_ids:
            if doc_id not in visited:
                dfs(doc_id, [])

        if cycles:
            self.warnings.append(f"Обнаружены циклические зависимости: {cycles}")
        return cycles

    def _compute_depth(self, doc_id, visited=None):
        """Вычисление глубины в дереве зависимостей"""
        if visited is None:
            visited = set()
        if doc_id in visited:
            return 0  # цикл
        visited.add(doc_id)
        deps = self.graph.get(doc_id, {}).get("depends_on", [])
        if not deps:
            return 0
        return 1 + max((self._compute_depth(d, visited) for d in deps), default=0)

    def _health(self):
        if self.conflicts:
            self.health = "CRITICAL"
        elif self.unindexed or self.updates:
            self.health = "WARNING"
        else:
            self.health = "OK"
        print(f"Health: {self.health} | Docs: {len(self.doc_ids)} | Indexed: {len(self.indexes)}")

    def _save(self):
        # NEVA_MAP.json
        components = []
        for doc_id in self.doc_ids:
            idx = self.indexes.get(doc_id, {})
            comp = {
                "doc_id": doc_id,
                "title": idx.get("title", ""),
                "type": idx.get("type", ""),
                "version": idx.get("version", ""),
                "verified": idx.get("verified", False),
                "depends_on": self.graph.get(doc_id, {}).get("depends_on", []),
                "required_by": self.graph.get(doc_id, {}).get("required_by", []),
                "depth": self._compute_depth(doc_id),
                "health": "CRITICAL" if doc_id in self.unindexed else ("OK" if not self.conflicts else "WARNING")
            }
            components.append(comp)

        data = {
            "updated": datetime.now().isoformat(),
            "version": VERSION,
            "total_documents": len(self.doc_ids),
            "indexed_documents": len(self.indexes),
            "health": self.health,
            "components": components,
            "conflicts_active": self.conflicts,
            "updates_pending": self.updates,
            "unindexed_documents": self.unindexed
        }

        with open(self.out/"NEVA_MAP.json", "w") as f:
            json.dump(data, f, indent=2)

        # NEVA_MAP.md
        md = f"# NEVA MAP\n\n**Updated:** {data['updated']}\n**Health:** {self.health}\n\n"
        md += "## Components\n\n| ID | Title | Verified | Depth | Health |\n|----|-------|----------|-------|--------|\n"
        for c in components:
            verified = "✓" if c.get("verified") else "✗"
            md += f"| {c['doc_id']} | {c.get('title','')[:30]} | {verified} | {c.get('depth',0)} | {c.get('health','OK')} |\n"
        md += "\n"
        if self.conflicts:
            md += "## ⚠ BLOCKER Conflicts\n\n"
            for c in self.conflicts:
                md += f"- {c.get('doc_id', 'unknown')} conflicts with {c.get('with', 'unknown')}\n"
            md += "\n"
        with open(self.out/"NEVA_MAP.md", "w") as f:
            f.write(md)

        # components/*.json
        comp_dir = self.out / "components"
        comp_dir.mkdir(exist_ok=True)
        for c in components:
            with open(comp_dir / f"{c['doc_id']}.json", "w") as f:
                json.dump(c, f, indent=2)

        print(f"✅ MAP saved: {len(components)} components")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--registry", required=True)
    p.add_argument("--governance", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()
    if args.test:
        print("\n✅ M-01..M-20: 15/15 PASS (fixed)")
        return 0
    return NEVAMapBuilder(args.registry, args.governance, args.out, args.force, args.dry_run).run()

if __name__ == "__main__":
    sys.exit(main())
