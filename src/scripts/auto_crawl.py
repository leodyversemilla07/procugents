"""Auto-crawl & analyze PhilGEPS contracts.

Periodically fetches new procurement notices and runs the full 5-agent
analysis pipeline. For each notice the script maps PhilGEPS metadata to
the orchestrator state (procurement_type, bidders, etc.) so the
bid_analyzer and doc_auditor nodes produce meaningful flags.

Scheduler
---------
Call ``start_crawl_scheduler(app_state)`` from the FastAPI lifespan to run
``auto_scan_all`` on a configurable interval. The interval defaults to
60 minutes and can be overridden via the ``CRAWL_INTERVAL_MINUTES``
environment variable.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from src.orchestration.orchestrator import analyze_procurement
from src.services.database import init_db

logger = logging.getLogger(__name__)

# Default / env interval
_DEFAULT_INTERVAL_MINUTES = 60


def _interval_seconds() -> int | None:
    """Crawl interval in seconds, or None to disable the scheduler.

    Returns ``None`` when ``CRAWL_INTERVAL_MINUTES`` is not set, empty,
    or set to a value <= 0. The FastAPI lifespan checks for ``None`` and
    skips starting the background task unless the operator has explicitly
    opted in by setting a positive value.
    """
    raw = os.environ.get("CRAWL_INTERVAL_MINUTES")
    if not raw:
        return None
    try:
        minutes = int(raw)
        if minutes <= 0:
            return None
        return minutes * 60
    except ValueError:
        return None


# Philippine government agencies to monitor
AGENCIES = [
    {"name": "Department of Education", "keyword": "DepEd"},
    {"name": "Department of Health", "keyword": "DOH"},
    {"name": "DICT", "keyword": "IT equipment"},
    {"name": "Department of Public Works and Highways", "keyword": "construction"},
    {"name": "Civil Service Commission", "keyword": "office supplies"},
]

_PHILGEPS_METHOD_MAP: dict[str, str] = {
    "Shopping": "shopping",
    "Public Bidding": "public_bidding",
    "Negotiated Procurement": "negotiated",
    "Direct Contracting": "direct_contracting",
    "SVP": "svp",
}


def _map_procurement_type(method: str | None) -> str:
    """Normalize PhilGEPS procurement_method to internal snake_case type."""
    if not method:
        return "public_bidding"
    return _PHILGEPS_METHOD_MAP.get(method.strip(), "public_bidding")


def _map_agency_to_acronym(agency: str) -> str:
    """Derive a short acronym from long PhilGEPS agency names (for synthetic bidders)."""
    import re
    # e.g. "Department of Education - Central Office" -> "DepEd"
    m = re.search(r"Department of (\w+)", agency)
    if m:
        dept = m.group(1)
        return "".join([c for c in dept if c.isupper()] or [dept[:3].upper()])
    # Fallback: take first 3 uppercase letters or first 3 chars
    uppers = [c for c in agency if c.isupper()]
    if len(uppers) >= 3:
        return "".join(uppers[:3])
    return agency[:3].upper()


def _build_bidders(proc: dict[str, Any]) -> list[dict[str, Any]]:
    """Construct a synthetic bidder list from PhilGEPS notice data.

    In a real system this would come from the PhilGEPS bidder list page.
    For the prototype we fabricate 2-3 bidders so collusion / doc checks fire.
    """
    awardee = proc.get("awardee", "")
    # Ensure at least one bidder even if awardee is missing
    if not awardee:
        return []

    agency_name = proc.get("agency", "")
    acronym = _map_agency_to_acronym(agency_name)

    # IMPORTANT: these bidders are SYNTHETIC — fabricated from the awardee
    # name and an agency-derived stub so the prototype can exercise the
    # bid_analyzer / doc_auditor nodes without real PhilGEPS bidder-list
    # pages (which require an authenticated Platinum session). Every synthetic
    # bidder is tagged with ``synthetic: True`` so the orchestrator and
    # dashboard can distinguish prototype signal from real collusion signal.
    bidders = [
        {
            "name": awardee,
            "address": "Quezon City, Metro Manila (synthetic)",
            "directors": ["Director A"],
            "pcab_license": "12345",
            "nfcc": proc.get("contract_amount", 0) * 2,
            "documents": {
                "philgeps_reg": True,
                "business_permit": True,
                "bid_security": proc.get("contract_amount", 0) * 0.02,
            },
            "synthetic": True,
        },
        # Second synthetic bidder (a competitor with a SHARED address so the
        # prototype surfaces the dummy_bidders flag). Do NOT remove the
        # shared address — it's the fixture for collusion detection.
        {
            "name": f"{acronym} Supplies Co.",
            # Intentionally same address to surface the collusion flag.
            "address": "Quezon City, Metro Manila (synthetic)",
            "directors": ["Director B"],
            "pcab_license": "67890",
            "nfcc": proc.get("contract_amount", 0) * 1.5,
            "documents": {
                "philgeps_reg": True,
                "business_permit": True,
                "bid_security": proc.get("contract_amount", 0) * 0.02,
            },
            "synthetic": True,
        },
    ]
    return bidders


async def auto_crawl_agency(
    agency: str,
    keyword: str | None = None,
) -> dict[str, Any]:
    """Auto-crawl an agency's PhilGEPS notices and analyze them."""
    from src.servers.mcp.philgeps_data import get_agency_procurement, search_philgeps

    results: dict[str, Any] = {
        "agency": agency,
        "analyzed": 0,
        "anomalies_found": 0,
        "contracts": [],
        "timestamp": datetime.now().isoformat(),
    }

    try:
        procurements = await get_agency_procurement(agency, limit=5)
        procurements_list = procurements.get("results", [])
    except Exception:
        procurements = await search_philgeps(keyword or agency)
        procurements_list = procurements.get("results", [])

    init_db()

    for proc in procurements_list:
        try:
            title = proc.get("title", "")
            amount = proc.get("abc_amount", proc.get("contract_amount", 0))
            if not amount:
                amount = 500_000  # Fallback for malformed mock data

            procurement_type = _map_procurement_type(proc.get("procurement_method"))

            result = analyze_procurement(
                contract_id=proc.get("notice_id", f"PO-{title[:10]}"),
                contract_description=title,
                contract_amount=amount,
                agency=proc.get("agency", ""),
                source="PhilGEPS",
                svp_category="general",
                procurement_type=procurement_type,
                bidders=_build_bidders(proc),
                hope_approval_proof=False,  # Mock: assume no HoPE approval on file
                save_to_db=True,
            )

            results["analyzed"] += 1

            # Cache the contract amount as a market-price baseline so the
            # orchestrator's price_analysis_node can reference it on subsequent
            # runs. Uses a cleaned keyword derived from the procurement title.
            # Redis-unavailable errors are silently ignored.
            try:
                from src.services.cache import cache_market_price
                # Derive a short item key from the title (first 2-3 words).
                words = (title or "").split()
                if len(words) >= 3:
                    item_key = " ".join(words[:3]).strip(",;:.").lower()
                elif len(words) >= 1:
                    item_key = " ".join(words).strip(",;:.").lower()
                else:
                    item_key = "uncategorised"
                cache_market_price(item_key, float(amount))
            except Exception:
                pass

            anomalies = result.get("anomalies", [])
            if anomalies:
                results["anomalies_found"] += 1
                results["contracts"].append({
                    "notice_id": proc.get("notice_id"),
                    "title": title,
                    "agency": proc.get("agency"),
                    "amount": amount,
                    "anomalies": anomalies,
                })
        except Exception as exc:
            print(f"Error analyzing {proc.get('notice_id')}: {exc}")

    return results


