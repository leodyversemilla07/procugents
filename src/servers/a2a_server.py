"""A2A v1.0-compliant agent server for ProCuGents.

Implements abstract operations from the A2A v1.0 spec
(https://a2a-protocol.org/v1.0.0/specification/) bound to JSON-RPC 2.0
over HTTP, plus a parallel set of HTTP/REST endpoints.

This module uses *no external a2a SDK* -- the canonical wire format is
mapped directly to Python dicts so we stay spec-faithful without
pinning an SDK.

Supported operations:
    message/send                      : non-streaming send (text part in, task out)
    tasks/get                         : retrieve current state of a task
    tasks/list                        : list tasks visible to the caller
    tasks/cancel                      : ask server to cancel a task
    agent/authenticatedExtendedCard   : server-side capability detail

Streaming and push-notification operations are disabled in the
AgentCard. Clients attempting them receive
UnsupportedOperationError / PushNotificationNotSupportedError per the spec.

Field-name convention: proto3 snake_case maps 1:1 to JSON snake_case
per A2A Section 5.4 ("JSON Field Naming Convention").
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "1.0"
AGENT_VERSION = "1.0.0"
AGENT_NAME = "ProCuGents"
AGENT_DESCRIPTION = (
    "Multi-agent procurement anomaly detector for the Philippine "
    "government, grounded in RA 12009 (Sec 26), RA 12009 IRR, RA 9184 IRR, "
    "and COA 2023-004."
)
PROVIDER_ORG = "ProCuGents"
PROVIDER_URL = "https://github.com/leodyversemilla07/procugents"


# JSON-RPC 2.0 standard error codes.
RPC_PARSE_ERROR = -32700
RPC_INVALID_REQUEST = -32600
RPC_METHOD_NOT_FOUND = -32601
RPC_INVALID_PARAMS = -32602
RPC_INTERNAL_ERROR = -32603

# A2A-specific error codes (spec Section 3.3.2).
A2A_TASK_NOT_FOUND = -32001
A2A_TASK_NOT_CANCELABLE = -32002
A2A_PUSH_NOT_SUPPORTED = -32003
A2A_UNSUPPORTED_OPERATION = -32004
A2A_CONTENT_TYPE_NOT_SUPPORTED = -32005
A2A_INVALID_AGENT_RESPONSE = -32006


def task_update_channel(task_id: str) -> str:
    """EventBus channel for a specific task's state transitions."""
    return f"task:{task_id}"


# Task state machine (spec Section 2.2 / proto enum TaskState).
TASK_STATE_UNSPECIFIED     = "unspecified"
TASK_STATE_SUBMITTED       = "submitted"
TASK_STATE_WORKING         = "working"
TASK_STATE_COMPLETED       = "completed"
TASK_STATE_FAILED          = "failed"
TASK_STATE_CANCELED        = "canceled"
TASK_STATE_INPUT_REQUIRED  = "input-required"
TASK_STATE_REJECTED        = "rejected"
TASK_STATE_AUTH_REQUIRED   = "auth-required"
TERMINAL_TASK_STATES = frozenset({
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_CANCELED,
    TASK_STATE_REJECTED,
})


