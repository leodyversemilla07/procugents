"""LLM Analysis agent for the ProcuGents orchestrator.

Optional node that performs LLM-powered deep analysis using LangChain.
Three providers are attempted in order (OpenCode free tier → OpenAI →
Anthropic); if none is configured the node writes ``llm_analysis``
marked unavailable and the workflow continues.

Falls back to the rule-based pipeline silently if the LLM is unavailable
or raises so the rest of the graph still runs.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.orchestration.state import ProcurementState

logger = logging.getLogger(__name__)

# Module-level LLM cache so multiple node invocations reuse the client.
_LLM_CACHE: dict[str, Any] = {}


def _try_langchain_openai(model: str, **kwargs) -> Any:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, temperature=0, max_retries=1, **kwargs)


def get_llm() -> Any | None:
    """Return a configured ChatModel, or None if no provider is set."""
    if "llm" in _LLM_CACHE:
        return _LLM_CACHE["llm"]

    opencode_key = os.environ.get("OPENCODE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if opencode_key:
        try:
            llm = _try_langchain_openai(
                "minimax-m2.5-free",
                api_key=opencode_key,
                base_url="https://opencode.ai/zen/v1",
                default_headers={"x-opencode-provider": "opencode"},
            )
            _LLM_CACHE["llm"] = llm
            return llm
        except Exception as exc:  # pragma: no cover
            msg = str(exc).lower()
            if "rate" in msg or "429" in msg or "limit" in msg:
                logger.info("Minimax rate limited, will try fallback on first use")

    if openai_key:
        try:
            llm = _try_langchain_openai("gpt-4o-mini", api_key=openai_key)
            _LLM_CACHE["llm"] = llm
            return llm
        except Exception:  # pragma: no cover
            logger.warning("OpenAI client construction failed")

    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic

            llm = ChatAnthropic(
                model_name="claude-3-haiku-20240307",
                api_key=anthropic_key,
                temperature=0,
            )
            _LLM_CACHE["llm"] = llm
            return llm
        except Exception:  # pragma: no cover
            logger.warning("Anthropic client construction failed")

    return None


def llm_analysis_node(state: ProcurementState) -> ProcurementState:
    """LLM-powered deep analysis (or rule-based fallback)."""
    llm = get_llm()
    if llm is None:
        state["llm_analysis"] = {
            "available": False,
            "note": (
                "Set OPENCODE_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY"
                " for LLM analysis"
            ),
        }
        return state

    description = state.get("contract_description", "")
    amount = state.get("contract_amount", 0)

    try:
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_core.prompts import ChatPromptTemplate
    except Exception as exc:  # pragma: no cover
        state["llm_analysis"] = {
            "available": False,
            "error": f"LangChain core not available: {exc}",
        }
        return state

    parser = JsonOutputParser()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Philippine government procurement analyst. Always reply with strict JSON."),
        ("human",
         "Analyze this Philippine government procurement for potential red flags:\n\n"
         "Contract description: {description}\n"
         "Amount: PHP {amount}\n\n"
         "Check for:\n"
         "1. RA 12009 compliance (SVP threshold PHP 1,000,000)\n"
         "2. Price reasonableness compared to market rates\n"
         "3. Common red flags (splitting contracts, favored bidders, etc.)\n"
         "4. PhilGEPS posting requirements\n\n"
         "Return a JSON object with keys:\n"
         "- anomalies_found: list of strings describing issues\n"
         "- risk_level: one of low | medium | high\n"
         "- recommendations: list of strings with suggested actions"),
    ])

    try:
        chain = prompt | llm | parser
        result = chain.invoke({"description": description, "amount": f"{amount:,}"})
        state["llm_analysis"] = {
            "available": True,
            "anomalies": result.get("anomalies_found", []),
            "risk_level": result.get("risk_level", "low"),
            "recommendations": result.get("recommendations", []),
        }
    except Exception as exc:
        state["llm_analysis"] = {
            "available": False,
            "error": str(exc),
            "fallback": "Rule-based analysis used",
        }

    return state


__all__ = ["llm_analysis_node", "get_llm"]
