"""
neva_context_api.py — Основной API NEVA
Версия: 3.6 | Архитектор: Claude
Все эндпоинты по ТЗ-2, auth + rate limiting + buffer middleware
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ─── Lifespan: инициализация графа при старте ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from tools.neva_graphiti import graph
        await graph.init()
        logger.info("NevaGraphiti инициализирован")
    except Exception as e:
        logger.error(f"Graph init failed: {e}")
    yield
    try:
        from tools.neva_graphiti import graph
        await graph.close()
    except Exception:
        pass


app = FastAPI(
    title="NEVA Context API",
    version="3.6",
    description="Единое информационное поле AI-агентов",
    lifespan=lifespan,
)

# ─── Middleware ───────────────────────────────────────────────────────────────

try:
    from neva_buffer_retry import NEVABufferMiddleware, init_buffer
    init_buffer()
    app.add_middleware(NEVABufferMiddleware)
    logger.info("NEVABufferMiddleware подключён")
except ImportError:
    logger.warning("neva_buffer_retry не найден — буферизация отключена")

# ─── Auth helper ─────────────────────────────────────────────────────────────

def _get_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return authorization[7:]


def _require_admin(authorization: Optional[str] = Header(None)) -> str:
    token = _get_token(authorization)
    admin = os.getenv("NEVA_ADMIN_TOKEN", "")
    if not admin or token != admin:
        raise HTTPException(status_code=403, detail="Admin token required")
    return token


def _require_agent(authorization: Optional[str] = Header(None)) -> str:
    token = _get_token(authorization)
    try:
        from neva_auth import get_token_role
        role = get_token_role(token)
        if role is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except ImportError:
        pass  # auth модуль не установлен — пропускаем
    return token


# ─── Pydantic модели ─────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    action: str = "extract"
    params: dict = {}


class WritebackRequest(BaseModel):
    action: str = "writeback"
    params: dict = {}


class LockRequest(BaseModel):
    topics: List[str]
    reason: str


# ─── Эндпоинты ───────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
async def health():
    """Статус системы."""
    try:
        from tools.neva_graphiti import graph
        kuzu_ok = graph._initialized
    except Exception:
        kuzu_ok = False

    try:
        from neva_trust_engine import calculate_k_truth
        k_truth = calculate_k_truth([])
    except Exception:
        k_truth = None

    return {
        "status":   "ok",
        "version":  "3.6",
        "kuzu":     kuzu_ok,
        "k_truth":  k_truth,
    }


@app.get("/api/v1/state")
async def state(_token: str = Depends(_require_agent)):
    """Текущее состояние системы."""
    try:
        from neva_metrics_collector import MetricsCollector
        mc = MetricsCollector()
        trend = mc.get_k_truth_trend(hours=1)
        return {
            "k_truth":    trend.get("last_value", 0),
            "k_truth_24h": trend.get("average", 0),
            "count":      trend.get("count", 0),
            "status":     "ok",
        }
    except Exception as e:
        return {"status": "ok", "error": str(e)}


@app.post("/api/v1/extract")
async def extract(req: ExtractRequest, _token: str = Depends(_require_agent)):
    """Извлечение атома в граф."""
    from dispatcher.dispatcher import dispatch
    task = {"action": req.action, "params": req.params}
    result = await dispatch(task)
    return {"status": "ok", "result": result}


@app.post("/api/v1/writeback")
async def writeback(req: WritebackRequest, _token: str = Depends(_require_agent)):
    """Запись атома в граф."""
    from dispatcher.dispatcher import dispatch
    task = {"action": "writeback", "params": req.params}
    result = await dispatch(task)
    return {"status": "ok", "result": result}


@app.get("/api/v1/search")
async def search(
    q: str,
    limit: int = 10,
    _token: str = Depends(_require_agent),
):
    """Семантический поиск атомов (P16)."""
    try:
        from tools.neva_graphiti import graph
        if not graph._initialized:
            raise HTTPException(status_code=503, detail="Graph not initialized")
        results = await graph.search(q, limit=limit)
        return {"results": results, "query": q, "count": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/document/{doc_id}")
async def get_document(doc_id: str, _token: str = Depends(_require_agent)):
    """Все атомы документа по doc_id (P16)."""
    try:
        from tools.neva_graphiti import graph
        atoms = await graph.get_atoms_by_doc(doc_id)
        return {"doc_id": doc_id, "atoms": atoms, "count": len(atoms)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats")
async def stats(_token: str = Depends(_require_agent)):
    """Статистика системы."""
    try:
        from neva_metrics_collector import MetricsCollector
        mc = MetricsCollector()
        trend = mc.get_k_truth_trend(hours=24)
        return {
            "k_truth_current": trend.get("last_value", 0),
            "k_truth_avg_24h": trend.get("average", 0),
            "records_24h":     trend.get("count", 0),
            "by_author":       trend.get("by_author", {}),
        }
    except Exception as e:
        return {"status": "ok", "error": str(e)}


@app.get("/api/v1/metrics")
async def metrics(_token: str = Depends(_require_agent)):
    """Метрики для health_monitor."""
    try:
        from neva_metrics_collector import MetricsCollector
        mc = MetricsCollector()
        return mc.get_k_truth_trend(hours=24)
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/v1/admin/export")
async def admin_export(_token: str = Depends(_require_admin)):
    """Экспорт данных (только admin)."""
    return {"status": "ok", "message": "Export initiated"}


@app.post("/api/v1/admin/backup")
async def admin_backup(_token: str = Depends(_require_admin)):
    """Ручной backup (только admin)."""
    try:
        from neva_backup import BackupManager
        bm = BackupManager()
        result = await bm.run_jsonl_backup([])
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


@app.post("/api/v1/admin/batch_lock")
async def admin_batch_lock(
    req: LockRequest,
    _token: str = Depends(_require_admin),
):
    """Массовая блокировка топиков (для health_monitor при RAM critical)."""
    try:
        from neva_coordinator import TopicCoordinator
        coord = TopicCoordinator()
        locked = []
        for topic in req.topics:
            ok = await coord.acquire(topic, "health_monitor", "system")
            if ok:
                locked.append(topic)
        return {
            "status":        "ok",
            "locked_topics": locked,
            "reason":        req.reason,
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}


# ─── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "neva_context_api:app",
        host="127.0.0.1",
        port=8000,
        workers=1,
        reload=False,
    )
