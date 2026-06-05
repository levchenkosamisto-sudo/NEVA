"""
neva_health_monitor.py — Мониторинг ресурсов и защита от OOM
Версия: 3.6 | Архитектор: Claude
Threshold Reactive Throttling (не линейная регрессия)
"""

import os
import asyncio
import sqlite3
import logging
from datetime import datetime

import psutil

logger = logging.getLogger(__name__)

THRESHOLDS = {
    "RAM_WARN":      int(os.getenv("RAM_WARN_PCT", "70")),
    "RAM_CRITICAL":  int(os.getenv("RAM_CRITICAL_PCT", "80")),
    "RAM_EMERGENCY": int(os.getenv("RAM_EMERGENCY_PCT", "90")),
    "CPU_WARN":      int(os.getenv("CPU_WARN_PCT", "70")),
    "TEMP_MAX_C":    int(os.getenv("TEMP_MAX_C", "85")),
}

DB_PATH = os.path.expanduser(
    os.getenv("NEVA_METRICS_DB", "~/Documents/NEVA/neva_metrics.db")
)
ADMIN_TOKEN = os.getenv("NEVA_ADMIN_TOKEN", "")
API_BASE = "http://localhost:8000"


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resource_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT NOT NULL,
            ram_pct      REAL NOT NULL,
            cpu_pct      REAL NOT NULL,
            ollama_active INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def send_macos_alert(title: str, message: str) -> None:
    """Безопасное macOS уведомление — экранируем кавычки."""
    safe_title = title.replace('"', '\\"').replace("'", "\\'")
    safe_msg   = message.replace('"', '\\"').replace("'", "\\'")
    os.system(
        f'osascript -e \'display notification "{safe_msg}" '
        f'with title "{safe_title}"\''
    )


async def trigger_buffer_mode() -> None:
    """Переводит систему в режим буферизации через batch_lock."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{API_BASE}/api/v1/admin/batch_lock",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
                json={"topics": ["extract", "writeback"], "reason": "RAM_CRITICAL"},
                timeout=aiohttp.ClientTimeout(total=3),
            )
        logger.warning("Buffer mode activated — RAM critical")
    except Exception as e:
        logger.error(f"trigger_buffer_mode failed: {e}")


async def alert_director(msg: str) -> None:
    send_macos_alert("NEVA ALERT", msg)
    logger.critical(f"DIRECTOR ALERT: {msg}")


async def check_resources() -> dict:
    """
    Threshold Reactive Throttling.
    Реагирует на скачок RAM немедленно — не через тренд.
    """
    ram_pct = psutil.virtual_memory().percent
    cpu_pct = psutil.cpu_percent(interval=0.5)

    ollama_active = any(
        "ollama" in (p.info.get("name") or "").lower()
        for p in psutil.process_iter(["name"])
    )

    # Немедленная реакция на критический уровень
    if ram_pct > THRESHOLDS["RAM_CRITICAL"] or \
       (ollama_active and ram_pct > 60):
        await trigger_buffer_mode()

    if ram_pct > THRESHOLDS["RAM_EMERGENCY"]:
        await alert_director(f"EMERGENCY: RAM {ram_pct:.1f}%")

    if ram_pct > THRESHOLDS["RAM_WARN"]:
        logger.warning(f"RAM WARNING: {ram_pct:.1f}%")

    # Сохраняем историю
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO resource_history "
            "(timestamp, ram_pct, cpu_pct, ollama_active) VALUES (?,?,?,?)",
            (datetime.utcnow().isoformat(), ram_pct, cpu_pct, int(ollama_active))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Metrics write error: {e}")

    return {
        "ram_pct":      ram_pct,
        "cpu_pct":      cpu_pct,
        "ollama_active": ollama_active,
        "status":       "ok",
    }


async def monitor_loop():
    """APScheduler-совместимый loop — запускается каждые 60 секунд."""
    init_db()
    while True:
        try:
            await check_resources()
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(monitor_loop())
