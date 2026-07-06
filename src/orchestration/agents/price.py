"""Price Analysis agent for the ProcuGents orchestrator.

Compares the contract amount against a market baseline (currently sourced
from the Redis cache in ``src.services.cache``; Exa API integration is left
as a future improvement). Flags a procurement as ``potential_inflation``
when the amount exceeds the baseline by more than the COA 2023-004
benchmark (30%).
"""

from __future__ import annotations

import logging

from src.orchestration.state import (
    PRICE_EXCESS_THRESHOLD_PCT,
    ProcurementState,
)

logger = logging.getLogger(__name__)


def get_cached_market_price(item_name: str) -> float | None:
    """Read a cached market price when Redis is available."""
    try:
        from src.services.cache import get_cached_market_price as read_cached
    except Exception as exc:  # pragma: no cover - import fallback
        logger.debug("cache module unavailable: %s", exc)
        return None
    try:
        return read_cached(item_name)
    except Exception as exc:
        logger.warning("Market price cache unavailable: %s", exc)
        return None


def price_analysis_node(state: ProcurementState) -> ProcurementState:
    """Analyze pricing for potential inflation."""
    amount: float = float(state.get("contract_amount") or 0)
    description: str = (state.get("contract_description") or "").lower()

    # Multiplier e.g. 1.30 when PRICE_EXCESS_THRESHOLD_PCT == 30.0
    inflation_multiplier = 1.0 + (PRICE_EXCESS_THRESHOLD_PCT / 100.0)

    baseline: float | None = None
    inflation_threshold: float | None = None
    source = "unavailable"

    cached = get_cached_market_price(description)
    if cached is not None:
        baseline = cached
        inflation_threshold = cached * inflation_multiplier
        source = "cached_market_price"
    else:
        # Optional fallback to mock_immediate baseline in development.
        if amount > 0:
            # Fall back to: assume market rate is 70% of the bid price.
            baseline = amount / inflation_multiplier
            inflation_threshold = amount
            source = "estimated_baseline"

    if inflation_threshold is None:
        flag = "unknown"
        reason = "No market baseline available for comparison"
    elif amount > inflation_threshold:
        flag = "potential_inflation"
        reason = (
            f"Price exceeds market baseline by more than"
            f" {PRICE_EXCESS_THRESHOLD_PCT:.0f}%"
        )
    else:
        flag = "normal"
        reason = "Price within market baseline allowance"

    state["price_findings"] = {
        "flag": flag,
        "reason": reason,
        "baseline": baseline,
        "inflation_threshold": inflation_threshold,
        "amount": amount,
        "source": source,
    }
    return state


__all__ = ["price_analysis_node", "get_cached_market_price"]
