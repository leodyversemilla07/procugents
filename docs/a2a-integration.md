# ProcuGents — A2A Integration (v1.0)

Concrete integration notes for the [A2A v1.0 spec](https://a2a-protocol.org/v1.0.0/specification/) (released by Google, donated to the Linux Foundation, merged with IBM ACP August 2025). The spec defines a three-layer data model:

1. **Canonical data model** expressed as Protocol Buffers (`spec/a2a.proto`).
2. **Abstract operations** (`message/send`, `tasks/get`, `tasks/cancel`, …).
3. **Protocol bindings** mapping those operations to JSON-RPC 2.0, gRPC, and HTTP+JSON.

We use the **JSON-RPC 2.0 over HTTP** binding as the canonical wire format. Where multiple agents are served behind one endpoint we use the v1.0 `tenant` opaque routing identifier. Field names follow the canonical proto-to-JSON mapping (snake_case throughout; see [`spec/a2a.proto`](https://github.com/a2aproject/A2A/blob/main/specification/a2a.proto)).

ProCuGents exposes 5 skills (one per orchestrator agent):

| Skill                         | Description                                                                                                  | Tags                              |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------- |
| `legal_compliance_check`        | RA 12009 Sec 26 SVP threshold and PhilGEPS posting verification                                                 | `legal`, `ra-12009`               |
| `price_anomaly_analysis`        | Market-baseline comparison per COA 2023-004 Sec 4.2                                                            | `price`, `coa-2023-004`            |
| `bidding_integrity_scan`        | Sub-3 bidder count, shared addresses, HoPE approval gaps                                                        | `bid`, `dummy-bidders`            |
| `document_compliance_audit`     | PhilGEPS registration, business permit, bid security, PCAB license                                              | `document`, `philgeps`            |
| `full_procurement_audit`         | Full LangGraph pipeline; emits COA-style disallowance report when warranted                                       | `audit`, `multi-agent`            |

## Endpoints

### Discovery

- `GET /a2a/card` — returns the v1.0 Agent Card (proto `AgentCard`).
- `POST /a2a/jsonrpc` — canonical JSON-RPC 2.0 endpoint. Accepts single envelopes; method names match the spec exactly:

  | Method                                  | Section |
  | --------------------------------------- | ------- |
  | `message/send`                            | 3.1.1   |
  | `tasks/get`                               | 3.1.3   |
  | `tasks/list`                              | 3.1.4   |
  | `tasks/cancel`                            | 3.1.5   |
  | `agent/authenticatedExtendedCard`         | 3.1.11  |

### REST bindings (HTTP+JSON; Section 11)

- `GET /a2a/tasks/{id}` — equivalent to `tasks/get`.
- `POST /a2a/tasks/{id}:cancel` — equivalent to `tasks/cancel`.

## Streaming and push notifications

The ProCuGents `AgentCard` declares `streaming: false` and `push_notifications: false`. Per spec Section 3.3.4, clients attempting `message/stream` / `tasks/subscribe` / push-config operations receive:

| Operation                          | Error                                  | Code  |
| ---------------------------------- | -------------------------------------- | ----- |
| `message/stream`                     | `UnsupportedOperationError`              | -32004 |
| `tasks/subscribe`                    | `UnsupportedOperationError`              | -32004 |
| `tasks/pushNotificationConfig/{set,get,list,delete}` | `PushNotificationNotSupportedError` | -32003 |

When the orchestrator moves to async background execution we will flip `streaming: true` and serve Server-Sent Events (SSE) from `/a2a/tasks/{id}:subscribe`. Push notifications require a webhook delivery path (a Tornado/ASGI endpoint POSTing to `tasks/pushNotificationConfig/{set}`-configured URLs).

## Examples

### 1. Discover the agent

```bash
curl -s http://localhost:8000/a2a/card | jq .
```

### 2. Send a `message/send` envelope (JSON-RPC)

```bash
curl -s -X POST http://localhost:8000/a2a/jsonrpc \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0","id":"r1","method":"message/send",
    "params":{
      "message":{
        "message_id":"m1","role":"user",
        "parts":[{"data":{"skill":"full_procurement_audit",
                          "params":{"contract_amount":5000000}},
                  "media_type":"application/json"}]
      }
    }
  }'
```

Response (snake_case throughout):

```json
{
  "jsonrpc":"2.0","id":"r1",
  "result":{
    "id":"task-…",
    "context_id":"ctx-…",
    "status":{"state":"completed","timestamp":"…Z","message":{...}},
    "history":[...],
    "artifacts":[{"artifact_id":"art-…","parts":[{"data":{...},"media_type":"application/json"}]}]
  }
}
```

### 3. Fetch a task via REST

```bash
curl -s http://localhost:8000/a2a/tasks/task-58394215000549088b37a9beaeb31155 | jq .
```

## Errors

Errors follow Section 3.3.2 + 9.5 and use the JSON-RPC 2.0 error envelope:

```json
{"jsonrpc":"2.0","id":"r1",
 "error":{"code":-32601, "message":"A2A RPC error -32601",
         "data":{"method":"foo/bar"}}}
```

| Code    | Meaning                              | A2A Error                         |
| ------- | ------------------------------------ | --------------------------------- |
| -32700  | parse error                            | n/a                                |
| -32600  | invalid JSON-RPC request envelope      | InvalidRequestError               |
| -32601  | method not known                       | MethodNotFoundError                |
| -32602  | invalid parameters                    | InvalidParamsError                 |
| -32603  | server internal error                  | InternalError                      |
| -32001  | task does not exist                    | TaskNotFoundError                  |
| -32002  | task already in terminal state          | TaskNotCancelableError             |
| -32003  | push notifs disabled                   | PushNotificationNotSupportedError  |
| -32004  | capability disabled                    | UnsupportedOperationError           |
| -32005  | unsupported content type                | ContentTypeNotSupportedError       |

## Implementation

The v1.0 server lives in `src/servers/a2a_server.py`. It does **not** depend on an external a2a SDK — the canonical wire format is mapped directly to Python dicts (`build_agent_card`, `handle_jsonrpc_request`, `A2AServer.op_*`) so we stay spec-faithful without pinning a third-party library that might lag behind spec changes.

Tested in `tests/test_a2a_v1.py`: 22 tests covering AgentCard shape conformance, JSON-RPC envelope errors, message/send round-trips, tasks/{get,list,cancel} lifecycles, `agent/authenticatedExtendedCard`, and the snake_case field-name convention.
