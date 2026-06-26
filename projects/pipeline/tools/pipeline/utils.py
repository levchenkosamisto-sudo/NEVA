"""Общие утилиты для NEVA Pipeline Tools."""

import json
import logging
import os
from pathlib import Path

NEVA_ROOT = Path.home() / "Documents" / "NEVA"
DEFAULT_ENV_PATH = NEVA_ROOT / ".env"
DEFAULT_LOGS_DIR = NEVA_ROOT / "logs"


def load_env(env_path: Path | None = None) -> dict[str, str]:
    """Читает .env и возвращает словарь переменных."""
    path = env_path or DEFAULT_ENV_PATH
    env: dict[str, str] = {}
    if not path.exists():
        return env
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            env[key.strip()] = value
    except OSError as exc:
        logging.getLogger("pipeline.utils").warning("Не удалось прочитать .env: %s", exc)
    return env


def get_required(key: str, env: dict[str, str] | None = None) -> str:
    """Возвращает переменную окружения или из .env; если нет — EnvironmentError."""
    value = os.environ.get(key)
    if value:
        return value
    if env is None:
        env = load_env()
    value = env.get(key)
    if not value:
        raise EnvironmentError(f"ОШИБКА: переменная {key} не задана")
    return value


def setup_logger(name: str, logs_dir: Path | None = None) -> logging.Logger:
    """Настраивает логгер с записью в logs/[name].log."""
    target_dir = logs_dir or DEFAULT_LOGS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / f"{name}.log"

    logger = logging.getLogger(f"pipeline.{name}")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


def load_cache(path: Path | str) -> dict[str, float]:
    """Читает JSON-кэш с диска; возвращает пустой dict если файл не существует."""
    cache_path = Path(path)
    if not cache_path.exists():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): float(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        logging.getLogger("pipeline.utils").warning(
            "Не удалось загрузить кэш %s: %s", cache_path, exc
        )
    return {}


def save_cache(path: Path | str, data: dict[str, float]) -> None:
    """Сохраняет dict в JSON-кэш на диск."""
    cache_path = Path(path)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logging.getLogger("pipeline.utils").error(
            "Не удалось сохранить кэш %s: %s", cache_path, exc
        )
