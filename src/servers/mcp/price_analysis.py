"""
Price Analysis MCP Server for RedFlag Agents PH.
Uses Exa API to search for Philippine government procurement pricing data.
"""

import os
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("price-analysis")


@mcp.tool()
async def search_procurement_prices(
    item_name: str,
    agency: str | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    """
    Search for historical procurement prices in the Philippines.

    Args:
        item_name: Name of the item (e.g., "office chairs", "laptops")
        agency: Optional government agency filter (e.g., "DepEd", "DOH")
        year: Optional year filter

    Returns:
        Dictionary with price data and sources
    """
    import httpx

    query = f"Philippine government procurement {item_name}"
    if agency:
        query += f" {agency}"
    if year:
        query += f" {year}"
    query += " contract awarded price"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.exa.ai/search",
            headers={
                "Authorization": f"Bearer {os.getenv('EXA_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "num_results": 10,
                "category": "government",
            },
            timeout=30.0,
        )

    if response.status_code != 200:
        return {"error": f"Exa API error: {response.status_code}", "results": []}

    data = response.json()
    results = []
    for item in data.get("results", []):
        results.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("text"),
            }
        )

    return {"query": query, "results": results}


@mcp.tool()
async def compare_market_price(
    item_name: str,
    reported_price: float,
    unit: str = "php",
) -> dict[str, Any]:
    """
    Flag potentially inflated prices by comparing to market rates.

    Searches Exa for historical procurement prices of the same item and
    compares the reported price against the lowest found contract amount
    (conservative baseline). Flags when price exceeds baseline by >30%.

    Args:
        item_name: Item description
        reported_price: Reported contract price
        unit: Currency unit (default: php)

    Returns:
        Analysis with flag status and market context
    """
    search_result = await search_procurement_prices(item_name)

    results = search_result.get("results", [])
    if not results:
        return {
            "item": item_name,
            "reported_price": reported_price,
            "unit": unit,
            "flag": "unknown",
            "reason": "No market data found for comparison",
        }

    # Extract PHP amounts from snippet text.
    import re

    prices: list[float] = []
    for r in results:
        snippet: str = (r.get("snippet") or r.get("text") or "")
        for match in re.finditer(
            r"(?:PHP|P|₱)?\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", snippet
        ):
            try:
                prices.append(float(match.group(1).replace(",", "")))
            except ValueError:
                continue

    if not prices:
        return {
            "item": item_name,
            "reported_price": reported_price,
            "unit": unit,
            "flag": "unknown",
            "reason": "No numerical price data could be parsed from results",
        }

    baseline_estimate = min(p for p in prices if p > 0)
    threshold = baseline_estimate * 1.30
    pct_above = ((reported_price - baseline_estimate) / baseline_estimate) * 100.0
    inflated = reported_price > threshold

    return {
        "item": item_name,
        "reported_price": reported_price,
        "unit": unit,
        "baseline": round(baseline_estimate, 2),
        "inflation_threshold": round(threshold, 2),
        "pct_above_market": round(pct_above, 1),
        "flag": "potential_inflation" if inflated else "normal",
        "reason": (
            f"Price exceeds market baseline by >30% (pct_above_market={pct_above:.1f}%)"
            if inflated
            else f"Price within 30% baseline allowance ({pct_above:.1f}% above)"
        ),
        "market_sources_count": len(results),
    }


if __name__ == "__main__":
    mcp.run()
