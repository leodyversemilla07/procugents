# RedFlag Agents PH — MCP Server Specs
*Planning Artifact | MCP server tool definitions, input/output schemas, agent mappings*
*Protocol: MCP 1.0 (local stdio transport, per native-mcp skill), core to tech stack per PLAN.md*

---

## 1. MCP Integration Overview
All agents access tools via **local MCP servers** (stdio transport) instead of importing Python modules directly. This enables:
- Tool reuse across agents without code duplication
- Future A2A integration (MCP servers can be exposed via A2A Agent Cards)
- Isolation of tool logic from agent prompt logic

Each agent calls MCP tools via LangGraph's `MCPToolkit` (Python), matching the Agent Prompt workflows defined earlier.

---

## 2. MCP Server 1: Legal Lookup MCP Server
### Purpose
Expose the Legal Rule Engine JSON lookup (from `legal-rule-engine.md` Section 3) to all agents for citation mapping.

### Agents Using It
All 5 agents + Orchestrator (every agent must map red flags to legal citations)

### Exposed Tools
#### Tool 1: `lookup_legal_citation`
Get legal citation details by red flag code.
```json
{
  "tool_name": "lookup_legal_citation",
  "description": "Returns legal citation, IIUEEU classification, severity for a given red flag code",
  "input_schema": {
    "type": "object",
    "properties": {
      "flag_code": {"type": "string", "enum": ["missing_philgeps_posting", "price_30pct_above_market", "less_than_3_bidders", "missing_philgeps_registration", "illegal_disallowance"]}
    },
    "required": ["flag_code"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "citation": {"type": "string", "example": "RA 12009 Sec 20.1"},
      "law_source": {"type": "string", "example": "RA 12009"},
      "iiueeu": {"type": "string", "enum": ["I", "IR", "U", "E", "EX", "UN"]},
      "severity": {"type": "integer", "minimum": 1, "maximum": 5},
      "description": {"type": "string"}
    }
  }
}
```

#### Tool 2: `list_flags_by_agent`
Get all red flags mapped to a specific agent.
```json
{
  "tool_name": "list_flags_by_agent",
  "description": "Returns all red flags + citations for a given agent name",
  "input_schema": {
    "type": "object",
    "properties": {
      "agent_name": {"type": "string", "enum": ["scraper_agent", "price_analyst_agent", "bid_analyzer_agent", "doc_auditor_agent", "alert_agent"]}
    },
    "required": ["agent_name"]
  },
  "output_schema": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "flag": {"type": "string"},
        "citation": {"type": "string"},
        "iiueeu": {"type": "string"},
        "severity": {"type": "integer"}
      }
    }
  }
}
```

#### Tool 3: `get_thresholds`
Get procurement threshold values (RA 12009 Sec 26).
```json
{
  "tool_name": "get_thresholds",
  "description": "Returns all procurement mode thresholds and red flag thresholds",
  "input_schema": {"type": "object", "properties": {}},
  "output_schema": {
    "type": "object",
    "properties": {
      "competitive_bidding_min": {"type": "integer", "example": 1000000},
      "svp_max": {"type": "integer", "example": 1000000},
      "price_excess_pct": {"type": "integer", "example": 30}
    }
  }
}
```

### Transport
`stdio` (local server, no network port)

---

## 3. MCP Server 2: Price Analysis MCP Server
### Purpose
Expose price comparison tools using Exa API (key in memory) + Chroma vector DB for market rate lookups.

### Agents Using It
Price Analyst Agent, Alert Agent

### Exposed Tools
#### Tool 1: `get_market_rate`
Fetch verified market rate for a procurement item via Exa search.
```json
{
  "tool_name": "get_market_rate",
  "description": "Returns average market rate for a given item name using Exa web search + Chroma embeddings",
  "input_schema": {
    "type": "object",
    "properties": {
      "item_name": {"type": "string", "example": "Laptop Dell Latitude 3520"},
      "procurement_type": {"type": "string", "enum": ["Goods", "Infrastructure", "Consulting"]}
    },
    "required": ["item_name"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "market_rate": {"type": "number", "example": 45000.00},
      "source_urls": {"type": "array", "items": {"type": "string"}},
      "pct_above_market": {"type": "number", "example": 25.5}
    }
  }
}
```

#### Tool 2: `check_budget_splitting`
Detect if multiple procurements from the same agency are split to stay under ₱1M threshold.
```json
{
  "tool_name": "check_budget_splitting",
  "description": "Checks if procurements from the same agency in 30 days sum to >₱1M (RA 12009 Sec 26(c) violation)",
  "input_schema": {
    "type": "object",
    "properties": {
      "agency": {"type": "string"},
      "procurement_ids": {"type": "array", "items": {"type": "integer"}}
    },
    "required": ["agency", "procurement_ids"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "is_split": {"type": "boolean"},
      "total_sum": {"type": "number"},
      "threshold": {"type": "integer", "example": 1000000}
    }
  }
}
```

### Transport
`stdio` (local server, Exa API key loaded from environment variable `EXA_API_KEY` per memory)

---

