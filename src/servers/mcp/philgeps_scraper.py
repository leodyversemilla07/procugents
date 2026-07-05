"""
PhilGEPS Scraper MCP Server for RedFlag Agents PH.

Thin MCP wrappers around the shared scraper functions in philgeps_data.
Tools exposed:
    search_philgeps(keyword, category, year)
    get_agency_procurement(agency_name, year, limit)
    check_notice_compliance(notice_id)

Live httpx + BeautifulSoup scraping still happens in philgeps_data; this
module only adapts the public API to fastmcp tool definitions.
"""

from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("philgeps-scraper")


@mcp.tool()
async def search_philgeps(
    keyword: str,
    category: str = "goods",
    year: int | None = None,
) -> dict[str, Any]:
    """Search PhilGEPS for government procurement opportunities."""
    from src.servers.mcp.philgeps_data import search_philgeps as _search

    return await _search(keyword=keyword, category=category, year=year)


@mcp.tool()
async def get_agency_procurement(
    agency_name: str,
    year: int | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Get procurement history for a specific government agency."""
    from src.servers.mcp.philgeps_data import get_agency_procurement as _get

    return await _get(agency_name=agency_name, year=year, limit=limit)


@mcp.tool()
async def check_notice_compliance(notice_id: str) -> dict[str, Any]:
    """Check PhilGEPS posting compliance for a specific notice."""
    from src.servers.mcp.philgeps_data import check_notice_compliance as _check

    return await _check(notice_id=notice_id)


if __name__ == "__main__":
    mcp.run()
