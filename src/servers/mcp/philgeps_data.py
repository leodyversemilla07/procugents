"""PhilGEPS data-access layer using the pluggable client registry.

Public functions (unchanged signature for backwards compatibility):
    search_philgeps(keyword, category, year) -> dict
    get_agency_procurement(agency_name, year, limit) -> dict
    check_notice_compliance(notice_id) -> dict

Each function delegates to the client returned by
``src.servers.mcp.philgeps.get_client()``, which is the mock client by
default and the live HTTP scraper when ``PHILGEPS_LIVE=true``.
"""

from __future__ import annotations

import logging
from typing import Any

from src.servers.mcp.philgeps import get_client
from src.servers.mcp.philgeps_mock import (
    find_by_agency as _find_by_agency,
    find_by_notice as _find_by_notice,
    search_mock as _search_mock,
)

# Backwards-compat: prior code referenced an internal _search_by_agency symbol.
_search_by_agency = _find_by_agency

logger = logging.getLogger(__name__)


async def search_philgeps(
    keyword: str,
    category: str = "goods",
    year: int | None = None,
) -> dict[str, Any]:
    """Search PhilGEPS for government procurement opportunities."""
    client = get_client()
    results = await client.search(keyword=keyword, category=category, year=year)
    if results is not None:
        return {
            "keyword": keyword,
            "category": category,
            "year": year,
            "source": client.name,
            "results": results,
        }

    # Fallback: mock (should not normally be reached — mock never returns None)
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
    client = get_client()
    results = await client.get_agency_procurement(
        agency_name=agency_name, year=year, limit=limit
    )
    if results is not None:
        return {
            "agency": agency_name,
            "year": year,
            "source": client.name,
            "results": results,
        }

    return {
        "agency": agency_name,
        "year": year,
        "source": "mock_data",
        "results": _find_by_agency(agency_name)[:limit],
    }


async def check_notice_compliance(notice_id: str) -> dict[str, Any]:
    """Check PhilGEPS posting compliance for a specific notice."""
    client = get_client()
    item = await client.check_notice_compliance(notice_id)
    if item is not None:
        return {**item, "compliant": True, "source": client.name}

    # Fallback to mock lookup
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
