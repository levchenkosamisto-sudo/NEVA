"""Telegram уведомление Директору при STATUS: BLOCKED в questions.md."""

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests  # noqa: E402

from tools.pipeline.utils import get_required, load_env, setup_logger  # noqa: E402

REASON_MAX_LEN = 500


def send_telegram(message: str) -> None:
    """Отправляет сообщение в Telegram."""
    env = load_env()
    token = get_required("NEVA_TELEGRAM_TOKEN", env)
    chat_id = get_required("NEVA_TELEGRAM_CHAT_ID", env)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": chat_id, "text": message},
        timeout=10,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Telegram API error: {response.status_code}")


def is_blocked(content: str) -> bool:
    """Проверяет, что файл содержит STATUS: BLOCKED."""
    if not content.strip():
        return False
    first_line = content.splitlines()[0].strip()
    return first_line == "STATUS: BLOCKED"


def extract_reason(content: str) -> str:
    """Извлекает текст причины после строки STATUS: BLOCKED."""
    lines = content.splitlines()
    if len(lines) <= 1:
        return ""
    return "\n".join(lines[1:]).strip()


def build_message(questions_path: Path, reason: str) -> str:
    """Формирует сообщение для Telegram."""
    project_name = questions_path.parent.name
    truncated = reason[:REASON_MAX_LEN]
    return f"🔴 BLOCKED: {project_name}\n{truncated}"


def send_with_retry(message: str, logger: logging.Logger) -> bool:
    """Отправляет сообщение с одним retry при timeout."""
    for attempt in range(2):
        try:
            send_telegram(message)
            return True
        except (TimeoutError, requests.Timeout) as exc:
            logger.warning("Telegram timeout (попытка %d): %s", attempt + 1, exc)
            if attempt == 1:
                return False
    return False


def main() -> int:
    """Точка входа: читает questions.md и отправляет уведомление при BLOCKED."""
    logger = setup_logger("notify_director")

    if len(sys.argv) < 2:
        print("ERROR: не указан путь к questions.md", file=sys.stderr)
        return 1

    questions_path = Path(sys.argv[1])

    if not questions_path.exists():
        logger.warning("Файл не существует: %s", questions_path)
        print("OK")
        return 0

    try:
        content = questions_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Не удалось прочитать %s: %s", questions_path, exc)
        print("OK")
        return 0

    if not content.strip():
        logger.warning("Файл пуст: %s", questions_path)
        print("OK")
        return 0

    if not is_blocked(content):
        print("OK")
        return 0

    reason = extract_reason(content)
    message = build_message(questions_path, reason)

    try:
        if send_with_retry(message, logger):
            print("OK")
            return 0
        print("ERROR", file=sys.stderr)
        return 1
    except EnvironmentError as exc:
        print(str(exc), file=sys.stderr)
        logger.error("%s", exc)
        return 1
    except (RuntimeError, requests.RequestException) as exc:
        logger.error("Telegram недоступен: %s", exc)
        print("ERROR", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
