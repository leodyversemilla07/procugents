# RedFlag Agents PH — Legal Rule Engine
*Planning Artifact | Maps all agent red flags to exact legal citations, IIUEEU classifications, and severity*
*Sources: RA 12009 (2024), RA 12009 IRR (2025), RA 9184 IRR (2016 Rev, 2024 Update), COA Circular 2023-004, GPPB Circulars 2025*

---

## 1. COA IIUEEU Classification Definitions (Disallowance Grounds)
All red flags must map to one of these 6 classifications per COA Circular 2023-004:

| Classification | Code | Definition | Example Red Flag |
|----------------|------|------------|------------------|
| **Illegal** | I | Violates RA 12009, IRR, or binding procurement law | No competitive bidding for >₱1M procurement |
| **Irregular** | IR | Violates GPPB circulars/procedural rules (not strictly illegal) | <3 bidders for open competitive bidding |
| **Unnecessary** | U | Procurement not aligned with agency mandate/core functions | Buying 10 gaming laptops for a rural health unit |
| **Excessive** | E | Price >30% above verified market rate (COA benchmark) | Bid price 40% higher than average market price for same item |
| **Extravagant** | EX | Luxury/unjustified premium items without prior justification | Buying gold-plated office supplies for a municipal clerk |
| **Unconscionable** | UN | Grossly unreasonable expenditures with no public benefit | Paying ₱1M for a 10-page consultancy report |

---

## 2. Per-Agent Red Flag → Legal Citation Mapping
### 2.1 Scraper Agent (Data Collection Red Flags)
*Flags related to missing/incomplete procurement postings on PhilGEPS*

| Red Flag | Legal Citation | Law Source | IIUEEU Class | Severity (1-5) | Description |
|----------|----------------|------------|--------------|----------------|-------------|
| Missing PhilGEPS posting for >₱50k procurement | RA 12009 Sec 20.1 | RA 12009 | Illegal | 5 | All procurements must be posted to PhilGEPS (mandatory transparency) |
| Missing Annual Procurement Plan (APP) posting | RA 12009 IRR Rule III Sec 3 | RA 12009 IRR | Irregular | 3 | APP must be posted to PhilGEPS by Jan 31 annually |
| ITB posting <7 calendar days before bid deadline | RA 12009 IRR Sec 52.2 | RA 12009 IRR | Irregular | 4 | Minimum 7-day posting period for Invitation to Bid |
| Missing bid results/NOA/NTP posting within 3 days | GPPB Circular 03-2025 Sec 7 | GPPB | Irregular | 3 | Mandatory post-award posting requirements |

---

### 2.2 Price Analyst Agent (Price Integrity Red Flags)
*Flags related to abnormal pricing, budget splitting, market rate deviations*

| Red Flag | Legal Citation | Law Source | IIUEEU Class | Severity (1-5) | Description |
|----------|----------------|------------|--------------|----------------|-------------|
| Bid price >30% above market rate | COA Circular 2023-004 Sec 4.2 | COA 2023-004 | Excessive | 4 | COA benchmark for excessive expenditure disallowance |
| Approved Budget for Contract (ABC) split to stay ≤₱1M (avoid competitive bidding) | RA 12009 Sec 26(c) | RA 12009 | Illegal | 5 | Prohibited budget splitting to bypass mandatory bidding |
| SVP used for procurement >₱1M threshold | RA 12009 Sec 26(a) | RA 12009 | Illegal | 5 | SVP only valid for ≤₱1M (lower for small LGUs) |
| Bid price = ABC (0% savings) | RA 9184 IRR Sec 50.1 | RA 9184 IRR | Illegal | 5 | Presumption of bidder-procurer collusion |
| Price quote from unregistered PhilGEPS supplier | IRR Annex H Appendix A Sec 2 | RA 12009 IRR | Irregular | 3 | Only PhilGEPS-registered suppliers allowed to bid |

---

### 2.3 Bid Analyzer Agent (Bidding Process Red Flags)
*Flags related to bidding compliance, bidder eligibility, competition integrity*

