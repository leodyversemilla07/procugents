# RedFlag Agents PH — Implementation Plan
*Multi-Agent AI System for PH Government Procurement Transparency*
*Working Title: RedFlag Agents PH | Grounded in RA 12009*

---

## 📋 Executive Summary

**Mission:** Build a production-grade multi-agent AI system that autonomously monitors, analyzes, and flags anomalous Philippine government procurements in real-time using legally-grounded detection rules.

**Why This Stack?** Every technology choice is optimized for:
1. **Agent Capability** — LangGraph's graph-native state machines handle complex multi-agent workflows
2. **Production Readiness** — PostgreSQL + Redis provide durable execution (crash recovery, checkpointing)
3. **Portfolio Impact** — MCP + A2A protocols match Sovrun/Agentium Labs job descriptions exactly
4. **Ecosystem Maturity** — Python-only backend (LangGraph/CrewAI have no TS equivalents in 2026)

---

## 🏗️ Tech Stack (Best Choice by Layer)

### 1. Agent Framework: **LangGraph (Python)**
*Why not CrewAI or mixing frameworks?*

| Criteria | LangGraph | CrewAI | Decision |
|----------|-----------|---------|----------|
| Graph-native state machine | ✅ Yes | ❌ No (role-based) | **LangGraph** |
| Durable checkpointing (Redis) | ✅ Native | ❌ Requires custom | **LangGraph** |
| Complex orchestration (dynamic routing) | ✅ Nodes + edges | ⚠️ Hierarchical only | **LangGraph** |
| Production deployments (LangChain ecosystem) | ✅ Yes | ⚠️ Limited | **LangGraph** |
| Job description match (Sovrun: "LangGraph") | ✅ Exact match | ⚠️ Partial | **LangGraph** |

**Verdict:** Use **LangGraph exclusively** for all 5 agents + orchestrator. One framework, unified state schema, no integration overhead.

### 2. Language: **Python 3.11+**
*Why not TypeScript/Kotlin?*

| Criteria | Python | TypeScript | Kotlin | Decision |
|----------|--------|-------------|--------|----------|
| LangGraph/LangChain support | ✅ Native, mature | ❌ Experimental (langchainjs) | ❌ No libs | **Python** |
| AI/ML ecosystem (Chroma, httpx, BeautifulSoup) | ✅ Rich | ⚠️ Smaller | ❌ Minimal | **Python** |
| Job description alignment (Sovrun, Agentium) | ✅ "Python expertise" | ⚠️ Partial | ❌ Never mentioned | **Python** |
| Your experience (agri-bantay, saliksik-ai) | ✅ You've used Python | ✅ Strong in TS | ✅ Strong in Kotlin | **Python** (domain match) |

**Verdict:** **Python-only backend**. Keep frontend separate in TypeScript (your strength for portfolio).

### 3. Database & State: **PostgreSQL 15+ + Redis 7+**
*Why this combination?*

| Component | Choice | Why Not Others? |
|------------|--------|------------------|
| **Primary Store** | PostgreSQL 15+ | SQLite (no concurrency), MySQL (weaker JSONB) |
| **JSON Storage** | JSONB columns | Separate NoSQL (unnecessary complexity) |
| **Agent State** | Redis 7+ | Memcached (no persistence), file-based (no atomic ops) |
| **Checkpointing** | Redis + LangGraph integration | PostgreSQL-only (slower for frequent updates) |
| **Pub/Sub (Dashboard)** | Redis channels | WebSockets only (no history) |

**Verdict:** PostgreSQL for structured data + Redis for real-time state = industry standard.

### 4. Protocols: **MCP + A2A (From Day 1)**
*Why not phase it in?*

| Protocol | Purpose | Why Include Early? |
|----------|---------|-------------------|
| **MCP (Model Context Protocol)** | Agents ↔ Tools (Exa API, PhilGEPS scraper) | You already use Hermes' native MCP client; matches Agentium JD ("MCP") |
| **A2A (Agent-to-Agent)** | Orchestrator ↔ Agents discovery + task delegation | 2026 standard (Google/Linux Foundation); matches "multi-agent systems" JDs |

**Verdict:** Implement MCP servers for each agent + A2A Agent Cards immediately. No "phasing" — the protocols *are* the architecture.

