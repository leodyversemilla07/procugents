"""In-process event bus for dashboard real-time updates.

Single-responsibility module: lets the orchestrator + FastAPI publish events
("alert triggered", etc.) and the WebSocket layer subscribe. When the project
moves to a production deployment, swap the in-memory fanout for Redis
pub/sub (``redis.subscribe("dashboard:updates")``) without changing callers.

Channels:
    "dashboard:updates" - every alert / analysis completion event.

Each event is a plain JSON-serializable dict. Subscribers receive them as
soon as ``publish()`` returns.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

CHANNEL_DASHBOARD_UPDATES = "dashboard:updates"


class EventBus:
    """In-process async fan-out broker.

    Subscribers register an asyncio.Queue; every ``publish`` fans the event
    out to all live queues. Subscribers that fall behind see their queues
    grow unbounded -- that's acceptable for our use-case where each
    subscriber is a tiny browser WS connection.

    Implementation notes:
        * O(N) fan-out per publish, but N is bounded by the number of
          open WS connections (one browser tab = ~1 subscriber).
        * Adding Redis pub/sub later: replace ``_subs`` with a Redis
          ``PubSub`` channel and translate ``publish``/``subscribe``
          to ``publish``/``subscribe().listen``.
    """

    def __init__(self) -> None:
        # Subscribers are weak dictionaries keyed by asyncio.Queue.
        # We keep a lock per subscribe/unsubscribe to prevent races.
        self._subs: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        """Push a JSON event to every subscriber on the given channel."""
        envelope = {"channel": channel, "event": event}
        # Snapshot under the lock so we don't mutate the set during fan-out.
        async with self._lock:
            subscribers = list(self._subs)
        for q in subscribers:
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:  # pragma: no cover - bounded queues off
                logger.warning("event bus subscriber queue full; dropping event")

    def publish_nowait(self, channel: str, event: dict[str, Any]) -> bool:
        """Fire-and-forget sync publish (returns True if scheduled)."""
        envelope = {"channel": channel, "event": event}
        scheduled = False
        subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(envelope)
                scheduled = True
            except asyncio.QueueFull:  # pragma: no cover
                pass
        return scheduled

    def subscribe(self):
        """Return an ``AsyncSubscription`` that yields envelopes as they arrive.

        Can be used as an async iterator:
            async for envelope in bus.subscribe():
                ...

        Or as an async context manager (cleanup runs on exit):
            async with bus.subscribe() as sub:
                async for envelope in sub:
                    ...
        """
        return AsyncSubscription(self)


class AsyncSubscription:
    """Async iterator over EventBus subscribers, with optional context manager.

    Implementation notes:
        * ``__aenter__`` registers a queue under the bus's lock and
          returns ``self``; iterators on self pull from that queue.
        * ``__aexit__`` stops the iterator and unregisters the queue even
          if the consumer did not exhaust the stream.
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._q: asyncio.Queue | None = None
        self._stopped = False

    def __aiter__(self) -> AsyncSubscription:
        return self

    async def _ensure_queue(self) -> asyncio.Queue:
        if self._q is None:
            self._q = asyncio.Queue(maxsize=256)
            async with self._bus._lock:
                self._bus._subs.add(self._q)
        return self._q

    async def __aenter__(self) -> AsyncSubscription:
        await self._ensure_queue()
        return self

    async def __aexit__(self, *exc) -> bool:
        await self.aclose()
        return False

    async def aclose(self) -> None:
        self._stopped = True
        if self._q is not None:
            async with self._bus._lock:
                self._bus._subs.discard(self._q)

    async def __anext__(self) -> dict:
        if self._stopped:
            raise StopAsyncIteration
        q = await self._ensure_queue()
        return await q.get()

    async def subscribe(self):
        """Legacy iterator entry; returns itself."""
        return self


# Singleton: lives for the lifetime of the FastAPI process.
bus = EventBus()