| Red Flag | Legal Citation | Law Source | IIUEEU Class | Severity (1-5) | Description |
|----------|----------------|------------|--------------|----------------|-------------|
| <3 bidders for open competitive bidding | RA 9184 IRR Sec 52.1 | RA 9184 IRR | Irregular | 4 | Minimum 3 bidders required for valid open bidding |
| Dummy bidders (shared addresses/directors) | COA Circular 2023-004 Sec 5.1 | COA 2023-004 | Illegal | 5 | Collusive bidding = automatic disallowance |
| Alternative mode (Shopping/NP/DC) used without HoPE approval | RA 12009 IRR Rule XVI Sec 2 | RA 12009 IRR | Illegal | 5 | Prior written HoPE approval mandatory for alternative modes |
| Bidder lacks PCAB license for infrastructure projects | IRR Annex H Appendix A Sec 3 | RA 12009 IRR | Irregular | 4 | Mandatory license for contractors >₱1M infrastructure |
| Bidder lacks net financial contracting capacity (NFCC) | RA 12009 IRR Sec 42.3 | RA 12009 IRR | Irregular | 4 | Proof of financial capacity required for competitive bidding |
| Single bidder for negotiated procurement >₱1M | RA 12009 Sec 26(b) | RA 12009 | Irregular | 3 | Negotiated procurement requires minimum 2 bidders for >₱1M |

---

### 2.4 Doc Auditor Agent (Document Compliance Red Flags)
*Flags related to missing documentary requirements per COA 2023-004*

| Red Flag | Legal Citation | Law Source | IIUEEU Class | Severity (1-5) | Description |
|----------|----------------|------------|--------------|----------------|-------------|
| Missing PhilGEPS Certificate of Registration | COA 2023-004 Annex A Item 1 | COA 2023-004 | Irregular | 3 | Mandatory for all bidders |
| Missing Mayor's/Business Permit (bidder) | COA 2023-004 Annex A Item 2 | COA 2023-004 | Irregular | 3 | Valid business permit required |
| Missing bid security for competitive bidding >₱1M | RA 12009 IRR Sec 45.1 | RA 12009 IRR | Irregular | 4 | 1-3% bid security required for open bidding |
| Missing PhilGEPS posting proof for RFQ/ITB | IRR Rule III Sec 20.2 | RA 12009 IRR | Irregular | 3 | Proof of posting required for audit |
| Using alternative mode without HoPE written approval | RA 12009 IRR Rule XVI Sec 2 | RA 12009 IRR | Illegal | 5 | Prior approval mandatory for SVP/Shopping/NP/DC |
| Missing COA post-audit submission within 30 days | COA Circular 2023-004 Sec 7 | COA 2023-004 | Irregular | 3 | Mandatory post-audit document submission |

---

### 2.5 Alert Agent (Disallowance Reporting Red Flags)
*Flags that trigger formal COA disallowance alerts with IIUEEU classification*

| Red Flag | Legal Citation | Law Source | IIUEEU Class | Severity (1-5) | Description |
|----------|----------------|------------|--------------|----------------|-------------|
| Any Illegal classification red flag | RA 12009 Sec 65 | RA 12009 | Illegal | 5 | Mandatory COA disallowance + potential criminal charges |
| Any Excessive classification (price >30% above market) | COA 2023-004 Sec 4.2 | COA 2023-004 | Excessive | 4 | Full amount disallowed by COA |
| Any Unnecessary classification (non-mandate procurement) | COA 2023-004 Sec 3.1 | COA 2023-004 | Unnecessary | 3 | Disallowed if no mandate alignment proof |
| Any Extravagant classification (luxury items) | COA 2023-004 Sec 3.2 | COA 2023-004 | Extravagant | 4 | Disallowed + agency head reprimand |
| Any Unconscionable classification | COA 2023-004 Sec 3.3 | COA 2023-004 | Unconscionable | 5 | Full disallowance + Ombudsman filing |

---

## 3. Agent Lookup Table (JSON Format for LangGraph Tool Use)
This is the machine-readable version agents will query via the Legal Tool:

