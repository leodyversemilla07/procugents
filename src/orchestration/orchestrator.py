"""
LangGraph Orchestrator for RedFlag Agents PH.
Coordinates multi-agent workflows for procurement anomaly detection.
"""

import logging
import os
from enum import StrEnum
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class AnalysisStatus(StrEnum):
    """Workflow status states."""
    PENDING = "pending"
    LEGAL_CHECK = "legal_check"
    PRICE_CHECK = "price_check"
    SCRAPING = "scraping"
    ALERTING = "alerting"
    COMPLETED = "completed"
    ERROR = "error"


class ProcurementState(TypedDict, total=False):
    """State passed through the LangGraph workflow."""
    contract_id: str
    contract_description: str
    contract_amount: float
    agency: str
    svp_category: str
    legal_findings: dict[str, Any]
    price_findings: dict[str, Any]
    scraping_results: dict[str, Any]
    llm_analysis: dict[str, Any]
    anomalies: list[dict[str, Any]]
    alerts_created: list[dict[str, Any]]
    status: str
    error: str | None


# RA 12009 thresholds
SVP_THRESHOLD = 1_000_000  # PHP 1M for Small Value Procurement

# LLM Configuration - set via environment variable
OPENCODE_API_KEY = os.environ.get("OPENCODE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def get_llm():
    """Get configured LLM with fallback on rate limit."""
    opencode_key = os.environ.get("OPENCODE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if opencode_key:
        from langchain_openai import ChatOpenAI
        
        # Try Minimax first
        try:
            llm = ChatOpenAI(
                model="minimax-m2.5-free",
                api_key=opencode_key,
                base_url="https://opencode.ai/zen/v1",
                default_headers={"x-opencode-provider": "opencode"},
                temperature=0,
                max_retries=1,
            )
            # Test connection
            llm.invoke("test")
            return llm
        except Exception as e:
            # Rate limited or error - try Nemotron fallback
            error_msg = str(e).lower()
            if "rate" in error_msg or "429" in error_msg or "limit" in error_msg:
                print(f"Minimax rate limited, trying Nemotron fallback...")
            
            # Try Nemotron 3 Super Free as fallback
            try:
                # Use OpenCode with Nemotron model
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model="nvidia/nemotron-3-super-nemotron-3-super-4b",
                    api_key=opencode_key,
                    base_url="https://opencode.ai/zen/v1",
                    default_headers={"x-opencode-provider": "opencode"},
                    temperature=0,
                    max_retries=1,
                )
            except:
                pass  # Fall through to try other providers
    
    if openai_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=openai_key,
            temperature=0,
        )
    if anthropic_key:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model="claude-3-haiku-20240307",
            api_key=anthropic_key,
            temperature=0,
        )
    return None


def legal_check_node(state: ProcurementState) -> ProcurementState:
    """Node: Check legal compliance for procurement (RA 12009 thresholds)."""
    amount = state.get("contract_amount", 0)
    is_compliant = amount <= SVP_THRESHOLD
    violations = []

    if amount > SVP_THRESHOLD:
        violations.append(f"Amount exceeds SVP threshold (PHP {SVP_THRESHOLD:,})")
        # Check if competitive bidding required (for amounts > 50K)
        if amount > 50_000:
            violations.append("Requires competitive bidding (amount > PHP 50,000)")

    state["legal_findings"] = {
        "threshold_compliant": is_compliant,
        "required_process": "competitive bidding" if amount > SVP_THRESHOLD else "small value procurement",
        "threshold": SVP_THRESHOLD,
        "violations": violations,
        "law": "RA 12009 (2024)",
    }
    state["status"] = AnalysisStatus.LEGAL_CHECK
    return state


