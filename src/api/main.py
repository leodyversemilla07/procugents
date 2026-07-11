"""
FastAPI Server for RedFlag Agents PH Dashboard
"""

import json
import logging
import sys
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uvicorn

from src.servers.a2a_server import (
    handle_jsonrpc_request,
    _A2AError,
)

# ---------------------------------------------------------------------------
# Structured JSON logging for the API layer
# ---------------------------------------------------------------------------


class JSONFormatter(logging.Formatter):
    """Log formatter that outputs newline-delimited JSON.

    Every log entry carries timestamp, level, logger, and message.
    The ``extra`` dict supplied by callers is merged as top-level keys
    (e.g. ``contract_id``, ``task_id``) so structured fields are
    queryable in log-aggregation tools (Loki, Datadog, etc.).

    Example output::

        {"ts": "2026-07-11T12:00:00Z", "level": "INFO", "logger": "uvicorn.access",
         "msg": "GET /api/health 200", "method": "GET", "path": "/api/health",
         "status": 200}
    """

    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge structured extras (contract_id, request_id, …).
        for key in ("contract_id", "task_id", "method", "path", "status"):
            val = getattr(record, key, None)
            if val is not None:
                base[key] = val
        if record.exc_info and record.exc_info[0]:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str)


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan — runs init_db once at startup, disposes at shutdown.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: initialize the database. Shutdown: dispose the connection pool."""
    logger.info("initializing database")
    from src.services.database import engine, init_db

    init_db()
    yield
    logger.info("disposing database engine")
    engine.dispose()


# ---------------------------------------------------------------------------
# Dependency: yields a SQLAlchemy session with commit/rollback lifecycle.
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session.

    The session is committed on success, rolled back on error, and
    always closed when the request finishes.
    """
    from src.services.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app = FastAPI(
    title="ProcuGents API",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProcurementRequest(BaseModel):
    contract_id: str
    contract_description: str
    contract_amount: float
    svp_category: str = "general"


class StatsResponse(BaseModel):
    total_analyzed: int
    anomalies_found: int
    active_alerts: int
    compliance_rate: float


# A2A Server instance
a2a_server = None


def get_a2a_server(base_url: str = "http://localhost:8000"):
    global a2a_server
    if a2a_server is None:
        from src.servers.a2a_server import A2AServer, RedisTaskStore

        # Use Redis-backed store when Redis is available, fall back to
        # InMemoryTaskStore automatically.
        store = RedisTaskStore()
        a2a_server = A2AServer(base_url=base_url, store=store)
    return a2a_server


@app.get("/api/health")
def health():
    return {"status": "ok"}

# ============== A2A v1.0 Protocol Endpoints ==============
# JSON-RPC 2.0 over HTTP at /a2a/jsonrpc (canonical A2A transport per spec
# Section 9), plus a parallel HTTP+JSON REST surface that wraps the same
# operations for clients that prefer /a2a/tasks/{id}-style URLs.


class _JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 envelope per RFC 7049."""
    jsonrpc: str
    method: str
    params: dict[str, Any] | None = None
    id: int | str | None = None


@app.post("/a2a/jsonrpc")
async def a2a_jsonrpc(request: _JSONRPCRequest, raw_req: Request):
    """A2A v1.0 canonical JSON-RPC endpoint.

    Accepts a single JSON-RPC 2.0 envelope and returns a single response
    envelope (or ``{}`` for notifications without ``id``).
    """
    body = request.model_dump()
    server = get_a2a_server(base_url=str(raw_req.base_url).rstrip("/"))
    resp = await handle_jsonrpc_request(server, body)
    return resp


@app.get("/a2a/tasks/{task_id}:subscribe")
async def a2a_subscribe_sse(task_id: str, raw_req: Request):
    """SSE stream of task state transitions.

    Per A2A v1.0 Section 4.3, the first event carries the current
    full ``Task`` object; subsequent events carry incremental state
    transitions as they happen. Events use the SSE ``data:`` format::

        data: {"jsonrpc":"2.0","id":"sub-<task_id>","result":{...}}

    The client disconnects by closing the HTTP connection.
    """
    import json

    from src.servers.a2a_server import task_update_channel
    from src.services.events import bus

    server = get_a2a_server()

    # Check the task exists.
    try:
        task = await server.op_get_task(id=task_id)
    except Exception as exc:
        raise _a2a_error_to_http(exc)

    sub_id = f"sub-{task_id}"

    async def _event_stream() -> AsyncIterator[str]:
        # 1. Emit the current snapshot.
        initial_state = task.get("status", {}).get("state")
        initial = {
            "jsonrpc": "2.0",
            "id": sub_id,
            "result": task,
        }
        yield f"data: {json.dumps(initial)}\n\n"

        # If the task is already terminal, the snapshot is the only
        # event — no need to subscribe for new transitions.
        if initial_state in {
            "completed", "failed", "canceled", "rejected",
        }:
            return

        # 2. Subscribe to task-state changes via the in-process EventBus.
        async with bus.subscribe() as sub:
            async for envelope in sub:
                if envelope.get("channel") == task_update_channel(task_id):
                    event = {
                        "jsonrpc": "2.0",
                        "id": sub_id,
                        "result": envelope["event"],
                    }
                    yield f"data: {json.dumps(event)}\n\n"
                # Check if task is terminal; if so, send a final event and stop.
                task_state = envelope["event"].get("status", {}).get("state")
                if task_state in {
                    "completed", "failed", "canceled", "rejected",
                }:
                    break

    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/a2a/card")
def a2a_discovery(raw_req: Request):
    """Agent Card discovery (the ``.well-known``-style GET).

    Mirrors the JSON-RPC ``agent/card`` style endpoint: clients discover
    capabilities and the JSON-RPC URL by GETting this resource.
    """
    server = get_a2a_server(base_url=str(raw_req.base_url).rstrip("/"))
    return server.get_agent_card()


@app.get("/a2a/tasks/{task_id}")
async def a2a_get_task(task_id: str):
    """REST equivalent of ``tasks/get``."""
    server = get_a2a_server()
    try:
        return await server.op_get_task(id=task_id)
    except Exception as exc:
        raise _a2a_error_to_http(exc)


@app.post("/a2a/tasks/{task_id}:cancel")
async def a2a_cancel_task(task_id: str):
    """REST equivalent of ``tasks/cancel``.

    Returns the cancelled Task (idempotent on terminal tasks returns
    A2A_TASK_NOT_CANCELABLE -> HTTP 409).
    """
    server = get_a2a_server()
    try:
        # op_cancel_task awaits its own lock.
        result = await server.op_cancel_task(id=task_id)
        import inspect
        if inspect.isawaitable(result):
            result = await result
        return result
    except Exception as exc:
        raise _a2a_error_to_http(exc)


def _a2a_error_to_http(exc: Exception):
    """Map internal _A2AError to HTTPException with appropriate status."""
    if not isinstance(exc, _A2AError):
        raise HTTPException(status_code=500, detail=str(exc))

    code_to_status = {
        -32602: 400,  # RPC_INVALID_PARAMS
        -32001: 404,  # A2A_TASK_NOT_FOUND
        -32002: 409,  # A2A_TASK_NOT_CANCELABLE
        -32003: 400,  # A2A_PUSH_NOT_SUPPORTED
        -32004: 400,  # A2A_UNSUPPORTED_OPERATION
        -32005: 415,  # A2A_CONTENT_TYPE_NOT_SUPPORTED
    }
    return HTTPException(
        status_code=code_to_status.get(exc.code, 400),
        detail={"code": exc.code, "message": str(exc), "data": exc.data},
    )


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics from database."""
    from sqlalchemy import func
    from src.services.database import AnalysisStatus, ProcurementAnalysis

    try:
        total = db.query(func.count(ProcurementAnalysis.id)).scalar() or 0
        active_alerts = db.query(func.count(ProcurementAnalysis.id)).filter(
            ProcurementAnalysis.status == AnalysisStatus.ALERTING
        ).scalar() or 0
        with_anomalies = active_alerts

        compliance_rate = 0.0
        if total > 0:
            compliance_rate = round((total - with_anomalies) / total * 100, 1)

        return StatsResponse(
            total_analyzed=total,
            anomalies_found=with_anomalies,
            active_alerts=active_alerts,
            compliance_rate=compliance_rate,
        )
    except Exception:
        return StatsResponse(
            total_analyzed=0,
            anomalies_found=0,
            active_alerts=0,
            compliance_rate=0.0,
        )


@app.post("/api/analyze")
def analyze(request: ProcurementRequest):
    """Analyze a procurement contract."""
    from src.orchestration.orchestrator import analyze_procurement

    logger.info("analyze contract", extra={
        "contract_id": request.contract_id,
        "amount": request.contract_amount,
    })

    try:
        return analyze_procurement(
            contract_id=request.contract_id,
            contract_description=request.contract_description,
            contract_amount=request.contract_amount,
            svp_category=request.svp_category,
            save_to_db=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analyses")
def get_analyses(
    limit: int = 50,
    min_risk: int | None = None,
    max_risk: int | None = None,
    alerted_only: bool = False,
    agency: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    """Get analyses from database with optional filters.

    Query params:
        limit:        max number of rows (default 50)
        min_risk:     only rows with final_risk_score >= min_risk (1..5)
        max_risk:     only rows with final_risk_score <= max_risk (1..5)
        alerted_only: only rows with alert_triggered = True
        agency:       case-insensitive substring match on agency name
        q:            case-insensitive substring match on contract_id OR
                      contract_description
    """
    from src.services.database import ProcurementAnalysis

    try:
        query = db.query(ProcurementAnalysis)
        if min_risk is not None:
            query = query.filter(ProcurementAnalysis.final_risk_score >= min_risk)
        if max_risk is not None:
            query = query.filter(ProcurementAnalysis.final_risk_score <= max_risk)
        if alerted_only:
            query = query.filter(ProcurementAnalysis.alert_triggered == 1)
        if agency:
            query = query.filter(ProcurementAnalysis.agency.ilike(f"%{agency}%"))
        if q:
            like = f"%{q}%"
            query = query.filter(
                (ProcurementAnalysis.contract_id.ilike(like))
                | (ProcurementAnalysis.contract_description.ilike(like))
            )

        analyses = query.order_by(ProcurementAnalysis.created_at.desc()).limit(limit).all()

        return [
            {
                "id": a.id,
                "contract_id": a.contract_id,
                "contract_description": a.contract_description,
                "contract_amount": a.contract_amount,
                "agency": a.agency or "",
                "source": a.source or "",
                "status": a.status,
                "anomalies_count": len(a.anomalies) if a.anomalies else 0,
                "final_risk_score": a.final_risk_score or 1,
                "alert_triggered": bool(a.alert_triggered),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in analyses
        ]
    except Exception:
        return []


@app.get("/api/analyses/{analysis_id}")
def get_analysis_detail(
    analysis_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed analysis by ID."""
    from src.services.database import ProcurementAnalysis

    try:
        analysis = db.query(ProcurementAnalysis).filter(
            ProcurementAnalysis.id == analysis_id
        ).first()

        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        return {
            "contract_id": analysis.contract_id,
            "contract_description": analysis.contract_description,
            "contract_amount": analysis.contract_amount,
            "agency": analysis.agency or "",
            "source": analysis.source or "",
            "status": analysis.status,
            "legal_findings": analysis.legal_findings or {},
            "price_findings": analysis.price_findings or {},
            "scraping_results": analysis.scraping_results or {},
            "llm_analysis": analysis.llm_analysis or {"available": False},
            "bid_findings": analysis.bid_findings or {},
            "bid_flags": analysis.bid_flags or [],
            "bid_risk_score": analysis.bid_risk_score or 1,
            "doc_findings": analysis.doc_findings or {},
            "doc_flags": analysis.doc_flags or [],
            "doc_risk_score": analysis.doc_risk_score or 1,
            "final_risk_score": analysis.final_risk_score or 1,
            "all_flags": analysis.all_flags or [],
            "all_citations": analysis.all_citations or [],
            "alert_triggered": bool(analysis.alert_triggered),
            "alert_report": analysis.alert_report,
            "anomalies": analysis.anomalies or [],
            "alerts": analysis.alerts_created or [],
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Alert Management Endpoints ==============


class AlertResolveRequest(BaseModel):
    resolution_notes: str = ""


@app.get("/api/alerts")
def list_alerts(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    severity: str | None = None,
    contract_id: str | None = None,
    db: Session = Depends(get_db),
):
    """List alerts with optional filters."""
    from src.services.database import Alert as AlertModel

    try:
        query = db.query(AlertModel)
        if status:
            query = query.filter(AlertModel.status == status)
        if severity:
            query = query.filter(AlertModel.severity == severity)
        if contract_id:
            query = query.filter(AlertModel.contract_id == contract_id)

        total = query.count()
        items = query.order_by(AlertModel.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "items": [
                {
                    "id": a.id,
                    "title": a.title,
                    "description": a.description,
                    "level": a.level,
                    "severity": a.severity,
                    "contract_id": a.contract_id,
                    "status": a.status,
                    "resolution_notes": a.resolution_notes,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                }
                for a in items
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/alerts/{alert_id}")
def resolve_alert(
    alert_id: int,
    body: AlertResolveRequest,
    db: Session = Depends(get_db),
):
    """Mark an alert as resolved (optionally with notes)."""
    from datetime import UTC, datetime
    from src.services.database import Alert as AlertModel

    try:
        alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.status = "resolved"
        alert.resolved_at = datetime.now(UTC)
        if body.resolution_notes:
            alert.resolution_notes = body.resolution_notes
        db.commit()
        db.refresh(alert)

        return {
            "id": alert.id,
            "title": alert.title,
            "status": alert.status,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "resolution_notes": alert.resolution_notes,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Analytics / Cohort Endpoints ==============


@app.get("/api/analytics/cohorts")
def cohort_analytics(
    min_date: str | None = None,
    max_date: str | None = None,
    min_risk: int | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Aggregate procurement metrics per agency (cohort view)."""
    from sqlalchemy import func, Integer
    from src.services.database import ProcurementAnalysis

    try:
        query = db.query(
            ProcurementAnalysis.agency,
            func.count(ProcurementAnalysis.id).label("contract_count"),
            func.sum(ProcurementAnalysis.contract_amount).label("total_amount"),
            func.avg(ProcurementAnalysis.final_risk_score).label("avg_risk_score"),
            func.max(ProcurementAnalysis.final_risk_score).label("max_risk_score"),
            func.sum(func.cast(ProcurementAnalysis.alert_triggered, Integer)).label("alert_count"),
        ).filter(
            ProcurementAnalysis.agency.isnot(None),
            ProcurementAnalysis.agency != "",
        )

        if min_date:
            query = query.filter(ProcurementAnalysis.created_at >= min_date)
        if max_date:
            query = query.filter(ProcurementAnalysis.created_at <= max_date)
        if min_risk is not None:
            query = query.filter(ProcurementAnalysis.final_risk_score >= min_risk)

        rows = query.group_by(ProcurementAnalysis.agency).order_by(
            func.count(ProcurementAnalysis.id).desc()
        ).limit(limit).all()

        cohorts = []
        for row in rows:
            cohorts.append(
                {
                    "agency": row[0] or "Unknown",
                    "contract_count": int(row[1] or 0),
                    "total_amount": float(row[2] or 0),
                    "avg_risk_score": round(float(row[3] or 1), 1),
                    "max_risk_score": int(row[4] or 1),
                    "alert_count": int(row[5] or 0),
                }
            )

        # Derive high_risk_count and anomaly_count per agency.
        for c in cohorts:
            high = (
                db.query(ProcurementAnalysis)
                .filter(
                    ProcurementAnalysis.agency == c["agency"],
                    ProcurementAnalysis.final_risk_score >= 4,
                )
                .count()
            )
            c["high_risk_count"] = high
            # Count rows where anomalies is not null
            anomaly_count = (
                db.query(ProcurementAnalysis)
                .filter(
                    ProcurementAnalysis.agency == c["agency"],
                    ProcurementAnalysis.anomalies.isnot(None),
                )
                .count()
            )
            c["anomaly_count"] = anomaly_count
            c["anomaly_rate"] = round(
                (c["anomaly_count"] / c["contract_count"] * 100)
                if c["contract_count"] > 0 else 0,
                1,
            )
            c["compliance_rate"] = round(
                ((c["contract_count"] - c["alert_count"]) / c["contract_count"] * 100)
                if c["contract_count"] > 0 else 0,
                1,
            )
            c["total_amount_formatted"] = f"PHP {c['total_amount']:,.2f}"

        return {"cohorts": cohorts, "total_agencies": len(cohorts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Auto-Crawl Endpoints ==============

@app.post("/api/crawl")
def crawl_agency(agency: str | None = None):
    """Auto-crawl and analyze PhilGEPS contracts for an agency."""
    import asyncio
    from src.scripts.auto_crawl import auto_crawl_agency, auto_scan_all

    try:
        result = asyncio.run(auto_crawl_agency(agency)) if agency else asyncio.run(auto_scan_all())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== WebSocket: live dashboard updates ==============
#
# The orchestrator's `alert_node` publishes events to the in-process
# event bus on `dashboard:updates` channel whenever an alert is
# triggered (final_risk_score >= 4 or an IIUEEU Illegal/Excessive/
# Unconscionable flag is raised). The /ws/alerts endpoint subscribes
# and forwards each event to the connected browser tab.
#
# In production this would be backed by Redis pub/sub:
#     redis.subscribe("dashboard:updates")
# The in-process implementation lives in src/services/events.py
# and has identical semantics.

@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """Stream dashboard alert events over WebSocket.

    The protocol is line-delimited JSON; every message is one
    ``{"channel": str, "event": dict}`` envelope as published by the
    EventBus.
    """
    await websocket.accept()
    from src.services.events import bus

    try:
        async for envelope in bus.subscribe():
            await websocket.send_json(envelope)
    except WebSocketDisconnect:
        pass
    finally:
        # The bus.subscribe() generator handles its own teardown.
        pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
