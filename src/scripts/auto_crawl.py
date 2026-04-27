"""
Auto-crawl & analyze PhilGEPS contracts.
Runs periodically to fetch and analyze new procurement notices.
"""

import asyncio
from datetime import datetime
from typing import Any

from src.orchestration.orchestrator import analyze_procurement
from src.services.database import ProcurementAnalysis, get_db, init_db


# Philippine government agencies to monitor
AGENCIES = [
    {"name": "Department of Education", "keyword": "DepEd"},
    {"name": "Department of Health", "keyword": "DOH"},
    {"name": "DICT", "keyword": "IT equipment"},
    {"name": "Department of Public Works and Highways", "keyword": "construction"},
    {"name": "Civil Service Commission", "keyword": "office supplies"},
]


async def auto_crawl_agency(agency: str, keyword: str | None = None) -> dict[str, Any]:
    """Auto-crawl an agency's PhilGEPS notices and analyze them."""
    from src.servers.mcp.philgeps_data import search_philgeps, get_agency_procurement
    
    results = {
        "agency": agency,
        "analyzed": 0,
        "anomalies_found": 0,
        "contracts": [],
        "timestamp": datetime.now().isoformat(),
    }
    
    try:
        # Get procurements for agency
        procurements = await get_agency_procurement(agency, limit=5)
        procurements_list = procurements.get("results", [])
    except Exception as e:
        # Fallback: search by keyword
        procurements = await search_philgeps(keyword or agency)
        procurements_list = procurements.get("results", [])
    
    init_db()
    db = get_db()
    
    for proc in procurements_list:
        try:
            # Analyze each contract
            title = proc.get("title", "")
            amount = proc.get("abc_amount", proc.get("contract_amount", 0))
            
            if not amount:
                # Estimate from mock data patterns
                amount = 500000  # Default
            
            result = await analyze_procurement(
                contract_id=proc.get("notice_id", f"PO-{proc.get('title', '')[:10]}"),
                contract_description=title,
                contract_amount=amount,
                agency=proc.get("agency", ""),
                source="PhilGEPS",
                svp_category="general",
                save_to_db=True,
            )
            
            results["analyzed"] += 1
            
            # Count anomalies
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
                
        except Exception as e:
            print(f"Error analyzing {proc.get('notice_id')}: {e}")
    
    return results


async def auto_scan_all() -> dict[str, Any]:
    """Scan all known agencies and analyze their recent contracts."""
    all_results = {
        "timestamp": datetime.now().isoformat(),
        "total_analyzed": 0,
        "total_anomalies": 0,
        "agencies": [],
    }
    
    for agency_info in AGENCIES:
        result = await auto_crawl_agency(
            agency_info["name"], 
            keyword=agency_info["keyword"]
        )
        all_results["total_analyzed"] += result["analyzed"]
        all_results["total_anomalies"] += result["anomalies_found"]
        all_results["agencies"].append({
            "name": agency_info["name"],
            "analyzed": result["analyzed"],
            "anomalies": result["anomalies_found"],
        })
    
    return all_results


if __name__ == "__main__":
    import asyncio
    
    async def main():
        result = await auto_scan_all()
        print(f"""
📊 Auto-scan Results
─────────────────
Agencies: {len(result['agencies'])}
Total analyzed: {result['total_analyzed']}
Anomalies found: {result['total_anomalies']}
Timestamp: {result['timestamp']}
        """)
    
    asyncio.run(main())