### 5. Vector Database: **Chroma (Local)**
*Why local vs managed?*

| Option | Pros | Cons | Verdict |
|--------|------|------|--------|
| **Chroma (local)** | Lightweight, no API key, LangChain integration | Less scalable | ✅ **Best for prototype + production** |
| **Pinecone** | Managed, scalable | Paid, needs API key | ⚠️ For scale only |
| **FAISS** | Facebook's local lib | Older, less integration | ❌ Deprecated |

**Verdict:** Chroma local — you need price history embeddings, not million-scale vectors.

### 6. Dashboard: **Next.js 16 + Shadcn v4 (Fresh Install)**
*Why not Streamlit or inside Kagu-tsuchi?*

| Option | Pros | Cons | Verdict |
|--------|------|------|--------|
| **Next.js (fresh)** | Your expertise, portfolio wow-factor, Shadcn components | More setup | ✅ **Best for portfolio** |
| **Streamlit** | Fastest (1 hour) | Looks like prototype, less impressive | ⚠️ Internal use only |
| **Inside Kagu-tsuchi** | Reuses UI | Mixed concerns, not standalone | ❌ Separate project |

**Verdict:** Fresh Next.js app with Shadcn (card, alert, badge, tabs, progress, sonner) for maximum portfolio impact.

### 7. API Layer: **FastAPI (Python)**
*Why not NestJS (your strength)?*

| Option | Pros | Cons | Verdict |
|--------|------|------|--------|
| **FastAPI** | Python-native, matches backend, WebSockets | New for you | ✅ **Keep backend Python-only** |
| **NestJS** | Your expertise | Breaks backend language consistency | ❌ Mixed stack unnecessary |

**Verdict:** FastAPI — one language (Python) for all backend code. Your NestJS skills can shine in the Next.js dashboard instead.

### 8. Web Scraping: **httpx + BeautifulSoup**
*Why not Selenium/Playwright?*

| Option | Pros | Cons | Verdict |
|--------|------|------|--------|
| **httpx + BeautifulSoup** | PhilGEPS is server-rendered, no JS needed | Less powerful for SPAs | ✅ **Perfect for target** |
| **Selenium/Playwright** | Handles JS-heavy sites | Your VPS has Chrome sandbox issues (saved in memory!) | ❌ Will break on VPS |

**Verdict:** Simple Python scraping — matches PhilGEPS architecture + your VPS constraints.

### 9. Validation: **Pydantic v2**
*Why?*

- LangGraph-native validation
- Type-safe agent outputs (matches your TypeScript background)
- Industry standard for Python data validation

---

## 🏗️ Project Structure (Standalone)

```
~/workspace/procure-agents/          # Standalone project (NOT inside Kagu-tsuchi)
├── agents/                               # LangGraph agents
│   ├── orchestrator.py                 # LangGraph state machine
│   ├── scraper_agent.py                # PhilGEPS monitoring
│   ├── price_analyst.py               # Price anomaly detection
│   ├── bid_analyst.py                 # Bidder collusion detection
│   ├── doc_auditor.py                 # Legal compliance (RA 12009)
│   ├── alert_agent.py                  # Multi-channel alerts
│   └── tools/                          # MCP tool implementations
│       ├── philgeps_scraper.py
│       ├── exa_search.py               # Your Exa API key
│       ├── price_benchmark.py
│       ├── legal_lookup.py             # Reads legal-basis.md
│       └── redis_state.py              # Agent state management
├── mcp_servers/                         # MCP server definitions
│   ├── mcp_scraper.py
│   ├── mcp_price_analyst.py
│   └── ... (one per agent)
├── api/                                  # FastAPI backend
│   ├── main.py                         # FastAPI app
│   ├── websocket.py                    # Dashboard WS endpoint
│   └── routes/                         # REST endpoints
├── dashboard/                            # Next.js 16 + Shadcn v4
│   ├── app/
│   │   ├── page.tsx                    # Main dashboard
│   │   ├── redflags/                  # Detailed alert view
│   │   └── components/                # Shadcn components
│   └── package.json
├── data/
│   ├── legal-basis.md                  # ✅ Already created (copy from Kagu-tsuchi)
│   ├── procurement_schema.sql          # PostgreSQL schema
│   └── sample_procurements.json
├── tests/
│   ├── test_agents.py
│   └── test_api.py
├── PLAN.md                             # This file
├── README.md
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## 🤖 LangGraph Agent Architecture

### State Schema (Shared Across All Agents)
```python
from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel

