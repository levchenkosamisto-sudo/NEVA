"""Создание новой папки проекта NEVA."""

import os
import sys
from pathlib import Path

NEVA_ROOT = Path.home() / "Documents" / "NEVA"
DEFAULT_PROJECTS_DIR = NEVA_ROOT / "projects"

SPEC_MD = """\
# Спецификация

## Требования

## Контракты

## Edge Cases

## Примеры I/O

"""

AGENTS_MD = """\
# AGENTS.md — Правила для Cursor

## ОБЯЗАТЕЛЬНО
- ruff перед каждым коммитом
- mypy опционален
- При блокировке: questions.md → STATUS: BLOCKED + описание
- После ответа: questions.md → STATUS: RESOLVED

## strict_type_checking: false
"""

TESTS_SPEC = """\
# Тесты контрактов — заполняется Claude до реализации

import pytest

"""

SMOKE_TEST = """\
#!/bin/bash
# smoke_test.sh — интеграционный тест реального запуска
# Заполняется Claude после реализации

set -e
echo "smoke_test.sh: заполнить после реализации"
"""

QUESTIONS_MD = "STATUS: IDLE\n"
ANSWERS_MD = ""


def _projects_dir() -> Path:
    override = os.environ.get("NEVA_PROJECTS_DIR")
    if override:
        return Path(override)
    return DEFAULT_PROJECTS_DIR


def _is_nonempty_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(path.iterdir())


def create_project(project_path: Path) -> None:
    """Создаёт структуру файлов проекта в указанной папке."""
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "logs").mkdir(exist_ok=True)

    files = {
        "spec.md": SPEC_MD,
        "AGENTS.md": AGENTS_MD,
        "tests_spec.py": TESTS_SPEC,
        "smoke_test.sh": SMOKE_TEST,
        "questions.md": QUESTIONS_MD,
        "answers.md": ANSWERS_MD,
    }
    for name, content in files.items():
        (project_path / name).write_text(content, encoding="utf-8")


def main() -> int:
    """Точка входа: создаёт папку проекта с шаблонами."""
    if len(sys.argv) < 2:
        print("Ошибка: не указано имя проекта", file=sys.stderr)
        return 1

    project_name = sys.argv[1]
    projects_dir = _projects_dir()
    project_path = projects_dir / project_name

    if project_path.exists() and _is_nonempty_dir(project_path):
        print(
            f"Папка {project_name} уже существует и не пуста. "
            "Удалите вручную или выберите другое имя.",
            file=sys.stderr,
        )
        return 1

    try:
        create_project(project_path)
    except OSError:
        print(f"Ошибка: нет прав на записи в {projects_dir}", file=sys.stderr)
        return 1

    print(f"Проект {project_name} создан: {project_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