def price_analysis_node(state: ProcurementState) -> ProcurementState:
    """Node: Analyze pricing for potential inflation."""
    amount = state.get("contract_amount", 0)
    description = state.get("contract_description", "").lower()

    # Try cache first for market price
    baseline = amount * 0.7  # Default baseline
    source = "default_baseline"

    try:
        from cache import get_cached_market_price
        cached = get_cached_market_price(description)
        if cached:
            baseline = cached * 0.9  # Allow 10% margin
            source = "cached_market_price"
    except Exception:
        pass

    is_inflated = amount > baseline

    state["price_findings"] = {
        "flag": "potential_inflation" if is_inflated else "normal",
        "reason": "Price exceeds market baseline" if is_inflated else "Price within normal range",
        "baseline": baseline,
        "amount": amount,
        "source": source,
    }
    state["status"] = AnalysisStatus.PRICE_CHECK
    return state


def scraping_node(state: ProcurementState) -> ProcurementState:
    """Node: Scrape PhilGEPS for related contracts."""
    description = state.get("contract_description", "")
    contract_amount = state.get("contract_amount", 0)
    agency = state.get("agency", "")
    
    # Try to use PhilGEPS scraper
    try:
        from src.servers.mcp.philgeps_data import search_philgeps, get_agency_procurement
        import asyncio
        
        # Search for related procurements
        if agency:
            result = asyncio.run(get_agency_procurement(agency_name=agency, limit=5))
        else:
            result = asyncio.run(search_philgeps(keyword=description, category="goods"))
        
        state["scraping_results"] = {
            "results": result.get("results", []),
            "source": result.get("source", "unknown"),
            "searched": description,
            "note": f"Found {len(result.get('results', []))} related procurements",
        }
    except Exception as e:
        state["scraping_results"] = {
            "results": [],
            "source": "fallback",
            "searched": description,
            "note": f"Scraper unavailable: {str(e)[:50]}",
        }
    
    state["status"] = AnalysisStatus.SCRAPING
    return state


def llm_analysis_node(state: ProcurementState) -> ProcurementState:
    """Node: LLM-powered deep analysis for procurement documents."""
    llm = get_llm()

    if llm is None:
        # No LLM configured, use rule-based fallback
        state["llm_analysis"] = {
            "available": False,
            "note": "Set OPENCODE_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY for LLM analysis",
        }
        state["status"] = AnalysisStatus.LEGAL_CHECK
        return state

    description = state.get("contract_description", "")
    amount = state.get("contract_amount", 0)

    # Prompt for LLM to analyze procurement
    prompt = f"""Analyze this Philippine government procurement for potential red flags:

Contract: {description}
Amount: PHP {amount:,}

Check for:
1. RA 12009 compliance (SVP threshold PHP 1,000,000)
2. Price reasonableness compared to market rates
3. Common red flags (splitting contracts, favored bidders, etc.)
4. PhilGEPS posting requirements

Return a JSON analysis with:
- anomalies_found: list of issues
- risk_level: low/medium/high
- recommendations: list of actions
"""

    try:
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_core.runnables import RunnableLambda

        parser = JsonOutputParser()

        # Simple chain: prompt -> llm -> parser
        def parse_response(request: dict) -> str:
            return prompt

        chain = RunnableLambda(parse_response) | llm | parser
        result = chain.invoke({})

        state["llm_analysis"] = {
            "available": True,
            "anomalies": result.get("anomalies_found", []),
            "risk_level": result.get("risk_level", "low"),
"recommendations": result.get("recommendations", []),
        }
    except Exception as e:
        state["llm_analysis"] = {
            "available": True,
            "error": str(e),
            "fallback": "Rule-based analysis used",
        }

    state["status"] = AnalysisStatus.LEGAL_CHECK
    return state


