"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Empty, EmptyDescription, EmptyTitle } from "@/components/ui/empty"
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/components/ui/pagination"
import { Input } from "@/components/ui/input"
import Image from "next/image"
import Link from "next/link"
import { Bot, FileText, ArrowRight, Search, X, Filter } from "lucide-react"

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
  agency: string
  source: string
  status: string
  anomalies_count: number
  final_risk_score: number
  alert_triggered: boolean
  created_at: string
}

interface Filters {
  q: string
  agency: string
  min_risk: number | null
  alerted_only: boolean
}

const EMPTY_FILTERS: Filters = {
  q: "",
  agency: "",
  min_risk: null,
  alerted_only: false,
}

const ITEMS_PER_PAGE = 10

async function fetchStatsData(): Promise<Stats> {
  const res = await fetch("/api/stats")
  return res.json()
}

async function fetchAnalysesData(filters: Filters): Promise<AnalysisListItem[]> {
  const params = new URLSearchParams()
  if (filters.q.trim()) params.set("q", filters.q.trim())
  if (filters.agency.trim()) params.set("agency", filters.agency.trim())
  if (filters.min_risk !== null) params.set("min_risk", String(filters.min_risk))
  if (filters.alerted_only) params.set("alerted_only", "true")
  params.set("limit", "500")
  const qs = params.toString()
  const res = await fetch(`/api/analyses?${qs}`)
  return res.json()
}

