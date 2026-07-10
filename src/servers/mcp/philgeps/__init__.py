"""Pluggable PhilGEPS client registry.

Usage::

    from src.servers.mcp.philgeps import get_client

    client = get_client()
    results = await client.search("office chairs")
    proc = await client.get_agency_procurement("DepEd")
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class PhilGEPSClient(Protocol):
    """Interface every PhilGEPS client must implement."""

    @property
    def name(self) -> str: ...

    async def search(
        self,
        keyword: str,
        category: str = "goods",
        year: int | None = None,
    ) -> list[dict[str, Any]] | None: ...

    async def get_agency_procurement(
        self,
        agency_name: str,
        year: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]] | None: ...

    async def check_notice_compliance(
        self,
        notice_id: str,
    ) -> dict[str, Any] | None: ...


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

_LIVE_CLIENT: PhilGEPSClient | None = None
_MOCK_CLIENT: PhilGEPSClient | None = None


def _env_prefer_live() -> bool:
    """Return True when the operator explicitly opted into live scraping."""
    val = os.environ.get("PHILGEPS_LIVE", "").strip().lower()
    return val in ("1", "true", "yes", "live")


def get_client(*, force: str | None = None) -> PhilGEPSClient:
    """Return the globally-configured PhilGEPS client.

    ``force`` can be ``"mock"`` or ``"live"`` to bypass auto-detection.
    Uses mock by default unless ``PHILGEPS_LIVE=true`` is set.
    """
    global _LIVE_CLIENT, _MOCK_CLIENT

    choice = force or ("live" if _env_prefer_live() else "mock")
    if choice == "live":
        if _LIVE_CLIENT is None:
            from src.servers.mcp.philgeps.live import make_live_client

            _LIVE_CLIENT = make_live_client()
        logger.debug("using live PhilGEPS client")
        return _LIVE_CLIENT
    else:
        if _MOCK_CLIENT is None:
            from src.servers.mcp.philgeps.mock import make_mock_client

            _MOCK_CLIENT = make_mock_client()
        logger.debug("using mock PhilGEPS client")
        return _MOCK_CLIENT


__all__ = [
    "get_client",
    "PhilGEPSClient",
]
