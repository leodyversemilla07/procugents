"use client"

import { useState, useEffect } from "react"

interface AnalysisResult {
  contract_id: string
  status: string
  legal_findings: { threshold_compliant: boolean; required_process: string; violations: string[] }
  price_findings: { flag: string; reason: string; baseline: number }
  scraping_results: { results: any[] }
  llm_analysis: { available: boolean }
  anomalies: { type: string; severity: string; description: string }[]
  alerts: { title: string; severity: string; description: string }[]
}

interface Stats {
  total_analyzed: number
  anomalies_found: number
  active_alerts: number
  compliance_rate: number
}

interface AnalysisListItem {
  id: number
  contract_id: string
  contract_description: string
  contract_amount: number
  status: string
  anomalies_count: number
  created_at: string
}

export default function Dashboard() {
  const [contractId, setContractId] = useState("")
  const [description, setDescription] = useState("")
  const [amount, setAmount] = useState("")
  const [loading, setLoading] = useState(false)
  const [crawling, setCrawling] = useState(false)
  const [crawlStatus, setCrawlStatus] = useState("")
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [stats, setStats] = useState<Stats>({
    total_analyzed: 0,
    anomalies_found: 0,
    active_alerts: 0,
    compliance_rate: 0,
  })

  const fetchStats = async () => {
    try {
      const res = await fetch("/api/stats")
      const data = await res.json()
      setStats(data)
    } catch (e) {
      console.error(e)
    }
  }

  const fetchAnalyses = async () => {
    try {
      const res = await fetch("/api/analyses")
      const data = await res.json()
      setAnalyses(data)
    } catch (e) {
      console.error(e)
    }
  }

  const loadDetail = async (id: number) => {
    setSelectedId(id)
    try {
      const res = await fetch(`/api/analyses/${id}`)
      const data = await res.json()
      setResult(data)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchStats()
    fetchAnalyses()
  }, [])

  const analyze = async () => {
    if (!contractId || !description || !amount) return
    setLoading(true)
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contract_id: contractId,
          contract_description: description,
          contract_amount: parseFloat(amount),
        }),
      })
      const data = await res.json()
      setResult(data)
      // Refresh stats after analysis
      fetchStats()
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  const triggerCrawl = async () => {
    setCrawling(true)
    setCrawlStatus("Crawling PhilGEPS...")
    try {
      const res = await fetch("/api/crawl", { method: "POST" })
      const data = await res.json()
      setCrawlStatus(`Crawled ${data.analyzed || 0} contracts`)
      fetchStats()
    } catch (e) {
      setCrawlStatus("Crawl failed")
    }
    setCrawling(false)
  }

  return (
    <div style={{ minHeight: "100vh", background: "#0f0f0f", color: "#fff", padding: "2rem" }}>
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ color: "#f43f5e" }}>●</span>
          RedFlag Agents PH
        </h1>
        <p style={{ color: "#888", marginTop: "0.25rem" }}>
          Philippine Government Procurement Anomaly Detection
        </p>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
        <StatCard label="Total Analyzed" value={stats.total_analyzed.toString()} />
        <StatCard label="Anomalies Found" value={stats.anomalies_found.toString()} />
        <StatCard label="Active Alerts" value={stats.active_alerts.toString()} />
        <StatCard label="Compliance Rate" value={`${stats.compliance_rate}%`} />
      </div>

      <section style={{ background: "#1a1a1a", borderRadius: "0.5rem", padding: "1.5rem", marginBottom: "2rem" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 500, marginBottom: "1rem" }}>Analyze Procurement</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          <input
            placeholder="Contract ID (e.g., PO-2024-001234)"
            value={contractId}
            onChange={(e) => setContractId(e.target.value)}
            style={inputStyle}
          />
          <input
            placeholder="Description (e.g., Office Chairs)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={inputStyle}
          />
          <input
            type="number"
            placeholder="Amount (PHP)"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            style={inputStyle}
          />
        </div>
        <button onClick={analyze} disabled={loading} style={{ ...buttonStyle, marginTop: "1rem" }}>
          {loading ? "Analyzing..." : "Analyze"}
        </button>
        <button onClick={triggerCrawl} disabled={crawling} style={{ ...buttonStyle, marginTop: "1rem", marginLeft: "0.5rem", background: crawling ? "#666" : "#22c55e" }}>
          {crawling ? "Crawling..." : "🤖 Auto-Crawl PhilGEPS"}
        </button>
        {crawlStatus && <span style={{ marginLeft: "1rem", color: "#888" }}>{crawlStatus}</span>}
      </section>

      {/* Recent Analyses List */}
      <section style={{ background: "#1a1a1a", borderRadius: "0.5rem", padding: "1.5rem", marginBottom: "2rem" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 500, marginBottom: "1rem" }}>Recent Analyses ({analyses.length})</h2>
        <div style={{ maxHeight: "300px", overflowY: "auto" }}>
          {analyses.slice(0, 20).map((a) => (
            <div 
              key={a.id} 
              onClick={() => loadDetail(a.id)}
              style={{ 
                padding: "0.75rem", 
                background: selectedId === a.id ? "#333" : "#252525", 
                borderRadius: "0.25rem", 
                marginBottom: "0.5rem",
                cursor: "pointer",
                border: selectedId === a.id ? "1px solid #f43f5e" : "1px solid transparent"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 500 }}>{a.contract_id}</span>
                <span style={{ color: a.anomalies_count > 0 ? "#f43f5e" : "#22c55e", fontSize: "0.75rem" }}>
                  {a.anomalies_count > 0 ? `${a.anomalies_count} anomalies` : "Clean"}
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "#888" }}>
                {a.contract_description} — ₱{a.contract_amount?.toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </section>

      {result && (
        <section style={{ background: "#1a1a1a", borderRadius: "0.5rem", padding: "1.5rem" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: 500, marginBottom: "1rem" }}>Results</h2>
          <div style={{ display: "grid", gap: "1rem" }}>
            <div>
              <div style={{ color: "#888", fontSize: "0.75rem" }}>Status</div>
              <div style={{ color: result.status === "alerting" ? "#f43f5e" : "#22c55e" }}>{result.status}</div>
            </div>
            <div>
              <div style={{ color: "#888", fontSize: "0.75rem" }}>Legal Findings</div>
              <div>
                {result.legal_findings?.threshold_compliant ? (
                  <span style={{ color: "#22c55e" }}>✓ Compliant</span>
                ) : (
                  <span style={{ color: "#f43f5e" }}>✗ Violations: {result.legal_findings?.violations?.join(", ")}</span>
                )}
              </div>
            </div>
            <div>
              <div style={{ color: "#888", fontSize: "0.75rem" }}>Price Analysis</div>
              <div style={{ color: result.price_findings?.flag === "normal" ? "#22c55e" : "#f43f5e" }}>
                {result.price_findings?.flag} — {result.price_findings?.reason}
              </div>
            </div>
            {result.scraping_results?.results?.length > 0 && (
              <div>
                <div style={{ color: "#888", fontSize: "0.75rem" }}>Similar Contracts Found</div>
                {result.scraping_results.results.slice(0, 3).map((r: any, i: number) => (
                  <div key={i} style={{ padding: "0.5rem", background: "#252525", borderRadius: "0.25rem", marginTop: "0.5rem" }}>
                    <div style={{ fontWeight: 500 }}>{r.title}</div>
                    <div style={{ fontSize: "0.75rem", color: "#888" }}>
                      {r.agency} — ₱{r.contract_amount?.toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {result.llm_analysis?.available === false && (
              <div style={{ padding: "0.5rem", background: "#252525", borderRadius: "0.25rem", fontSize: "0.75rem", color: "#888" }}>
                ℹ️ Set OPENCODE_API_KEY for AI-powered analysis
              </div>
            )}
            {result.anomalies?.length > 0 && (
              <div>
                <div style={{ color: "#888", fontSize: "0.75rem" }}>Anomalies ({result.anomalies.length})</div>
                {result.anomalies.map((a, i) => (
                  <div key={i} style={{ padding: "0.5rem", background: "#252525", borderRadius: "0.25rem", marginTop: "0.5rem" }}>
                    <span style={{ color: a.severity === "high" ? "#f43f5e" : "#fbbf24", marginRight: "0.5rem" }}>
                      [{a.severity.toUpperCase()}]
                    </span>
                    {a.type}: {a.description}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "#1a1a1a", borderRadius: "0.5rem", padding: "1.5rem" }}>
      <div style={{ color: "#888", fontSize: "0.75rem", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: "1.5rem", fontWeight: 600, marginTop: "0.25rem" }}>{value}</div>
    </div>
  )
}

const inputStyle = {
  background: "#252525",
  border: "1px solid #333",
  borderRadius: "0.375rem",
  padding: "0.75rem",
  color: "#fff",
  width: "100%",
  fontSize: "0.875rem",
} as const

const buttonStyle = {
  background: "#f43f5e",
  border: "none",
  borderRadius: "0.375rem",
  padding: "0.75rem 1.5rem",
  color: "#fff",
  fontWeight: 500,
  cursor: "pointer",
} as const