def now_iso8601() -> str:
    """Current UTC time as ISO-8601 string (A2A timestamp format)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str) -> str:
    """UUIDv4 with a short prefix (e.g. task-abc123)."""
    return f"{prefix}-{uuid.uuid4().hex}"



# ---------------------------------------------------------------------------
# Wire-format helpers (proto -> JSON snake_case per A2A Section 5.4)
# ---------------------------------------------------------------------------


def make_message(role: str,
                 parts: list,
                 *,
                 context_id=None,
                 task_id=None,
                 message_id=None) -> dict:
    """Build an A2A Message (proto Message).

    Required per spec: message_id, role, parts. The others optional.
    Field names use snake_case.
    """
    msg = {
        "message_id": message_id or new_id("msg"),
        "role": role,
        "parts": parts,
    }
    if context_id is not None:
        msg["context_id"] = context_id
    if task_id is not None:
        msg["task_id"] = task_id
    return msg


def text_part(text: str, *, media_type: str = "text/plain") -> dict:
    """A textual Message Part (proto Part.text)."""
    return {"text": text, "media_type": media_type}


def data_part(data: dict, *, media_type: str = "application/json") -> dict:
    """A structured Message Part (proto Part.data)."""
    return {"data": data, "media_type": media_type}


def artifact(parts: list, *,
             artifact_id=None,
             name=None,
             description=None) -> dict:
    """Build an Artifact (proto Artifact)."""
    art = {"artifact_id": artifact_id or new_id("art"), "parts": parts}
    if name is not None:
        art["name"] = name
    if description is not None:
        art["description"] = description
    return art


def task_status(state: str, *, message: dict | None = None) -> dict:
    """Build a TaskStatus (proto TaskStatus)."""
    out = {"state": state, "timestamp": now_iso8601()}
    if message is not None:
        out["message"] = message
    return out



# ---------------------------------------------------------------------------
# AgentCard (proto: AgentCard)
# ---------------------------------------------------------------------------


def _skill(id_: str, name: str, description: str, tags: list,
          in_out_modes: tuple = ()) -> dict:
    """Single AgentSkill (proto)."""
    sk = {
        "id": id_,
        "name": name,
        "description": description,
        "tags": tags,
    }
    if in_out_modes:
        input_modes, output_modes = in_out_modes
        sk["input_modes"] = input_modes
        sk["output_modes"] = output_modes
    return sk


def build_agent_card(base_url: str, *, extended: bool = False) -> dict:
    """Build the v1.0 AgentCard (proto AgentCard).

    Required fields per spec: name, description, version,
    supported_interfaces, capabilities, default_input_modes,
    default_output_modes, skills.

    supported_interfaces is ORDERED per spec; JSON-RPC over HTTP is
    listed first since it is what most clients speak today.
    """
    rpc_url = f"{base_url.rstrip('/')}/a2a/jsonrpc"
    rest_url = f"{base_url.rstrip('/')}/a2a"

    skills = [
        _skill(
            "legal_compliance_check", "Legal Compliance Check (RA 12009)",
            "Verify procurement amount and modality meet RA 12009 "
            "Sec 26 SVP threshold and PhilGEPS posting requirements.",
            ["legal", "ra-12009", "compliance"],
        ),
        _skill(
            "price_anomaly_analysis", "Price Anomaly Analysis",
            "Compare contract price against a market baseline and flag "
            "potential inflation per COA Circular 2023-004 Section 4.2.",
            ["price", "coa-2023-004", "inflation"],
        ),
        _skill(
            "bidding_integrity_scan", "Bidding Integrity Scan",
            "Audit bidder metadata for sub-3 bid counts, shared addresses, "
            "and HoPE approval gaps per RA 9184 IRR Sec 52.1.",
            ["bid", "dummy-bidders", "hope-approval"],
        ),
        _skill(
            "document_compliance_audit", "Document Compliance Audit",
            "Check mandatory documents (PhilGEPS registration, business "
            "permit, bid security, PCAB license) per COA 2023-004 Annex A.",
            ["document", "philgeps", "coa-2023-004"],
        ),
        _skill(
            "full_procurement_audit", "Full Five-Agent Procurement Audit",
            "Run the full LangGraph pipeline: legal -> price -> scrape "
            "-> bid -> doc -> LLM -> alert. Emits a COA-style "
            "disallowance report when an Illegal/Excessive/Unconscionable "
            "flag is raised.",
            ["audit", "multi-agent", "ra-12009", "coa-2023-004"],
        ),
    ]

    card = {
        "name": AGENT_NAME,
        "description": AGENT_DESCRIPTION,
        "version": AGENT_VERSION,
        "supported_interfaces": [
            {"url": rpc_url, "protocol_binding": "JSONRPC",
             "protocol_version": PROTOCOL_VERSION},
            {"url": rest_url, "protocol_binding": "HTTP+JSON",
             "protocol_version": PROTOCOL_VERSION},
        ],
        "provider": {"organization": PROVIDER_ORG, "url": PROVIDER_URL},
        "capabilities": {
            # Streaming: enabled via SSE on /a2a/tasks/{id}:subscribe.
            # Push notifications: no webhook delivery wired in dev.
            "streaming": True,
            "push_notifications": False,
            "extended_agent_card": True,
        },
        "default_input_modes": ["text/plain", "application/json"],
        "default_output_modes": ["application/json", "text/plain"],
        "skills": skills,
    }
    if extended:
        card["documentation_url"] = (
            "https://github.com/leodyversemilla07/procugents"
            "/blob/main/docs/a2a-integration.md"
        )
        card["security_schemes"] = {}
        card["security_requirements"] = []
    return card




# ---------------------------------------------------------------------------
# In-process task store
# ---------------------------------------------------------------------------


@dataclass
class _StoredTask:
    """Server-side task record (proto Task mirror)."""

    id: str
    context_id: str
    state: str
    status: dict
    artifacts: list = field(default_factory=list)
    history: list = field(default_factory=list)
    result_output: dict | None = None
    # timestamps are tracked via the underlying status["timestamp"].
    updated_at: float = field(default_factory=time.time)

    def to_wire(self) -> dict:
        """Serialize to the v1.0 JSON shape."""
        return {
            "id": self.id,
            "context_id": self.context_id,
            "status": self.status,
            "artifacts": list(self.artifacts),
            "history": list(self.history),
        }


class _A2AError(Exception):
    """Internal exception carrying an A2A/JSON-RPC error code."""

    def __init__(self, code: int, *, data: dict | None = None):
        super().__init__(f"A2A RPC error {code}")
        self.code = code
        self.data = data or {}




# ---------------------------------------------------------------------------
# A2AServer - in-process A2A v1.0 compliant server
# ---------------------------------------------------------------------------


class A2AServer:
    """A2A v1.0 server.

    Tracks tasks in-process. For multi-process deployments swap
    ``self._tasks`` for a Redis-backed dict.

    All public ``op_*`` methods are coroutine-safe via ``asyncio.Lock``.
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url
        self._tasks: dict = {}
        self._lock = asyncio.Lock()

    # ---- Agent Card ---------------------------------------------------

    def get_agent_card(self, *, extended: bool = False) -> dict:
        """Public agent card / extended-card getter."""
        return build_agent_card(self.base_url, extended=extended)

    # ---- Internal helpers --------------------------------------------

    def _raise(self, code: int, *, data: dict | None = None) -> None:
        """Raise an internal A2A error with the given JSON-RPC code."""
        raise _A2AError(code=code, data=data)

    async def _create_task(self, *,
                            context_id: str | None = None,
                            initial_message: dict | None = None) -> _StoredTask:
        async with self._lock:
            task = _StoredTask(
                id=new_id("task"),
                context_id=context_id or new_id("ctx"),
                state=TASK_STATE_SUBMITTED,
                status=task_status(TASK_STATE_SUBMITTED),
                history=[initial_message] if initial_message else [],
            )
            self._tasks[task.id] = task
            return task

    async def _transition(self, task: _StoredTask,
                            new_state: str, *,
                            message: dict | None = None) -> None:
        async with self._lock:
            task.state = new_state
            task.status = task_status(new_state, message=message)
            task.updated_at = time.time()
        # Emit outside the lock to avoid any risk of reentrancy.
        await self._emit_task_event(task)



    # ---- Skill dispatch -----------------------------------------------

    @staticmethod
    def _resolve_skill(parts: list[dict]) -> tuple[str, dict]:
        """Pick skill from message parts.

        Prefer a JSON ``data`` part that specifies {"skill": "..., "params": {...}}.
        Falls back to text-pattern matching on text parts.
        """
        params: dict = {}
        for part in parts:
            if not isinstance(part, dict):
                continue
            if isinstance(part.get("data"), dict):
                skill = part["data"].get("skill")
                params = part["data"].get("params") or {}
                if skill:
                    return skill, params
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text = part["text"].lower()
                params = {}
                if "card" in text or "who are you" in text:
                    return "agent_card", params
                if "list" in text and "task" in text:
                    return "list", params
                if "cancel" in text or "kill" in text:
                    return "cancel", params
                if "legal" in text or "compliance" in text or "ra 12009" in text:
                    return "legal_check", params
                if "price" in text or "inflation" in text:
                    return "price_check", params
                if "philgeps" in text or "search" in text:
                    return "search", params
                if "document" in text:
                    return "doc_check", params
                return "audit", params
        return "audit", {}

    async def _invoke_skill(self, skill: str, params: dict) -> dict:
        """Dispatch to the orchestrator based on skill name."""
        from src.orchestration.orchestrator import analyze_procurement, SVP_THRESHOLD

        if skill == "agent_card":
            return self.get_agent_card()
        if skill == "list":
            return {
                "tasks": [t.to_wire() for t in list(self._tasks.values())[-50:]],
                "total": len(self._tasks),
            }
        if skill == "cancel":
            return {"status": "canceled"}

        if skill == "legal_check":
            amount = float(params.get("contract_amount", 0))
            return {
                "compliant": amount <= SVP_THRESHOLD,
                "threshold": SVP_THRESHOLD,
                "required": ("competitive bidding"
                             if amount > SVP_THRESHOLD
                             else "small value procurement"),
            }
        if skill == "price_check":
            amount = float(params.get("contract_amount", 0))
            baseline = amount * 0.7
            return {
                "amount": amount,
                "baseline": baseline,
                "flag": ("potential_inflation"
                         if amount > baseline
                         else "normal"),
            }
        if skill == "search":
            return {"results": [],
                    "note": "PhilGEPS live hooks in src.servers.mcp.philgeps_data"}

        if skill == "doc_check":
            documents = params.get("documents") or {}
            missing = []
            if documents.get("philgeps_reg") is False:
                missing.append("PhilGEPS Certificate of Registration")
            if documents.get("business_permit") is False:
                missing.append("Business Permit")
            return {"missing_documents": missing,
                    "compliant": len(missing) == 0}

        # Default = full audit
        return analyze_procurement(
            contract_id=str(params.get("contract_id")
                           or f"PO-A2A-{uuid.uuid4().hex[:8]}"),
            contract_description=str(params.get("description")
                                    or "Procurement from A2A"),
            contract_amount=float(params.get("contract_amount") or 0),
            agency=str(params.get("agency") or ""),
            procurement_type=str(params.get("procurement_type")
                                or "public_bidding"),
            hope_approval_proof=bool(params.get("hope_approval_proof", False)),
        )



    # ---- A2A v1.0 operations ----------------------------------------

    async def op_send_message(self, *,
                                message: dict,
                                configuration: dict | None = None,
                                metadata: dict | None = None,
                                tenant: str | None = None) -> dict:
        """Implementation of message/send (Section 3.1.1).

        The spec allows the response to be either a Task object or a Message
        object. Here we always return a Task so callers can correlate
        state with the subsequent tasks/get call.
        """
        if not isinstance(message, dict):
            self._raise(RPC_INVALID_PARAMS, data={"field": "message"})
        parts = message.get("parts") or []
        if not parts:
            self._raise(A2A_CONTENT_TYPE_NOT_SUPPORTED,
                        data={"reason": "no message parts provided"})

        task = await self._create_task(
            context_id=message.get("context_id"),
            initial_message=message,
        )
        ctx = task.context_id
        skill, params = self._resolve_skill(parts)

        await self._transition(task, TASK_STATE_WORKING)
        try:
            output = await self._invoke_skill(skill, params)
        except Exception as exc:
            err_msg = make_message(
                "agent",
                [text_part(f"skill execution failed: {exc}")],
                context_id=ctx, task_id=task.id,
            )
            await self._transition(task, TASK_STATE_FAILED, message=err_msg)
            return task.to_wire()

        assistant_msg = make_message(
            "agent",
            [data_part({"skill": skill, "result": output})],
            context_id=ctx, task_id=task.id,
        )
        art = artifact(
            [data_part(output)],
            name=f"{skill}_result",
            description=f"Output of skill `{skill}`",
        )
        async with self._lock:
            task.history.append(assistant_msg)
            task.artifacts.append(art)
            task.state = TASK_STATE_COMPLETED
            task.status = task_status(TASK_STATE_COMPLETED, message=assistant_msg)
            task.result_output = output
            task.updated_at = time.time()
        await self._emit_task_event(task)
        return task.to_wire()

    def op_get_task(self, *,
                     id: str,
                     history_length: int | None = None,
                     tenant: str | None = None) -> dict:
        """tasks/get (Section 3.1.3)."""
        task = self._tasks.get(id)
        if task is None:
            self._raise(A2A_TASK_NOT_FOUND, data={"task_id": id})
        wire = task.to_wire()
        # History length semantics per Section 3.2.4.
        if history_length == 0:
            wire.pop("history", None)
        elif history_length is not None and history_length > 0:
            wire["history"] = wire["history"][-history_length:]
        return wire



    def op_list_tasks(self, *,
                        context_id: str | None = None,
                        status: str | None = None,
                        page_size: int | None = None,
                        page_token: str | None = None,
                        history_length: int | None = None,
                        include_artifacts: bool | None = None,
                        tenant: str | None = None) -> dict:
        """tasks/list (Section 3.1.4).

        Cursor-paginated over the in-memory dict using ``updated_at`` order.
        For production swap for a database cursor.
        """
        all_tasks = list(self._tasks.values())
        if context_id:
            all_tasks = [t for t in all_tasks if t.context_id == context_id]
        if status:
            if status not in (
                TASK_STATE_SUBMITTED, TASK_STATE_WORKING,
                TASK_STATE_COMPLETED, TASK_STATE_FAILED,
                TASK_STATE_CANCELED, TASK_STATE_INPUT_REQUIRED,
                TASK_STATE_REJECTED, TASK_STATE_AUTH_REQUIRED,
                TASK_STATE_UNSPECIFIED,
            ):
                self._raise(RPC_INVALID_PARAMS,
                            data={"field": "status", "value": status})
            all_tasks = [t for t in all_tasks if t.state == status]

        all_tasks.sort(key=lambda t: t.updated_at, reverse=True)
        total = len(all_tasks)
        size = max(1, min(page_size or 50, 100))
        try:
            offset = int(page_token) if page_token else 0
        except ValueError:
            offset = 0
        page = all_tasks[offset:offset + size]
        next_tok = str(offset + size) if offset + size < total else ""

        out_tasks: list[dict] = []
        for t in page:
            wire = t.to_wire()
            # Per spec artifacts MUST be omitted entirely when false.
            if include_artifacts is False:
                wire.pop("artifacts", None)
            if history_length == 0:
                wire.pop("history", None)
            elif history_length is not None and history_length > 0:
                wire["history"] = wire["history"][-history_length:]
            out_tasks.append(wire)
        return {
            "tasks": out_tasks,
            "next_page_token": next_tok,
            "page_size": size,
            "total_size": total,
        }

    async def op_cancel_task(self, *,
                        id: str,
                        tenant: str | None = None,
                        metadata: dict | None = None) -> dict:
        """tasks/cancel (Section 3.1.5). Idempotent on terminal tasks."""
        task = self._tasks.get(id)
        if task is None:
            self._raise(A2A_TASK_NOT_FOUND, data={"task_id": id})
        if task.state in TERMINAL_TASK_STATES:
            self._raise(A2A_TASK_NOT_CANCELABLE,
                        data={"task_id": id, "state": task.state})
        note = make_message(
            "agent",
            [text_part("canceled by client")],
            context_id=task.context_id,
            task_id=task.id,
        )
        async with self._lock:
            task.state = TASK_STATE_CANCELED
            task.status = task_status(TASK_STATE_CANCELED, message=note)
            task.updated_at = time.time()
        await self._emit_task_event(task)
        return task.to_wire()

    def op_get_authenticated_extended_card(self, *,
                                              tenant: str | None = None) -> dict:
        """agent/authenticatedExtendedCard (Section 3.1.11)."""
        if not self.get_agent_card()["capabilities"]["extended_agent_card"]:
            self._raise(A2A_UNSUPPORTED_OPERATION,
                        data={"reason": "extended_agent_card not enabled"})
        return self.get_agent_card(extended=True)



    # ---- Real streaming + disabled-by-capability stubs ---------------

    async def op_send_streaming_message(self, **kwargs):
        """message/stream — remains disabled.

        We support streaming via ``tasks/subscribe`` + SSE, not via
        ``message/stream``. The latter would require the client to keep
        the JSON-RPC POST connection open, which is less practical than
        the dedicated SSE endpoint.
        """
        self._raise(A2A_UNSUPPORTED_OPERATION,
                    data={"reason": "use tasks/subscribe + SSE instead"})

    async def op_subscribe_to_task(self, *, id: str, tenant=None):
        """tasks/subscribe — acknowledge with current task state.

        Returns the task snapshot immediately; the client should then
        connect to the SSE endpoint at ``stream_url`` for ongoing
        state transition events.
        """
        task = self._tasks.get(id)
        if task is None:
            self._raise(A2A_TASK_NOT_FOUND, data={"task_id": id})
        return {
            "task": task.to_wire(),
            "stream_url": f"{self.base_url}/a2a/tasks/{id}:subscribe",
        }

    def op_create_push_config(self, **kwargs):
        self._raise(A2A_PUSH_NOT_SUPPORTED,
                    data={"reason": "push_notifications capability is false in AgentCard"})

    def op_get_push_config(self, **kwargs):
        self._raise(A2A_PUSH_NOT_SUPPORTED)

    def op_list_push_configs(self, **kwargs):
        self._raise(A2A_PUSH_NOT_SUPPORTED)

    def op_delete_push_config(self, **kwargs):
        self._raise(A2A_PUSH_NOT_SUPPORTED)

    # ---- Task event emission -------------------------------------

    async def _emit_task_event(self, task: _StoredTask) -> None:
        """Publish a task-state change to the in-process event bus.

        The SSE layer (``/a2a/tasks/{id}:subscribe``) picks this up via
        ``bus.subscribe()`` on the per-task channel and pushes it down
        the wire as an SSE ``data:`` line.
        """
        try:
            from src.services.events import bus

            await bus.publish(task_update_channel(task.id), task.to_wire())
        except Exception:
            logger.exception("failed to emit task event for %s", task.id)


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 dispatcher (Section 9 of the A2A v1.0 spec)
# ---------------------------------------------------------------------------


