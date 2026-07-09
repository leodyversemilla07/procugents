"""Tests for the A2A v1.0 protocol implementation (https://a2a-protocol.org/v1.0.0/specification).

Covers:
    * Agent Card shape conformance to v1.0 / proto AgentCard
    * message/send round-trip through the orchestrator
    * tasks/get and tasks/cancel lifecycle
    * tasks/list with cursor pagination
    * agent/authenticatedExtendedCard
    * Error envelope correctness (JSON-RPC + A2A-specific codes)
    * Disabled-by-capability operations (streaming, push-notifications)
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
    # Error codes
    A2A_TASK_NOT_FOUND,
    A2A_TASK_NOT_CANCELABLE,
    A2A_PUSH_NOT_SUPPORTED,
    A2A_UNSUPPORTED_OPERATION,
    A2A_CONTENT_TYPE_NOT_SUPPORTED,
    RPC_METHOD_NOT_FOUND,
    RPC_INVALID_REQUEST,
    RPC_INVALID_PARAMS,
    # Constants
    TASK_STATE_COMPLETED,
    TASK_STATE_CANCELED,
    TASK_STATE_WORKING,
    TERMINAL_TASK_STATES,
    PROTOCOL_VERSION,
    AGENT_VERSION,
    AGENT_NAME,
    # Helpers
    build_agent_card,
    handle_jsonrpc_request,
)


def _server():
    """Return a fresh A2AServer for each test."""
    from src.servers.a2a_server import A2AServer

    return A2AServer("http://localhost:8000")


async def _send(server, *, method: str, params: dict[str, Any] | None = None, req_id="req-1"):
    """Send a JSON-RPC envelope and return the response dict."""
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
    """v1.0 Agent Card must conform to proto AgentCard fields."""

    def test_required_fields_present(self):
        card = build_agent_card("http://localhost:8000")
        for f in (
            "name",
            "description",
            "version",
            "supported_interfaces",
            "capabilities",
            "default_input_modes",
            "default_output_modes",
            "skills",
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
        # First entry is JSON-RPC per spec convention (preferred).
        assert interfaces[0]["protocol_binding"] == "JSONRPC"
        assert interfaces[0]["protocol_version"] == "1.0"
        # Each interface has url + protocol_binding + protocol_version
        for i in interfaces:
            assert {"url", "protocol_binding", "protocol_version"}.issubset(set(i))

    def test_capabilities_matches_proto(self):
        card = build_agent_card("http://localhost:8000")
        caps = card["capabilities"]
        # streaming & push_notifications explicitly disabled.
        assert caps["streaming"] is False
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
        # Provider is optional but we populate it.
        card = build_agent_card("http://localhost:8000")
        assert "provider" in card
        assert "organization" in card["provider"]
        assert "url" in card["provider"]

    def test_field_names_are_snake_case(self):
        card = build_agent_card("http://localhost:8000")
        # All agent-card keys must be snake_case; check top-level + nested.
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
    """Implementation of JSON-RPC method message/send."""

    @pytest.mark.asyncio
    async def test_legal_check_compliant(self):
        server = _server()
        resp = await _send(server, method="message/send", params={
            "message": {
                "message_id": "m-1",
                "role": "user",
                "parts": [{"data": {"skill": "legal_check", "params": {"contract_amount": 500000}}}],
            },
        })
        assert "result" in resp, resp
        task = resp["result"]
        assert task["status"]["state"] == TASK_STATE_COMPLETED
        # Legal compliance check is the inner skill response.
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
        assert len(task["history"]) >= 2  # user request + assistant reply

    @pytest.mark.asyncio
    async def test_task_state_fields_match_proto(self):
        server = _server()
        resp = await _send(server, method="message/send", params={
            "message": {"message_id": "m", "role": "user",
                          "parts": [{"text": "x", "media_type": "text/plain"}]},
        })
        task = resp["result"]
        # Spec: id, context_id, status, artifacts, history
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
        # Plain text mentioning 'legal' should resolve to legal_check skill
        # (amount passed via text parsing is best-effort; we expect either
        # 0 or a returned result; test just verifies the message is accepted)
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
        from src.servers.a2a_server import A2AServer

        server = A2AServer("http://localhost:8000")
        # create a task by hand
        from src.servers.a2a_server import _StoredTask, task_status as _ts

        server._tasks["task-fake"] = _StoredTask(
            id="task-fake",
            context_id="ctx-fake",
            state=TASK_STATE_COMPLETED,
            status=_ts(TASK_STATE_COMPLETED),
        )
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
            A2AServer,
            _StoredTask,
            task_status as _ts,
        )

        server = A2AServer("http://localhost:8000")
        server._tasks["task-h"] = _StoredTask(
            id="task-h",
            context_id="ctx-h",
            state=TASK_STATE_COMPLETED,
            status=_ts(TASK_STATE_COMPLETED),
            history=[{"messageId": "any", "role": "user", "parts": []}],
        )
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
            A2AServer,
            _StoredTask,
            task_status as _ts,
        )

        server = A2AServer("http://localhost:8000")
        # Create one completed and one canceled task.
        for i in range(2):
            state = TASK_STATE_COMPLETED if i == 0 else TASK_STATE_CANCELED
            server._tasks[f"task-{i}"] = _StoredTask(
                id=f"task-{i}", context_id=f"ctx-{i}",
                state=state, status=_ts(state),
            )

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
        server._tasks["task-done"] = _StoredTask(
            id="task-done", context_id="ctx",
            state=TASK_STATE_COMPLETED, status=_ts(TASK_STATE_COMPLETED),
        )
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
        server._tasks["task-stuck"] = _StoredTask(
            id="task-stuck", context_id="ctx",
            state=TASK_STATE_WORKING, status=_ts(TASK_STATE_WORKING),
        )
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

    def test_subscribe_to_task_rejected(self):
        server = _server()
        resp = asyncio.run(
            _send(server, method="tasks/subscribe",
                  params={"id": "task-anything"}),
        )
        assert resp["error"]["code"] == A2A_UNSUPPORTED_OPERATION

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
        resp = asyncio.run(
            _send(server, method="not/a/method", params={})
        )
        assert resp["error"]["code"] == RPC_METHOD_NOT_FOUND

    def test_invalid_jsonrpc_version(self):
        server = _server()
        body = {"jsonrpc": "1.0", "id": "x", "method": "tasks/get", "params": {}}
        resp = asyncio.run(handle_jsonrpc_request(server, body))
        assert resp["error"]["code"] == RPC_INVALID_REQUEST

    def test_notification_request_no_id_returns_empty(self):
        """A notification (no id) returns {} per spec."""
        server = _server()
        body = {"jsonrpc": "2.0", "method": "tasks/cancel",
                "params": {"id": "task-anything"}}
        # Body with no "id" field => notification; expect an empty dict.
        resp = asyncio.run(handle_jsonrpc_request(server, body))
        assert resp == {}

    def test_notification_with_error_returns_empty(self):
        """Even errors reported in notification form return {} per spec."""
        server = _server()
        body = {"jsonrpc": "2.0", "method": "bogus/method", "params": {}}
        resp = asyncio.run(handle_jsonrpc_request(server, body))
        assert resp == {}

    def test_bad_envelope_returns_invalid_request(self):
        server = _server()
        body = []  # not a dict
        resp = asyncio.run(handle_jsonrpc_request(server, body))
        assert resp["error"]["code"] == RPC_INVALID_REQUEST

    def test_threaded_request_with_awaitable_handler(self):
        """make sure async ops work even from sync-result dispatcher."""
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
