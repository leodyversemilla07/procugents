"""Doc Auditor agent for the ProcuGents orchestrator.

Validates the mandatory documentary requirements defined in COA 2023-004
Annex A and RA 12009 IRR Annex H. Operates per-bidder so the dashboard can
show which documents are missing for which company.

Mapped flags (per ``docs/legal_rule_engine.json`` Section 2.4):
    * missing PhilGEPS registration       -> missing_philgeps_registration
    * missing business permit            -> missing_business_permit
    * missing bid security (over SVP)     -> missing_bid_security
    * missing PCAB license (infra)        -> missing_pcab_license
    * alt mode without HoPE approval      -> alt_mode_no_hope_approval
"""

from __future__ import annotations

from typing import Any

from src.orchestration.state import ProcurementState, SVP_THRESHOLD_PHP


def _flag(flag: str, citation: str, law: str, iiueeu: str, severity: int,
          missing_doc: str | None, bidder_name: str | None, description: str,
          *, synthetic: bool | None = None) -> dict[str, Any]:
    return {
        "flag": flag,
        "citation": citation,
        "law_source": law,
        "iiueeu": iiueeu,
        "severity": severity,
        "missing_doc": missing_doc,
        "bidder_name": bidder_name,
        "description": description,
        "synthetic": synthetic,
    }


def doc_auditor_node(state: ProcurementState) -> ProcurementState:
    """Inspect each bidder's documents and emit missing-document flags."""
    bidders: list[dict[str, Any]] = list(state.get("bidders") or [])
    procurement_type = state.get("procurement_type") or "public_bidding"
    contract_amount: float = float(state.get("contract_amount") or 0)
    hope_approval = bool(state.get("hope_approval_proof"))

    flags: list[dict[str, Any]] = []
    citations: list[str] = []

    alt_modes = {"svp", "shopping", "negotiated", "direct_contracting"}
    requires_pcab = procurement_type in {"public_bidding", "shopping"}
    requires_bid_security = (
        procurement_type == "public_bidding" and contract_amount > SVP_THRESHOLD_PHP
    )

    # Rule on alt-mode procurement itself (single global flag, not per-bidder)
    if procurement_type in alt_modes and contract_amount > SVP_THRESHOLD_PHP and not hope_approval:
        flags.append(_flag(
            flag="alt_mode_no_hope_approval",
            citation="RA 12009 IRR Rule XVI Sec 2",
            law="RA 12009 IRR",
            iiueeu="I",
            severity=5,
            missing_doc="HoPE written approval",
            bidder_name=None,
            description=(
                f"Procurement ({procurement_type}) at PHP {contract_amount:,.0f}"
                " has no HoPE approval on file."
            ),
        ))
        citations.append("RA 12009 IRR Rule XVI Sec 2")

    for b in bidders:
        name = b.get("name") or "(unknown bidder)"
        docs = b.get("documents") or {}

        # 1. PhilGEPS registration
        if docs.get("philgeps_reg") is False:
            flags.append(_flag(
                flag="missing_philgeps_registration",
                citation="COA 2023-004 Annex A Item 1",
                law="COA 2023-004",
                iiueeu="IR",
                severity=3,
                missing_doc="PhilGEPS Certificate of Registration",
                bidder_name=name,
                description=f"Bidder '{name}' has no PhilGEPS certificate of registration.",
                synthetic=bool(b.get("synthetic")),
            ))
            citations.append("COA 2023-004 Annex A Item 1")

        # 2. Business permit
        if docs.get("business_permit") is False:
            flags.append(_flag(
                flag="missing_business_permit",
                citation="COA 2023-004 Annex A Item 2",
                law="COA 2023-004",
                iiueeu="IR",
                severity=3,
                missing_doc="Mayor's / Business Permit",
                bidder_name=name,
                description=f"Bidder '{name}' has no valid business permit on file.",
                synthetic=bool(b.get("synthetic")),
            ))
            citations.append("COA 2023-004 Annex A Item 2")

        # 3. Bid security (only required above SVP threshold for open bidding)
        if requires_bid_security and not docs.get("bid_security"):
            flags.append(_flag(
                flag="missing_bid_security",
                citation="RA 12009 IRR Sec 45.1",
                law="RA 12009 IRR",
                iiueeu="IR",
                severity=4,
                missing_doc="Bid Security (1-3% of ABC)",
                bidder_name=name,
                description=(
                    f"Bidder '{name}' did not post bid security for competitive"
                    f" bidding over PHP {SVP_THRESHOLD_PHP:,.0f}."
                ),
                synthetic=bool(b.get("synthetic")),
            ))
            citations.append("RA 12009 IRR Sec 45.1")

        # 4. PCAB license (mandatory for infra projects > 1M)
        if requires_pcab and not b.get("pcab_license"):
            flags.append(_flag(
                flag="missing_pcab_license",
                citation="RA 12009 IRR Annex H Appendix A Sec 3",
                law="RA 12009 IRR",
                iiueeu="IR",
                severity=4,
                missing_doc="PCAB contractor license",
                bidder_name=name,
                description=(
                    f"Bidder '{name}' has no PCAB license for this"
                    f" {procurement_type} contract."
                ),
                synthetic=bool(b.get("synthetic")),
            ))
            citations.append("RA 12009 IRR Annex H Appendix A Sec 3")

    severity_max = max((f["severity"] for f in flags), default=1)

    state["doc_flags"] = flags
    state["doc_citations"] = sorted(set(citations))
    state["doc_risk_score"] = severity_max if flags else 1
    state["doc_findings"] = {
        "bidders_checked": len(bidders),
        "procurement_type": procurement_type,
        "hope_approval_proof": hope_approval,
        "status": "completed",
    }
    return state


__all__ = ["doc_auditor_node"]
