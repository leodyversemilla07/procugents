"""Tests for the A2A v1.0 protocol implementation (https://a2a-protocol.org/v1.0.0/specification).

Covers:
    * Agent Card shape conformance to v1.0 / proto AgentCard
    * message/send round-trip through the orchestrator
    * tasks/get and tasks/cancel lifecycle
    * tasks/list with cursor pagination
    * agent/authenticatedExtendedCard
    * Error envelope correctness (JSON-RPC + A2A-specific codes)
    * Streaming (SSE, tasks/subscribe, task events)
    * Field-name convention: proto3 snake_case -> JSON snake_case
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402

from src.servers.a2a_server import (  # noqa: E402
    A2A_TASK_NOT_FOUND,
    A2A_TASK_NOT_CANCELABLE,
    A2A_PUSH_NOT_SUPPORTED,
    A2A_UNSUPPORTED_OPERATION,
    A2A_CONTENT_TYPE_NOT_SUPPORTED,
    RPC_METHOD_NOT_FOUND,
    RPC_INVALID_REQUEST,
    RPC_INVALID_PARAMS,
    TASK_STATE_COMPLETED,
    TASK_STATE_CANCELED,
    TASK_STATE_WORKING,
    TASK_STATE_FAILED,
    TERMINAL_TASK_STATES,
    PROTOCOL_VERSION,
    AGENT_VERSION,
    AGENT_NAME,
    build_agent_card,
    handle_jsonrpc_request,
)


def _server():
    from src.servers.a2a_server import A2AServer

    return A2AServer("http://localhost:8000")


async def _send(server, *, method: str, params: dict[str, Any] | None = None, req_id="req-1"):
    body = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }
    return await handle_jsonrpc_request(server, body)


# ---------------------------------------------------------------------------
# Agent Card shape
# ---------------------------------------------------------------------------


class TestAgentCard:

    def test_required_fields_present(self):
        card = build_agent_card("http://localhost:8000")
        for f in (
            "name", "description", "version", "supported_interfaces",
            "capabilities", "default_input_modes", "default_output_modes", "skills",
        ):
            assert f in card, f"missing required AgentCard field: {f}"

    def test_identity_fields(self):
        card = build_agent_card("http://localhost:8000")
        assert card["name"] == AGENT_NAME
        assert card["version"] == AGENT_VERSION
        assert len(card["description"]) > 0

    def test_supported_interfaces_is_ordered_with_jsonrpc_first(self):
        card = build_agent_card("http://localhost:8000")
        interfaces = card["supported_interfaces"]
        assert isinstance(interfaces, list) and len(interfaces) >= 1
        assert interfaces[0]["protocol_binding"] == "JSONRPC"
        assert interfaces[0]["protocol_version"] == "1.0"
        for i in interfaces:
            assert {"url", "protocol_binding", "protocol_version"}.issubset(set(i))

    def test_capabilities_matches_proto(self):
        card = build_agent_card("http://localhost:8000")
        caps = card["capabilities"]
        assert caps["streaming"] is True
        assert caps["push_notifications"] is False
        assert caps["extended_agent_card"] is True

    def test_skills_have_required_proto_fields(self):
        card = build_agent_card("http://localhost:8000")
        for sk in card["skills"]:
            assert {"id", "name", "description", "tags"}.issubset(set(sk))
            assert isinstance(sk["tags"], list) and len(sk["tags"]) >= 1

    def test_default_io_modes_present(self):
        card = build_agent_card("http://localhost:8000")
        assert "text/plain" in card["default_input_modes"]
        assert "application/json" in card["default_input_modes"]

    def test_provider_present(self):
        card = build_agent_card("http://localhost:8000")
        assert "provider" in card
        assert "organization" in card["provider"]
        assert "url" in card["provider"]

    def test_field_names_are_snake_case(self):
        card = build_agent_card("http://localhost:8000")
        camel = re.compile(r"[a-z][A-Z]")

        def assert_snake(d):
            for k, v in d.items():
                assert not camel.search(k), f"non-snake_case key: {k}"
                if isinstance(v, dict):
                    assert_snake(v)
        assert_snake(card)


# ---------------------------------------------------------------------------
# message/send
# ---------------------------------------------------------------------------


class TestSendMessage:

    @pytest.mark.asyncio
    async def test_legal_check_compliant(self):
        server = _server()
        resp = await _send(server, method="message/send", params={
            "message": {
                "message_id": "m-1", "role": "user",
                "parts": [{"data": {"skill": "legal_check", "params": {"contract_amount": 500000}}}],
            },
        })
        assert "result" in resp, resp
        task = resp["result"]
        assert task["status"]["state"] == TASK_STATE_COMPLETED
        result_part = task["status"]["message"]["parts"][0]["data"]["result"]
        assert result_part["compliant"] is True

    @pytest.mark.asyncio
    async def test_legal_check_non_compliant(self):
        server = _server()
        resp = await _send(server, method="message/send", params={
            "message": {
                "message_id": "m-2", "role": "user",
                "parts": [{"data": {"skill": "legal_check", "params": {"contract_amount": 5_000_000}}}],
            },
        })
        assert "result" in resp
        result_part = resp["result"]["status"]["message"]["parts"][0]["data"]["result"]
        assert result_part["compliant"] is False
        assert "competitive bidding" in result_part["required"]

    @pytest.mark.asyncio
    async def test_full_audit_creates_task_and_artifact(self):
        server = _server()
        resp = await _send(server, method="message/send", params={
            "message": {
                "message_id": "m-3", "role": "user",
                "parts": [{"data": {"skill": "audit", "params": {"contract_amount": 5_000_000}}}],
            },
        })
        task = resp["result"]
        assert task["status"]["state"] == TASK_STATE_COMPLETED
        assert len(task["artifacts"]) == 1
        assert len(task["history"]) >= 2

    @pytest.mark.asyncio
    async def test_task_state_fields_match_proto(self):
        server = _server()
        resp = await _send(server, method="message/send", params={
            "message": {"message_id": "m", "role": "user",
                          "parts": [{"text": "x", "media_type": "text/plain"}]},
        })
        task = resp["result"]
        assert {"id", "context_id", "status", "artifacts", "history"}.issubset(set(task))
        assert "task-" in task["id"]
        assert "ctx-" in task["context_id"]
        assert {"state", "timestamp"}.issubset(set(task["status"]))

    @pytest.mark.asyncio
    async def test_no_message_parts_returns_content_type_error(self):
        server = _server()
        resp = await _send(server, method="message/send", params={
            "message": {"message_id": "m", "role": "user", "parts": []},
        })
        assert "error" in resp
        assert resp["error"]["code"] == A2A_CONTENT_TYPE_NOT_SUPPORTED

    @pytest.mark.asyncio
    async def test_skill_resolution_via_text_pattern(self):
        server = _server()
        resp = await _send(server, method="message/send", params={
            "message": {"message_id": "m", "role": "user",
                          "parts": [{"text": "legal compliance please"}]},
        })
        assert "result" in resp
        assert resp["result"]["status"]["state"] == TASK_STATE_COMPLETED


# ---------------------------------------------------------------------------
# tasks/get
# ---------------------------------------------------------------------------


class TestGetTask:

    def test_round_trip(self):
        from src.servers.a2a_server import A2AServer, _StoredTask, task_status as _ts

        server = A2AServer("http://localhost:8000")
        asyncio.run(server._store.set(_StoredTask(
            id="task-fake", context_id="ctx-fake",
            state=TASK_STATE_COMPLETED, status=_ts(TASK_STATE_COMPLETED),
        )))
        resp = asyncio.run(_send(server, method="tasks/get", params={"id": "task-fake"}))
        assert resp["result"]["id"] == "task-fake"
        assert resp["result"]["context_id"] == "ctx-fake"
        assert resp["result"]["status"]["state"] == TASK_STATE_COMPLETED

    def test_unknown_task_returns_not_found(self):
        server = _server()
        resp = asyncio.run(_send(server, method="tasks/get", params={"id": "task-bogus"}))
        assert "error" in resp
        assert resp["error"]["code"] == A2A_TASK_NOT_FOUND

    def test_history_length_zero_omits_history(self):
        from src.servers.a2a_server import (
            A2AServer, _StoredTask, task_status as _ts,
        )

        server = A2AServer("http://localhost:8000")
        asyncio.run(server._store.set(_StoredTask(
            id="task-h", context_id="ctx-h",
            state=TASK_STATE_COMPLETED, status=_ts(TASK_STATE_COMPLETED),
            history=[{"messageId": "any", "role": "user", "parts": []}],
        )))
        resp = asyncio.run(_send(server, method="tasks/get",
                                 params={"id": "task-h", "history_length": 0}))
        assert "history" not in resp["result"]


# ---------------------------------------------------------------------------
# tasks/list
# ---------------------------------------------------------------------------


class TestListTasks:

    def test_returns_pagination_envelope(self):
        server = _server()
        resp = asyncio.run(_send(server, method="tasks/list", params={}))
        assert {"tasks", "next_page_token", "page_size", "total_size"}.issubset(
            set(resp["result"])
        )

    def test_filter_by_status(self):
        from src.servers.a2a_server import (
            A2AServer, _StoredTask, task_status as _ts,
        )

        server = A2AServer("http://localhost:8000")
        for i in range(2):
            state = TASK_STATE_COMPLETED if i == 0 else TASK_STATE_CANCELED
            asyncio.run(server._store.set(_StoredTask(
                id=f"task-{i}", context_id=f"ctx-{i}",
                state=state, status=_ts(state),
            )))
        resp = asyncio.run(_send(server, method="tasks/list",
                                 params={"status": TASK_STATE_COMPLETED}))
        ids = [t["id"] for t in resp["result"]["tasks"]]
        assert "task-0" in ids
        assert "task-1" not in ids

    def test_invalid_status_value_returns_invalid_params(self):
        server = _server()
        resp = asyncio.run(_send(server, method="tasks/list",
                                 params={"status": "not-a-state"}))
        assert resp["error"]["code"] == RPC_INVALID_PARAMS


# ---------------------------------------------------------------------------
# tasks/cancel
# ---------------------------------------------------------------------------


class TestCancelTask:

    def test_cancel_terminal_returns_not_cancelable(self):
        from src.servers.a2a_server import A2AServer, _StoredTask, task_status as _ts

        server = A2AServer("http://localhost:8000")
        asyncio.run(server._store.set(_StoredTask(
            id="task-done", context_id="ctx",
            state=TASK_STATE_COMPLETED, status=_ts(TASK_STATE_COMPLETED),
        )))
        resp = asyncio.run(
            _send(server, method="tasks/cancel", params={"id": "task-done"})
        )
        assert "error" in resp
        assert resp["error"]["code"] == A2A_TASK_NOT_CANCELABLE

    def test_cancel_bogus_task_returns_not_found(self):
        server = _server()
        resp = asyncio.run(
            _send(server, method="tasks/cancel", params={"id": "task-fake"})
        )
        assert resp["error"]["code"] == A2A_TASK_NOT_FOUND

    def test_cancel_inflight_task_succeeds(self):
        from src.servers.a2a_server import A2AServer, _StoredTask, task_status as _ts

        server = A2AServer("http://localhost:8000")
        asyncio.run(server._store.set(_StoredTask(
            id="task-stuck", context_id="ctx",
            state=TASK_STATE_WORKING, status=_ts(TASK_STATE_WORKING),
        )))
        resp = asyncio.run(
            _send(server, method="tasks/cancel", params={"id": "task-stuck"})
        )
        assert resp["result"]["status"]["state"] == TASK_STATE_CANCELED


# ---------------------------------------------------------------------------
# agent/authenticatedExtendedCard
# ---------------------------------------------------------------------------


class TestExtendedCard:

    def test_extended_card_includes_documentation_url(self):
        server = _server()
        resp = asyncio.run(
            _send(server, method="agent/authenticatedExtendedCard", params={})
        )
        card = resp["result"]
        assert "documentation_url" in card
        assert card["capabilities"]["extended_agent_card"] is True


# ---------------------------------------------------------------------------
# Disabled-by-capability operations
# ---------------------------------------------------------------------------


class TestDisabledByCapability:

    def test_streaming_rejected(self):
        server = _server()
        resp = asyncio.run(_send(server, method="message/stream", params={
            "message": {"message_id": "m", "role": "user",
                          "parts": [{"text": "x", "media_type": "text/plain"}]},
        }))
        assert resp["error"]["code"] == A2A_UNSUPPORTED_OPERATION

    def test_subscribe_to_task_returns_current_task(self):
        """tasks/subscribe now returns the current task snapshot + stream_url."""
        from src.servers.a2a_server import _StoredTask, task_status as _ts

        server = _server()
        asyncio.run(server._store.set(_StoredTask(
            id="task-sub", context_id="ctx-sub",
            state=TASK_STATE_COMPLETED, status=_ts(TASK_STATE_COMPLETED),
        )))
        resp = asyncio.run(
            _send(server, method="tasks/subscribe",
                  params={"id": "task-sub"}),
        )
        assert "result" in resp
        assert "task" in resp["result"]
        assert "stream_url" in resp["result"]
        assert "task-sub" in resp["result"]["stream_url"]
        assert resp["result"]["task"]["id"] == "task-sub"

    def test_subscribe_to_nonexistent_task_returns_error(self):
        server = _server()
        resp = asyncio.run(
            _send(server, method="tasks/subscribe",
                  params={"id": "task-nope"}),
        )
        assert resp["error"]["code"] == A2A_TASK_NOT_FOUND

    @pytest.mark.parametrize("method", [
        "tasks/pushNotificationConfig/set",
        "tasks/pushNotificationConfig/get",
        "tasks/pushNotificationConfig/list",
        "tasks/pushNotificationConfig/delete",
    ])
    def test_push_config_rejected(self, method):
        server = _server()
        resp = asyncio.run(_send(server, method=method, params={}))
        assert resp["error"]["code"] == A2A_PUSH_NOT_SUPPORTED


# ---------------------------------------------------------------------------
# JSON-RPC envelope errors
# ---------------------------------------------------------------------------


class TestJSONRPCEnvelope:

    def test_unknown_method(self):
        server = _server()
        resp = asyncio.run(_send(server, method="not/a/method", params={}))
        assert resp["error"]["code"] == RPC_METHOD_NOT_FOUND

    def test_invalid_jsonrpc_version(self):
        server = _server()
        body = {"jsonrpc": "1.0", "id": "x", "method": "tasks/get", "params": {}}
        resp = asyncio.run(handle_jsonrpc_request(server, body))
        assert resp["error"]["code"] == RPC_INVALID_REQUEST

    def test_notification_request_no_id_returns_empty(self):
        server = _server()
        body = {"jsonrpc": "2.0", "method": "tasks/cancel",
                "params": {"id": "task-anything"}}
        resp = asyncio.run(handle_jsonrpc_request(server, body))
        assert resp == {}

    def test_notification_with_error_returns_empty(self):
        server = _server()
        body = {"jsonrpc": "2.0", "method": "bogus/method", "params": {}}
        resp = asyncio.run(handle_jsonrpc_request(server, body))
        assert resp == {}

    def test_bad_envelope_returns_invalid_request(self):
        server = _server()
        body = []
        resp = asyncio.run(handle_jsonrpc_request(server, body))
        assert resp["error"]["code"] == RPC_INVALID_REQUEST

    def test_threaded_request_with_awaitable_handler(self):
        server = _server()
        resp = asyncio.run(_send(server, method="message/send", params={
            "message": {"message_id": "m-async", "role": "user",
                          "parts": [{"text": "hello", "media_type": "text/plain"}]},
        }))
        assert "result" in resp
        assert resp["result"]["status"]["state"] == TASK_STATE_COMPLETED


# ---------------------------------------------------------------------------
# Protocol metadata
# ---------------------------------------------------------------------------


def test_protocol_version_constant_is_v1():
    assert PROTOCOL_VERSION == "1.0"
    assert AGENT_VERSION.count(".") >= 1


def test_terminal_task_states_constant_is_frozenset():
    assert isinstance(TERMINAL_TASK_STATES, frozenset)
    assert TASK_STATE_COMPLETED in TERMINAL_TASK_STATES
    assert TASK_STATE_CANCELED in TERMINAL_TASK_STATES
    assert TASK_STATE_FAILED in TERMINAL_TASK_STATES


# ---------------------------------------------------------------------------
# Task-event emission
# ---------------------------------------------------------------------------


class TestTaskEvents:

    @pytest.mark.asyncio
    async def test_transition_emits_event(self):
        from src.servers.a2a_server import (
            A2AServer, _StoredTask, task_status as _ts, task_update_channel,
        )
        from src.services.events import bus as event_bus

        server = A2AServer("http://localhost:8000")
        task = _StoredTask(
            id="task-ev-1", context_id="ctx-ev-1",
            state=TASK_STATE_WORKING, status=_ts(TASK_STATE_WORKING),
        )
        await server._store.set(task)

        # Subscribe *before* the transition so there's no race.
        ready = asyncio.Event()
        received: list[dict] = []

        async def _collect():
            async with event_bus.subscribe() as sub:
                ready.set()
                async for envelope in sub:
                    if envelope.get("channel") == task_update_channel("task-ev-1"):
                        received.append(envelope["event"])
                    if len(received) >= 2:
                        break

        collector = asyncio.create_task(_collect())
        await ready.wait()
        # Now transition — collector is live.
        await server._transition(task, TASK_STATE_COMPLETED)
        # Give the event a moment to propagate then cancel.
        await asyncio.sleep(0.05)
        collector.cancel()

        assert len(received) >= 1
        assert received[-1]["status"]["state"] == TASK_STATE_COMPLETED

    @pytest.mark.asyncio
    async def test_send_message_emits_event(self):
        from src.services.events import bus as event_bus

        server = _server()
        ready = asyncio.Event()
        received: list[dict] = []

        async def _collect():
            nonlocal received
            async with event_bus.subscribe() as sub:
                ready.set()
                async for envelope in sub:
                    if envelope.get("channel", "").startswith("task:"):
                        received.append(envelope["event"])
                        # Collect until we see a completed/canceled state.
                        if envelope["event"].get("status", {}).get("state") in (
                            "completed", "failed", "canceled", "rejected",
                        ):
                            return

        collector = asyncio.create_task(_collect())
        await ready.wait()
        resp = await _send(server, method="message/send", params={
            "message": {"message_id": "m-ev", "role": "user",
                          "parts": [{"text": "hello", "media_type": "text/plain"}]},
        })
        await asyncio.sleep(0.05)
        collector.cancel()

        task = resp["result"]
        assert task["status"]["state"] == TASK_STATE_COMPLETED
        assert len(received) >= 2, f"expected >=2 events, got {len(received)}: {received}"
        # First event should be working state.
        assert received[0]["status"]["state"] == TASK_STATE_WORKING
        # Last event should be completed.
        assert received[-1]["status"]["state"] == TASK_STATE_COMPLETED

    @pytest.mark.asyncio
    async def test_event_bus_publication(self):
        from src.servers.a2a_server import (
            A2AServer, _StoredTask, task_status as _ts, task_update_channel,
        )
        from src.services.events import bus as event_bus

        server = A2AServer("http://localhost:8000")
        task = _StoredTask(
            id="task-ev-2", context_id="ctx-ev-2",
            state=TASK_STATE_WORKING, status=_ts(TASK_STATE_WORKING),
        )
        await server._store.set(task)

        ready = asyncio.Event()
        received: list[dict] = []

        async def _collect():
            async with event_bus.subscribe() as sub:
                ready.set()
                async for envelope in sub:
                    if envelope.get("channel") == task_update_channel("task-ev-2"):
                        received.append(envelope)
                        break

        collector = asyncio.create_task(_collect())
        await ready.wait()
        await server._transition(task, TASK_STATE_COMPLETED)
        await asyncio.sleep(0.05)
        collector.cancel()

        assert len(received) == 1
        env = received[0]
        assert env["channel"] == "task:task-ev-2"
        ev = env["event"]
        assert ev["id"] == "task-ev-2"
        assert ev["status"]["state"] == TASK_STATE_COMPLETED


# ---------------------------------------------------------------------------
# SSE endpoint integration
# ---------------------------------------------------------------------------


class TestSSEEndpoint:

    def test_sse_404_for_nonexistent_task(self):
        import src.api.main as api_main
        from fastapi.testclient import TestClient

        with TestClient(api_main.app) as client:
            resp = client.get("/a2a/tasks/task-ghost:subscribe")
            assert resp.status_code == 404

    def test_sse_first_event_for_completed_task(self):
        """Terminal task -> SSE yields one event then completes."""
        import json
        import src.api.main as api_main
        from fastapi.testclient import TestClient
        from src.servers.a2a_server import (
            A2AServer, _StoredTask, task_status as _ts,
        )

        with TestClient(api_main.app) as client:
            server = A2AServer("http://testserver")
            asyncio.run(server._store.set(_StoredTask(
                id="task-sse-c", context_id="ctx-sse-c",
                state=TASK_STATE_COMPLETED, status=_ts(TASK_STATE_COMPLETED),
            )))
            old = api_main.a2a_server
            api_main.a2a_server = server
            try:
                resp = client.get("/a2a/tasks/task-sse-c:subscribe")
                assert resp.status_code == 200
                ct = resp.headers.get("content-type", "")
                assert "text/event-stream" in ct
                data_lines = [
                    ln for ln in resp.text.split("\n")
                    if ln.startswith("data: ")
                ]
                assert len(data_lines) >= 1
                first = json.loads(data_lines[0][6:])
                assert first["jsonrpc"] == "2.0"
                assert first["result"]["id"] == "task-sse-c"
                assert first["result"]["status"]["state"] == TASK_STATE_COMPLETED
            finally:
                api_main.a2a_server = old

    def test_sse_content_type_header(self):
        import src.api.main as api_main
        from fastapi.testclient import TestClient
        from src.servers.a2a_server import (
            A2AServer, _StoredTask, task_status as _ts,
        )

        with TestClient(api_main.app) as client:
            server = A2AServer("http://testserver")
            asyncio.run(server._store.set(_StoredTask(
                id="task-sse-ct", context_id="ctx-ct",
                state=TASK_STATE_COMPLETED, status=_ts(TASK_STATE_COMPLETED),
            )))
            old = api_main.a2a_server
            api_main.a2a_server = server
            try:
                resp = client.get("/a2a/tasks/task-sse-ct:subscribe")
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                assert "no-cache" in resp.headers.get("cache-control", "")
            finally:
                api_main.a2a_server = old
