"""
neva_ollama_watchdog.py — Контроль локальных моделей Ollama
Версия: 3.6 | Архитектор: Claude
Cold start delay 10с — нет ложных restart loop
"""

import os
import asyncio
import logging

logger = logging.getLogger(__name__)

OLLAMA_API = "http://localhost:11434"
CHECK_INTERVAL = 60  # секунд


def get_ollama_service_label() -> str:
    """Определяет реальный label Ollama в launchd."""
    result = os.popen("launchctl list | grep ollama").read()
    if "homebrew.mxcl.ollama" in result:
        return "homebrew.mxcl.ollama"
    if os.path.exists("/Applications/Ollama.app"):
        return "app"
    return "unknown"


async def _ping_ollama() -> bool:
    """Проверяет доступность Ollama через /api/tags."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            r = await session.get(
                f"{OLLAMA_API}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5),
            )
            return r.status == 200
    except Exception:
        return False


async def restart_ollama() -> None:
    """Перезапускает Ollama в зависимости от способа установки."""
    label = get_ollama_service_label()
    logger.warning(f"Restarting Ollama (label={label})")

    if label == "homebrew.mxcl.ollama":
        os.system("brew services restart ollama")
    elif label == "app":
        os.system("pkill -f Ollama")
        await asyncio.sleep(2)
        os.system("open -a Ollama")
    else:
        os.system("pkill ollama || true")
        await asyncio.sleep(2)
        os.system("ollama serve &")


async def check_ollama() -> dict:
    """
    Проверяет доступность Ollama.
    Cold start delay 10с перед restart — нет ложных срабатываний.
    Не перезапускает если модель просто выгружена (KEEP_ALIVE=1m).
    """
    # Первая проверка
    if await _ping_ollama():
        return {"status": "running"}

    # Cold start delay — Ollama мог просто запускаться
    logger.info("Ollama не отвечает — ждём cold start (10с)...")
    await asyncio.sleep(10)

    # Повторная проверка
    if await _ping_ollama():
        logger.info("Ollama поднялся после cold start")
        return {"status": "running", "note": "cold_start"}

    # Реальный сбой — перезапуск
    logger.warning("Ollama недоступен — перезапуск")
    await restart_ollama()

    # Ждём после перезапуска
    await asyncio.sleep(15)

    if await _ping_ollama():
        return {"status": "restarted", "ok": True}
    else:
        return {"status": "restarted", "ok": False, "note": "still_unavailable"}


async def watchdog_loop():
    """Цикл проверки каждые 60 секунд."""
    logger.info("Ollama watchdog started")
    while True:
        try:
            result = await check_ollama()
            if result.get("status") == "restarted":
                logger.warning(f"Ollama restart: {result}")
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(watchdog_loop())