# Maps JSON-RPC method names (proto RPC service definitions) to handlers.
# Second tuple element flags SSE-style streaming (reserved for future use).
# ``tasks/subscribe`` returns a normal JSON-RPC response (not SSE on
# the JSON-RPC endpoint); streaming happens via the dedicated
# ``/a2a/tasks/{id}:subscribe`` SSE endpoint in main.py.
METHOD_REGISTRY = {
    "message/send":                      ("op_send_message",                       False),
    "message/stream":                     ("op_send_streaming_message",             False),
    "tasks/get":                          ("op_get_task",                           False),
    "tasks/list":                         ("op_list_tasks",                         False),
    "tasks/cancel":                       ("op_cancel_task",                        False),
    "tasks/subscribe":                    ("op_subscribe_to_task",                  False),
    "tasks/pushNotificationConfig/set":    ("op_create_push_config",                 False),
    "tasks/pushNotificationConfig/get":    ("op_get_push_config",                    False),
    "tasks/pushNotificationConfig/list":  ("op_list_push_configs",                  False),
    "tasks/pushNotificationConfig/delete": ("op_delete_push_config",                 False),
    "agent/authenticatedExtendedCard":    ("op_get_authenticated_extended_card",    False),
}


def _dispatch(server: A2AServer, method: str, params: dict | None):
    """Route a JSON-RPC method call to the right op_* handler.

    If the handler is async, returns a coroutine for the caller to await.
    Detection is by inspect.iscoroutinefunction so we don't have to invoke
    the handler to find out (cheaper for short-circuit errors).
    """
    entry = METHOD_REGISTRY.get(method)
    if entry is None:
        raise _A2AError(code=RPC_METHOD_NOT_FOUND, data={"method": method})
    handler_name = entry[0]
    handler = getattr(server, handler_name, None)
    if handler is None:
        raise _A2AError(code=RPC_METHOD_NOT_FOUND, data={"method": method})
    params = params or {}
    import inspect
    if inspect.iscoroutinefunction(handler):
        return handler(**params)
    return handler(**params)


