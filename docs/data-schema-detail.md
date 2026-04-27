# ProcuGents — Data Schema Detail
*Planning Artifact | Full PostgreSQL schema + Redis key structures, aligned with Agent Prompts + Legal Rule Engine*
*Constraint: Planning phase only — schema definitions, no implementation code*

---

## 1. PostgreSQL Schema (Expanded from procurement_schema.sql)
All tables use `JSONB` for flexible agent outputs, matching the Agent Prompt output schemas.

### 1.1 Enable Extensions
```sql
-- Run in target PostgreSQL database (v14+)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- For future UUID-based procurement IDs
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- For fuzzy text search on project names/agencies
```

### 1.2 Main Procurements Table
Stores all PhilGEPS procurement records + aggregated agent results.
```sql
CREATE TABLE IF NOT EXISTS procurements (
    -- Primary key
    id SERIAL PRIMARY KEY,
    notice_id VARCHAR(255) UNIQUE NOT NULL,  -- PhilGEPS unique notice ID
    
    -- Core procurement fields (from Scraper Agent)
    agency VARCHAR(255) NOT NULL,
    project_name TEXT NOT NULL,
    approved_budget DECIMAL(15,2) NOT NULL,  -- ABC (Approved Budget for Contract)
    contractor VARCHAR(255),
    bid_price DECIMAL(15,2),
    date_posted DATE NOT NULL,
    procurement_type VARCHAR(100) NOT NULL,  -- "Goods", "Infrastructure", "Consulting"
    source_url TEXT,  -- PhilGEPS posting URL
    
    -- Price Analyst Agent outputs (Section 2.2 Agent Prompts)
    price_risk_score INT CHECK (price_risk_score BETWEEN 1 AND 5),
    price_flags JSONB DEFAULT '[]',  -- Matches Agent Prompt output: [{"flag": "...", "citation": "..."}]
    price_citations TEXT[],           -- Deduplicated citation list
    abc_vs_market_diff_pct DECIMAL(5,2),  -- % difference from market rate
    
    -- Bid Analyzer Agent outputs (Section 2.3 Agent Prompts)
    bid_risk_score INT CHECK (bid_risk_score BETWEEN 1 AND 5),
    bid_flags JSONB DEFAULT '[]',
    bid_citations TEXT[],
    bidder_count INT,  -- Number of valid bidders
    
    -- Doc Auditor Agent outputs (Section 2.4 Agent Prompts)
    doc_risk_score INT CHECK (doc_risk_score BETWEEN 1 AND 5),
    doc_flags JSONB DEFAULT '[]',
    doc_citations TEXT[],
    missing_docs TEXT[],  -- List of missing mandatory documents
    
    -- Alert Agent outputs (Section 2.5 Agent Prompts)
    final_risk_score INT CHECK (final_risk_score BETWEEN 1 AND 5),
    all_flags JSONB DEFAULT '[]',  -- Aggregated flags from all agents
    all_citations TEXT[],           -- Deduplicated all citations
    alert_triggered BOOLEAN DEFAULT FALSE,
    alert_report TEXT,  -- COA-formatted disallowance report
    
    -- Workflow state (Orchestrator Agent)
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'scraping', 'price_analysis', 'bid_analysis', 'doc_audit', 'alert_generated', 'completed', 'error')),
    current_agent VARCHAR(100),  -- Last agent to process this procurement
    retry_count INT DEFAULT 0 CHECK (retry_count <= 2),
    error TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance (matching Orchestrator query patterns)
CREATE INDEX IF NOT EXISTS idx_procurements_agency ON procurements(agency);
CREATE INDEX IF NOT EXISTS idx_procurements_risk ON procurements(final_risk_score);
CREATE INDEX IF NOT EXISTS idx_procurements_status ON procurements(status);
CREATE INDEX IF NOT EXISTS idx_procurements_date ON procurements(date_posted);
CREATE INDEX IF NOT EXISTS idx_procurements_type ON procurements(procurement_type);
-- GIN index for JSONB flag queries (find all procurements with "illegal" flags)
CREATE INDEX IF NOT EXISTS idx_procurements_price_flags ON procurements USING GIN (price_flags);
CREATE INDEX IF NOT EXISTS idx_procurements_all_flags ON procurements USING GIN (all_flags);
```

### 1.3 Agent Results Table
Stores individual agent run outputs (for audit trails, matches Orchestrator state).
```sql
CREATE TABLE IF NOT EXISTS agent_results (
    id SERIAL PRIMARY KEY,
    procurement_id INT REFERENCES procurements(id) ON DELETE CASCADE,
    agent_name VARCHAR(100) NOT NULL CHECK (agent_name IN ('scraper', 'price_analyst', 'bid_analyzer', 'doc_auditor', 'alert')),
    result JSONB NOT NULL,  -- Full agent output matching Agent Prompt schemas
    risk_score INT CHECK (risk_score BETWEEN 1 AND 5),
    executed_at TIMESTAMP DEFAULT NOW(),
    
    -- Track agent run metadata
    redis_session_id VARCHAR(255),  -- Links to Redis state key
    retry_attempt INT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_agent_results_procurement ON agent_results(procurement_id);
CREATE INDEX IF NOT EXISTS idx_agent_results_agent ON agent_results(agent_name);
```

