"""Public entry point for the ProcuGents orchestrator.

``analyze_procurement`` is the function called by the FastAPI layer and
the auto-crawl script; everything else in this package is internal.

The previous version of this module exposed every node inline; nodes now
live under ``src.orchestration.agents.*`` and the graph wiring under
``src.orchestration.graph``. Backwards-compatible re-exports are kept so
existing callers (e.g., ``tests/test_orchestrator.py``) keep working.
"""

from __future__ import annotations

import logging
from typing import Any

from src.orchestration.agents.alert import alert_node
from src.orchestration.agents.bid import bid_analyzer_node
from src.orchestration.agents.doc import doc_auditor_node
from src.orchestration.agents.legal import legal_check_node
from src.orchestration.agents.llm import get_llm, llm_analysis_node
from src.orchestration.agents.price import price_analysis_node
from src.orchestration.agents.scraping import scraping_node
from src.orchestration.graph import create_procurement_graph
from src.orchestration.state import ProcurementState
from src.services.database import AnalysisStatus

# Backwards-compat constants for tests / external callers.
SVP_THRESHOLD = 1_000_000  # Mirrors state.SVP_THRESHOLD_PHP.

logger = logging.getLogger(__name__)


# Re-exports for tests and external callers.
__all__ = [
    "analyze_procurement",
    "create_procurement_graph",
    "legal_check_node",
    "price_analysis_node",
    "scraping_node",
    "llm_analysis_node",
    "bid_analyzer_node",
    "doc_auditor_node",
    "alert_node",
    "get_llm",
    "ProcurementState",
    "AnalysisStatus",
    "SVP_THRESHOLD",
]


def analyze_procurement(
    contract_id: str,
    contract_description: str,
    contract_amount: float,
    agency: str = "",
    source: str = "",
    svp_category: str = "general",
    save_to_db: bool = False,
    procurement_type: str = "public_bidding",
    bidders: list[dict[str, Any]] | None = None,
    hope_approval_proof: bool = False,
) -> dict[str, Any]:
    """Analyze a procurement for anomalies."""
    initial_state: ProcurementState = {
        "contract_id": contract_id,
        "contract_description": contract_description,
        "contract_amount": float(contract_amount),
        "agency": agency,
        "source": source,
        "svp_category": svp_category,
        "procurement_type": procurement_type,
        "bidders": list(bidders or []),
        "hope_approval_proof": hope_approval_proof,
        "legal_findings": {},
        "price_findings": {},
        "scraping_results": {},
        "bid_flags": [],
        "bid_citations": [],
        "bid_risk_score": 1,
        "doc_flags": [],
        "doc_citations": [],
        "doc_risk_score": 1,
        "anomalies": [],
        "alerts_created": [],
        "final_risk_score": 1,
        "all_flags": [],
        "all_citations": [],
        "alert_triggered": False,
        "alert_report": None,
        "status": AnalysisStatus.PENDING,
        "error": None,
    }

    try:
        graph = create_procurement_graph()
        # LangGraph invoke is sync (compatible with FastAPI thread workers).
        result = graph.invoke(initial_state)

        final_status = AnalysisStatus.ALERTING if result.get("alert_triggered") else (
            AnalysisStatus.ERROR if result.get("error") else AnalysisStatus.COMPLETED
        )

        output: dict[str, Any] = {
            "contract_id": result.get("contract_id"),
            "contract_description": result.get("contract_description"),
            "contract_amount": result.get("contract_amount"),
            "agency": result.get("agency"),
            "status": final_status,
            "legal_findings": result.get("legal_findings"),
            "price_findings": result.get("price_findings"),
            "scraping_results": result.get("scraping_results"),
            "llm_analysis": result.get("llm_analysis"),
            "bid_findings": result.get("bid_findings"),
            "bid_flags": result.get("bid_flags"),
            "bid_risk_score": result.get("bid_risk_score"),
            "doc_findings": result.get("doc_findings"),
            "doc_flags": result.get("doc_flags"),
            "doc_risk_score": result.get("doc_risk_score"),
            "final_risk_score": result.get("final_risk_score"),
            "all_flags": result.get("all_flags"),
            "all_citations": result.get("all_citations", []),
            "anomalies": result.get("anomalies", []),
            "alerts": result.get("alerts_created", []),
            "alert_triggered": result.get("alert_triggered"),
            "alert_report": result.get("alert_report"),
        }

        if save_to_db:
            try:
                from src.services.database import ProcurementAnalysis, get_db, init_db
                init_db()
                with get_db() as db:
                    db.add(ProcurementAnalysis(
                        contract_id=contract_id,
                        contract_description=contract_description,
                        contract_amount=contract_amount,
                        agency=agency,
                        source=source,
                        svp_category=svp_category,
                        status=final_status,
                        legal_findings=result.get("legal_findings"),
                        price_findings=result.get("price_findings"),
                        scraping_results=result.get("scraping_results"),
                        llm_analysis=result.get("llm_analysis"),
                        bid_findings=result.get("bid_findings"),
                        bid_flags=result.get("bid_flags"),
                        bid_risk_score=result.get("bid_risk_score"),
                        doc_findings=result.get("doc_findings"),
                        doc_flags=result.get("doc_flags"),
                        doc_risk_score=result.get("doc_risk_score"),
                        final_risk_score=result.get("final_risk_score"),
                        all_flags=result.get("all_flags"),
                        all_citations=result.get("all_citations", []),
                        alerts_created=result.get("alerts_created", []),
                        alert_triggered=1 if result.get("alert_triggered") else 0,
                        alert_report=result.get("alert_report"),
                        anomalies=result.get("anomalies", []),
                    ))
                output["saved"] = True
            except Exception as exc:
                logger.warning("Failed to save to DB: %s", exc)
                output["saved"] = False

        return output
    except Exception as exc:
        logger.error("Analysis failed: %s", exc)
        return {
            "contract_id": contract_id,
            "status": AnalysisStatus.ERROR,
            "error": str(exc),
        }


if __name__ == "__main__":
    import json
    import sys

    sample = analyze_procurement(
        contract_id="PO-2024-001234",
        contract_description="Office Chairs",
        contract_amount=500_000,
    )
    sys.stdout.write(json.dumps(sample, indent=2, default=str))
    sys.stdout.write("\n")