def alert_node(state: ProcurementState) -> ProcurementState:
    """Node: Create alerts if anomalies detected."""
    anomalies = []
    # Check legal findings
    legal_f = state.get("legal_findings")
    if legal_f and not legal_f.get("threshold_compliant", True):
        for v in legal_f.get("violations", []):
            anomalies.append({
                "type": "legal",
                "severity": "high",
                "description": v,
                "law": legal_f.get("law"),
            })

    # Check price findings
    price_f = state.get("price_findings")
    if price_f and price_f.get("flag") == "potential_inflation":
        anomalies.append({
            "type": "price",
            "severity": "medium",
            "description": price_f.get("reason"),
        })

    state["anomalies"] = anomalies
    state["alerts_created"] = [
        {"title": a["type"], "severity": a["severity"], "description": a["description"]}
        for a in anomalies
    ]
    state["status"] = AnalysisStatus.ALERTING
    return state


def should_continue(state: ProcurementState) -> Literal["price_analysis", "alert"]:
    """Conditional routing: continue to price analysis or skip to alert on legal failure."""
    if state.get("legal_findings", {}).get("threshold_compliant", True):
        return "price_analysis"
    return "alert"


def create_procurement_graph() -> StateGraph:
    """Create the LangGraph state machine for procurement analysis."""
    graph = StateGraph(ProcurementState)

    graph.add_node("legal_check", legal_check_node)
    graph.add_node("price_analysis", price_analysis_node)
    graph.add_node("scraping", scraping_node)
    graph.add_node("llm_analysis", llm_analysis_node)
    graph.add_node("alert", alert_node)

    graph.add_edge("__start__", "legal_check")
    graph.add_conditional_edges(
        "legal_check",
        should_continue,
        {"price_analysis": "price_analysis", "alert": "alert"},
    )
    graph.add_edge("price_analysis", "scraping")
    graph.add_edge("scraping", "llm_analysis")
    graph.add_edge("llm_analysis", "alert")
    graph.add_edge("alert", END)

    return graph.compile()


async def analyze_procurement(
    contract_id: str,
    contract_description: str,
    contract_amount: float,
    svp_category: str = "general",
    save_to_db: bool = False,
) -> dict[str, Any]:
    """
    Main entry point: analyze a procurement for anomalies.
    """
    initial_state: ProcurementState = {
        "contract_id": contract_id,
        "contract_description": contract_description,
        "contract_amount": contract_amount,
        "svp_category": svp_category,
        "legal_findings": {},
        "price_findings": {},
        "scraping_results": {},
        "anomalies": [],
        "alerts_created": [],
        "status": AnalysisStatus.PENDING,
        "error": None,
    }

    try:
        graph = create_procurement_graph()
        result = await graph.ainvoke(initial_state)

        output = {
            "contract_id": result.get("contract_id"),
            "contract_description": result.get("contract_description"),
            "contract_amount": result.get("contract_amount"),
            "status": result.get("status"),
            "legal_findings": result.get("legal_findings"),
            "price_findings": result.get("price_findings"),
            "scraping_results": result.get("scraping_results"),
            "llm_analysis": result.get("llm_analysis"),
            "anomalies": result.get("anomalies", []),
            "alerts": result.get("alerts_created", []),
        }

        if save_to_db:
            try:
                from src.services.database import ProcurementAnalysis, get_db, init_db
                init_db()
                with get_db() as db:
                    analysis = ProcurementAnalysis(
                    contract_id=contract_id,
                    contract_description=contract_description,
                    contract_amount=contract_amount,
                    svp_category=svp_category,
                    status=result.get("status"),
                    legal_findings=result.get("legal_findings"),
                    price_findings=result.get("price_findings"),
                    anomalies=result.get("anomalies", []),
                    alerts_created=result.get("alerts_created", []),
                    )
                    db.add(analysis)
                output["saved"] = True
            except Exception as e:
                logger.warning(f"Failed to save to DB: {e}")
                output["saved"] = False

        return output

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return {
            "contract_id": contract_id,
            "status": "error",
            "error": str(e),
        }


if __name__ == "__main__":
    import asyncio

    result = asyncio.run(
        analyze_procurement(
            contract_id="PO-2024-001234",
            contract_description="Office Chairs",
            contract_amount=500_000,
        )
    )
    print(f"Analysis complete: {result.get('status')}")
