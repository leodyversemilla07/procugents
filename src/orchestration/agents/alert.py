"""Alert / COA disallowance reporting agent.

Aggregates findings from every prior agent in the graph and:

* collects every red flag into ``all_flags`` and ``anomalies``;
* computes ``final_risk_score`` as the maximum of all per-agent scores;
* persists flagged procurements into the ``Alert`` SQLAlchemy table;
* emits a COA-style disallowance report when any flag carries an
  ``Illegal`` / ``Excessive`` / ``Unconscionable`` IIUEEU classification.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.orchestration.state import ProcurementState

logger = logging.getLogger(__name__)


# Alerts only triggered when an IIUEEU classification demands a formal
# COA response. Per Legal Rule Engine Sections 2.5 + ``COA_2023-004 Sec 4.2``.
ALERT_TRIGGER_IIUEEU = {"I", "E", "UN"}
COA_SEVERITY_THRESHOLD = 4


def _coerce_severity(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(5, score))


def alert_node(state: ProcurementState) -> ProcurementState:
    """Aggregate flags from all agents and produce a final alert report."""
    all_flags: list[dict[str, Any]] = []
    all_citations: set[str] = set()
    per_agent_scores: list[int] = []

    # --- Legal ---
    legal_f = state.get("legal_findings") or {}
    legal_seen_citations: set[str] = set()
    if legal_f and not legal_f.get("threshold_compliant", True):
        for violation in legal_f.get("violations", []):
            citation = "RA 12009 Sec 26"
            legal_seen_citations.add(citation)
            all_flags.append({
                "source_agent": "legal",
                "type": "legal",
                "flag": "svp_over_threshold",
                "citation": citation,
                "law_source": "RA 12009",
                "iiueeu": "I",
                "severity": 5,
                "description": violation,
            })
            per_agent_scores.append(5)
        all_citations.update(legal_seen_citations)

    # --- Price ---
    price_f = state.get("price_findings") or {}
    if price_f.get("flag") == "potential_inflation":
        all_flags.append({
            "source_agent": "price",
            "type": "price",
            "flag": "price_30pct_above_market",
            "citation": "COA 2023-004 Sec 4.2",
            "law_source": "COA 2023-004",
            "iiueeu": "E",
            "severity": 4,
            "description": price_f.get("reason"),
        })
        all_citations.add("COA 2023-004 Sec 4.2")
        per_agent_scores.append(4)

    # --- Bid (new agent) ---
    for flag in state.get("bid_flags") or []:
        all_flags.append({
            **flag,
            "source_agent": "bid",
            "type": "bid",
            "description": flag.get("description"),
        })
        if flag.get("citation"):
            all_citations.add(flag["citation"])
        if flag.get("severity"):
            per_agent_scores.append(_coerce_severity(flag["severity"]))

    # --- Doc (new agent) ---
    for flag in state.get("doc_flags") or []:
        all_flags.append({
            **flag,
            "source_agent": "doc",
            "type": "doc",
            "description": flag.get("description"),
        })
        if flag.get("citation"):
            all_citations.add(flag["citation"])
        if flag.get("severity"):
            per_agent_scores.append(_coerce_severity(flag["severity"]))

    # --- LLM ---
    llm_f = state.get("llm_analysis") or {}
    if llm_f.get("available"):
        for anomaly in llm_f.get("anomalies") or []:
            all_flags.append({
                "source_agent": "llm",
                "type": "llm",
                "flag": "llm_textual_anomaly",
                "citation": "n/a",
                "law_source": "n/a",
                "iiueeu": "U",  # LLM-detected anomalies default to Unnecessary
                "severity": 3,
                "description": str(anomaly),
            })

    # Aggregate risk score = max of all per-agent components (clamped to 1..5).
    final_risk_score = max([1] + per_agent_scores)
    state["final_risk_score"] = final_risk_score

    # Alert trigger: any flag with a triggering IIUEEU classification OR severity >= 4.
    alert_triggered = any(
        flag.get("iiueeu") in ALERT_TRIGGER_IIUEEU
        or _coerce_severity(flag.get("severity")) >= COA_SEVERITY_THRESHOLD
        for flag in all_flags
    )

    # Build a COA-style report if any alert-triggering flag is present.
    alert_report: str | None = None
    if alert_triggered:
        alert_report = _format_coa_report(state, all_flags)

    state["all_flags"] = all_flags
    state["all_citations"] = sorted(all_citations)
    state["anomalies"] = [
        {
            "type": f.get("type"),
            "severity": f.get("severity"),
            "description": f.get("description"),
            "law": f.get("law_source"),
            "citation": f.get("citation"),
        }
        for f in all_flags
    ]
    state["alerts_created"] = [
        {"title": f.get("flag"), "severity": f.get("severity"), "description": f.get("description")}
        for f in all_flags
        if f.get("iiueeu") in ALERT_TRIGGER_IIUEEU
        or _coerce_severity(f.get("severity")) >= COA_SEVERITY_THRESHOLD
    ]
    state["alert_triggered"] = alert_triggered
    state["alert_report"] = alert_report

    try:
        from src.services.cache import cache_alert
        from src.services.database import Alert, get_db, init_db

        if alert_triggered and state.get("contract_id"):
            cache_alert(
                f"cohort:{state['contract_id']}",
                {
                    "contract_id": state.get("contract_id"),
                    "final_risk_score": final_risk_score,
                    "citations": state["all_citations"],
                    "report": alert_report,
                },
            )
            try:
                init_db()
                with get_db() as db:
                    db.add(Alert(
                        title=f"Procurement {state.get('contract_id')} requires disallowance review",
                        description=alert_report or "See analysis for details.",
                        level=_severity_to_level(final_risk_score),
                        severity=str(final_risk_score),
                        contract_id=state.get("contract_id") or "",
                        status="pending",
                    ))
            except Exception as db_exc:
                logger.warning("Failed to persist Alert row: %s", db_exc)
    except Exception as cache_exc:
        logger.debug("Alert cache unavailable: %s", cache_exc)

    return state


def _severity_to_level(score: int) -> str:
    if score >= 5:
        return "critical"
    if score >= 4:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def _format_coa_report(state: ProcurementState, flags: list[dict[str, Any]]) -> str:
    """Produce a COA-style disallowance summary (plain text, COA 2023-004)."""
    lines = [
        "PROCUGENTS — COA DISALLOWANCE REPORT",
        "=" * 50,
        f"Contract ID:   {state.get('contract_id')}",
        f"Agency:        {state.get('agency') or 'n/a'}",
        f"Amount:        PHP {float(state.get('contract_amount') or 0):.2f}",
        f"Generated at:  {datetime.now(UTC).isoformat()}",
        "",
        "RED FLAGS:",
    ]
    for idx, flag in enumerate(flags, start=1):
        lines.append(
            f"  {idx}. [{flag.get('source_agent', '?').upper()}]"
            f" {flag.get('flag', '?')}"
            f" [{flag.get('iiueeu', '?')}/severity {flag.get('severity')}]"
            f" — {flag.get('citation', 'n/a')}"
        )
        if flag.get("description"):
            lines.append(f"     {flag['description']}")
    lines.append("")
    lines.append("RECOMMENDED ACTION:")
    if any(f.get("iiueeu") == "I" for f in flags):
        lines.append("  → Issue Notice of Disallowance per RA 12009 Sec 65.")
    if any(f.get("iiueeu") == "E" for f in flags):
        lines.append("  → Compute disallowance of price excess above market benchmark.")
    if all(f.get("iiueeu") not in {"I", "E", "U"} for f in flags) and flags:
        lines.append("  → Document findings and elevate to Audit Committee for review.")
    return "\n".join(lines)


__all__ = ["alert_node", "ALERT_TRIGGER_IIUEEU", "COA_SEVERITY_THRESHOLD"]
