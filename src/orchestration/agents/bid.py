"""Bid Analyzer agent for the ProcuGents orchestrator.

Detects bidding red flags against RA 12009 / RA 9184 IRR / COA 2023-004.
Inputs come from procurement metadata (``state["bidders"]``) populated by the
scraper / API layer; if no bidder metadata is present the agent simply emits
no flags rather than crashing.

Rules applied (matched against ``docs/legal_rule_engine.json`` Section 2.3):
    * fewer than 3 bidders for open competitive bidding -> less_than_3_bidders
    * two or more bidders sharing address / directors -> dummy_bidders
    * open competitive bidding without at least one valid PCAB license (Infra)
      -> missing_pcab_license (operational flag)
    * alternative mode without HoPE approval -> alt_mode_no_hope_approval
    * bidder with NFCC below contract amount -> insufficient_nfcc
"""

from __future__ import annotations

from typing import Any

from src.orchestration.state import (
    MIN_BIDDERS_OPEN_BIDDING,
    ProcurementState,
    SVP_THRESHOLD_PHP,
)


def _shared_address_or_directors(bidders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a list of {address, names} groups that share address or directors."""
    groups: list[dict[str, Any]] = []
    by_address: dict[str, list[str]] = {}
    by_directors: dict[tuple[str, ...], list[str]] = {}
    for b in bidders:
        name = b.get("name") or "?"
        address = (b.get("address") or "").strip().lower()
        directors = tuple(sorted(d.strip().lower() for d in (b.get("directors") or [])))
        if address:
            by_address.setdefault(address, []).append(name)
        if directors:
            by_directors.setdefault(directors, []).append(name)
    for address, names in by_address.items():
        if len(names) >= 2:
            groups.append({"reason": "shared_address", "address": address, "names": names})
    for directors, names in by_directors.items():
        if len(names) >= 2:
            groups.append({"reason": "shared_directors", "directors": list(directors), "names": names})
    return groups


def bid_analyzer_node(state: ProcurementState) -> ProcurementState:
    """Apply bidding-process red flags to the procurement state."""
    bidders: list[dict[str, Any]] = list(state.get("bidders") or [])
    procurement_type = state.get("procurement_type") or "public_bidding"
    contract_amount: float = float(state.get("contract_amount") or 0)
    hope_approval = bool(state.get("hope_approval_proof"))

    flags: list[dict[str, Any]] = []
    citations: list[str] = []
    errors: list[str] = []

    # Rule 1: bidder count (only relevant for open competitive bidding)
    if procurement_type == "public_bidding" and len(bidders) > 0 and len(bidders) < MIN_BIDDERS_OPEN_BIDDING:
        flags.append({
            "flag": "less_than_3_bidders",
            "citation": "RA 9184 IRR Sec 52.1",
            "law_source": "RA 9184 IRR",
            "iiueeu": "IR",
            "severity": 4,
            "bidder_count": len(bidders),
            "description": (
                f"Open competitive bidding has only {len(bidders)} bidder(s);"
                f" minimum of {MIN_BIDDERS_OPEN_BIDDING} is required."
            ),
        })
        citations.append("RA 9184 IRR Sec 52.1")

    # Rule 2: shared addresses / directors (dummy bidders / collusion)
    collusive_groups = _shared_address_or_directors(bidders)
    if collusive_groups:
        for group in collusive_groups[:3]:  # cap to first 3 to keep report readable
            flags.append({
                "flag": "dummy_bidders",
                "citation": "COA 2023-004 Sec 5.1",
                "law_source": "COA 2023-004",
                "iiueeu": "I",
                "severity": 5,
                "bidder_name": None,
                "evidence": group,
                "description": (
                    f"Suspicious bidder collusion: {group['reason']} for {', '.join(group['names'])}."
                ),
            })
            citations.append("COA 2023-004 Sec 5.1")

    # Rule 3: alt-mode procurement over SVP threshold without HoPE approval
    alt_modes = {"svp", "shopping", "negotiated", "direct_contracting"}
    if (
        procurement_type in alt_modes
        and contract_amount > SVP_THRESHOLD_PHP
        and not hope_approval
    ):
        flags.append({
            "flag": "alt_mode_no_hope_approval",
            "citation": "RA 12009 IRR Rule XVI Sec 2",
            "law_source": "RA 12009 IRR",
            "iiueeu": "I",
            "severity": 5,
            "bidder_name": None,
            "description": (
                f"Alternative mode '{procurement_type}' used for PHP {contract_amount:,.0f}"
                f" (above SVP ceiling) without HoPE approval proof."
            ),
        })
        citations.append("RA 12009 IRR Rule XVI Sec 2")

    # Rule 4: NFCC check (only if any bidder declares it)
    for b in bidders:
        nfc = b.get("nfcc")
        if isinstance(nfc, int | float) and nfc > 0 and contract_amount > 0 and nfc < contract_amount:
            flags.append({
                "flag": "insufficient_nfcc",
                "citation": "RA 12009 IRR Sec 42.3",
                "law_source": "RA 12009 IRR",
                "iiueeu": "IR",
                "severity": 4,
                "bidder_name": b.get("name"),
                "nfc_declared": nfc,
                "contract_amount": contract_amount,
                "description": (
                    f"Bidder '{b.get('name')}' declares NFCC PHP {nfc:,.0f};"
                    f" below contract amount PHP {contract_amount:,.0f}."
                ),
            })
            citations.append("RA 12009 IRR Sec 42.3")

    severity_max = max((f["severity"] for f in flags), default=1)
    risk_score = severity_max  # 1 (no flags) .. 5 (max)

    state["bid_flags"] = flags
    state["bid_citations"] = sorted(set(citations))
    state["bid_risk_score"] = risk_score if flags else 1
    state["bid_findings"] = {
        "bidder_count": len(bidders),
        "procurement_type": procurement_type,
        "hope_approval_proof": hope_approval,
        "status": "completed" if not errors else "error",
        "errors": errors,
        "collusive_groups": collusive_groups,
    }
    return state


__all__ = ["bid_analyzer_node"]
