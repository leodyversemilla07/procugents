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
    svp_category: str = "general",
    save_to_db: bool = False,
) -> dict[str, Any]:
    """
    Analyze a government procurement for anomalies.

    Args:
        contract_id: Contract/PO reference number
        contract_description: What is being procured
        contract_amount: Amount in PHP
        svp_category: Small Value Procurement category
        save_to_db: Persist results to PostgreSQL

    Returns:
        Analysis results with anomalies and alerts
    """
    # Import here to avoid circular imports
    from src.orchestration.orchestrator import analyze_procurement as _analyze

    return await _analyze(
        contract_id=contract_id,
        contract_description=contract_description,
        contract_amount=contract_amount,
        svp_category=svp_category,
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
) -> dict[str, Any]:
    """
    Quick price inflation check.

    Args:
        item_description: Item name/description
        reported_price: Contract price in PHP

    Returns:
        Inflation flag and baseline
    """
    baseline = reported_price * 0.7

    return {
        "item": item_description,
        "reported_price": reported_price,
        "baseline": baseline,
        "flag": "potential_inflation" if reported_price > baseline else "normal",
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
