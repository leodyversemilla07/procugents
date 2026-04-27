"""
A2A Protocol support for RedFlag Agents PH.
Enables agent-to-agent communication with other A2A-compatible agents.
"""

import json
from enum import StrEnum
from typing import Any
from dataclasses import dataclass, field


class AgentCapability(StrEnum):
    """Capabilities exposed via A2A."""
    LEGAL_LOOKUP = "legal_lookup"
    PRICE_ANALYSIS = "price_analysis"
    PROCUREMENT_SEARCH = "procurement_search"
    ALERTING = "alerting"
    FULL_ANALYSIS = "full_analysis"


@dataclass
class AgentCard:
    """A2A Agent Card - describes agent capabilities."""
    name: str = "RedFlag Agents PH"
    description: str = "Philippine Government Procurement Anomaly Detection"
    url: str = "http://localhost:8000"
    version: str = "1.0.0"
    capabilities: list[AgentCapability] = field(
        default_factory=lambda: [
            AgentCapability.LEGAL_LOOKUP,
            AgentCapability.PRICE_ANALYSIS,
            AgentCapability.PROCUREMENT_SEARCH,
            AgentCapability.ALERTING,
            AgentCapability.FULL_ANALYSIS,
        ]
    )
    skills: list[str] = field(
        default_factory=lambda: [
            "ra_12009_compliance",
            "price_inflation_detection",
            "philgeps_search",
            "alert_creation",
        ]
    )


@dataclass
class TaskMessage:
    """A2A Task Message."""
    task_id: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


class A2AServer:
    """A2A Protocol Server for RedFlag Agents."""

    def __init__(self):
        self.agent_card = AgentCard()
        self.tasks: dict[str, dict[str, Any]] = {}

    def get_agent_card(self) -> dict[str, Any]:
        """Return agent card for discovery."""
        return {
            "name": self.agent_card.name,
            "description": self.agent_card.description,
            "url": self.agent_card.url,
            "version": self.agent_card.version,
            "capabilities": [c.value for c in self.agent_card.capabilities],
            "skills": self.agent_card.skills,
        }

    async def handle_task(self, task: TaskMessage) -> dict[str, Any]:
        """Handle incoming A2A task."""
        message = task.message.lower()

        if "legal" in message or "compliance" in message:
            result = await self._legal_check(task)
        elif "price" in message or "market" in message:
            result = await self._price_check(task)
        elif "search" in message or "philgeps" in message:
            result = await self._search_procurement(task)
        else:
            result = await self._full_analysis(task)

        task_id = f"task_{task.task_id}"
        self.tasks[task_id] = result

        return {
            "task_id": task_id,
            "status": "completed",
            "result": result,
        }

    async def _legal_check(self, task: TaskMessage) -> dict[str, Any]:
        """Handle legal compliance check."""
        from src.orchestration.orchestrator import SVP_THRESHOLD

        amount = task.metadata.get("contract_amount", 0)
        return {
            "type": "legal_check",
            "compliant": amount <= SVP_THRESHOLD,
            "threshold": SVP_THRESHOLD,
            "required": "competitive bidding" if amount > SVP_THRESHOLD else "svp",
        }

    async def _price_check(self, task: TaskMessage) -> dict[str, Any]:
        """Handle price analysis."""
        amount = task.metadata.get("contract_amount", 0)
        baseline = amount * 0.7
        return {
            "type": "price_check",
            "amount": amount,
            "baseline": baseline,
            "flag": "potential_inflation" if amount > baseline else "normal",
        }

    async def _search_procurement(self, task: TaskMessage) -> dict[str, Any]:
        """Handle PhilGEPS search."""
        return {
            "type": "search",
            "results": [],
            "note": "PhilGEPS integration pending",
        }

    async def _full_analysis(self, task: TaskMessage) -> dict[str, Any]:
        """Handle full procurement analysis."""
        from src.orchestration.orchestrator import analyze_procurement

        contract_id = task.metadata.get("contract_id", f"PO-{task.task_id}")
        description = task.metadata.get("description", "General Procurement")
        amount = task.metadata.get("contract_amount", 0)

        result = await analyze_procurement(
            contract_id=contract_id,
            contract_description=description,
            contract_amount=amount,
        )
        return result

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get task status."""
        return self.tasks.get(task_id)


# A2A JSON-RPC methods
A2A_METHODS = {
    "agent/card": lambda server: server.get_agent_card(),
    "agent/tasks": lambda server, task: server.handle_task(task),
}


if __name__ == "__main__":
    server = A2AServer()
    print(json.dumps(server.get_agent_card(), indent=2))