export default function Dashboard() {
  const [crawling, setCrawling] = useState(false)
  const [crawlStatus, setCrawlStatus] = useState("")
  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([])
  const [stats, setStats] = useState<Stats>({
    total_analyzed: 0,
    anomalies_found: 0,
    active_alerts: 0,
    compliance_rate: 0,
  })
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [searchInput, setSearchInput] = useState("")
  const [agencyInput, setAgencyInput] = useState("")

  useEffect(() => {
    let cancelled = false
    async function loadDashboard() {
      try {
        const [statsData, analysesData] = await Promise.all([
          fetchStatsData(),
          fetchAnalysesData(filters),
        ])
        if (!cancelled) {
          setStats(statsData)
          setAnalyses(analysesData)
        }
      } catch (error) {
        console.error(error)
      }
    }
    void loadDashboard()
    return () => {
      cancelled = true
    }
  }, [filters])

  const triggerCrawl = async () => {
    setCrawling(true)
    setCrawlStatus("Scanning PhilGEPS for anomalies...")
    try {
      const res = await fetch("/api/crawl", { method: "POST" })
      if (!res.ok) throw new Error(`Crawl failed: ${res.status}`)
      const data = await res.json()
      setCrawlStatus(
        `Analyzed ${data.total_analyzed} contracts — found ${data.total_anomalies} anomalies`
      )
      try {
        const [statsData, analysesData] = await Promise.all([
          fetchStatsData(),
          fetchAnalysesData(filters),
        ])
        setStats(statsData)
        setAnalyses(analysesData)
        setPage(1)
      } catch (error) {
        console.error("Failed to refresh dashboard after crawl", error)
      }
    } catch {
      setCrawlStatus("Scan failed - check backend is running")
    }
    setCrawling(false)
  }

  const applyFilters = () => {
    setFilters({
      q: searchInput,
      agency: agencyInput,
      min_risk: filters.min_risk,
      alerted_only: filters.alerted_only,
    })
    setPage(1)
  }

  const clearFilters = () => {
    setSearchInput("")
    setAgencyInput("")
    setFilters(EMPTY_FILTERS)
    setPage(1)
  }

  const toggleAlertedOnly = () => {
    setFilters((prev) => ({ ...prev, alerted_only: !prev.alerted_only }))
    setPage(1)
  }

  const toggleRiskFilter = (threshold: number | null) => {
    setFilters((prev) => ({
      ...prev,
      min_risk: prev.min_risk === threshold ? null : threshold,
    }))
    setPage(1)
  }

  const hasActiveFilters =
    filters.q !== "" ||
    filters.agency !== "" ||
    filters.min_risk !== null ||
    filters.alerted_only

  // Pagination
  const totalPages = Math.ceil(analyses.length / ITEMS_PER_PAGE)
  const paginatedAnalyses = analyses.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE)

  return (
    <div className="min-h-screen bg-background p-6">
      {/* Header */}
      <header className="mb-8">
        <h1 className="text-2xl font-semibold flex items-center gap-3">
          <Image src="/logo.png" alt="ProcuGents" width={32} height={32} className="h-8 w-auto" priority />
          ProcuGents
        </h1>
        <p className="text-muted-foreground mt-1">
          Automated Philippine Government Procurement Anomaly Detection
        </p>
      </header>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase flex items-center gap-2">
              <FileText className="h-3 w-3" /> Contracts Analyzed
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.total_analyzed}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase flex items-center gap-2">
              <FileText className="h-3 w-3 text-destructive" /> Anomalies Found
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-destructive">{stats.anomalies_found}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase">Active Alerts</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-amber-500">{stats.active_alerts}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase">Compliance Rate</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-500">{stats.compliance_rate}%</div>
          </CardContent>
        </Card>
      </div>

      {/* Auto-Crawl Card */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" /> Automated Detection
          </CardTitle>
          <CardDescription>
            ProcuGents automatically crawls PhilGEPS and detects procurement anomalies
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Button onClick={triggerCrawl} disabled={crawling} size="lg">
              {crawling ? (
                <span className="flex items-center gap-2">
                  <Bot className="h-4 w-4 animate-pulse" /> Scanning...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Bot className="h-4 w-4" /> Start Auto-Detection
                </span>
              )}
            </Button>
            {crawlStatus && (
              <span className="text-sm text-muted-foreground">{crawlStatus}</span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* History Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Contract History
            </span>
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="text-xs"
              >
                <X className="h-3 w-3 mr-1" /> Clear filters
              </Button>
            )}
          </CardTitle>
          <CardDescription>
            {hasActiveFilters
              ? `${analyses.length} matching contracts (filtered)`
              : `${analyses.length} contracts analyzed — click to view details`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filter bar */}
          <div className="flex flex-wrap items-end gap-3 p-3 bg-muted/30 rounded-lg">
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs text-muted-foreground mb-1 block">
                Search ID / description
              </label>
              <div className="relative">
                <Search className="h-3 w-3 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="e.g. NBCC-2024 or 'chairs'"
                  value={searchInput}
                  onChange={(e) => {
                    setSearchInput(e.target.value)
                    if (e.target.value === "") {
                      setFilters((prev) => ({ ...prev, q: "" }))
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") applyFilters()
                  }}
                  className="pl-7 h-8 text-sm"
                />
              </div>
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs text-muted-foreground mb-1 block">
                Agency
              </label>
              <Input
                placeholder="e.g. DepEd, DOH"
                value={agencyInput}
                onChange={(e) => {
                  setAgencyInput(e.target.value)
                  if (e.target.value === "") {
                    setFilters((prev) => ({ ...prev, agency: "" }))
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") applyFilters()
                }}
                className="h-8 text-sm"
              />
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={applyFilters}
              className="h-8"
            >
              Apply
            </Button>
            <div className="flex flex-wrap gap-1 items-center">
              <span className="text-xs text-muted-foreground mr-1">Risk:</span>
              {([null, 1, 2, 3, 4] as const).map((threshold) => {
                const active = filters.min_risk === threshold
                const label =
                  threshold === null ? "Any" : `${threshold}+`
                return (
                  <Badge
                    key={String(threshold)}
                    variant={active ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => toggleRiskFilter(threshold)}
                  >
                    {label}
                  </Badge>
                )
              })}
              <Badge
                variant={filters.alerted_only ? "destructive" : "outline"}
                className="cursor-pointer"
                onClick={toggleAlertedOnly}
              >
                Alerts only
              </Badge>
            </div>
          </div>

          {analyses.length === 0 ? (
            <Empty className="min-h-[300px]">
              <EmptyTitle>
                {hasActiveFilters ? "No contracts match your filters" : "No contracts analyzed yet"}
              </EmptyTitle>
              <EmptyDescription>
                {hasActiveFilters
                  ? "Try clearing or loosening your filters above."
                  : "Start auto-detection to analyze PhilGEPS procurements."}
              </EmptyDescription>
            </Empty>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Contract ID</TableHead>
                    <TableHead>Agency</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Risk</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Anomalies</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedAnalyses.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className="font-medium">
                        <Link href={`/contracts/${a.id}`} className="hover:underline flex items-center gap-2">
                          {a.contract_id}
                          {a.anomalies_count > 0 && <ArrowRight className="h-3 w-3" />}
                        </Link>
                      </TableCell>
                      <TableCell>{a.agency || "-"}</TableCell>
                      <TableCell>
                        {a.source ? (
                          <Badge variant="outline">{a.source}</Badge>
                        ) : "-"}
                      </TableCell>
                      <TableCell>{a.contract_description}</TableCell>
                      <TableCell>PHP {a.contract_amount?.toLocaleString()}</TableCell>
                      <TableCell>
                        <Badge variant={a.final_risk_score >= 4 ? "destructive" : a.final_risk_score >= 3 ? "secondary" : "outline"} className="font-mono">
                          {a.final_risk_score ?? 1}/5
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {a.alert_triggered ? (
                          <Badge variant="destructive">Alert</Badge>
                        ) : (
                          <Badge variant="outline" className="text-green-500">Clean</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {a.anomalies_count > 0 ? (
                          <Badge variant="secondary">{a.anomalies_count}</Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Link href={`/contracts/${a.id}`}>
                          <Button variant="ghost" size="sm">View</Button>
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="mt-4">
                  <Pagination>
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious 
                          onClick={() => setPage(p => Math.max(1, p - 1))}
                          className={page === 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                        />
                      </PaginationItem>
                      {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                        const pageNum = i + 1
                        return (
                          <PaginationItem key={pageNum}>
                            <PaginationLink 
                              onClick={() => setPage(pageNum)}
                              isActive={page === pageNum}
                            >
                              {pageNum}
                            </PaginationLink>
                          </PaginationItem>
                        )
                      })}
                      <PaginationItem>
                        <PaginationNext 
                          onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                          className={page === totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"}
                        />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                  <p className="text-sm text-muted-foreground text-center mt-2">
                    Page {page} of {totalPages}
                  </p>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}