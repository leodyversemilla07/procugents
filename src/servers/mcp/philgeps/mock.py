"""Mock PhilGEPS client used when no live credentials are configured.

Returns deterministic data derived from the in-memory procurement fixture.
"""

from __future__ import annotations

import logging
from typing import Any

from src.servers.mcp.philgeps_mock import (
    find_by_agency,
    find_by_notice,
    search_mock,
)

logger = logging.getLogger(__name__)


class MockClient:
    """Client that always returns the fixture data.

    Use this in dev/test where there's no live PhilGEPS connectivity.
    """

    name = "mock"

    async def search(
        self,
        keyword: str,
        category: str = "goods",
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        logger.debug("mock client search kw=%s cat=%s year=%s", keyword, category, year)
        return search_mock(keyword)

    async def get_agency_procurement(
        self,
        agency_name: str,
        year: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        items = find_by_agency(agency_name)
        return items[:limit]

    async def check_notice_compliance(self, notice_id: str) -> dict[str, Any] | None:
        return find_by_notice(notice_id)


def make_mock_client() -> MockClient:
    return MockClient()
