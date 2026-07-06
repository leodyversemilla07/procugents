"""Scraping agent for the ProcuGents orchestrator.

Looks up related procurements in PhilGEPS using the shared
``src.servers.mcp.philgeps_data`` scraper (which falls back to mock data
if the live endpoint requires auth).

This node is sync, but the scraper is async. Detect whether we're already
inside an event loop (when the graph is invoked via ``ainvoke``) and
dispatch the coroutine to a worker thread if so.
"""

from __future__ import annotations

import asyncio
import concurrent.futures

from src.orchestration.state import ProcurementState


def _run_async(coro):
    """Run an async coroutine, returning its result synchronously.

    If a loop is already running on this thread (LangGraph ainvoke case),
    we execute the coroutine on a worker thread which gives it its own loop.
    """
    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False

    if running:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def scraping_node(state: ProcurementState) -> ProcurementState:
    """Scrape PhilGEPS for related procurements."""
    description: str = state.get("contract_description") or ""
    agency: str = state.get("agency") or ""

    try:
        from src.servers.mcp.philgeps_data import (
            get_agency_procurement,
            search_philgeps,
        )

        if agency:
            result = _run_async(get_agency_procurement(agency_name=agency, limit=5))
        else:
            result = _run_async(search_philgeps(keyword=description, category="goods"))

        results = result.get("results", [])
        state["scraping_results"] = {
            "results": results,
            "source": result.get("source", "unknown"),
            "searched": description,
            "note": f"Found {len(results)} related procurements",
        }
    except Exception as exc:
        state["scraping_results"] = {
            "results": [],
            "source": "fallback",
            "searched": description,
            "note": f"Scraper unavailable: {str(exc)[:50]}",
        }

    return state


__all__ = ["scraping_node"]
