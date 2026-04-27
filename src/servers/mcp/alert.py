"""
Alert/Notification MCP Server for RedFlag Agents PH.
Sends alerts for detected procurement anomalies.
"""

from enum import StrEnum
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("alert")


class AlertLevel(StrEnum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertChannel(StrEnum):
    """Available notification channels."""

    EMAIL = "email"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    CONSOLE = "console"


alert_store: list[dict[str, Any]] = []


@mcp.tool()
async def create_alert(
    title: str,
    description: str,
    level: AlertLevel = AlertLevel.MEDIUM,
    related_contract_id: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create a procurement anomaly alert.

    Args:
        title: Alert title
        description: Detailed description of the anomaly
        level: Severity level (low, medium, high, critical)
        related_contract_id: Associated contract reference
        tags: Optional tags for categorization

    Returns:
        Created alert object
    """
    alert = {
        "id": f"alert_{len(alert_store) + 1}",
        "title": title,
        "description": description,
        "level": level.value,
        "contract_id": related_contract_id,
        "tags": tags or [],
        "status": "pending",
    }

    alert_store.append(alert)

    return alert


@mcp.tool()
async def get_alerts(
    level: AlertLevel | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Query stored alerts.

    Args:
        level: Filter by severity level
        status: Filter by status (pending, sent, resolved)
        limit: Maximum results
    """
    results = alert_store

    if level:
        results = [a for a in results if a["level"] == level.value]
    if status:
        results = [a for a in results if a["status"] == status]

    return {
        "alerts": results[:limit],
        "total": len(results),
    }


@mcp.tool()
async def send_alert(
    alert_id: str,
    channel: AlertChannel = AlertChannel.CONSOLE,
    recipient: str | None = None,
) -> dict[str, Any]:
    """
    Send alert via specified channel.

    Args:
        alert_id: ID of alert to send
        channel: Delivery channel (email, telegram, webhook, console)
        recipient: Channel-specific recipient
    """
    alert = next((a for a in alert_store if a["id"] == alert_id), None)

    if not alert:
        return {"error": f"Alert {alert_id} not found"}

    if channel == AlertChannel.TELEGRAM and recipient:
        return {"sent": True, "channel": "telegram", "recipient": recipient}

    if channel == AlertChannel.WEBHOOK and recipient:
        return {"sent": True, "channel": "webhook", "url": recipient}

    # Console alerts logged via return message
    alert["status"] = "sent"
    alert["channel"] = channel.value

    return {
        "sent": True,
        "alert_id": alert_id,
        "channel": channel.value,
        "message": f"[ALERT {alert['level'].upper()}] {alert['title']}: {alert['description']}",
    }


@mcp.tool()
async def resolve_alert(
    alert_id: str,
    resolution_notes: str | None = None,
) -> dict[str, Any]:
    """
    Mark alert as resolved.

    Args:
        alert_id: ID of alert to resolve
        resolution_notes: Optional resolution notes
    """
    alert = next((a for a in alert_store if a["id"] == alert_id), None)

    if not alert:
        return {"error": f"Alert {alert_id} not found"}

    alert["status"] = "resolved"
    alert["resolution_notes"] = resolution_notes

    return {"resolved": True, "alert_id": alert_id}


if __name__ == "__main__":
    mcp.run()
