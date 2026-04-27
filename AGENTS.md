# ProcuGents

Philippine Government Procurement Anomaly Detection using Multi-Agent AI.

## Overview

RedFlag Agents PH is an AI-powered system that detects procurement anomalies in Philippine government contracts. It uses multi-agent orchestration to analyze contracts against RA 12009 (2024) thresholds and detect price inflation, legal violations, and compliance issues.

## Project Structure

```
procugents/
├── src/
│   ├── api/
│   │   └── main.py              # FastAPI endpoints
│   ├── orchestration/
│   │   └── orchestrator.py     # LangGraph workflow
│   ├── servers/
│   │   ├── a2a_server.py     # A2A Protocol server
│   │   └── mcp/            # MCP tool servers
│   │       ├── alert.py
│   │       ├── legal_lookup.py
│   │       ├── orchestrator_mcp.py
│   │       ├── philgeps_data.py
│   │       ├── philgeps_scraper.py
│   │       └── price_analysis.py
│   ├── services/
│   │   ├── cache.py           # Redis caching
│   │   └── database.py       # PostgreSQL storage
│   └── scripts/
│       └── auto_crawl.py     # PhilGEPS crawler
├── web/                       # Next.js 15 UI
│   └── src/app/
│       └── api/              # API routes
├── docs/                      # Data docs & schemas
├── tests/
│   └── test_orchestrator.py
├── Dockerfile
├── docker-compose.yaml
├── pyproject.toml
└── README.md
```

## Architecture

### Multi-Agent Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Legal     │───▶│   Price    │───▶│  PhilGEPS  │
│  Check     │    │  Analysis  │    │  Scraper   │
│  Agent     │    │  Agent    │    │   Agent    │
└─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │
       └──────────┬───────┴────────────────┘
                  ▼
         ┌─────────────┐
         │  Alert    │
         │  Agent   │
         └─────────────┘
```

### Workflow States (LangGraph)

| State | Description |
|-------|-------------|
| `pending` | Contract received |
| `legal_check` | RA 12009 threshold check |
| `price_check` | Price inflation analysis |
| `scraping` | PhilGEPS data retrieval |
| `alerting` | Create alerts for anomalies |
| `completed` | Analysis done |
| `error` | Workflow failed |

### Agents

1. **Legal Check Agent** — Validates SVP thresholds (₱1M), competitive bidding requirements
2. **Price Analysis Agent** — Detects price inflation (>70% baseline)
3. **PhilGEPS Scraper Agent** — Fetches procurement opportunities from PhilGEPS
4. **Alert Agent** — Creates alerts for detected anomalies

## Key Files

### Core

| File | Purpose |
|------|---------|
| `src/orchestration/orchestrator.py` | LangGraph workflow definition |
| `src/api/main.py` | FastAPI REST endpoints |
| `src/servers/mcp/orchestrator_mcp.py` | MCP tool exposed to agents |

### MCP Tools

| Tool | Description |
|------|-------------|
| `legal_lookup` | RA 12009 threshold lookup |
| `price_analysis` | Price inflation detection |
| `philgeps_scraper` | PhilGEPS web scraping |
| `philgeps_data` | PhilGEPS data access |
| `alert` | Alert creation |

### Services

| File | Purpose |
|------|---------|
| `src/services/database.py` | SQLAlchemy PostgreSQL |
| `src/services/cache.py` | Redis caching |

## API Endpoints

```bash
# Analyze contract
POST /api/analyze
{
  "contract_id": "PO-2024-001",
  "contract_description": "Office Chairs",
  "contract_amount": 500000
}

# Crawl PhilGEPS
POST /api/crawl

# Get stats
GET /api/stats

# List analyses
GET /api/analyses

# Get specific analysis
GET /api/analyses/{id}
```

## Legal Basis

- **RA 12009 (2024)** — Philippine Procurement Reform Act
  - SVP Threshold: ₱1,000,000
  - Competitive Bidding: > ₱1,000,000
- **PhilGEPS** — Required for procurements > ₱50,000
- **COA IIUEEU** — Irregular, Inappropriate, Unnecessary, Excessive, Extravagant

## Tech Stack

| Layer | Technology |
|-------|------------|
| Orchestration | LangGraph |
| Agents | MCP (Model Context Protocol) |
| Communication | A2A Protocol |
| Database | PostgreSQL (SQLAlchemy) |
| Cache | Redis |
| Frontend | Next.js 15 |
| Linting | ruff + ty |

## Quick Start

```bash
# Clone
git clone https://github.com/your-org/procugents.git
cd procugents

# Install
uv sync

# Run tests
python -m pytest tests/ -v

# Run orchestrator
python -m src.orchestration.orchestrator

# Run API
python -m src.api.main

# Run web UI
cd web && pnpm dev
```

## Docker

```bash
docker-compose up --build
```

## License

MIT