### 1.4 Legal Citations Table
Lookup table for RA 12009/IRR/COA citations (matches Legal Rule Engine Section 3).
```sql
CREATE TABLE IF NOT EXISTS legal_citations (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,  -- e.g., "RA 12009 Sec 20.1"
    description TEXT NOT NULL,
    coa_classification VARCHAR(50) NOT NULL CHECK (coa_classification IN ('Illegal', 'Irregular', 'Unnecessary', 'Excessive', 'Extravagant', 'Unconscionable')),
    law_source VARCHAR(100) NOT NULL,  -- "RA 12009", "COA 2023-004", etc.
    severity INT NOT NULL CHECK (severity BETWEEN 1 AND 5),  -- Matches Legal Rule Engine severity
    agent_target VARCHAR(100)[]  -- Which agents use this citation e.g., ["price_analyst", "alert"]
);

-- Insert seed data from Legal Rule Engine
INSERT INTO legal_citations (code, description, coa_classification, law_source, severity, agent_target) VALUES
('RA 12009 Sec 20.1', 'Mandatory PhilGEPS posting for all procurements', 'Illegal', 'RA 12009', 5, ARRAY['scraper', 'doc_auditor']),
('RA 12009 Sec 26(c)', 'Budget splitting to avoid competitive bidding', 'Illegal', 'RA 12009', 5, ARRAY['price_analyst']),
('RA 12009 Sec 26(a)', 'SVP only valid for ≤₱1M procurements', 'Illegal', 'RA 12009', 5, ARRAY['price_analyst']),
('COA 2023-004 Sec 4.2', 'Price >30% above market rate = Excessive', 'Excessive', 'COA 2023-004', 4, ARRAY['price_analyst', 'alert']),
('RA 9184 IRR Sec 52.1', '<3 bidders for open bidding = Irregular', 'Irregular', 'RA 9184 IRR', 4, ARRAY['bid_analyzer']),
('COA 2023-004 Sec 5.1', 'Dummy bidders = Collusive bidding (Illegal)', 'Illegal', 'COA 2023-004', 5, ARRAY['bid_analyzer', 'alert']),
('RA 12009 IRR Rule XVI Sec 2', 'Alternative modes require prior HoPE approval', 'Illegal', 'RA 12009 IRR', 5, ARRAY['bid_analyzer', 'doc_auditor']),
('COA 2023-004 Annex A Item 1', 'Missing PhilGEPS registration = Irregular', 'Irregular', 'COA 2023-004', 3, ARRAY['doc_auditor']),
('RA 12009 Sec 65', 'Illegal expenditures = Mandatory COA disallowance', 'Illegal', 'RA 12009', 5, ARRAY['alert'])
ON CONFLICT (code) DO UPDATE SET
  description = EXCLUDED.description,
  coa_classification = EXCLUDED.coa_classification,
  severity = EXCLUDED.severity,
  agent_target = EXCLUDED.agent_target;
```

### 1.5 Alert Queue Table
Pending alerts for the Alert Agent to process (matches Alert Agent output).
```sql
CREATE TABLE IF NOT EXISTS alert_queue (
    id SERIAL PRIMARY KEY,
    procurement_id INT REFERENCES procurements(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) CHECK (alert_type IN ('illegal', 'excessive', 'unconscionable')),
    trigger_citation TEXT NOT NULL,
    coa_classification VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'generated', 'sent', 'error')),
    generated_report TEXT,  -- Final COA report
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_queue_status ON alert_queue(status);
CREATE INDEX IF NOT EXISTS idx_alert_queue_type ON alert_queue(alert_type);
```

---

## 2. Redis Key Structures (Agent State + Checkpointing)
Used by Orchestrator Agent for durable state management (LangGraph RedisSaver).

### 2.1 Procurement State Keys
```text
Key Format: procurement:{notice_id}:state
Type: JSON String
TTL: 86400s (24h, cleared after completion)
Content: Full ProcurementState dict matching Orchestrator input/output schemas
Example:
{
  "notice_id": "2026-04-001",
  "agency": "Dept of Public Works",
  "current_agent": "price_analyst",
  "scraper_status": "completed",
  "price_status": "in_progress",
  "retry_count": 0
}
```

### 2.2 Agent Task Locks
```text
Key Format: procurement:{notice_id}:locks:{agent_name}
Type: String (SETNX lock)
TTL: 60s (heartbeat)
Purpose: Prevent duplicate agent runs for the same procurement
```

### 2.3 Agent Heartbeat
```text
Key Format: procurement:{notice_id}:heartbeat:{agent_name}
Type: String (timestamp)
TTL: 60s (updated every 30s by agent)
Purpose: Orchestrator checks if agent is alive before retrying
```

### 2.4 Dashboard Pub/Sub Channel
```text
Channel: dashboard:updates
Message Format: JSON
Purpose: Notify Next.js frontend of procurement status changes
Example Message:
{
  "type": "procurement_updated",
  "notice_id": "2026-04-001",
  "status": "alert_generated",
  "final_risk_score": 5
}
```

### 2.5 LangGraph Checkpointing (RedisSaver)
```text
Key Format: langgraph_checkpoint:{thread_id}:{checkpoint_id}
Type: Binary (LangGraph serialized state)
TTL: 7d (for retry/resume)
Purpose: Durable checkpointing for Orchestrator graph runs
```

---

## 3. Schema Verification Checklist
- [x] All tables use JSONB for agent outputs (matches Agent Prompt schemas)
- [x] Indexes cover common Orchestrator query patterns (agency, risk score, status)
- [x] GIN indexes for JSONB flag queries (find illegal flags fast)
- [x] Redis keys have TTL to prevent stale state
- [x] Alert queue matches Alert Agent trigger rules (Illegal/Excessive/Unconscionable)
- [x] Legal citations table seeded with Legal Rule Engine data
- [x] All constraints (CHECK, FOREIGN KEY) enforce data integrity

*Next Planning Step: MCP Server Specs (detail every tool each MCP server exposes, input/output JSON schemas)*
