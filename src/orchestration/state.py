"""Shared types for the ProcuGents LangGraph orchestrator.

Single home for ``ProcurementState`` and cross-agent thresholds so each agent
node file stays small. New agents should add their findings under a dedicated
typed key instead of overloading ``legal_findings`` / ``price_findings``.

Legal grounding constants (SVP budget ceiling, PhilGEPS posting threshold,
3-bidder minimum for open bidding) are also defined here so all agents share
the same numbers — they must match ``docs/legal_rule_engine.json``.
"""

from typing import Any, TypedDict

# RA 12009 budget thresholds
SVP_THRESHOLD_PHP: float = 1_000_000.0  # Small Value Procurement ceiling
PHILGEPS_POSTING_THRESHOLD_PHP: float = 50_000.0
MIN_BIDDERS_OPEN_BIDDING: int = 3

# COA 2023-004 price-excess benchmark
PRICE_EXCESS_THRESHOLD_PCT: float = 30.0  # > 30% above market = Excessive

# Reference data dicts (kept here so nodes don't all import the JSON).
PROCURING_ENTITY_TYPES = {"public_bidding", "shopping", "svp", "negotiated", "direct_contracting"}


class ProcurementState(TypedDict, total=False):
    """State passed through the LangGraph workflow.

    Conventions:
        *_findings keys carry the rule-engine output (legal, price, ...)
        *_flags    keys carry the structured red-flag list from each agent
        *_risk_score keys hold an ordinal 1-5 risk score per agent
    """

    # Input
    contract_id: str
    contract_description: str
    contract_amount: float
    agency: str
    source: str
    svp_category: str
    procurement_type: str  # e.g. "public_bidding" | "shopping" | "svp" | ...
    bidders: list[dict[str, Any]]  # [{name, address, directors, pcab_license, nfc, documents}, ...]
    hope_approval_proof: bool  # True if alternative mode has HoPE approval on file

    # Rule-engine outputs (existing)
    legal_findings: dict[str, Any]
    price_findings: dict[str, Any]
    scraping_results: dict[str, Any]
    llm_analysis: dict[str, Any]

    # New per-agent outputs
    bid_findings: dict[str, Any]
    bid_flags: list[dict[str, Any]]
    bid_risk_score: int
    bid_citations: list[str]

    doc_findings: dict[str, Any]
    doc_flags: list[dict[str, Any]]
    doc_risk_score: int
    doc_citations: list[str]

    # Aggregated
    final_risk_score: int
    all_flags: list[dict[str, Any]]
    all_citations: list[str]
    alert_report: str | None
    alert_triggered: bool

    # Workflow
    anomalies: list[dict[str, Any]]
    alerts_created: list[dict[str, Any]]
    status: str
    error: str | None


__all__ = [
    "ProcurementState",
    "SVP_THRESHOLD_PHP",
    "PHILGEPS_POSTING_THRESHOLD_PHP",
    "MIN_BIDDERS_OPEN_BIDDING",
    "PRICE_EXCESS_THRESHOLD_PCT",
    "PROCURING_ENTITY_TYPES",
]
