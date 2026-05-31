#!/usr/bin/env python3
"""
ARKA Explorer Indexer v0.1

Итерация 1:
- поиск файлов
- фильтрация директорий
- сбор метаданных
- извлечение DECISION
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime

ARKA_ROOT = Path.home() / "Documents" / "ARKA"

INCLUDE_EXTENSIONS = {".md", ".json"}

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "arc_profile",
    "browser_profile",
    "logs",
    "cache",
    "Extensions",
    "GPUCache",
    "ShaderCache",
    "component_crx_cache",
    "extensions_crx_cache",
}

DECISION_RE = re.compile(r"DECISION-\d+")


def is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & EXCLUDED_DIRS)


def collect_files(root: Path) -> list[Path]:
    files = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if is_excluded(path):
            continue

        if path.suffix.lower() not in INCLUDE_EXTENSIONS:
            continue

        files.append(path)

    return sorted(files)


def extract_decisions(text: str) -> list[str]:
    return sorted(set(DECISION_RE.findall(text)))


def build_document_record(path: Path) -> dict:
    try:
        content = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )
    except Exception:
        content = ""

    return {
        "path": str(path.relative_to(ARKA_ROOT)),
        "size_bytes": path.stat().st_size,
        "decisions": extract_decisions(content),
        "word_count": len(content.split()),
    }


def build_index() -> dict:
    files = collect_files(ARKA_ROOT)

    documents = []

    all_decisions = {}

    for file_path in files:
        record = build_document_record(file_path)

        documents.append(record)

        for decision in record["decisions"]:
            all_decisions.setdefault(decision, []).append(
                record["path"]
            )

    return {
        "built_at": datetime.utcnow().isoformat(),
        "total_files": len(documents),
        "documents": documents,
        "decisions": all_decisions,
    }


def main():
    index = build_index()

    output = Path("arka_index_stage1.json")

    output.write_text(
        json.dumps(
            index,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(f"Файлов: {index['total_files']}")
    print(f"Решений: {len(index['decisions'])}")
    print(f"Сохранено: {output}")


if __name__ == "__main__":
    main()