## 4. MCP Server 3: PhilGEPS Scraper MCP Server
### Purpose
Expose PhilGEPS scraping tools using `httpx` + `BeautifulSoup` (VPS-compatible, no Chrome sandbox needed).

### Agents Using It
Scraper Agent, Orchestrator

### Exposed Tools
#### Tool 1: `scrape_procurements`
Scrape PhilGEPS for procurements matching agency/project filters.
```json
{
  "tool_name": "scrape_procurements",
  "description": "Returns raw procurement listings from PhilGEPS.gov.ph for given filters",
  "input_schema": {
    "type": "object",
    "properties": {
      "agency_filter": {"type": "string", "example": "Department of Public Works"},
      "project_filter": {"type": "string|null"},
      "date_from": {"type": "string", "format": "date"}
    },
    "required": ["agency_filter"]
  },
  "output_schema": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "notice_id": {"type": "string"},
        "project_name": {"type": "string"},
        "approved_budget": {"type": "number"},
        "date_posted": {"type": "string", "format": "date"}
      }
    }
  }
}
```

#### Tool 2: `check_posting_compliance`
Validate if a procurement meets PhilGEPS posting requirements (RA 12009 Sec 20).
```json
{
  "tool_name": "check_posting_compliance",
  "description": "Checks for missing mandatory PhilGEPS postings (APP, ITB, bid results)",
  "input_schema": {
    "type": "object",
    "properties": {
      "notice_id": {"type": "string"}
    },
    "required": ["notice_id"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "missing_postings": {"type": "array", "items": {"type": "string"}},
      "posting_compliant": {"type": "boolean"}
    }
  }
}
```

### Transport
`stdio` (local server, respects VPS no-Chrome constraint)

---

## 5. MCP Server 4: Document Validation MCP Server
### Purpose
Validate mandatory documentary requirements per COA 2023-004 Annex A + RA 12009 IRR Annex H.

### Agents Using It
Doc Auditor Agent, Bid Analyzer Agent

### Exposed Tools
#### Tool 1: `validate_bidder_docs`
Check if a bidder has all mandatory documents.
```json
{
  "tool_name": "validate_bidder_docs",
  "description": "Returns missing mandatory documents for a bidder per COA 2023-004",
  "input_schema": {
    "type": "object",
    "properties": {
      "bidder_name": {"type": "string"},
      "documents": {
        "type": "object",
        "properties": {
          "philgeps_reg": {"type": "boolean"},
          "business_permit": {"type": "boolean"},
          "pcab_license": {"type": "string|null"},
          "nfcc": {"type": "number|null"}
        }
      }
    },
    "required": ["bidder_name", "documents"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "missing_docs": {"type": "array", "items": {"type": "string"}},
      "compliant": {"type": "boolean"}
    }
  }
}
```

### Transport
`stdio` (local server)

---

## 6. MCP Server 5: Alert MCP Server
### Purpose
Generate COA-formatted disallowance reports and manage alert queue.

### Agents Using It
Alert Agent, Orchestrator

### Exposed Tools
#### Tool 1: `generate_alert_report`
Create COA-formatted disallowance report for Illegal/Excessive/Unconscionable flags.
```json
{
  "tool_name": "generate_alert_report",
  "description": "Returns COA-compliant disallowance report with all citations and IIUEEU classification",
  "input_schema": {
    "type": "object",
    "properties": {
      "all_flags": {"type": "array", "items": {"type": "object"}},
      "procurement_id": {"type": "integer"}
    },
    "required": ["all_flags", "procurement_id"]
  },
  "output_schema": {
    "type": "string",  -- COA-formatted text report
    "properties": {
      "report_text": {"type": "string"},
      "alert_type": {"type": "string", "enum": ["illegal", "excessive", "unconscionable"]}
    }
  }
}
```

#### Tool 2: `queue_alert`
Add an alert to the `alert_queue` PostgreSQL table.
```json
{
  "tool_name": "queue_alert",
  "description": "Inserts a pending alert into the alert_queue table for processing",
  "input_schema": {
    "type": "object",
    "properties": {
      "procurement_id": {"type": "integer"},
      "alert_type": {"type": "string"},
      "trigger_citation": {"type": "string"}
    },
    "required": ["procurement_id", "alert_type", "trigger_citation"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "queue_id": {"type": "integer"},
      "status": {"type": "string", "example": "pending"}
    }
  }
}
```

### Transport
`stdio` (local server, writes to PostgreSQL alert_queue table)

---

## 7. Verification Checklist
- [x] All 5 MCP servers mapped to agents per Agent Prompts
- [x] Every tool has strict input/output JSON schemas (no loose typing)
- [x] Legal Lookup server uses Legal Rule Engine JSON directly
- [x] Price server uses Exa API key from memory (no hardcoded keys)
- [x] Scraper server respects VPS no-Chrome constraint (httpx + BeautifulSoup)
- [x] All transports are local stdio (matches MCP + A2A core architecture)
- [x] Alert server writes to PostgreSQL alert_queue table (matches Data Schema)

*Next Planning Step: A2A Integration (Agent Cards, task delegation flow, Orchestrator ↔ Agent communication)*
