"""LangGraph wiring for the ProcuGents procurement analysis workflow.

Order:
    legal_check -> price_analysis -> scraping -> bid_analyzer -> doc_auditor
    -> llm_analysis -> alert -> END

If the legal check fails the graph short-circuits to the alert node (the
``should_continue`` router defined in this module) so we don't waste LLM
tokens on procurements that have already crossed the SVP ceiling.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from src.orchestration.agents.alert import alert_node
from src.orchestration.agents.bid import bid_analyzer_node
from src.orchestration.agents.doc import doc_auditor_node
from src.orchestration.agents.legal import legal_check_node
from src.orchestration.agents.llm import llm_analysis_node
from src.orchestration.agents.price import price_analysis_node
from src.orchestration.agents.scraping import scraping_node
from src.orchestration.state import ProcurementState


def should_continue(state: ProcurementState) -> Literal["price_analysis", "alert"]:
    """Skip the rest of the graph when the legal threshold check fails.

    RA 12009 violations are loud enough that we don't need price/bid/doc/llm
    evidence to produce an alert.
    """
    if state.get("legal_findings", {}).get("threshold_compliant", True):
        return "price_analysis"
    return "alert"


def create_procurement_graph() -> StateGraph:
    """Construct and compile the LangGraph state machine."""
    graph = StateGraph(ProcurementState)

    graph.add_node("legal_check", legal_check_node)
    graph.add_node("price_analysis", price_analysis_node)
    graph.add_node("scraping", scraping_node)
    graph.add_node("bid_analyzer", bid_analyzer_node)
    graph.add_node("doc_auditor", doc_auditor_node)
    graph.add_node("llm_analysis", llm_analysis_node)
    graph.add_node("alert", alert_node)

    graph.add_edge("__start__", "legal_check")
    graph.add_conditional_edges(
        "legal_check",
        should_continue,
        {"price_analysis": "price_analysis", "alert": "alert"},
    )
    graph.add_edge("price_analysis", "scraping")
    graph.add_edge("scraping", "bid_analyzer")
    graph.add_edge("bid_analyzer", "doc_auditor")
    graph.add_edge("doc_auditor", "llm_analysis")
    graph.add_edge("llm_analysis", "alert")
    graph.add_edge("alert", END)

    return graph.compile()


__all__ = ["create_procurement_graph", "should_continue"]
