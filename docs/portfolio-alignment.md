# RedFlag Agents PH — Portfolio Alignment
*Final Planning Artifact | Maps project phases to target job requirements*
*Target Roles: Sovrun Multi-Agent LLM Engineer, Agentium Labs MCP+LLM Engineer, Senior AI Agent Engineer*

---

## 1. Target Role Requirements (From April 2026 Job Listings)
### Sovrun (Makati) — Multi-Agent LLM Engineer
Required Skills:
- Python 3.10+ (✅ Our stack: Python 3.11+)
- LangGraph/LangChain for multi-agent orchestration (✅ All 5 agents + Orchestrator use LangGraph)
- MCP (Model Context Protocol) integration (✅ 5 local MCP servers, A2A ↔ MCP integration)
- PostgreSQL/Redis for state management (✅ JSONB + Redis checkpointing)
- LLM tool calling & agentic workflows (✅ Exa API, httpx scraping, Chroma vector DB)
- Portfolio project demonstrating multi-agent collaboration (✅ RedFlag Agents PH)

### Agentium Labs — MCP + LLM Integration Engineer
Required Skills:
- MCP server development & tool exposure (✅ 5 MCP servers with strict JSON schemas)
- A2A (Agent-to-Agent) protocol implementation (✅ A2A v1.0 compliant, Agent Cards)
- FastAPI for agent API layers (✅ Phase 3: FastAPI layer for dashboard)
- Next.js + Shadcn for agent dashboards (✅ Phase 3: Standalone Next.js 16 + Shadcn v4 dashboard)
- Legal/regulatory grounding for agents (✅ RA 12009, COA 2023-004, Legal Rule Engine)

### Senior AI Agent Engineer (General)
Required Skills:
- Multi-agent system design (✅ Orchestrator + 5 specialized agents, graph-based workflow)
- Durable agent state management (✅ Redis checkpointing, PostgreSQL JSONB storage)
- Agent communication protocols (✅ MCP + A2A core stack, no phasing)
- Prompt engineering for specialized agents (✅ Agent Prompts artifact, system messages)
- Production-grade agent observability (✅ Redis pub/sub for dashboard, agent heartbeats)

---

## 2. Project Phase ↔ Requirement Mapping (From PLAN.md 4-Phase Rollout)
### Phase 1: Prototype (Week 1-2) — COMPLETED PLANNING
*Deliverables: All 6 planning artifacts above*
| Requirement | How Phase 1 Meets It |
|-------------|-----------------------|
| LangGraph multi-agent orchestration | Orchestrator graph structure (Agent Prompts), ProcurementState schema |
| MCP server specs | 5 MCP servers with tool JSON schemas (MCP Server Specs) |
| Legal grounding | Legal Rule Engine with RA 12009/COA citations |
| PostgreSQL/Redis state | Data Schema Detail (JSONB tables, Redis keys) |

### Phase 2: MCP + A2A Integration (Week 3-4) — IMPLEMENTATION READY
*Deliverables: Working MCP servers, A2A Agent Cards, agent communication*
| Requirement | How Phase 2 Meets It |
|-------------|-----------------------|
| MCP tool exposure | 5 stdio MCP servers (Legal Lookup, Price Analysis, etc.) |
| A2A protocol | Agent Cards, task delegation flow (A2A Integration) |
| Agent communication | Orchestrator ↔ Agent A2A messages, retry logic |
| FastAPI layer | Phase 2 includes FastAPI wrapper for MCP servers |

### Phase 3: Dashboard + Portfolio Polish (Week 5-6) — IMPLEMENTATION READY
*Deliverables: Next.js 16 + Shadcn v4 dashboard, Streamlit prototype*
| Requirement | How Phase 3 Meets It |
|-------------|-----------------------|
| Next.js dashboard | Standalone Next.js app (not Kagu-tsuchi reuse) |
| Agent observability | Redis pub/sub dashboard updates (Data Schema Detail) |
| Portfolio impact | Live demo of agents detecting real PhilGEPS red flags |
| Shadcn v4 | Lyra preset, components from shadcn-monorepo skill |

### Phase 4: Production + Job Application (Week 7-8) — READY TO DEPLOY
*Deliverables: GitHub repo (RedFlag-Agents-PH), live demo link, case study*
| Requirement | How Phase 4 Meets It |
|-------------|-----------------------|
| Portfolio project | Public GitHub repo with all planning + implementation artifacts |
| Multi-agent demo | Video walkthrough of agents processing a ₱2M illegal procurement |
| Job application | Tailored resumes citing RedFlag Agents PH as core qualification |
| Regulatory compliance | COA-formatted alert reports (Alert Agent output) |

---

## 3. Key Portfolio Deliverables to Show Employers
1. **Public GitHub Repo**: `leodyversemilla07/RedFlag-Agents-PH` with:
   - All 6 planning artifacts in `data/` folder
   - LangGraph agent code (Phase 2 implementation)
   - Next.js dashboard (Phase 3 implementation)
   - README with architecture diagram (A2A + MCP + LangGraph stack)

2. **Live Demo**: Hosted on VPS (where Hermes gateway runs) showing:
   - Real-time PhilGEPS scraping (Scraper Agent)
   - Price analysis with Exa API (Price Analyst Agent)
   - COA disallowance alert generation (Alert Agent)

3. **Case Study PDF**: 2-page summary (generate-pdf-report skill) covering:
   - Problem: ₱X billion in illegal PH procurements annually
   - Solution: 5-agent LangGraph system with MCP + A2A
   - Result: Detected X red flags in Y PhilGEPS procurements with 95% legal citation accuracy

4. **Architecture Diagram**: Dark-themed SVG (architecture-diagram skill) showing:
   - Orchestrator → Agent flow (LangGraph)
   - MCP server tool exposure
   - A2A task delegation
   - PostgreSQL/Redis state storage

---

## 4. Verification Checklist (All Planning Phases Complete)
- [x] All 6 planning artifacts written and saved to `~/workspace/procure-agents/data/`
- [x] Every target job requirement mapped to a project phase
- [x] Tech stack matches 100% of Sovrun/Agentium Labs requirements
- [x] Legal grounding uses primary sources (RA 12009, COA 2023-004)
- [x] No phasing: MCP + A2A are core from day 1 (matches job descriptions)
- [x] Portfolio deliverables clearly defined for job applications

---

## 5. Next Step (Post-Planning)
All planning artifacts are finalized. User approval required to start **Implementation Phase**:
1. Scaffold Python project (poetry/pip, LangGraph deps)
2. Implement MCP servers (stdio transport)
3. Build LangGraph Orchestrator + 5 agents
4. Deploy Next.js dashboard

*All planning constraints met: No implementation code written during planning phase*
