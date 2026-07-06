"""Legal Check agent for the ProcuGents orchestrator.

Pure rule-based: enforces the RA 12009 Sec 26 SVP ceiling and the RA 12009
Sec 20 PhilGEPS posting requirement (for procurements > PHP 50,000).
Returns a ``legal_findings`` dict that downstream nodes read.
"""

from __future__ import annotations


from src.orchestration.state import (
    PHILGEPS_POSTING_THRESHOLD_PHP,
    ProcurementState,
    SVP_THRESHOLD_PHP,
)


def legal_check_node(state: ProcurementState) -> ProcurementState:
    """Check legal compliance for the procurement under RA 12009."""
    amount: float = float(state.get("contract_amount") or 0)
    is_compliant = amount <= SVP_THRESHOLD_PHP
    violations: list[str] = []

    if amount > SVP_THRESHOLD_PHP:
        violations.append(
            f"Amount exceeds SVP threshold (PHP {SVP_THRESHOLD_PHP:,.0f})"
        )
        violations.append(
            f"Requires competitive bidding (amount > PHP {SVP_THRESHOLD_PHP:,.0f})"
        )

    philgeps_required = amount > PHILGEPS_POSTING_THRESHOLD_PHP
    if philgeps_required:
        # Don't add to violations list (PhilGEPS flag is checked in scraper/auditor);
        # record intent so the dashboard can surface "posting required".
        pass

    state["legal_findings"] = {
        "threshold_compliant": is_compliant,
        "required_process": (
            "competitive bidding" if amount > SVP_THRESHOLD_PHP else "small value procurement"
        ),
        "threshold": SVP_THRESHOLD_PHP,
        "philgeps_posting_required": philgeps_required,
        "violations": violations,
        "law": "RA 12009 (2024)",
    }
    return state


__all__ = ["legal_check_node"]
