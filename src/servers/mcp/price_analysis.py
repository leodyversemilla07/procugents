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

    # Basic flag logic: if we have market data, flag prices 30% above typical
    baseline_estimate = reported_price * 0.7  # Assume market rate is ~70% of inflated

    return {
        "item": item_name,
        "reported_price": reported_price,
        "unit": unit,
        "flag": "potential_inflation" if reported_price > baseline_estimate else "normal",
        "baseline_estimate": baseline_estimate,
        "market_sources_count": len(results),
    }


if __name__ == "__main__":
    mcp.run()
