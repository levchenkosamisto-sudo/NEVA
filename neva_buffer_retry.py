"""
neva_buffer_retry.py — FastAPI Middleware буферизации
Версия: 3.6 | Архитектор: Claude
При недоступности Graphiti → буфер → 202 Accepted
"""

import os
import time
import sqlite3
import asyncio
import logging
from datetime import datetime

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

BUFFER_DB = os.path.expanduser(
    os.getenv("BUFFER_DB", "~/Documents/NEVA/neva_buffer.db")
)
API_BASE  = "http://localhost:8000"


def init_buffer():
    """Инициализирует буферную БД."""
    os.makedirs(os.path.dirname(BUFFER_DB), exist_ok=True)
    conn = sqlite3.connect(BUFFER_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_buffer (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE,
            method     TEXT NOT NULL,
            path       TEXT NOT NULL,
            headers    TEXT NOT NULL,
            body       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            retries    INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def _buffer_request(request: Request, body: bytes) -> None:
    """Сохраняет запрос в буфер с уникальным request_id."""
    request_id = request.headers.get(
        "x-request-id",
        f"{request.method}:{request.url.path}:{time.time()}"
    )
    conn = sqlite3.connect(BUFFER_DB)
    conn.execute(
        "INSERT OR IGNORE INTO request_buffer "
        "(request_id, method, path, headers, body, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            request_id,
            request.method,
            str(request.url.path),
            str(dict(request.headers)),
            body.decode("utf-8", errors="ignore"),
            datetime.utcnow().isoformat(),
        )
    )
    conn.commit()
    conn.close()
    logger.info(f"Request buffered: {request_id}")


async def _graphiti_available() -> bool:
    """Реальная проверка доступности API — не return True."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            r = await session.get(
                f"{API_BASE}/api/v1/health",
                timeout=aiohttp.ClientTimeout(total=2),
            )
            return r.status == 200
    except Exception:
        return False


async def retry_buffered_requests() -> int:
    """Проигрывает буферизованные запросы. APScheduler каждые 5 минут."""
    replayed = 0
    try:
        import aiohttp
        conn = sqlite3.connect(BUFFER_DB)
        rows = conn.execute(
            "SELECT id, method, path, headers, body FROM request_buffer "
            "WHERE retries < 5 ORDER BY id LIMIT 50"
        ).fetchall()
        conn.close()

        async with aiohttp.ClientSession() as session:
            for row in rows:
                rid, method, path, headers_str, body = row
                try:
                    r = await session.request(
                        method,
                        f"{API_BASE}{path}",
                        data=body.encode(),
                        timeout=aiohttp.ClientTimeout(total=5),
                    )
                    if r.status < 500:
                        conn = sqlite3.connect(BUFFER_DB)
                        conn.execute(
                            "DELETE FROM request_buffer WHERE id=?", (rid,)
                        )
                        conn.commit()
                        conn.close()
                        replayed += 1
                    else:
                        conn = sqlite3.connect(BUFFER_DB)
                        conn.execute(
                            "UPDATE request_buffer SET retries=retries+1 WHERE id=?",
                            (rid,)
                        )
                        conn.commit()
                        conn.close()
                except Exception as e:
                    logger.error(f"Retry failed for id={rid}: {e}")
    except Exception as e:
        logger.error(f"retry_buffered_requests error: {e}")
    return replayed


class NEVABufferMiddleware(BaseHTTPMiddleware):
    """
    Middleware буферизации.
    КРИТИЧНО: перезаписывает request._body после чтения.
    """

    async def dispatch(self, request: Request, call_next):
        # Читаем body и ОБЯЗАТЕЛЬНО перезаписываем
        body = await request.body()
        request._body = body  # без этого handler получит пустой body

        # Буферизуем только если внешний Graphiti недоступен
        # Пропускаем проверку для внутренних запросов самого сервера
        skip_paths = ["/api/v1/health", "/api/v1/metrics"]
        if request.method == "POST" and str(request.url.path) not in skip_paths:
            if not await _graphiti_available():
                _buffer_request(request, body)
                return JSONResponse(
                    {"status": "buffered", "message": "Graphiti недоступен"},
                    status_code=202
                )

        return await call_next(request)


# Инициализация при импорте
init_buffer()
