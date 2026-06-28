"""Демон мониторинга projects/ на STATUS: BLOCKED."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.pipeline.utils import load_cache, save_cache, setup_logger  # noqa: E402

PIPELINE_DIR = Path(__file__).resolve().parent
NOTIFY_SCRIPT = PIPELINE_DIR / "notify_director.py"
DEFAULT_CACHE_FILE = Path.home() / ".neva_inspector_cache.json"
MTIME_WINDOW_SEC = 600
NOTIFY_COOLDOWN_SEC = 600


def scan_projects(projects_dir: str) -> list[str]:
    """Сканирует projects/ и возвращает пути к questions.md с STATUS: BLOCKED."""
    results: list[str] = []
    projects_path = Path(projects_dir)
    if not projects_path.exists():
        return results

    for project in projects_path.iterdir():
        if not project.is_dir():
            continue
        questions = project / "questions.md"
        if not questions.exists():
            continue
        try:
            content = questions.read_text(encoding="utf-8")
        except OSError:
            continue
        if not content.strip():
            continue
        first_line = content.splitlines()[0].strip()
        if first_line == "STATUS: BLOCKED":
            results.append(str(questions))
    return results


class InspectorPoll:
    """Периодическая проверка questions.md во всех проектах."""

    def __init__(
        self,
        projects_dir: str,
        interval: int = 180,
        dry_run: bool = False,
        cache_file: Path | str | None = None,
    ) -> None:
        self.projects_dir = Path(projects_dir)
        self.interval = interval
        self.dry_run = dry_run
        self.cache_file = Path(cache_file or DEFAULT_CACHE_FILE)
        self.cache: dict[str, float] = load_cache(self.cache_file)
        self.logger = setup_logger("inspector_poll")

    def ensure_projects_dir(self) -> None:
        """Создаёт projects/ если не существует."""
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def is_recently_modified(self, questions_path: str) -> bool:
        """Файл модифицирован менее 10 минут назад."""
        path = Path(questions_path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return False
        return time.time() - mtime < MTIME_WINDOW_SEC

    def should_notify(self, questions_path: str) -> bool:
        """Проверяет, нужно ли отправлять уведомление."""
        import os
        if os.environ.get("INSPECTOR_NOTIFY", "false").lower() == "false":
            return False
        last_sent = self.cache.get(questions_path)
        if last_sent is None:
            return True
        return time.time() - last_sent >= NOTIFY_COOLDOWN_SEC

    def notify(self, questions_path: str) -> None:
        """Вызывает notify_director.py для указанного файла."""
        if self.dry_run:
            self.logger.info("dry-run: уведомление для %s", questions_path)
            return

        result = subprocess.run(
            [sys.executable, str(NOTIFY_SCRIPT), questions_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"notify_director exit {result.returncode}: {result.stderr}"
            )

    def check_once(self) -> None:
        """Одна итерация сканирования."""
        self.ensure_projects_dir()
        blocked_paths = scan_projects(str(self.projects_dir))

        for questions_path in blocked_paths:
            if not self.is_recently_modified(questions_path):
                continue
            if not self.should_notify(questions_path):
                continue
            try:
                self.notify(questions_path)
                self.cache[questions_path] = time.time()
                save_cache(self.cache_file, self.cache)
                self.logger.info("Уведомление отправлено: %s", questions_path)
            except Exception as exc:
                self.logger.error(
                    "Ошибка уведомления %s: %s", questions_path, exc
                )

    def run(self) -> None:
        """Запускает демон с периодическим сканированием."""
        self.logger.info(
            "Inspector poll запущен: dir=%s interval=%d dry_run=%s",
            self.projects_dir,
            self.interval,
            self.dry_run,
        )
        while True:
            self.check_once()
            time.sleep(self.interval)


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(description="NEVA Inspector Poll")
    parser.add_argument(
        "--interval",
        type=int,
        default=180,
        help="Интервал сканирования в секундах (default: 180)",
    )
    parser.add_argument(
        "--projects-dir",
        type=str,
        default=str(Path.home() / "Documents" / "NEVA" / "projects"),
        help="Путь к каталогу projects",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только лог, без Telegram",
    )
    parser.add_argument(
        "--cache-file",
        type=str,
        default=str(DEFAULT_CACHE_FILE),
        help="Путь к файлу кэша уведомлений",
    )
    return parser.parse_args()


def main() -> int:
    """Точка входа."""
    args = parse_args()
    poll = InspectorPoll(
        projects_dir=args.projects_dir,
        interval=args.interval,
        dry_run=args.dry_run,
        cache_file=args.cache_file,
    )
    poll.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
