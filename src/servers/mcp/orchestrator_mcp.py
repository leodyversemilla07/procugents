"""
MCP Server for RedFlag Agents PH Orchestrator.
Exposes procurement analysis as MCP tools.
"""

from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("redflag-orchestrator")

# RA 12009 SVP threshold
SVP_THRESHOLD = 1_000_000


@mcp.tool()
async def analyze_procurement(
    contract_id: str,
    contract_description: str,
    contract_amount: float,
    agency: str = "",
    source: str = "",
    svp_category: str = "general",
    procurement_type: str = "public_bidding",
    bidders: list[dict[str, Any]] | None = None,
    hope_approval_proof: bool = False,
    save_to_db: bool = False,
) -> dict[str, Any]:
    """
    Analyze a government procurement for anomalies.

    Runs the full 7-node LangGraph pipeline (legal -> price -> scraping ->
    bid -> doc -> llm -> alert) and returns the aggregated findings.

    Args:
        contract_id: Contract / PO / notice reference number
        contract_description: What is being procured
        contract_amount: Amount in PHP
        agency: Procuring entity name (e.g. "DepEd")
        source: Where the contract was sourced (e.g. "PhilGEPS")
        svp_category: Small Value Procurement category
        procurement_type: public_bidding | shopping | svp | negotiated |
            direct_contracting
        bidders: Bidder metadata list, each with keys name / address /
            directors / pcab_license / nfcc / documents. Drives the
            bid_analyzer and doc_auditor nodes.
        hope_approval_proof: True if an alternative-mode procurement has
            HoPE written approval on file
        save_to_db: Persist results to PostgreSQL / SQLite

    Returns:
        Analysis results with per-agent findings, anomalies and alerts.
    """
    # Import here to avoid circular imports. The orchestrator's
    # ``analyze_procurement`` is a *sync* function (LangGraph ``invoke`` is
    # sync), so we call it directly — no ``await``.
    from src.orchestration.orchestrator import analyze_procurement as _analyze

    return _analyze(
        contract_id=contract_id,
        contract_description=contract_description,
        contract_amount=contract_amount,
        agency=agency,
        source=source,
        svp_category=svp_category,
        procurement_type=procurement_type,
        bidders=bidders,
        hope_approval_proof=hope_approval_proof,
        save_to_db=save_to_db,
    )


@mcp.tool()
async def quick_legal_check(contract_amount: float) -> dict[str, Any]:
    """
    Quick legal compliance check for procurement threshold (RA 12009).

    Args:
        contract_amount: Contract amount in PHP

    Returns:
        Compliance status and required process
    """
    is_compliant = contract_amount <= SVP_THRESHOLD

    return {
        "compliant": is_compliant,
        "threshold": SVP_THRESHOLD,
        "required_process": "competitive bidding" if contract_amount > SVP_THRESHOLD else "small value procurement",
        "law": "RA 12009 (2024)",
    }


@mcp.tool()
async def quick_price_check(
    item_description: str,
    reported_price: float,
    market_price: float | None = None,
) -> dict[str, Any]:
    """
    Quick price inflation check against a market baseline.

    A price is flagged ``potential_inflation`` when it exceeds the market
    baseline by more than the COA 2023-004 benchmark of 30%.

    Args:
        item_description: Item name/description
        reported_price: Reported contract price in PHP
        market_price: Reference / market price in PHP. When omitted the
            tool cannot compare and returns ``flag="unknown"`` rather
            than silently asserting the price is normal.

    Returns:
        Inflation flag and baseline
    """
    from src.orchestration.state import PRICE_EXCESS_THRESHOLD_PCT

    inflation_multiplier = 1.0 + (PRICE_EXCESS_THRESHOLD_PCT / 100.0)

    if market_price is None or market_price <= 0:
        return {
            "item": item_description,
            "reported_price": reported_price,
            "market_price": None,
            "inflation_threshold": None,
            "flag": "unknown",
            "reason": "No market baseline supplied for comparison",
        }

    inflation_threshold = market_price * inflation_multiplier
    is_inflated = reported_price > inflation_threshold
    pct_above = ((reported_price - market_price) / market_price * 100.0) if market_price else 0.0

    return {
        "item": item_description,
        "reported_price": reported_price,
        "market_price": market_price,
        "inflation_threshold": inflation_threshold,
        "pct_above_market": round(pct_above, 1),
        "flag": "potential_inflation" if is_inflated else "normal",
        "reason": (
            f"Price exceeds market baseline by more than"
            f" {PRICE_EXCESS_THRESHOLD_PCT:.0f}%"
            if is_inflated
            else "Price within market baseline allowance"
        ),
    }


@mcp.tool()
async def create_alert(
    title: str,
    description: str,
    severity: str = "medium",
    contract_id: str | None = None,
) -> dict[str, Any]:
    """
    Create an alert for procurement anomaly.

    Args:
        title: Alert title
        description: Alert description
        severity: low, medium, high, critical
        contract_id: Related contract ID
    """
    return {
        "id": f"alert_{hash(title) % 10000}",
        "title": title,
        "description": description,
        "severity": severity,
        "contract_id": contract_id,
        "status": "created",
    }


if __name__ == "__main__":
    mcp.run()
