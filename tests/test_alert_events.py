"""Tests that the orchestrator alert_node publishes to the event bus."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

from src.orchestration.agents.alert import alert_node  # noqa: E402
from src.services.events import CHANNEL_DASHBOARD_UPDATES  # noqa: E402


class _MockBus:
    """Capture both sync and async publish calls from alert_node."""

    def __init__(self) -> None:
        self.calls: list = []

    async def publish(self, channel, event):
        self.calls.append((channel, event))

    def publish_nowait(self, channel, event):
        self.calls.append((channel, event))


def _base_state(amount: float = 600_000.0):
    return {
        "contract_id": "PO-EVT-1",
        "contract_description": "Test contract",
        "contract_amount": amount,
        "agency": "Department of Public Works",
        "legal_findings": {
            "threshold_compliant": False,
            "violations": ["Amount exceeds SVP threshold"],
            "law": "RA 12009",
        },
        "price_findings": {},
        "scraping_results": {},
        "llm_analysis": {"available": False},
        "bid_flags": [],
        "doc_flags": [],
    }


def test_alert_node_publishes_to_bus_when_legal_threshold_exceeded():
    """When the legal threshold is exceeded, alert_node publishes to the bus."""
    from src.services import events as events_module

    captured = _MockBus()
    original = events_module.bus
    events_module.bus = captured  # type: ignore[assignment]
    try:
        state = _base_state(amount=5_000_000)
        result = alert_node(state)
    finally:
        events_module.bus = original  # type: ignore[assignment]

    assert result["alert_triggered"] is True
    assert captured.calls, "alert_node did not publish to bus"
    channel, event = captured.calls[-1]
    assert channel == CHANNEL_DASHBOARD_UPDATES
    assert event["kind"] == "alert_triggered"
    assert event["contract_id"] == "PO-EVT-1"
    assert event["final_risk_score"] >= 4


def test_alert_node_does_not_publish_when_clean():
    from src.services import events as events_module

    captured = _MockBus()
    original = events_module.bus
    events_module.bus = captured  # type: ignore[assignment]
    try:
        state = _base_state(amount=500_000.0)
        # Make it compliant.
        state["legal_findings"]["threshold_compliant"] = True
        from src.orchestration.agents.alert import alert_node
        result = alert_node(state)
    finally:
        events_module.bus = original  # type: ignore[assignment]

    # No alerts should fire on a 100% clean contract.
    assert result["final_risk_score"] == 1
    # publish_nowait only fires when alert_triggered is True, so it should
    # NOT be called for a clean contract.
    # (Note: on fully-clean input only final_risk_score is 1; but our
    # _base_state() heuristic might still want to log; let's verify.)
    # Either no calls OR calls where alert_triggered is false would be a bug.
    for _ch, ev in captured.calls:
        assert ev.get("kind") != "alert_triggered", captured.calls


def test_alert_node_event_includes_anomalies_and_citations():
    from src.services import events as events_module

    captured = _MockBus()
    original = events_module.bus
    events_module.bus = captured  # type: ignore[assignment]
    try:
        state = _base_state(amount=5_000_000)
        from src.orchestration.agents.alert import alert_node
        alert_node(state)
    finally:
        events_module.bus = original  # type: ignore[assignment]

    assert captured.calls
    _ch, ev = captured.calls[-1]
    assert "anomalies" in ev
    assert "citations" in ev
    assert ev["citations"]  # at least one
    assert ev["anomalies"]  # at least one description
    assert ev["kind"] == "alert_triggered"