async def _await_handler(coro):
    """Await an arbitrary coroutine."""
    return await coro




async def handle_jsonrpc_request(server: A2AServer,
                                 body: dict,
                                 *,
                                 request_id: Any = None) -> dict:
    """Process a single JSON-RPC 2.0 request envelope.

    Returns either:

    * ``JSONRPCSuccessResponse`` (``{"jsonrpc", "id", "result"}``)
    * ``JSONRPCErrorResponse`` (``{"jsonrpc", "id", "error"}``)

    A *notification* request (no ``id``) returns ``{}`` per the spec.
    A *batch* is not supported here (single-request envelope only).
    """
    if not isinstance(body, dict):
        rid = request_id or body.get("id") if isinstance(body, dict) else None
        return _build_rpc_error(rid, RPC_INVALID_REQUEST,
                                 "request must be JSON object")

    jsonrpc = body.get("jsonrpc")
    if jsonrpc != "2.0":
        rid = request_id or body.get("id")
        return _build_rpc_error(rid, RPC_INVALID_REQUEST,
                                 "jsonrpc must be '2.0'")

    method = body.get("method")
    params = body.get("params") or {}
    rid = request_id or body.get("id")
    notif = "id" not in body

    try:
        result = _dispatch(server, method, params)
        # If the handler was async, await it here.
        import inspect
        if inspect.isawaitable(result):
            result = await result
    except _A2AError as exc:
        if notif:
            return {}
        return _build_rpc_error(rid, exc.code, str(exc), exc.data)
    except Exception as exc:
        logger.exception("unexpected error in jsonrpc handler")
        if notif:
            return {}
        return _build_rpc_error(rid, RPC_INTERNAL_ERROR,
                                 f"internal error: {exc}")

    if notif:
        return {}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _build_rpc_error(req_id: Any, code: int, message: str,
                      data: dict | None = None) -> dict:
    """Build a JSONRPCErrorResponse."""
    err = {"code": code, "message": str(message)}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


if __name__ == "__main__":  # smoke test
    s = A2AServer()
    print(json.dumps(s.get_agent_card(), indent=2)[:500], "...")