class ProcurementState(TypedDict):
    # Input
    procurement_id: str
    agency: str
    project_name: str
    approved_budget: float
    contractor: str
    bid_price: Optional[float]
    date_posted: str
    procurement_type: str
    source_url: str
    
    # Agent Outputs
    price_risk_score: Optional[int]           # 0-100
    price_flags: List[str]                    # ["excessive_30pct", ...]
    price_citations: List[str]                # ["COA 2023-004", ...]
    
    bid_risk_score: Optional[int]
    bid_flags: List[str]                      # ["<3_bidders", "dummy_bidder"]
    bid_citations: List[str]
    
    doc_risk_score: Optional[int]
    doc_flags: List[str]                      # ["missing_philgeps", ...]
    doc_citations: List[str]
    
    # Aggregated
    final_risk_score: Optional[int]
    all_flags: List[str]
    all_citations: List[str]
    
    # Workflow
    current_agent: str
    next_agent: str
    error: Optional[str]
```

### Agent Graph (LangGraph)
```python
from langgraph.graph import StateGraph, END

# Initialize graph
workflow = StateGraph(ProcurementState)

# Add agent nodes
workflow.add_node("scraper", scraper_agent)
workflow.add_node("price_analyst", price_analyst_agent)
workflow.add_node("bid_analyst", bid_analyst_agent)
workflow.add_node("doc_auditor", doc_auditor_agent)
workflow.add_node("alert_agent", alert_agent)

# Define routing logic
def should_continue(state: ProcurementState):
    if state["current_agent"] == "scraper":
        return "price_analyst"
    elif state["current_agent"] == "price_analyst":
        # Skip bid_analyst if SVP mode (no bidders)
        if state.get("procurement_type") == "SVP":
            return "doc_auditor"
        return "bid_analyst"
    elif state["current_agent"] == "bid_analyst":
        return "doc_auditor"
    elif state["current_agent"] == "doc_auditor":
        return "alert_agent"
    else:
        return END

# Add conditional edges
workflow.add_conditional_edges("scraper", should_continue)
workflow.add_conditional_edges("price_analyst", should_continue)
workflow.add_conditional_edges("bid_analyst", should_continue)
workflow.add_conditional_edges("doc_auditor", should_continue)

# Set entry point
workflow.set_entry_point("scraper")

# Compile with Redis checkpointing
app = workflow.compile(
    checkpointer=RedisSaver(url="redis://localhost:6379")
)
```

---

## 🔌 MCP + A2A Implementation

### MCP Server (Per Agent)
```python
# mcp_servers/mcp_price_analyst.py
from mcp import MCPServer

server = MCPServer(name="price_analyst")

@server.tool()
def analyze_price(procurement_id: str) -> Dict[str, Any]:
    """Analyze price anomaly for a procurement (RA 12009 Sec 26, COA 2023-004)"""
    # ... implementation
    return {
        "risk_score": 85,
        "flags": ["excessive_30pct_above_market"],
        "citations": ["COA 2023-004", "RA 12009 Sec 26"]
    }

if __name__ == "__main__":
    server.run()
```

### A2A Agent Card (Per Agent)
```json
// .well-known/agent.json
{
  "name": "Price Analyst Agent",
  "description": "Detects price anomalies using market benchmarks (COA 2023-004)",
  "url": "https://redflag-agents.ph/agents/price-analyst",
  "version": "1.0.0",
  "capabilities": [
    "price_analysis",
    "market_benchmarking",
    "exa_api_integration"
  ],
  "authentication": {
    "type": "bearer"
  }
}
```

---

## 💾 Database Schema (PostgreSQL + Redis)

### PostgreSQL (Structured Data)
```sql
-- procurements table
CREATE TABLE procurements (
    id SERIAL PRIMARY KEY,
    notice_id VARCHAR(255) UNIQUE,
    agency VARCHAR(255) NOT NULL,
    project_name TEXT NOT NULL,
    approved_budget DECIMAL(15,2) NOT NULL,
    contractor VARCHAR(255),
    bid_price DECIMAL(15,2),
    date_posted DATE NOT NULL,
    procurement_type VARCHAR(100) NOT NULL,
    source_url TEXT,
    abc_vs_market_diff_pct DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_agency (agency),
    INDEX idx_risk (final_risk_score)
);

