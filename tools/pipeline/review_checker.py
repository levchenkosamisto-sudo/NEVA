"""Проверка чеклиста review.md."""

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

CHECKLIST_PATTERN = re.compile(r"^-\s+\[([ xX])\]\s+(.*)$")


def parse_checklist(content: str) -> tuple[list[str], list[str]]:
    """Разделяет пункты чеклиста на закрытые и незакрытые."""
    checked: list[str] = []
    unchecked: list[str] = []
    for line in content.splitlines():
        match = CHECKLIST_PATTERN.match(line.strip())
        if not match:
            continue
        marker, text = match.group(1), match.group(2).strip()
        if marker.lower() == "x":
            checked.append(text)
        else:
            unchecked.append(text)
    return checked, unchecked


def main() -> int:
    """Точка входа: проверяет review.md и выводит результат."""
    if len(sys.argv) < 2:
        print("Не указан путь к review.md", file=sys.stderr)
        return 1

    review_path = Path(sys.argv[1])

    if not review_path.exists():
        print("review.md не найден", file=sys.stderr)
        return 1

    try:
        content = review_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Не удалось прочитать review.md: {exc}", file=sys.stderr)
        return 1

    checked, unchecked = parse_checklist(content)

    if not checked and not unchecked:
        print("чеклист пуст", file=sys.stderr)
        return 1

    if unchecked:
        for item in unchecked:
            print(item)
        return 1

    print("OK — все пункты закрыты")
    return 0


if __name__ == "__main__":
    sys.exit(main())
