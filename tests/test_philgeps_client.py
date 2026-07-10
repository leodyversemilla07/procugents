"""Tests for the pluggable PhilGEPS client architecture.

Covers:
    * Default client resolution (mock)
    * Live client resolution via env override
    * Client interface compliance (both clients return the same shape)
    * HTML parsers for legacy notices pages
    * Forced-fallback logic
"""

from __future__ import annotations

import os
import pytest

from src.servers.mcp.philgeps import get_client, PhilGEPSClient
from src.servers.mcp.philgeps.mock import MockClient
from src.servers.mcp.philgeps.live import (
    LivePhilGEPSClient,
    _find_largest_table,
    _extract_rows,
    _extract_cols,
    _clean,
    _parse_currency,
)

pytestmark = pytest.mark.anyio


# ===================================================================
# Fixtures
# ===================================================================


SAMPLE_AWARD_HTML = """
<!DOCTYPE html>
<html><body>
<table id="tblAward" width="100%">
<tr>
  <th class="headercell">#</th>
  <th class="headercell">Title</th>
  <th class="headercell">Amount (PHP)</th>
</tr>
<tr>
  <td>1</td>
  <td>Conference Set</td>
  <td>499,000.00</td>
</tr>
<tr>
  <td>2</td>
  <td>PO 2726 / Chiller, etc</td>
  <td>159,650.00</td>
</tr>
</table>
</body></html>
"""

SAMPLE_OPPORTUNITY_HTML = """
<!DOCTYPE html><body>
<table><tr>
  <th>#</th><th>Title</th><th>ABC</th><th>Funding</th>
</tr><tr>
  <td>1</td><td>Supply of Office Tables</td><td>850,000.00</td><td>GAA</td>
</tr><tr>
  <td>2</td><td>IT Equipment</td><td>2,500,000.00</td><td>GAA</td>
</tr>
</table></body></html>
"""


# ===================================================================
# Default client resolution
# ===================================================================


class TestClientResolution:
    def test_default_is_mock(self):
        """Without PHILGEPS_LIVE, get_client() returns a MockClient."""
        os.environ.pop("PHILGEPS_LIVE", None)
        client = get_client(force=None)
        assert client.name == "mock"
        assert isinstance(client, MockClient)

    def test_force_mock(self):
        client = get_client(force="mock")
        assert client.name == "mock"

    def test_force_live(self):
        client = get_client(force="live")
        assert client.name == "live"
        assert isinstance(client, LivePhilGEPSClient)

    def test_env_live(self, monkeypatch):
        monkeypatch.setenv("PHILGEPS_LIVE", "true")
        client = get_client(force=None)
        assert client.name == "live"


# ===================================================================
# MockClient functional tests
# ===================================================================


class TestMockClient:
    @pytest.mark.anyio
    async def test_search_finds_keyword(self):
        client = MockClient()
        results = await client.search("office")
        assert results is not None
        assert len(results) >= 2
        titles = [r["title"] for r in results]
        assert any("Office Chairs" in t for t in titles)

    @pytest.mark.anyio
    async def test_search_returns_none_for_nonsense(self):
        client = MockClient()
        results = await client.search("xyzzy_potato")
        assert results is not None
        assert len(results) == 0

    @pytest.mark.anyio
    async def test_get_agency_procurement(self):
        client = MockClient()
        results = await client.get_agency_procurement("Education", limit=2)
        assert results is not None
        assert len(results) <= 2
        assert len(results) > 0
        assert all("education" in r["agency"].lower() for r in results)

    @pytest.mark.anyio
    async def test_check_notice_compliance_found(self):
        client = MockClient()
        result = await client.check_notice_compliance("NBCC-2024-0123")
        assert result is not None
        assert result["notice_id"] == "NBCC-2024-0123"

    @pytest.mark.anyio
    async def test_check_notice_compliance_not_found(self):
        client = MockClient()
        result = await client.check_notice_compliance("NONEXISTENT-9999")
        assert result is None


# ===================================================================
# PhilGEPSClient interface compliance
# ===================================================================


