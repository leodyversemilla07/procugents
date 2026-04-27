"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Empty, EmptyDescription, EmptyTitle } from "@/components/ui/empty"
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/components/ui/pagination"
import Link from "next/link"
import { Bot, FileText, ArrowRight } from "lucide-react"

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
  created_at: string
}

const ITEMS_PER_PAGE = 10

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

  useEffect(() => {
    fetchStats()
    fetchAnalyses()
  }, [])

  const triggerCrawl = async () => {
    setCrawling(true)
    setCrawlStatus("Scanning PhilGEPS for anomalies...")
    try {
      const res = await fetch("/api/crawl", { method: "POST" })
      const data = await res.json()
      setCrawlStatus(`Analyzed ${data.total_analyzed} contracts — found ${data.total_anomalies} anomalies`)
      fetchStats()
      fetchAnalyses()
    } catch (e) {
      setCrawlStatus("Scan failed - check backend is running")
    }
    setCrawling(false)
  }

  // Pagination
  const totalPages = Math.ceil(analyses.length / ITEMS_PER_PAGE)
  const paginatedAnalyses = analyses.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE)

  return (
    <div className="min-h-screen bg-background p-6">
      {/* Header */}
      <header className="mb-8">
        <h1 className="text-2xl font-semibold flex items-center gap-3">
          <img src="/logo.png" alt="ProcuGents" className="h-8 w-auto" />
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
          <CardTitle>Contract History</CardTitle>
          <CardDescription>
            {analyses.length} contracts analyzed - click to view details
          </CardDescription>
        </CardHeader>
        <CardContent>
          {analyses.length === 0 ? (
            <Empty className="min-h-[300px]">
              <EmptyTitle>No contracts analyzed yet</EmptyTitle>
              <EmptyDescription>Start auto-detection to find anomalies.</EmptyDescription>
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
                        <Badge variant={a.anomalies_count > 0 ? "destructive" : "secondary"}>
                          {a.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {a.anomalies_count > 0 ? (
                          <Badge variant="destructive">{a.anomalies_count}</Badge>
                        ) : (
                          <Badge variant="outline" className="text-green-500">Clean</Badge>
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