-- agent_results table
CREATE TABLE agent_results (
    id SERIAL PRIMARY KEY,
    procurement_id INT REFERENCES procurements(id),
    agent_name VARCHAR(100) NOT NULL,
    result JSONB NOT NULL,               -- Full agent output
    risk_score INT,
    executed_at TIMESTAMP DEFAULT NOW()
);

-- legal_citations lookup
CREATE TABLE legal_citations (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL,           -- "RA 12009 Sec 26"
    description TEXT,
    coa_classification VARCHAR(50),       -- "Illegal", "Excessive", etc.
    UNIQUE(code)
);
```

### Redis (Agent State)
```
# Keys structure
procurement:{id}:state          # JSON of ProcurementState
procurement:{id}:locks          # Agent task locks (SETNX)
procurement:{id}:heartbeat     # Agent alive check (TTL 60s)
alerts:queue                   # Pending alerts for Alert Agent
dashboard:updates             # Pub/Sub channel for Next.js
```

---

## 🌐 FastAPI Endpoints (Backend)

```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="RedFlag Agents PH API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/procurement/analyze")
async def analyze_procurement(procurement: ProcurementInput):
    """Trigger full 5-agent analysis"""
    result = app.invoke(procurement)  # LangGraph call
    return result

@app.get("/api/alerts")
async def get_alerts(agency: Optional[str] = None, min_risk: int = 70):
    """Get red flag alerts"""
    # Query PostgreSQL
    pass

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """Real-time alert streaming to Next.js dashboard"""
    await websocket.accept()
    # Subscribe to Redis pub/sub "dashboard:updates"
```

---

## 🎨 Next.js Dashboard (Fresh Install)

### Tech Stack
- **Next.js 16.1.6** (latest)
- **TypeScript** (your strength)
- **Shadcn v4** (Lyra preset, base-lyra, neutral colors, Phosphor icons)
- **Tailwind CSS** (included with Shadcn)
- **WebSocket client** (for real-time alerts)

### Key Pages
```
dashboard/
├── app/
│   ├── page.tsx                    # Main dashboard (red flag list)
│   ├── procurement/[id]/page.tsx   # Detailed procurement view
│   └── components/
│       ├── RedFlagCard.tsx          # Shadcn card + alert + badge
│       ├── RiskScoreBadge.tsx       # Shadcn badge (color-coded)
│       ├── LegalCitation.tsx         # Displays RA 12009 citations
│       └── AgentStatus.tsx          # Shadcn progress (agent health)
```

### Component Usage (From Your Existing Shadcn Knowledge)
```typescript
// components/RedFlagCard.tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"

