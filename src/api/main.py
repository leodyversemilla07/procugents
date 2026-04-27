"""
FastAPI Server for RedFlag Agents PH Dashboard
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from typing import Any

app = FastAPI(title="ProcuGents API")

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


def get_a2a_server():
    global a2a_server
    if a2a_server is None:
        from src.servers.a2a_server import A2AServer
        a2a_server = A2AServer()
    return a2a_server


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ============== A2A Protocol Endpoints ==============

@app.get("/a2a/card")
def get_agent_card():
    """A2A: Get agent card for discovery."""
    server = get_a2a_server()
    return server.get_agent_card()


class A2ATaskRequest(BaseModel):
    """A2A task request."""
    task_id: str
    message: str
    contract_id: str | None = None
    contract_amount: float | None = None
    description: str | None = None


@app.post("/a2a/tasks")
async def create_task(request: A2ATaskRequest):
    """A2A: Submit a task for processing."""
    from src.servers.a2a_server import TaskMessage
    
    server = get_a2a_server()
    
    task = TaskMessage(
        task_id=request.task_id,
        message=request.message,
        metadata={
            "contract_id": request.contract_id,
            "contract_amount": request.contract_amount,
            "description": request.description,
        },
    )
    
    result = await server.handle_task(task)
    return result


@app.get("/a2a/tasks/{task_id}")
def get_task(task_id: str):
    """A2A: Get task status."""
    server = get_a2a_server()
    result = server.get_task_status(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@app.get("/api/stats")
def get_stats():
    """Get dashboard statistics from database."""
    from src.services.database import get_db, init_db, ProcurementAnalysis
    from sqlalchemy import func
    
    init_db()
    try:
        with get_db() as db:
            total = db.query(func.count(ProcurementAnalysis.id)).scalar() or 0
            with_anomalies = db.query(func.count(ProcurementAnalysis.id)).filter(
                ProcurementAnalysis.anomalies != "[]"
            ).scalar() or 0
            active_alerts = db.query(func.count(ProcurementAnalysis.id)).filter(
                ProcurementAnalysis.status == "alerting"
            ).scalar() or 0
            
            # Calculate compliance rate
            compliance_rate = 0.0
            if total > 0:
                compliance_rate = round((total - with_anomalies) / total * 100, 1)
            
            return StatsResponse(
                total_analyzed=total,
                anomalies_found=with_anomalies,
                active_alerts=active_alerts,
                compliance_rate=compliance_rate,
            )
    except Exception as e:
        # Return defaults if DB not available
        return StatsResponse(
            total_analyzed=0,
            anomalies_found=0,
            active_alerts=0,
            compliance_rate=0.0,
        )


@app.post("/api/analyze")
def analyze(request: ProcurementRequest):
    """Analyze a procurement contract."""
    import asyncio
    from src.orchestration.orchestrator import analyze_procurement
    
    try:
        result = asyncio.run(analyze_procurement(
            contract_id=request.contract_id,
            contract_description=request.contract_description,
            contract_amount=request.contract_amount,
            svp_category=request.svp_category,
            save_to_db=True,
        ))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analyses")
def get_analyses(limit: int = 50):
    """Get all analyses from database."""
    from src.services.database import get_db, init_db, ProcurementAnalysis
    
    init_db()
    try:
        with get_db() as db:
            analyses = db.query(ProcurementAnalysis).order_by(
                ProcurementAnalysis.created_at.desc()
            ).limit(limit).all()
            
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
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in analyses
            ]
    except Exception as e:
        return []


@app.get("/api/analyses/{analysis_id}")
def get_analysis_detail(analysis_id: int):
    """Get detailed analysis by ID."""
    from src.services.database import get_db, init_db, ProcurementAnalysis
    
    init_db()
    try:
        with get_db() as db:
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
                "anomalies": analysis.anomalies or [],
                "alerts": analysis.alerts_created or [],
                "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Auto-Crawl Endpoints ==============

@app.post("/api/crawl")
def crawl_agency(agency: str | None = None):
    """Auto-crawl and analyze PhilGEPS contracts for an agency."""
    import asyncio
    from src.scripts.auto_crawl import auto_crawl_agency, auto_scan_all
    
    try:
        if agency:
            result = asyncio.run(auto_crawl_agency(agency))
        else:
            result = asyncio.run(auto_scan_all())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)