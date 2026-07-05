"""
PhilGEPS scraper functions for RedFlag Agents PH.
Separated from MCP server for direct import.

Public functions:
    search_philgeps(keyword, category, year) -> dict
    get_agency_procurement(agency_name, year, limit) -> dict
    check_notice_compliance(notice_id) -> dict

Falls back to shared mock data (philgeps_mock.MOCK_PROCUREMENTS) when the live
PhilGEPS endpoint is unreachable or requires authentication.
"""

from typing import Any

from src.servers.mcp.philgeps_mock import (
    MOCK_PROCUREMENTS,
    find_by_agency as _find_by_agency,
    find_by_notice as _find_by_notice,
    search_mock as _search_mock,
)

# Backwards-compat: prior code referenced an internal _search_by_agency symbol.
_search_by_agency = _find_by_agency

PHILGEPS_URL = "https://philgeps.gov.ph"
USER_AGENT = "Mozilla/5.0 (compatible; RedFlagAgentsPH/1.0)"


async def _try_live_search(keyword: str, category: str, year: int | None) -> list[dict[str, Any]] | None:
    """Return live search results from PhilGEPS, or None if unreachable."""
    try:
        import httpx
        from bs4 import BeautifulSoup

        params: dict[str, str] = {"q": keyword, "category": category}
        if year:
            params["year"] = str(year)

        headers = {"User-Agent": USER_AGENT}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PHILGEPS_URL}/search",
                params=params,
                headers=headers,
                timeout=10.0,
                follow_redirects=True,
            )

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            for row in soup.select(".result-row, .procurement-item"):
                link = row.select_one("a")
                agency_elem = row.select_one(".agency, .requesting-office")
                if link:
                    results.append({
                        "title": link.get_text(strip=True),
                        "url": link.get("href", ""),
                        "agency": agency_elem.get_text(strip=True) if agency_elem else None,
                    })
            return results[:20] if results else None
    except Exception:
        return None


async def _try_live_agency(agency_name: str, limit: int) -> list[dict[str, Any]] | None:
    """Return live agency search results from PhilGEPS, or None if unreachable."""
    try:
        import httpx
        from bs4 import BeautifulSoup

        headers = {"User-Agent": USER_AGENT}
        params = {"agency": agency_name, "limit": str(limit)}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PHILGEPS_URL}/agency/search",
                params=params,
                headers=headers,
                timeout=10.0,
            )

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            for row in soup.select(".result-row")[:limit]:
                link = row.select_one("a")
                if link:
                    results.append({
                        "title": link.get_text(strip=True),
                        "url": link.get("href", ""),
                    })
            return results if results else None
    except Exception:
        return None


async def _try_live_compliance(notice_id: str) -> bool:
    """Return True if the live PhilGEPS endpoint reports the notice, else False."""
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PHILGEPS_URL}/notice/{notice_id}",
                timeout=10.0,
            )
            return response.status_code == 200
    except Exception:
        return False


async def search_philgeps(
    keyword: str,
    category: str = "goods",
    year: int | None = None,
) -> dict[str, Any]:
    """Search PhilGEPS for government procurement opportunities."""
    live = await _try_live_search(keyword, category, year)
    if live is not None:
        return {
            "keyword": keyword,
            "category": category,
            "year": year,
            "results": live,
        }

    return {
        "keyword": keyword,
        "category": category,
        "year": year,
        "source": "mock_data",
        "results": _search_mock(keyword),
    }


async def get_agency_procurement(
    agency_name: str,
    year: int | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Get procurement history for a specific government agency."""
    live = await _try_live_agency(agency_name, limit)
    if live is not None:
        return {"agency": agency_name, "year": year, "results": live}

    return {
        "agency": agency_name,
        "year": year,
        "source": "mock_data",
        "results": _find_by_agency(agency_name)[:limit],
    }


async def check_notice_compliance(notice_id: str) -> dict[str, Any]:
    """Check PhilGEPS posting compliance for a specific notice."""
    if await _try_live_compliance(notice_id):
        return {"notice_id": notice_id, "compliant": True}

    item = _find_by_notice(notice_id)
    if item is not None:
        return {
            "notice_id": notice_id,
            "title": item["title"],
            "agency": item["agency"],
            "abc_amount": item["abc_amount"],
            "procurement_method": item["procurement_method"],
            "status": item["status"],
            "awardee": item["awardee"],
            "compliant": True,
            "source": "mock_data",
        }

    return {
        "notice_id": notice_id,
        "compliant": False,
        "reason": "Notice not found in PhilGEPS",
        "source": "mock_data",
    }


# Backwards-compat aliases for callers that imported the private helpers.
_search_mock = _search_mock
_search_by_agency = _find_by_agency
MOCK_PROCUREMENTS = __import__("src.servers.mcp.philgeps_mock", fromlist=["MOCK_PROCUREMENTS"]).MOCK_PROCUREMENTS