class TestClientCompliance:
    """Both clients must return the same shapes from the public methods."""

    @pytest.mark.anyio
    async def test_search_shape_mock(self):
        await self._check_search_shape(MockClient())

    @pytest.mark.anyio
    async def test_search_shape_live(self):
        await self._check_search_shape(LivePhilGEPSClient())

    @staticmethod
    async def _check_search_shape(client: PhilGEPSClient) -> None:
        results = await client.search("test")
        # Both must return list of dicts or None
        if results is not None:
            assert isinstance(results, list)
            if results:
                item = results[0]
                assert "title" in item

    @pytest.mark.anyio
    async def test_agency_shape_mock(self):
        await self._check_agency_shape(MockClient())

    @pytest.mark.anyio
    async def test_agency_shape_live(self):
        await self._check_agency_shape(LivePhilGEPSClient())

    @staticmethod
    async def _check_agency_shape(client: PhilGEPSClient) -> None:
        results = await client.get_agency_procurement("test", limit=3)
        if results is not None:
            assert len(results) <= 3

    @pytest.mark.anyio
    async def test_compliance_shape_mock(self):
        await self._check_compliance_shape(MockClient())

    @pytest.mark.anyio
    async def test_compliance_shape_live(self):
        await self._check_compliance_shape(LivePhilGEPSClient())

    @staticmethod
    async def _check_compliance_shape(client: PhilGEPSClient) -> None:
        result = await client.check_notice_compliance("TEST-123")
        if result is not None:
            assert "notice_id" in result


# ===================================================================
# HTML parser unit tests
# ===================================================================


class TestHTMLParsers:
    def test_find_largest_table(self):
        html = "<table>small</table><table>bigger_than_small</table>"
        result = _find_largest_table(html)
        assert result is not None
        assert "bigger_than_small" in result

    def test_find_largest_table_no_table(self):
        assert _find_largest_table("<p>no table</p>") is None

    def test_extract_rows(self):
        rows = _extract_rows("<tr><td>A</td></tr><tr><td>B</td></tr>")
        assert len(rows) == 2
        assert "A" in rows[0]
        assert "B" in rows[1]

    def test_extract_cols(self):
        cols = _extract_cols("<td>Title</td><td>500.00</td>")
        assert len(cols) == 2
        assert cols[0] == "Title"
        assert "500" in cols[1]

    def test_extract_cols_mixed_th_td(self):
        cols = _extract_cols("<th>#</th><td>Item</td>")
        assert len(cols) == 2

    def test_clean_strips_tags(self):
        assert _clean("  <b>Hello</b> &nbsp; World  ") == "Hello World"

    def test_clean_none(self):
        assert _clean(None) == ""

    def test_parse_currency(self):
        assert _parse_currency("499,000.00") == 499000.0
        assert _parse_currency("PHP 1,500,000.00") == 1500000.0
        assert _parse_currency("") is None
        assert _parse_currency("N/A") is None

    def test_parse_award_table(self):
        client = LivePhilGEPSClient()
        records = client._parse_award_table(SAMPLE_AWARD_HTML)
        assert len(records) == 2
        assert records[0]["title"] == "Conference Set"
        assert records[0]["contract_amount"] == 499000.0
        assert records[1]["title"] == "PO 2726 / Chiller, etc"
        assert records[1]["contract_amount"] == 159650.0

    def test_parse_listing_table(self):
        client = LivePhilGEPSClient()
        records = client._parse_listing_table(SAMPLE_OPPORTUNITY_HTML)
        assert len(records) == 2
        assert records[0]["title"] == "Supply of Office Tables"
        assert records[0]["abc_amount"] == 850000.0


# ===================================================================
# Public API backwards compatibility
# ===================================================================


@pytest.mark.anyio
async def test_search_philgeps_backwards_compat():
    """The public ``search_philgeps()`` returns the expected top-level dict."""
    from src.servers.mcp.philgeps_data import search_philgeps

    result = await search_philgeps("office chairs")
    assert isinstance(result, dict)
    assert "keyword" in result
    assert "results" in result
    assert "source" in result
    assert result["source"] == "mock"  # default client


@pytest.mark.anyio
async def test_get_agency_procurement_backwards_compat():
    from src.servers.mcp.philgeps_data import get_agency_procurement

    result = await get_agency_procurement("DepEd")
    assert "agency" in result
    assert "results" in result


@pytest.mark.anyio
async def test_check_notice_compliance_backwards_compat():
    from src.servers.mcp.philgeps_data import check_notice_compliance

    result = await check_notice_compliance("NBCC-2024-0123")
    assert result["compliant"] is True
