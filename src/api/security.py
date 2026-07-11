"""API security: rate limiting and optional API-key authentication.

Rate limiter
------------
Sliding 60-second window tracked per IP. Uses Redis when available via
``get_redis()``, falls back to an in-memory dict. Applies to all HTTP
endpoints except ``/api/health``.

API-key authentication
----------------------
When ``API_KEY`` is set in the environment, every API call (except
``/api/health``, ``/docs``, ``/openapi.json``) must carry the header
``X-API-Key: <key>``. WebSocket connections authenticate via a
``?token=<key>`` query parameter.

When ``API_KEY`` is *not* set, authentication is skipped entirely
(development mode).
"""

from __future__ import annotations

import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger: Any = None


def _log() -> Any:
    global logger
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)
    return logger


# ---------------------------------------------------------------------------
# Rate limiter configuration
# ---------------------------------------------------------------------------

RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

# In-memory fallback: {ip: (window_start, count)}
_memory_store: dict[str, tuple[float, int]] = {}


def _rate_limit_key(request: Request) -> str:
    """Derive a rate-limit key from the client IP."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else request.client.host if request.client else "127.0.0.1"
    )
    return client_ip


async def _rate_limit_redis(ip: str) -> bool:
    """Check rate limit via Redis. Returns True if allowed."""
    from src.services.cache import get_redis

    try:
        r = get_redis()
        now = time.time()
        key = f"ratelimit:{ip}"
        # Remove entries outside the window.
        r.zremrangebyscore(key, 0, now - RATE_LIMIT_WINDOW)
        # Count current entries.
        count = r.zcard(key)
        if count >= RATE_LIMIT_REQUESTS:
            return False
        # Add this request.
        r.zadd(key, {str(now): now})
        r.expire(key, RATE_LIMIT_WINDOW)
        return True
    except Exception:
        # Redis unavailable — fall through to in-memory.
        return await _rate_limit_memory(ip)


async def _rate_limit_memory(ip: str) -> bool:
    """Check rate limit via in-memory dict. Returns True if allowed."""
    now = time.time()
    entry = _memory_store.get(ip)
    if entry is None or now - entry[0] > RATE_LIMIT_WINDOW:
        # Start a new window.
        _memory_store[ip] = (now, 1)
        # Garbage collect stale entries (every 100th request).
        if len(_memory_store) > 1000:
            _gc_memory()
        return True
    _, count = entry
    if count >= RATE_LIMIT_REQUESTS:
        return False
    _memory_store[ip] = (entry[0], count + 1)
    return True


def _gc_memory() -> None:
    """Remove entries whose window has expired."""
    now = time.time()
    stale = [ip for ip, (ts, _) in _memory_store.items()
             if now - ts > RATE_LIMIT_WINDOW]
    for ip in stale:
        _memory_store.pop(ip, None)


# ---------------------------------------------------------------------------
# API key authentication
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("API_KEY", "").strip()


def _check_api_key(request: Request) -> str | None:
    """Return the API key from header, or None."""
    return request.headers.get("X-API-Key") or request.headers.get("x-api-key")


# Paths that never require auth.
_SKIP_AUTH_PATHS = frozenset({
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
})


def _needs_auth(path: str) -> bool:
    """True if the path should be protected."""
    return path not in _SKIP_AUTH_PATHS and not path.startswith("/docs") and not path.startswith("/redoc")


# ---------------------------------------------------------------------------
# Middleware — applies rate limiting + API key check to every HTTP request.
# ---------------------------------------------------------------------------


def install_security_middleware(app: FastAPI) -> None:
    """Install the combined rate-limit + auth middleware on *app*.

    Call this once after creating the FastAPI instance.
    """
    log = _log()

    @app.middleware("http")
    async def _security_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable],
    ) -> Any:
        path = request.url.path

        # ---- Rate limit (every path except WebSocket upgrade). -----
        if request.scope.get("type") == "http":
            ip = _rate_limit_key(request)
            allowed = await _rate_limit_redis(ip)
            if not allowed:
                log.warning("rate limit exceeded for %s on %s", ip, path)
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many requests. Try again later.",
                        "retry_after_seconds": RATE_LIMIT_WINDOW,
                    },
                    headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
                )

        # ---- API key auth. -----------------------------------------
        if API_KEY and _needs_auth(path):
            key = _check_api_key(request)
            if key != API_KEY:
                log.warning("invalid API key on %s", path)
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Missing or invalid API key"},
                    headers={"WWW-Authenticate": "ApiKey"},
                )

        return await call_next(request)

    if API_KEY:
        log.info("API key authentication enabled")
    else:
        log.info("API key authentication disabled (set API_KEY env var to enable)")
    log.info(
        "rate limiting: %d requests per %d seconds per IP",
        RATE_LIMIT_REQUESTS,
        RATE_LIMIT_WINDOW,
    )