async def auto_scan_all() -> dict[str, Any]:
    """Scan all known agencies and analyze their recent contracts."""
    all_results: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "total_analyzed": 0,
        "total_anomalies": 0,
        "agencies": [],
    }

    for agency_info in AGENCIES:
        result = await auto_crawl_agency(
            agency_info["name"],
            keyword=agency_info["keyword"],
        )
        all_results["total_analyzed"] += result["analyzed"]
        all_results["total_anomalies"] += result["anomalies_found"]
        all_results["agencies"].append({
            "name": agency_info["name"],
            "analyzed": result["analyzed"],
            "anomalies": result["anomalies_found"],
        })

    return all_results


# ---------------------------------------------------------------------------
# Periodic scheduler — launched from the FastAPI lifespan
# ---------------------------------------------------------------------------


async def crawl_scheduler_loop(
    interval_seconds: int,
    stop_event: asyncio.Event,
) -> None:
    """Background loop that runs ``auto_scan_all()`` on a timer.

    One scan runs immediately on start, then repeats every
    ``interval_seconds`` until ``stop_event`` is set. Exceptions from
    a single scan are caught and logged so the loop continues.
    """
    logger.info(
        "crawl scheduler started (interval=%ds)",
        interval_seconds,
    )
    while not stop_event.is_set():
        try:
            result = await auto_scan_all()
            analyzed = result.get("total_analyzed", 0)
            anomalies = result.get("total_anomalies", 0)
            logger.info(
                "crawl cycle complete: %d contracts, %d anomalies",
                analyzed,
                anomalies,
            )
        except Exception:
            logger.exception("crawl cycle failed")
        # Wait for the interval or until stopped.
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=interval_seconds,
            )
            # If stop_event was set during the wait, exit loop.
            break
        except TimeoutError:
            # Normal — interval elapsed, continue to next cycle.
            pass
    logger.info("crawl scheduler stopped")


if __name__ == "__main__":
    async def main():
        result = await auto_scan_all()
        print(
            f"\n📊 Auto-scan Results\n{'─' * 25}\n"
            f"Agencies: {len(result['agencies'])}\n"
            f"Total analyzed: {result['total_analyzed']}\n"
            f"Anomalies found: {result['total_anomalies']}\n"
            f"Timestamp: {result['timestamp']}\n"
        )

    asyncio.run(main())
