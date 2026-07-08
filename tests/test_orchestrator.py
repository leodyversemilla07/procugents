"""Tests for ProcuGents orchestrator and per-agent nodes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.orchestration.agents.bid import bid_analyzer_node
from src.orchestration.agents.doc import doc_auditor_node
from src.orchestration.agents.legal import legal_check_node
from src.orchestration.agents.price import (
    price_analysis_node,
)
from src.orchestration.orchestrator import (
    SVP_THRESHOLD,
    analyze_procurement,
    create_procurement_graph,
)


@pytest.fixture
def sample_state():
    return {
        "contract_id": "PO-2024-TEST",
        "contract_description": "Test Item",
        "contract_amount": 500_000,
        "svp_category": "general",
        "procurement_type": "public_bidding",
        "bidders": [],
        "hope_approval_proof": False,
    }


# ------------------------- legal_check_node -------------------------


class TestLegalCheck:
    """Tests for legal compliance node."""

    def test_svp_compliant(self, sample_state):
        sample_state["contract_amount"] = 500_000
        result = legal_check_node(sample_state)

        assert result["legal_findings"]["threshold_compliant"] is True
        assert result["legal_findings"]["required_process"] == "small value procurement"
        assert result["legal_findings"]["threshold"] == SVP_THRESHOLD
        assert result["legal_findings"]["violations"] == []

    def test_above_svp_threshold(self, sample_state):
        sample_state["contract_amount"] = 2_000_000
        result = legal_check_node(sample_state)

        assert result["legal_findings"]["threshold_compliant"] is False
        assert result["legal_findings"]["required_process"] == "competitive bidding"
        assert len(result["legal_findings"]["violations"]) > 0

    def test_requires_bidding_over_1m(self, sample_state):
        sample_state["contract_amount"] = 2_000_000
        result = legal_check_node(sample_state)

        violations = result["legal_findings"]["violations"]
        assert any("competitive bidding" in v for v in violations)


# ------------------------- price_analysis_node -------------------------


class TestPriceAnalysis:
    """Tests for price analysis node."""

    def test_unknown_price_without_market_data(self, monkeypatch, sample_state):
        """When no market data is available, fallback baseline kicks in."""
        from src.orchestration.agents import price as price_mod

        monkeypatch.setattr(price_mod, "get_cached_market_price", lambda _: None)
        sample_state["contract_amount"] = 100_000
        result = price_analysis_node(sample_state)

        # No cache -> estimated_baseline is computed (amount / 1.30),
        # which means the flag will NOT be "unknown".
        assert result["price_findings"]["flag"] in {"normal", "unknown"}
        assert result["price_findings"]["baseline"] is not None
        assert result["price_findings"]["source"] == "estimated_baseline"

    def test_cached_market_price_flags_inflation(self, monkeypatch, sample_state):
        """Cached market data exposes inflation when over threshold."""
        from src.orchestration.agents import price as price_mod

        monkeypatch.setattr(price_mod, "get_cached_market_price", lambda _: 100_000)
        sample_state["contract_amount"] = 150_000
        result = price_analysis_node(sample_state)

        assert result["price_findings"]["flag"] == "potential_inflation"
        assert result["price_findings"]["baseline"] == 100_000
        assert result["price_findings"]["inflation_threshold"] == 130_000


# ------------------------- bid_analyzer_node -------------------------


class TestBidAnalyzer:
    def test_no_metadata_emits_no_flags(self, sample_state):
        sample_state["bidders"] = []
        result = bid_analyzer_node(sample_state)
        assert result["bid_flags"] == []
        assert result["bid_risk_score"] == 1
        assert result["bid_citations"] == []

    def test_less_than_three_bidders(self, sample_state):
        sample_state["bidders"] = [
            {"name": "Acme", "address": "Quezon City", "directors": ["A"]},
        ]
        result = bid_analyzer_node(sample_state)
        assert any(f["flag"] == "less_than_3_bidders" for f in result["bid_flags"])
        assert result["bid_risk_score"] >= 4

    def test_shared_address_collusion(self, sample_state):
        sample_state["bidders"] = [
            {"name": "Acme", "address": "Same Street 1", "directors": []},
            {"name": "Beta", "address": "Same Street 1", "directors": []},
        ]
        result = bid_analyzer_node(sample_state)
        assert any(f["flag"] == "dummy_bidders" for f in result["bid_flags"])
        assert result["bid_risk_score"] == 5

    def test_alt_mode_without_hope_approval(self, sample_state):
        sample_state["procurement_type"] = "shopping"
        sample_state["contract_amount"] = 2_000_000
        sample_state["hope_approval_proof"] = False
        result = bid_analyzer_node(sample_state)
        assert any(f["flag"] == "alt_mode_no_hope_approval" for f in result["bid_flags"])

    def test_insufficient_nfcc_flagged(self, sample_state):
        sample_state["bidders"] = [
            {"name": "Acme", "address": "Q", "directors": ["X"], "nfcc": 100_000},
        ]
        sample_state["contract_amount"] = 2_000_000
        result = bid_analyzer_node(sample_state)
        assert any(f["flag"] == "insufficient_nfcc" for f in result["bid_flags"])


# ------------------------- doc_auditor_node -------------------------


class TestDocAuditor:
    def test_missing_philgeps_registration(self, sample_state):
        sample_state["bidders"] = [
            {
                "name": "Acme",
                "documents": {"philgeps_reg": False, "business_permit": True},
            },
        ]
        result = doc_auditor_node(sample_state)
        flags = {f["flag"] for f in result["doc_flags"]}
        assert "missing_philgeps_registration" in flags

    def test_missing_business_permit(self, sample_state):
        sample_state["bidders"] = [
            {
                "name": "Acme",
                "documents": {"philgeps_reg": True, "business_permit": False},
            },
        ]
        result = doc_auditor_node(sample_state)
        flags = {f["flag"] for f in result["doc_flags"]}
        assert "missing_business_permit" in flags

    def test_missing_bid_security_above_svp(self, sample_state):
        sample_state["contract_amount"] = 2_000_000
        sample_state["procurement_type"] = "public_bidding"
        sample_state["bidders"] = [
            {
                "name": "Acme",
                "documents": {"bid_security": None, "philgeps_reg": True, "business_permit": True},
            },
        ]
        result = doc_auditor_node(sample_state)
        flags = {f["flag"] for f in result["doc_flags"]}
        assert "missing_bid_security" in flags

    def test_alt_mode_triggers_global_flag(self, sample_state):
        sample_state["procurement_type"] = "svp"
        sample_state["contract_amount"] = 2_000_000
        sample_state["hope_approval_proof"] = False
        result = doc_auditor_node(sample_state)
        flags = {f["flag"] for f in result["doc_flags"]}
        assert "alt_mode_no_hope_approval" in flags


# ------------------------- Integration (full graph) -------------------------


class TestIntegration:
    def test_full_analysis_compliant(self, monkeypatch):
        from src.orchestration.agents import price as price_mod

        monkeypatch.setattr(price_mod, "get_cached_market_price", lambda _: None)

        result = analyze_procurement(
            contract_id="PO-TEST-001",
            contract_description="Office Chairs",
            contract_amount=500_000,
        )

        assert result["status"] in {"completed", "alerting"}
        assert result["legal_findings"]["threshold_compliant"] is True

    def test_full_analysis_non_compliant(self):
        result = analyze_procurement(
            contract_id="PO-TEST-002",
            contract_description="IT Equipment",
            contract_amount=5_000_000,
            procurement_type="public_bidding",
        )

        assert result["status"] == "alerting"
        assert result["legal_findings"]["threshold_compliant"] is False
        assert len(result["anomalies"]) > 0
        # bid_analyzer is in the graph but emits no flags without bidders.
        assert "bid_flags" in result
        assert "doc_flags" in result

    def test_full_analysis_with_collusive_bidders(self):
        result = analyze_procurement(
            contract_id="PO-TEST-003",
            contract_description="Office Supplies",
            contract_amount=900_000,
            procurement_type="public_bidding",
            bidders=[
                {"name": "Acme", "address": "Same Street", "directors": [], "documents": {}},
                {"name": "Beta", "address": "Same Street", "directors": [], "documents": {}},
            ],
        )

        assert result["final_risk_score"] >= 4
        assert result["alert_triggered"] is True
        # Bid analyzer should flag the shared address.
        assert any(f["flag"] == "dummy_bidders" for f in result["bid_flags"])

    def test_graph_creation(self):
        graph = create_procurement_graph()
        assert graph is not None


# ------------------------- API filter tests ------------------------------------


class TestApiFilters:
    """Verify ``/api/analyses`` filter params work end-to-end."""

    def _setup_two_rows(self, tmp_db_session):
        from src.services.database import ProcurementAnalysis

        tmp_db_session.add_all([
            ProcurementAnalysis(
                contract_id="HIGH-RISK-001",
                contract_description="Construction",
                contract_amount=5_000_000,
                agency="Department of Public Works",
                final_risk_score=5,
                alert_triggered=1,
            ),
            ProcurementAnalysis(
                contract_id="LOW-RISK-002",
                contract_description="Office Supplies",
                contract_amount=500_000,
                agency="Civil Service Commission",
                final_risk_score=1,
                alert_triggered=0,
            ),
        ])
        tmp_db_session.commit()

    def test_min_risk_filter(self, monkeypatch):
        """Only rows with risk >= the threshold are returned."""
        from src.services.database import get_db, init_db

        monkeypatch.setenv("POSTGRES_PASSWORD", "")  # force SQLite
        init_db()

        with get_db() as db:
            self._setup_two_rows(db)

        client = TestClient(__import__("src.api.main", fromlist=["app"]).app)
        resp = client.get("/api/analyses?min_risk=4&limit=10")
        ids = [r["contract_id"] for r in resp.json()]
        assert "HIGH-RISK-001" in ids
        assert "LOW-RISK-002" not in ids

    def test_alerted_only_filter(self, monkeypatch):
        """``alerted_only=true`` excludes rows without alerts."""
        from src.services.database import get_db, init_db

        monkeypatch.setenv("POSTGRES_PASSWORD", "")
        init_db()

        with get_db() as db:
            self._setup_two_rows(db)

        client = TestClient(__import__("src.api.main", fromlist=["app"]).app)
        resp = client.get("/api/analyses?alerted_only=true&limit=10")
        ids = [r["contract_id"] for r in resp.json()]
        assert "HIGH-RISK-001" in ids
        assert "LOW-RISK-002" not in ids

    def test_q_substring_filter(self, monkeypatch):
        """``q=...`` matches against contract_id or description."""
        from src.services.database import get_db, init_db

        monkeypatch.setenv("POSTGRES_PASSWORD", "")
        init_db()

        with get_db() as db:
            self._setup_two_rows(db)

        client = TestClient(__import__("src.api.main", fromlist=["app"]).app)

        # match via description substring
        desc_match = client.get("/api/analyses?q=supplies&limit=10")
        ids = [r["contract_id"] for r in desc_match.json()]
        assert "LOW-RISK-002" in ids
        assert "HIGH-RISK-001" not in ids

        # match via contract_id substring
        id_match = client.get("/api/analyses?q=HIGH&limit=10")
        ids = [r["contract_id"] for r in id_match.json()]
        assert "HIGH-RISK-001" in ids
        assert "LOW-RISK-002" not in ids

    def test_agency_filter(self, monkeypatch):
        """``agency=...`` does a case-insensitive substring match."""
        from src.services.database import get_db, init_db

        monkeypatch.setenv("POSTGRES_PASSWORD", "")
        init_db()

        with get_db() as db:
            self._setup_two_rows(db)

        client = TestClient(__import__("src.api.main", fromlist=["app"]).app)
        resp = client.get("/api/analyses?agency=civil&limit=10")
        ids = [r["contract_id"] for r in resp.json()]
        assert "LOW-RISK-002" in ids
        assert "HIGH-RISK-001" not in ids