```json
{
  "iiueeu_classifications": {
    "I": {"name": "Illegal", "description": "Violates RA 12009/IRR", "severity_weight": 5},
    "IR": {"name": "Irregular", "description": "Violates GPPB circulars/procedural rules", "severity_weight": 4},
    "U": {"name": "Unnecessary", "description": "Not aligned with agency mandate", "severity_weight": 3},
    "E": {"name": "Excessive", "description": "Price >30% above market rate", "severity_weight": 4},
    "EX": {"name": "Extravagant", "description": "Luxury items without justification", "severity_weight": 4},
    "UN": {"name": "Unconscionable", "description": "Grossly unreasonable expenditure", "severity_weight": 5}
  },
  "agent_red_flags": {
    "scraper_agent": [
      {"flag": "missing_philgeps_posting", "citation": "RA 12009 Sec 20.1", "law_source": "RA 12009", "iiueeu": "I", "severity": 5},
      {"flag": "missing_app_posting", "citation": "RA 12009 IRR Rule III Sec 3", "law_source": "RA 12009 IRR", "iiueeu": "IR", "severity": 3}
    ],
    "price_analyst_agent": [
      {"flag": "price_30pct_above_market", "citation": "COA 2023-004 Sec 4.2", "law_source": "COA 2023-004", "iiueeu": "E", "severity": 4},
      {"flag": "budget_splitting", "citation": "RA 12009 Sec 26(c)", "law_source": "RA 12009", "iiueeu": "I", "severity": 5},
      {"flag": "svp_over_threshold", "citation": "RA 12009 Sec 26(a)", "law_source": "RA 12009", "iiueeu": "I", "severity": 5},
      {"flag": "bid_price_equals_abc", "citation": "RA 9184 IRR Sec 50.1", "law_source": "RA 9184 IRR", "iiueeu": "I", "severity": 5}
    ],
    "bid_analyzer_agent": [
      {"flag": "less_than_3_bidders", "citation": "RA 9184 IRR Sec 52.1", "law_source": "RA 9184 IRR", "iiueeu": "IR", "severity": 4},
      {"flag": "dummy_bidders", "citation": "COA 2023-004 Sec 5.1", "law_source": "COA 2023-004", "iiueeu": "I", "severity": 5},
      {"flag": "alt_mode_no_hope_approval", "citation": "RA 12009 IRR Rule XVI Sec 2", "law_source": "RA 12009 IRR", "iiueeu": "I", "severity": 5}
    ],
    "doc_auditor_agent": [
      {"flag": "missing_philgeps_registration", "citation": "COA 2023-004 Annex A Item 1", "law_source": "COA 2023-004", "iiueeu": "IR", "severity": 3},
      {"flag": "missing_business_permit", "citation": "COA 2023-004 Annex A Item 2", "law_source": "COA 2023-004", "iiueeu": "IR", "severity": 3},
      {"flag": "missing_bid_security", "citation": "RA 12009 IRR Sec 45.1", "law_source": "RA 12009 IRR", "iiueeu": "IR", "severity": 4}
    ],
    "alert_agent": [
      {"flag": "illegal_disallowance", "citation": "RA 12009 Sec 65", "law_source": "RA 12009", "iiueeu": "I", "severity": 5},
      {"flag": "excessive_disallowance", "citation": "COA 2023-004 Sec 4.2", "law_source": "COA 2023-004", "iiueeu": "E", "severity": 4}
    ]
  },
  "thresholds": {
    "competitive_bidding_min": 1000000,
    "svp_max": 1000000,
    "shopping_max": 500000,
    "price_excess_threshold_pct": 30,
    "min_bidders_open_bidding": 3
  }
}
```

---

## 4. Verification Checklist for Planning Phase
- [x] All 5 agents have mapped red flags to exact legal citations
- [x] Every red flag has IIUEEU classification
- [x] Severity scores (1-5) assigned consistently
- [x] Machine-readable JSON lookup table created for agent use
- [x] Primary law (RA 12009) prioritized over repealed RA 9184 for current procurements
- [x] COA 2023-004 benchmarks included for price/audit red flags

*Next Planning Step: Agent Prompts (write LangGraph system messages for all 5 agents + orchestrator)*
