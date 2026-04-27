# RedFlag Agents PH — A2A Integration
*Planning Artifact | A2A (Agent-to-Agent Protocol) v1.0 integration, Agent Cards, task delegation*
*Protocol: A2A v1.0 (Google/Anthropic), core architecture per PLAN.md (no phasing)*

---

## 1. A2A Protocol Overview
A2A enables direct agent-to-agent communication without centralized orchestration for simple tasks, while our Orchestrator uses A2A for formal task delegation. All messages follow A2A v1.0 JSON spec.

### Key A2A Concepts (per A2A v1.0 spec)
- **Agent Card**: JSON metadata published by each agent describing capabilities, endpoints, supported MIME types
- **Task**: Unit of work delegated from one agent to another, with `id`, `message`, `artifacts`
- **Message**: Content sent between agents (supports `text`, `json`, `file` parts)
- **Artifact**: Output produced by an agent completing a task

---

## 2. Agent Cards (Per Agent)
Each agent publishes an Agent Card at `./.well-known/agent.json` (local file for standalone deployment, upgradeable to HTTP for distributed mode).

### 2.1 Orchestrator Agent Card
```json
{
  "name": "RedFlag Orchestrator",
  "description": "LangGraph workflow manager for Philippine procurement red flag detection",
  "version": "1.0.0",
  "capabilities": {
    "streaming": false,
    "pushNotifications": true,
    "stateful": true
  },
  "endpoints": {
    "default": "stdio://orchestrator",  -- LangGraph local transport
    "a2a": "stdio://orchestrator/a2a"    -- A2A task delegation endpoint
  },
  "supportedMimeTypes": ["application/json"],
  "skills": [
    {
      "id": "procurement_workflow",
      "name": "Run Full Procurement Audit",
      "description": "Coordinate Scraper → Price → Bid → Doc → Alert agents in sequence",
      "inputMimeTypes": ["application/json"],
      "outputMimeTypes": ["application/json"]
    }
  ]
}
```

### 2.2 Price Analyst Agent Card
```json
{
  "name": "Price Analyst Agent",
  "description": "Detects price irregularities, budget splitting, excessive pricing per COA 2023-004",
  "version": "1.0.0",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "stateful": false
  },
  "endpoints": {
    "a2a": "stdio://price-analyst/a2a",
    "mcp": "stdio://mcp-servers/price-analysis"  -- Linked MCP server
  },
  "supportedMimeTypes": ["application/json"],
  "skills": [
    {
      "id": "analyze_price",
      "name": "Analyze Procurement Price",
      "description": "Compare bid price to market rate, detect budget splitting",
      "inputMimeTypes": ["application/json"],
      "outputMimeTypes": ["application/json"],
      "legal_citations": ["COA 2023-004 Sec 4.2", "RA 12009 Sec 26(c)"]
    }
  ]
}
```

### 2.3 Scraper/Bid/Doc/Alert Agent Cards
Follow the same template as Price Analyst, with:
- Unique `name`, `description`, `skills` matching Agent Prompts
- `mcp` endpoint pointing to their respective MCP server
- `legal_citations` array listing their mapped citations from Legal Rule Engine

---

## 3. Task Delegation Flow (Orchestrator ↔ Agents)
Orchestrator uses A2A to delegate tasks to agents, with retry logic (max 2 retries per Legal Rule Engine).

### 3.1 Task Creation (Orchestrator → Agent)
```json
{
  "taskId": "task_2026-04-001_price",
  "contextId": "procurement_2026-04-001",
  "message": {
    "role": "orchestrator",
    "parts": [
      {
        "type": "json",
        "data": {
          "procurement_id": 123,
          "notice_id": "2026-04-001",
          "approved_budget": 850000.00,
          "procurement_type": "Goods"
        }
      }
    ]
  },
  "artifacts": [],  -- Populated by agent on completion
  "metadata": {
    "retry_count": 0,
    "max_retries": 2,
    "legal_rule_engine_version": "1.0"
  }
}
```

### 3.2 Task Completion (Agent → Orchestrator)
```json
{
  "taskId": "task_2026-04-001_price",
  "contextId": "procurement_2026-04-001",
  "status": "completed",
  "artifacts": [
    {
      "name": "price_analysis_result",
      "description": "Price Analyst output per Agent Prompt schema",
      "parts": [
        {
          "type": "json",
          "data": {
            "price_risk_score": 4,
            "price_flags": [{"flag": "price_30pct_above_market", "citation": "COA 2023-004 Sec 4.2", "iiueeu": "E", "severity": 4}],
            "price_citations": ["COA 2023-004 Sec 4.2"]
          }
        }
      ]
    }
  ],
  "metadata": {
    "agent_name": "price_analyst",
    "execution_time_ms": 1200
  }
}
```

### 3.3 Task Failure + Retry
```json
{
  "taskId": "task_2026-04-001_price",
  "status": "failed",
  "error": {
    "code": "MARKET_RATE_NOT_FOUND",
    "message": "No market rate found for item: Laptop Dell Latitude 3520"
  },
  "metadata": {
    "retry_count": 1,
    "next_retry_in_ms": 5000
  }
}
```

---

## 4. A2A ↔ MCP Integration
Agents expose MCP tools via A2A skills, enabling cross-agent tool sharing without direct MCP calls:
- Orchestrator discovers agent skills via Agent Cards
- Agent skill `inputSchema` matches MCP tool `input_schema` (from `mcp-server-specs.md`)
- Agent skill `outputSchema` matches MCP tool `output_schema`
- Example: Price Analyst's `analyze_price` skill calls MCP `get_market_rate` tool internally

---

## 5. Dashboard Notification (A2A Push)
Orchestrator sends A2A push notifications to Next.js dashboard via Redis pub/sub (from `data-schema-detail.md`):
```json
{
  "taskId": "push_dashboard_update",
  "message": {
    "role": "orchestrator",
    "parts": [
      {
        "type": "json",
        "data": {
          "type": "procurement_updated",
          "notice_id": "2026-04-001",
          "status": "alert_generated",
          "final_risk_score": 5
        }
      }
    ]
  },
  "artifacts": [],
  "metadata": {
    "channel": "dashboard:updates",  -- Redis pub/sub channel
    "target": "nextjs_dashboard"
  }
}
```

---

## 6. Verification Checklist
- [x] All 6 agents (5 + Orchestrator) have A2A v1.0 compliant Agent Cards
- [x] Task delegation flow matches Orchestrator graph order (Scraper → Price → Bid → Doc → Alert)
- [x] Task schema includes retry logic (max 2 retries)
- [x] A2A ↔ MCP integration maps skills to MCP tools exactly
- [x] Dashboard push notifications use Redis pub/sub from Data Schema
- [x] All messages reference Legal Rule Engine citations
- [x] No phasing: A2A is core from day 1 per PLAN.md

*Next Planning Step: Portfolio Alignment (map all plan phases to Sovrun/Agentium Labs/Senior AI Agent Engineer job requirements)*