export function RedFlagCard({ alert }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{alert.project_name}</CardTitle>
        <Badge variant={alert.risk_score > 80 ? "destructive" : "default"}>
          Risk: {alert.risk_score}/100
        </Badge>
      </CardHeader>
      <CardContent>
        <Alert variant="destructive">
          <AlertDescription>
            {alert.flags.map(flag => (
              <span key={flag}>{flag} (RA 12009)</span>
            ))}
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  )
}
```

---

## 📋 Implementation Phases

### Phase 1: Prototype (Week 1-2) — "Hello World Agents"
**Goal:** 2 agents working (Scraper + Price Analyst) with real PhilGEPS data.

**Tasks:**
1. ✅ Set up Python venv, install LangGraph + dependencies
2. ✅ Create PostgreSQL schema + Redis connection
3. ✅ Build **Scraper Agent** (LangGraph):
   - Scrape DOH procurements from PhilGEPS
   - Store to PostgreSQL
   - Use Exa API for market price lookups
4. ✅ Build **Price Analyst Agent** (LangGraph):
   - Read from PostgreSQL
   - Apply COA 2023-004 rule (>30% above market = Excessive)
   - Output: Risk score + legal citation
5. ✅ Test on 10 recent DOH procurements
6. ✅ Validate against COA DOH audit reports (accuracy check)

**Deliverable:** Working 2-agent system with real data.

### Phase 2: Scale Agents (Week 3-4) — "All 5 Agents"
**Goal:** Complete multi-agent system with LangGraph orchestration.

**Tasks:**
1. ✅ Add **Bid Analyst Agent** (LangGraph):
   - Network graph of bidders (shared addresses/directors)
   - RA 9184 IRR Sec 52.1 (<3 bidders = Irregular)
   - Dummy bidder detection
2. ✅ Add **Doc Auditor Agent** (LangGraph):
   - NLP parsing of PhilGEPS PDFs
   - RA 12009 IRR Annex H checklist
   - IIUEEU classification (Illegal, Irregular, etc.)
3. ✅ Implement **LangGraph Orchestrator**:
   - State machine with conditional routing
   - Redis checkpointing (crash recovery)
   - Deadlock guards (hop counters, timeouts)
4. ✅ Add **Alert Agent** (LangGraph):
   - Format for COA (formal audit report)
   - Post to X/Twitter via `xurl` skill
   - Push to Next.js dashboard (WebSocket)

**Deliverable:** Full 5-agent system with Redis state management.

### Phase 3: Productionize (Month 2) — "MCP + A2A + Dashboard"
**Goal:** Industry-standard protocols + polished portfolio dashboard.

**Tasks:**
1. ✅ Convert agents to **MCP servers** (expose tools)
2. ✅ Add **A2A Agent Cards** for discovery
3. ✅ Build **FastAPI backend** (REST + WebSocket)
4. ✅ Build **Next.js dashboard** (fresh install):
   - Use Shadcn components (card, alert, badge, tabs, progress, sonner)
   - Real-time alerts via WebSocket
   - Filter by agency/risk score
5. ✅ Deploy to VPS (use existing Hermes gateway system service)

**Deliverable:** Deployed system with professional dashboard.

### Phase 4: Portfolio (Month 3) — "Showcase"
**Goal:** Use for job applications to Sovrun, Agentium Labs, Senior AI Engineer roles.

**Tasks:**
1. ✅ Create GitHub repo `leodyversemilla07/RedFlag-Agents-PH`
2. ✅ Write **Medium article**:
   - "How I Built a Multi-Agent System to Detect Procurement Corruption (RA 12009 Grounded)"
3. ✅ Update **GitHub README.md**:
   - Architecture diagram (LangGraph graph visualization)
   - Demo GIF (dashboard in action)
   - Accuracy metrics (vs COA audit reports)
4. ✅ **Apply to target roles**:
   - Sovrun: Mention LangGraph + multi-agent systems
   - Agentium Labs: Mention MCP + Exa API integration
   - Senior AI Engineer: Mention Redis checkpointing, deadlock guards, IIUEEU compliance

**Deliverable:** Portfolio piece that directly answers job descriptions.

---

## 🎯 Portfolio Value (Why This Stack?)

| Job Description | How RedFlag Agents PH Answers It |
|-----------------|--------------------------------------|
| **Sovrun:** "LangChain/LangGraph experience, multi-agent LLM systems, AWS deployment" | ✅ LangGraph exclusively, 5-agent system, deployed on VPS (similar to AWS) |
| **Agentium Labs:** "LangChain, LlamaIndex, MCP, OpenAI/Anthropic APIs" | ✅ LangGraph (LangChain ecosystem), MCP native servers, Exa API (Anthropic partner) |
| **Senior AI Engineer:** "Production-grade agents, structured reasoning, memory, tool use, failure handling" | ✅ Redis checkpointing, deadlock guards, error handling, IIUEEU legal grounding |

**Key Differentiator:** Most candidates build TODO-list agents. You built a **legally-grounded, socially-impactful system** on **real government data** (PhilGEPS) with **measurable outcomes** (COA audit accuracy).

---

## 🚀 Immediate Next Step (This Session)

**I'll start Phase 1, Task 2 (Database Schema):**
1. ✅ Write `procurement_schema.sql` (PostgreSQL + Redis structure)
2. ✅ Create `requirements.txt` with all Python dependencies
3. ✅ Scaffold `orchestrator.py` with LangGraph boilerplate

**Want me to proceed?** (Say "Yes, start Phase 1" and I'll write the SQL + Python files.)
