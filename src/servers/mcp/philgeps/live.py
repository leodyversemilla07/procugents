"""Live HTTP client that scrapes the legacy PhilGEPS notices pages.

The modernized PhilGEPS portal (philgeps.gov.ph) and Open Data analytics
dashboard (open.philgeps.gov.ph) are JS-driven / require session auth, so
we target the legacy ``notices.philgeps.gov.ph`` pages which return
server-rendered HTML.

Two public surfaces are scrapable without authentication:

    * Recent Award Notices   – ``/GEPSNONPILOT/Tender/RecentAwardNoticeUI.aspx``
    * Open Opportunities     – ``/GEPSNONPILOT/Tender/SplashOpenOpportunitiesUI.aspx``

Cookies can be supplied via ``PHILGEPS_COOKIE_FILE`` (a cookie jar in
Netscape format, exported from a browser session with a Platinum account)
to unlock more detailed pages.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEGACY_BASE = "https://notices.philgeps.gov.ph"
USER_AGENT = "ProCuGents/0.1 (+https://github.com/leodyversemilla07/procugents)"
DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MAX_RECORDS = 50

# ---------------------------------------------------------------------------
# Cookie jar helper
# ---------------------------------------------------------------------------


def _load_cookies() -> dict[str, str]:
    """Return cookie dict from ``PHILGEPS_COOKIE_FILE``, or empty."""
    path = os.environ.get("PHILGEPS_COOKIE_FILE")
    if not path:
        return {}
    try:
        from http.cookiejar import MozillaCookieJar

        jar = MozillaCookieJar(str(Path(path).resolve()))
        jar.load(ignore_discard=True, ignore_expires=True)
        return {c.name: c.value for c in jar}
    except Exception as exc:
        logger.warning("failed to load PHILGEPS cookies from %s: %s", path, exc)
        return {}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LivePhilGEPSClient:
    """Scrapes legacy PhilGEPS pages for procurement notices.

    Attempts live scraping first; whenever an endpoint returns a non-200
    or zero-results, *returns None* so the caller can fall back to mock.
    """

    name = "live"

    def __init__(
        self,
        *,
        cookies: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self._cookies = cookies or _load_cookies()
        self._timeout = timeout or DEFAULT_TIMEOUT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        keyword: str,
        category: str = "goods",
        year: int | None = None,
    ) -> list[dict[str, Any]] | None:
        """Search open opportunities by keyword."""
        raw = await self._fetch_opportunities(keyword=keyword, year=year)
        return raw

    async def get_agency_procurement(
        self,
        agency_name: str,
        year: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]] | None:
        """Search by agency name."""
        raw = await self._fetch_opportunities(keyword=agency_name, year=year)
        if not raw:
            return None
        return raw[:limit]

    async def check_notice_compliance(self, notice_id: str) -> dict[str, Any] | None:
        """Check whether a notice_id is posted on PhilGEPS."""
        # Try the search endpoint: if the ID exists, we know it is compliant.
        raw = await self._fetch_opportunities(keyword=notice_id)
        if not raw:
            return None
        return {
            "notice_id": notice_id,
            "title": raw[0].get("title", ""),
            "agency": raw[0].get("agency", ""),
        }

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    async def _fetch_opportunities(
        self,
        keyword: str | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]] | None:
        """Fetch open opportunities listing page and parse rows."""
        url = f"{LEGACY_BASE}/GEPSNONPILOT/Tender/SplashOpenOpportunitiesUI.aspx"
        params: dict[str, str] = {"menuIndex": "3"}
        if keyword:
            params["keyword"] = keyword
        if year:
            params["year"] = str(year)

        page = await self._get(url, params=params)
        if page is None:
            return None

        records = self._parse_listing_table(page)
        return records[:MAX_RECORDS] if records else None

    async def _fetch_award_notices(
        self,
        keyword: str | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]] | None:
        """Fetch recent award notices listing."""
        url = f"{LEGACY_BASE}/GEPSNONPILOT/Tender/RecentAwardNoticeUI.aspx"
        params: dict[str, str] = {"menuIndex": "3"}
        if keyword:
            params["keyword"] = keyword
        if year:
            params["year"] = str(year)

        page = await self._get(url, params=params)
        if page is None:
            return None

        records = self._parse_award_table(page)
        return records[:MAX_RECORDS] if records else None

    # ------------------------------------------------------------------
    # HTTP transport
    # ------------------------------------------------------------------

    async def _get(
        self,
        url: str,
        params: dict[str, str] | None = None,
    ) -> str | None:
        """Perform a GET with user-agent and cookies, return HTML text."""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                cookies=self._cookies,
            ) as client:
                headers = {
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                resp = await client.get(
                    url,
                    params=params,
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.warning("PhilGEPS %s returned %d", url.split("?")[0], resp.status_code)
                    return None
                return resp.text
        except httpx.HTTPError as exc:
            logger.warning("PhilGEPS GET error for %s: %s", url.split("?")[0], exc)
            return None

    # ------------------------------------------------------------------
    # HTML parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_listing_table(html: str) -> list[dict[str, Any]]:
        """Extract rows from an open-opportunities listing table."""
        records: list[dict[str, Any]] = []
        # The legacy site renders data in a <table> with rows like
        #   <tr><td>1</td><td>Title</td><td>Amount</td></tr>
        table = _find_largest_table(html)
        if not table:
            return records

        rows = _extract_rows(table)
        # Skip header row (contains <th> or column labels)
        for row in rows[1:]:
            cols = _extract_cols(row)
            if len(cols) < 2:
                continue
            records.append(
                {
                    "title": _clean(cols[1]) if len(cols) > 1 else "",
                    "abc_amount": _parse_currency(cols[2]) if len(cols) > 2 else None,
                    "source_url": LEGACY_BASE,
                }
            )
        return records

    @staticmethod
    def _parse_award_table(html: str) -> list[dict[str, Any]]:
        """Extract rows from a recent-award-notices table (2 cols: Title, Amount)."""
        records: list[dict[str, Any]] = []
        table = _find_largest_table(html)
        if not table:
            return records

        rows = _extract_rows(table)
        for row in rows[1:]:
            cols = _extract_cols(row)
            if len(cols) < 2:
                continue
            records.append(
                {
                    "title": _clean(cols[1]) if len(cols) > 1 else _clean(cols[0]),
                    "contract_amount": _parse_currency(cols[-1]),
                    "source_url": LEGACY_BASE,
                }
            )
        return records


# ---------------------------------------------------------------------------
# Module-level HTML helpers (shared by statics)
# ---------------------------------------------------------------------------


def _find_largest_table(html: str) -> str | None:
    """Return the HTML of the <table> with the most bytes in ``html``."""
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, flags=re.DOTALL | re.IGNORECASE)
    if not tables:
        return None
    return max(tables, key=len)


def _extract_rows(table_html: str) -> list[str]:
    """Return list of ``<tr>...</tr>`` fragments."""
    return re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.DOTALL | re.IGNORECASE)


def _extract_cols(row_html: str) -> list[str]:
    """Return list of inner HTML of each ``<td>`` or ``<th>`` in the row."""
    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.DOTALL | re.IGNORECASE)
    return cells


def _clean(text: str | None) -> str:
    """Strip tags and normalise whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_currency(text: str | None) -> float | None:
    """Parse a PHP currency string like ``"499,000.00"`` into a float."""
    cleaned = _clean(text) if text else ""
    cleaned = cleaned.replace(",", "").replace("PHP", "").replace(" ", "")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_live_client() -> LivePhilGEPSClient:
    return LivePhilGEPSClient()
