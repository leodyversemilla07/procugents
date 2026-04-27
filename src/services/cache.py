"""
Redis cache for RedFlag Agents PH.
"""

import json
from typing import Any

import redis


REDIS_URL = "redis://localhost:6379"

_client = None


def get_redis() -> redis.Redis:
    """Get Redis client."""
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def cache_analysis(contract_id: str, result: dict[str, Any], ttl: int = 3600) -> None:
    """Cache analysis result in Redis."""
    r = get_redis()
    r.setex(f"analysis:{contract_id}", ttl, json.dumps(result))


def get_cached_analysis(contract_id: str) -> dict[str, Any] | None:
    """Get cached analysis result."""
    r = get_redis()
    data = r.get(f"analysis:{contract_id}")
    return json.loads(data) if data else None


def cache_alert(alert_id: str, alert: dict[str, Any], ttl: int = 86400) -> None:
    """Cache alert in Redis."""
    r = get_redis()
    r.setex(f"alert:{alert_id}", ttl, json.dumps(alert))


def get_cached_alert(alert_id: str) -> dict[str, Any] | None:
    """Get cached alert."""
    r = get_redis()
    data = r.get(f"alert:{alert_id}")
    return json.loads(data) if data else None


def cache_market_price(item_name: str, price: float, ttl: int = 604800) -> None:
    """Cache market price (7 day TTL)."""
    r = get_redis()
    r.setex(f"market_price:{item_name.lower()}", ttl, str(price))


def get_cached_market_price(item_name: str) -> float | None:
    """Get cached market price."""
    r = get_redis()
    data = r.get(f"market_price:{item_name.lower()}")
    return float(data) if data else None
