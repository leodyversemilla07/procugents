-- RedFlag Agents PH — PostgreSQL Schema (Phase 1)
-- Run this in your PostgreSQL database

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main procurements table
CREATE TABLE IF NOT EXISTS procurements (
    id SERIAL PRIMARY KEY,
    notice_id VARCHAR(255) UNIQUE NOT NULL,
    agency VARCHAR(255) NOT NULL,
    project_name TEXT NOT NULL,
    approved_budget DECIMAL(15,2) NOT NULL,
    contractor VARCHAR(255),
    bid_price DECIMAL(15,2),
    date_posted DATE NOT NULL,
    procurement_type VARCHAR(100) NOT NULL,
    source_url TEXT,
    abc_vs_market_diff_pct DECIMAL(5,2),
    
    -- Agent outputs (populated as agents process)
    price_risk_score INT,
    price_flags JSONB DEFAULT '[]',
    price_citations TEXT[],
    
    bid_risk_score INT,
    bid_flags JSONB DEFAULT '[]',
    bid_citations TEXT[],
    
    doc_risk_score INT,
    doc_flags JSONB DEFAULT '[]',
    doc_citations TEXT[],
    
    -- Aggregated
    final_risk_score INT,
    all_flags JSONB DEFAULT '[]',
    all_citations TEXT[],
    
    -- Workflow
    status VARCHAR(50) DEFAULT 'pending',
    current_agent VARCHAR(100),
    error TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_procurements_agency ON procurements(agency);
CREATE INDEX IF NOT EXISTS idx_procurements_risk ON procurements(final_risk_score);
CREATE INDEX IF NOT EXISTS idx_procurements_status ON procurements(status);
CREATE INDEX IF NOT EXISTS idx_procurements_date ON procurements(date_posted);

-- Agent results table (individual agent outputs)
CREATE TABLE IF NOT EXISTS agent_results (
    id SERIAL PRIMARY KEY,
    procurement_id INT REFERENCES procurements(id) ON DELETE CASCADE,
    agent_name VARCHAR(100) NOT NULL,
    result JSONB NOT NULL,
    risk_score INT,
    executed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_results_procurement ON agent_results(procurement_id);

-- Legal citations lookup table
CREATE TABLE IF NOT EXISTS legal_citations (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    coa_classification VARCHAR(50),  -- "Illegal", "Irregular", "Excessive", etc.
    law_source VARCHAR(100),           -- "RA 12009", "COA 2023-004", etc.
    severity INT                       -- 1-5 scale
);

-- Insert key legal citations (from legal-basis.md)
INSERT INTO legal_citations (code, description, coa_classification, law_source, severity) VALUES
('RA 12009 Sec 26', 'Mandatory competitive bidding for >₱1M', 'Illegal', 'RA 12009', 5),
('RA 12009 Sec 20', 'PhilGEPS posting mandatory for all procurements', 'Illegal', 'RA 12009', 5),
('COA 2023-004', 'Price >30% above market rate = Excessive Expenditure', 'Excessive', 'COA 2023-004', 4),
('RA 9184 IRR Sec 52.1', '<3 bidders for open bidding = Irregular', 'Irregular', 'RA 9184 IRR', 4),
('RA 9184 IRR Sec 50', 'Bid price = Approved Budget = Collusion presumption', 'Illegal', 'RA 9184 IRR', 5),
('IRR Annex H App A', 'Missing PhilGEPS registration = Irregular', 'Irregular', 'IRR Annex H', 3),
('RA 12009 Sec 26(c)', 'Budget splitting to avoid competitive bidding = Illegal', 'Illegal', 'RA 12009', 5)
ON CONFLICT (code) DO NOTHING;

-- Redis key structure (documentation, not SQL)
-- Keys:
--   procurement:{id}:state          -> JSON of ProcurementState
--   procurement:{id}:locks          -> Agent task locks (SETNX)
--   procurement:{id}:heartbeat     -> Agent alive check (TTL 60s)
--   alerts:queue                   -> Pending alerts for Alert Agent
--   dashboard:updates             -> Pub/Sub channel for Next.js

COMMENT ON TABLE procurements IS 'Main table storing all PH government procurement records and agent analysis results';
COMMENT ON TABLE agent_results IS 'Individual agent outputs (each agent writes here)';
COMMENT ON TABLE legal_citations IS 'Lookup table for RA 12009, IRR, COA circulars';
