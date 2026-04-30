"""Tests for RedFlag Agents PH orchestrator."""

import pytest

from src.orchestration.orchestrator import (
    SVP_THRESHOLD,
    analyze_procurement,
    create_procurement_graph,
    legal_check_node,
    price_analysis_node,
)


@pytest.fixture
def sample_state():
    return {
        "contract_id": "PO-2024-TEST",
        "contract_description": "Test Item",
        "contract_amount": 500_000,
        "svp_category": "general",
    }


class TestLegalCheck:
    """Tests for legal compliance node."""

    def test_svp_compliant(self, sample_state):
        """Test SVP threshold compliance."""
        sample_state["contract_amount"] = 500_000
        result = legal_check_node(sample_state)

        assert result["legal_findings"]["threshold_compliant"] is True
        assert result["legal_findings"]["required_process"] == "small value procurement"
        assert result["legal_findings"]["threshold"] == SVP_THRESHOLD
        assert result["legal_findings"]["violations"] == []

    def test_above_svp_threshold(self, sample_state):
        """Test amounts above SVP threshold."""
        sample_state["contract_amount"] = 2_000_000
        result = legal_check_node(sample_state)

        assert result["legal_findings"]["threshold_compliant"] is False
        assert result["legal_findings"]["required_process"] == "competitive bidding"
        assert len(result["legal_findings"]["violations"]) > 0

    def test_requires_bidding_over_1m(self, sample_state):
        """Test competitive bidding requirement > 1M SVP threshold."""
        sample_state["contract_amount"] = 2_000_000
        result = legal_check_node(sample_state)

        violations = result["legal_findings"]["violations"]
        has_bidding_violation = any("competitive bidding" in v for v in violations)
        assert has_bidding_violation


class TestPriceAnalysis:
    """Tests for price analysis node."""

    def test_unknown_price_without_market_data(self, monkeypatch, sample_state):
        """Test price analysis does not flag without market data."""
        import src.orchestration.orchestrator as orchestrator

        monkeypatch.setattr(orchestrator, "get_cached_market_price", lambda _: None)
        sample_state["contract_amount"] = 100_000
        result = price_analysis_node(sample_state)

        assert result["price_findings"]["flag"] == "unknown"
        assert result["price_findings"]["baseline"] is None
        assert result["price_findings"]["source"] == "unavailable"

    def test_cached_market_price_flags_inflation(self, monkeypatch, sample_state):
        """Test inflated price detection when cached market data exists."""
        import src.orchestration.orchestrator as orchestrator

        monkeypatch.setattr(orchestrator, "get_cached_market_price", lambda _: 100_000)
        sample_state["contract_amount"] = 150_000
        result = price_analysis_node(sample_state)

        assert result["price_findings"]["flag"] == "potential_inflation"
        assert result["price_findings"]["baseline"] == 100_000
        assert result["price_findings"]["inflation_threshold"] == 130_000


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_full_analysis_compliant(self, monkeypatch):
        """Test full analysis for compliant procurement."""
        import src.orchestration.orchestrator as orchestrator

        monkeypatch.setattr(orchestrator, "get_cached_market_price", lambda _: None)
        result = await analyze_procurement(
            contract_id="PO-TEST-001",
            contract_description="Office Chairs",
            contract_amount=500_000,
        )

        assert result["status"] == "completed"
        assert result["legal_findings"]["threshold_compliant"] is True
        assert result["anomalies"] == []

    @pytest.mark.asyncio
    async def test_full_analysis_non_compliant(self):
        """Test full analysis for non-compliant procurement."""
        result = await analyze_procurement(
            contract_id="PO-TEST-002",
            contract_description="IT Equipment",
            contract_amount=5_000_000,
        )

        assert result["status"] == "alerting"
        assert result["legal_findings"]["threshold_compliant"] is False
        assert len(result["anomalies"]) > 0

    @pytest.mark.asyncio
    async def test_graph_creation(self):
        """Test graph can be created."""
        graph = create_procurement_graph()
        assert graph is not None