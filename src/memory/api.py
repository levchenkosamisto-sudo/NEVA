"""
NEVA ПАМЯТЬ v3 — FastAPI сервер
src/memory/api.py

Endpoints:
  POST /memory/search    — поиск (Claude Desktop, ДУМА, API ИИ)
  POST /memory/index     — индексация файла
  POST /memory/reindex   — переоценка файла (ручная)
  GET  /memory/status    — статистика базы
  GET  /memory/health    — health check
"""
import os
import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

from .db import init_db, get_conn
from .indexer import index_document, vectorize_pending
from .search import search as memory_search
from .dedup import run_dedup

log = logging.getLogger("neva.memory_api")
app = FastAPI(title="NEVA Memory API v3")

ADMIN_TOKEN = os.environ.get("NEVA_ADMIN_TOKEN", "")
AGENT_TOKEN = os.environ.get("NEVA_AGENT_TOKEN", "")


def check_auth(token: str | None) -> None:
    if not token or token not in (ADMIN_TOKEN, AGENT_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Модели запросов ──────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    asked_by: str = "unknown"
    include_obsolete: bool = False


class IndexRequest(BaseModel):
    path: str
    text: str | None = None  # если None — читаем с диска


class ReindexRequest(BaseModel):
    path: str


# ── Endpoints ────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_db()
    log.info("[MEMORY API] запущен")


@app.get("/memory/health")
def health():
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}


@app.get("/memory/status")
def status(authorization: str | None = Header(None)):
    check_auth(authorization)
    with get_conn() as conn:
        stats = {}
        for table in ("facts", "episodes", "procedures"):
            total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            актуально = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE status='АКТУАЛЬНО'"
            ).fetchone()[0]
            pending = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE status='ОЖИДАЕТ_ВЕКТОРИЗАЦИИ'"
            ).fetchone()[0]
            stats[table] = {
                "total": total,
                "актуально": актуально,
                "ожидает_векторизации": pending,
            }
        log_count = conn.execute("SELECT COUNT(*) FROM search_log").fetchone()[0]
    return {"tables": stats, "search_log_count": log_count}


@app.post("/memory/search")
def search(req: SearchRequest, authorization: str | None = Header(None)):
    check_auth(authorization)
    result = memory_search(
        query=req.query,
        asked_by=req.asked_by,
        include_obsolete=req.include_obsolete,
    )
    return result


@app.post("/memory/index")
def index(req: IndexRequest, authorization: str | None = Header(None)):
    check_auth(authorization)
    if req.text:
        text = req.text
    else:
        p = Path(req.path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Файл не найден: {req.path}")
        text = p.read_text(encoding="utf-8", errors="ignore")

    count = index_document(req.path, text)
    return {"indexed_facts": count, "path": req.path}


@app.post("/memory/reindex")
def reindex(req: ReindexRequest, authorization: str | None = Header(None)):
    check_auth(authorization)
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Файл не найден: {req.path}")
    text = p.read_text(encoding="utf-8", errors="ignore")
    count = index_document(req.path, text)
    return {"reindexed_facts": count, "path": req.path}


@app.post("/memory/dedup")
def dedup(authorization: str | None = Header(None)):
    check_auth(authorization)
    result = run_dedup()
    return result


@app.post("/memory/vectorize_pending")
def vectorize(authorization: str | None = Header(None)):
    check_auth(authorization)
    count = vectorize_pending()
    return {"vectorized": count}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=8001, workers=1)
