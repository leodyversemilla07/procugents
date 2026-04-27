"""Legal Lookup MCP Server for RedFlag Agents PH.

Exposes tools to query legal citations, red flags, and thresholds
from the Legal Rule Engine JSON.
"""

import json
from pathlib import Path

from fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("legal-lookup")

# Load Legal Rule Engine JSON
LEGAL_RULE_ENGINE_PATH = Path(__file__).parent.parent / "data" / "legal_rule_engine.json"

with open(LEGAL_RULE_ENGINE_PATH) as f:
    _legal_data: dict = json.load(f)


@mcp.tool()
def lookup_legal_citation(flag_code: str) -> dict:
    """Return legal citation, IIUEEU classification, and severity for a red flag.

    Args:
        flag_code: Red flag code (e.g., "missing_philgeps_posting")

    Returns:
        Dict with citation, law_source, iiueeu, severity, description
    """
    for agent_flags in _legal_data["agent_red_flags"].values():
        for flag in agent_flags:
            if flag["flag"] == flag_code:
                iiueeu_code = flag["iiueeu"]
                iiueeu_info = _legal_data["iiueeu_classifications"].get(iiueeu_code, {})
                return {
                    "citation": flag["citation"],
                    "law_source": flag["law_source"],
                    "iiueeu": iiueeu_code,
                    "severity": flag["severity"],
                    "description": iiueeu_info.get("description", ""),
                }
    return {"error": f"Flag code '{flag_code}' not found"}


@mcp.tool()
def list_flags_by_agent(agent_name: str) -> list[dict]:
    """Return all red flags mapped to a specific agent.

    Args:
        agent_name: Agent name (e.g., "price_analyst_agent")

    Returns:
        List of flag dicts with flag, citation, iiueeu, severity
    """
    # Normalize agent name to match JSON keys (remove _agent suffix if present)
    key = agent_name.replace("_agent", "")
    return _legal_data["agent_red_flags"].get(key, [])


@mcp.tool()
def get_thresholds() -> dict:
    """Return all procurement mode thresholds and red flag thresholds.

    Returns:
        Dict with competitive_bidding_min, svs_max, etc.
    """
    return _legal_data["thresholds"]


if __name__ == "__main__":
    mcp.run(transport="stdio")
