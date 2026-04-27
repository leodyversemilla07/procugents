# ProcuGents

 Philippine Government Procurement Anomaly Detection using Multi-Agent AI.

## Features

- **Legal Compliance Check** - RA 12009 (2024) threshold verification (SVP ≤ ₱1M)
- **Price Analysis** - Detect potential price inflation (70% baseline)
- **PhilGEPS Integration** - Scrape procurement opportunities
- **Alerting System** - Create alerts for detected anomalies
- **A2A Protocol** - Agent-to-agent communication support
- **LangGraph Orchestrator** - Multi-agent workflow coordination
- **PostgreSQL + Redis** - Persistent storage and caching

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
# Clone and setup
cd ~/workspace/procugents

# Install dependencies
uv sync

# Set API key for AI analysis (free at https://opencode.ai/settings/api-keys)
export OPENCODE_API_KEY="your-key-here"

# Run tests
python -m pytest tests/ -v

# Run orchestrator
python -m src.orchestration.orchestrator

# Run API server
python -m src.api.main

# Run web UI
cd web && pnpm dev
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| OPENCODE_API_KEY | Free AI API from https://opencode.ai/settings/api-keys | No |
| OPENAI_API_KEY | OpenAI API key (fallback) | No |
| ANTHROPIC_API_KEY | Anthropic API key (fallback) | No |
| POSTGRES_PASSWORD | PostgreSQL password | No (SQLite default) |

## API Usage

```bash
curl -X POST http://localhost:3000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "contract_id": "PO-2024-001",
    "contract_description": "Office Chairs",
    "contract_amount": 500000
  }'
```

## MCP Tools

```python
from src.servers.mcp.orchestrator_mcp import analyze_procurement

result = await analyze_procurement(
    contract_id="PO-2024-001",
    contract_description="Office Chairs",
    contract_amount=500_000,
)
```

## Project Structure

```
procugents/
├── src/
│   ├── api/              # FastAPI endpoints
│   │   └── main.py
│   ├── orchestration/    # LangGraph workflow
│   │   └── orchestrator.py
│   ├── servers/
│   │   ├── a2a_server.py      # A2A Protocol server
│   │   └── mcp/               # MCP tool servers
│   │       ├── legal_lookup.py
│   │       ├── price_analysis.py
│   │       ├── philgeps_scraper.py
│   │       ├── philgeps_data.py
│   │       ├── alert.py
│   │       └── orchestrator_mcp.py
│   └── services/         # Business logic
│       ├── database.py
│       └── cache.py
├── web/                  # Next.js 15 UI
├── scripts/             # Utility scripts
│   └── auto_crawl.py
├── tests/                # pytest tests
├── data/                 # Data files
├── Dockerfile
├── docker-compose.yaml
├── pyproject.toml
└── README.md
```

## Legal Basis

- **RA 12009 (2024)** - Philippine Procurement Reform Act
  - SVP Threshold: ₱1,000,000
  - Competitive Bidding: > ₱1,000,000
- **PhilGEPS** - Required for procurements > ₱50,000
- **COA IIUEEU** - Irregular, Inappropriate, Unnecessary, Excessive, Extravagant

## License

MIT