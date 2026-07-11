"""Price Analysis agent for the ProcuGents orchestrator.

Compares the contract amount against a market baseline. Resolution order:

1. Redis cache (``get_cached_market_price``) — fastest, used for repeated items.
2. Exa API live search (when ``EXA_API_KEY`` env var is set) — real market data
   from government procurement pages.
3. ``unknown`` — honest fallback when no data source is available.

Flags a procurement as ``potential_inflation`` when the amount exceeds the
baseline by more than the COA 2023-004 benchmark (30%).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from src.orchestration.state import (
    PRICE_EXCESS_THRESHOLD_PCT,
    ProcurementState,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Redis cache helpers
# ---------------------------------------------------------------------------


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


def _cache_market_price(item_name: str, price: float) -> None:
    """Write a market price to Redis for future lookups."""
    try:
        from src.services.cache import cache_market_price

        cache_market_price(item_name, price)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Exa API live search (fallback when cache misses)
# ---------------------------------------------------------------------------


async def _search_exa_price(item_name: str) -> float | None:
    """Query the Exa API for a market price estimate.

    Returns the lowest contract price found (conservative baseline), or
    ``None`` when ``EXA_API_KEY`` is unset / the API returns no useful data.
    The caller is responsible for caching the result.
    """
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        return None

    import httpx

    query = (
        f"Philippine government procurement \"{item_name}\""
        " contract awarded price PHP"
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "num_results": 5,
                    "category": "government",
                },
                timeout=15.0,
            )
            if resp.status_code != 200:
                logger.debug("Exa API returned %s", resp.status_code)
                return None

            data = resp.json()
            results: list[dict[str, Any]] = data.get("results") or []
            prices: list[float] = []
            for item in results:
                snippet: str = (item.get("text") or item.get("snippet") or "")
                # Crude PHP-amount extraction: look for "PHP X,XXX"
                # or "₱X,XXX.XX" or plain numbers near "million" / "thousand".
                import re

                for match in re.finditer(
                    r"(?:PHP|₱|P\s)?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
                    snippet,
                ):
                    try:
                        prices.append(float(match.group(1).replace(",", "")))
                    except ValueError:
                        continue
            if prices:
                # Use the lowest found price as a conservative market baseline.
                return min(p for p in prices if p > 0)
    except Exception as exc:
        logger.debug("Exa API search failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Orchestrator node
# ---------------------------------------------------------------------------


def _run_async(coro):
    """Run an async coroutine synchronously, handling running-loop scenarios."""
    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False
    if running:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


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
        logger.info(
            "price cache hit",
            extra={"item": description, "baseline": cached},
        )
    else:
        # Cache miss — try Exa API live search before giving up.
        logger.info(
            "price cache miss, trying Exa API",
            extra={"item": description},
        )
        try:
            exa_price = _run_async(_search_exa_price(description))
            if exa_price is not None and exa_price > 0:
                baseline = exa_price
                inflation_threshold = exa_price * inflation_multiplier
                source = "exa_api"
                logger.info(
                    "exa price found",
                    extra={"item": description, "baseline": exa_price},
                )
                # Cache it for next time.
                _cache_market_price(description, exa_price)
            else:
                source = "unavailable"
        except Exception as exc:
            logger.debug("Exa price lookup failed: %s", exc)
            source = "unavailable"

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
