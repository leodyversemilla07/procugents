"""Tests for the dashboard real-time event bus.

Verifies the in-process fan-out broker used by alert_node and the
/ws/alerts WebSocket endpoint.
"""

from __future__ import annotations

import asyncio
import contextlib


from src.services.events import CHANNEL_DASHBOARD_UPDATES, EventBus, bus


async def test_subscribe_receives_published_event():
    bus = EventBus()

    pub_task: asyncio.Task | None = None
    sub_task: asyncio.Task | None = None

    async def subscriber():
        async with bus.subscribe() as reader:
            envelope = await asyncio.wait_for(reader.__anext__(), timeout=0.5)
            return envelope

    async def publisher():
        await asyncio.sleep(0.02)
        await bus.publish(CHANNEL_DASHBOARD_UPDATES, {"kind": "alert_triggered"})

    sub_task = asyncio.create_task(subscriber())
    pub_task = asyncio.create_task(publisher())

    envelope, _ = await asyncio.gather(sub_task, pub_task)
    assert envelope["channel"] == CHANNEL_DASHBOARD_UPDATES
    assert envelope["event"] == {"kind": "alert_triggered"}


async def test_publish_fans_to_multiple_subscribers():
    bus = EventBus()
    a: list = []
    b: list = []
    c: list = []

    async def pump(sink, bus_obj):
        async for ev in bus_obj.subscribe():
            sink.append(ev)
            if len(sink) >= 3:
                break

    async def driver():
        for i in range(3):
            await bus.publish(CHANNEL_DASHBOARD_UPDATES, {"i": i})

    tasks = [asyncio.create_task(pump(x, bus)) for x in (a, b, c)]

    # Let subscribers register.
    await asyncio.sleep(0.02)
    await driver()

    done, pending = await asyncio.wait(tasks, timeout=0.5)
    for t in pending:
        t.cancel()

    assert [e["event"]["i"] for e in a] == [0, 1, 2]
    assert [e["event"]["i"] for e in b] == [0, 1, 2]
    assert [e["event"]["i"] for e in c] == [0, 1, 2]


async def test_unsubscribe_isolates_other_subscribers():
    bus = EventBus()
    keep: list = []

    a_task: asyncio.Task | None = None
    drop_task: asyncio.Task | None = None
    drop: list = []

    async def pump(sink, bus_obj):
        try:
            async for ev in bus_obj.subscribe():
                sink.append(ev)
        except asyncio.CancelledError:
            pass

    drop_task = asyncio.create_task(pump(drop, bus))
    await asyncio.sleep(0.02)  # let drop subscribe
    a_task = asyncio.create_task(pump(keep, bus))
    await asyncio.sleep(0.02)  # let keep subscribe

    await bus.publish(CHANNEL_DASHBOARD_UPDATES, {"i": 1})
    await asyncio.sleep(0.02)
    assert len(drop) == 1 and len(keep) == 1

    # Cancel the 'drop' subscriber.
    drop_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await drop_task

    await bus.publish(CHANNEL_DASHBOARD_UPDATES, {"i": 2})
    await asyncio.sleep(0.02)
    assert len(drop) == 1  # no new events after unsubscribe
    assert len(keep) == 2  # keep is still subscribed

    a_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await a_task


async def test_publish_synchronous_falls_back_to_modern_loop():
    """publish_nowait is a sync façade used from the alert_node sync path."""
    bus = EventBus()
    received: list = []

    async def pump():
        async for ev in bus.subscribe():
            received.append(ev)
            if len(received) >= 1:
                return

    task = asyncio.create_task(pump())
    await asyncio.sleep(0.02)

    # sync API, no awaiting required
    assert bus.publish_nowait("dashboard:updates", {"i": 7})

    await asyncio.wait_for(task, timeout=0.5)
    assert received[0]["event"] == {"i": 7}


async def test_module_singleton_bus_is_usable():
    """The default singleton `bus` exported from the module should also work."""
    received: list = []

    async def pump():
        async for ev in bus.subscribe():
            received.append(ev)
            if len(received) >= 1:
                return

    task = asyncio.create_task(pump())
    await asyncio.sleep(0.02)
    await bus.publish(CHANNEL_DASHBOARD_UPDATES, {"i": 42})
    await asyncio.wait_for(task, timeout=0.5)
    assert received[0]["event"] == {"i": 42}
