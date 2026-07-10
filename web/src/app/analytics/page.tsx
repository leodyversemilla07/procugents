"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ArrowLeft, BarChart3, Building2, FileText, ShieldAlert, TrendingDown, TrendingUp } from "lucide-react"
import { Severity } from "@/lib/severity"

interface CohortItem {
  agency: string
  contract_count: number
  total_amount: number
  total_amount_formatted: string
  avg_risk_score: number
  max_risk_score: number
  high_risk_count: number
  anomaly_count: number
  alert_count: number
  anomaly_rate: number
  compliance_rate: number
}

interface CohortsResponse {
  cohorts: CohortItem[]
  total_agencies: number
}

export default function AnalyticsPage() {
  const [cohorts, setCohorts] = useState<CohortItem[]>([])
  const [loading, setLoading] = useState(true)
  const [minDate, setMinDate] = useState("")
  const [maxDate, setMaxDate] = useState("")
  const [minRisk, setMinRisk] = useState<string>("")

  const fetchCohorts = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (minDate) params.set("min_date", minDate)
      if (maxDate) params.set("max_date", maxDate)
      if (minRisk) params.set("min_risk", minRisk)

      const res = await fetch(`/api/analytics/cohorts?${params.toString()}`)
      const data: CohortsResponse = await res.json()
      setCohorts(data.cohorts)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }, [minDate, maxDate, minRisk])

  useEffect(() => {
    void fetchCohorts()
  }, [fetchCohorts])

  // Aggregate stats across all cohorts
  const aggregateStats = useMemo(() => {
    const totalContracts = cohorts.reduce((s, c) => s + c.contract_count, 0)
    const totalAmount = cohorts.reduce((s, c) => s + c.total_amount, 0)
    const totalHighRisk = cohorts.reduce((s, c) => s + c.high_risk_count, 0)
    const totalAnomalies = cohorts.reduce((s, c) => s + c.anomaly_count, 0)
    const avgCompliance =
      cohorts.length > 0
        ? round(cohorts.reduce((s, c) => s + c.compliance_rate, 0) / cohorts.length, 1)
        : 0
    return { totalContracts, totalAmount, totalHighRisk, totalAnomalies, avgCompliance }
  }, [cohorts])

  return (
    <div className="min-h-screen bg-background p-6">
      {/* Header */}
      <header className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Link href="/">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-1" /> Dashboard
            </Button>
          </Link>
          <Link href="/alerts">
            <Button variant="ghost" size="sm">
              <ShieldAlert className="h-4 w-4 mr-1" /> Alerts
            </Button>
          </Link>
        </div>
        <h1 className="text-2xl font-semibold flex items-center gap-3">
          <BarChart3 className="h-6 w-6" />
          Cohort Analytics
        </h1>
        <p className="text-muted-foreground mt-1">
          Per-agency procurement metrics — compare contract volumes, risk scores, and anomaly rates
        </p>
      </header>

      {/* Aggregate Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase">Agencies</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{cohorts.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase flex items-center gap-1">
              <FileText className="h-3 w-3" /> Contracts
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{aggregateStats.totalContracts}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase flex items-center gap-1">
              <Building2 className="h-3 w-3" /> Total Amount
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold truncate" title={`PHP ${aggregateStats.totalAmount.toLocaleString()}`}>
              PHP {(aggregateStats.totalAmount / 1_000_000).toFixed(1)}M
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase flex items-center gap-1">
              <TrendingUp className="h-3 w-3 text-destructive" /> High Risk
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-destructive">{aggregateStats.totalHighRisk}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs uppercase">Avg Compliance</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-500">{aggregateStats.avgCompliance}%</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Filter by date range & risk threshold</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">From</label>
              <Input
                type="date"
                value={minDate}
                onChange={(e) => setMinDate(e.target.value)}
                className="h-8 w-40"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">To</label>
              <Input
                type="date"
                value={maxDate}
                onChange={(e) => setMaxDate(e.target.value)}
                className="h-8 w-40"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Min risk score</label>
              <Input
                type="number"
                min={1}
                max={5}
                placeholder="1"
                value={minRisk}
                onChange={(e) => setMinRisk(e.target.value)}
                className="h-8 w-28"
              />
            </div>
            {(minDate || maxDate || minRisk) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setMinDate("")
                  setMaxDate("")
                  setMinRisk("")
                }}
                className="h-8"
              >
                Clear
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Cohort Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Per-Agency Metrics
          </CardTitle>
          <CardDescription>{cohorts.length} agencies with analyzed contracts</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-12 text-muted-foreground">Loading analytics...</div>
          ) : cohorts.length === 0 ? (
            <Empty className="min-h-[300px]">
              <EmptyTitle>No cohort data</EmptyTitle>
              <EmptyDescription>
                Analyze some contracts first to see per-agency metrics. Try running auto-detection
                from the dashboard.
              </EmptyDescription>
            </Empty>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Agency</TableHead>
                    <TableHead className="text-right">Contracts</TableHead>
                    <TableHead className="text-right">Total Amount</TableHead>
                    <TableHead className="text-right">Avg Risk</TableHead>
                    <TableHead className="text-right">Max Risk</TableHead>
                    <TableHead className="text-right">High Risk</TableHead>
                    <TableHead className="text-right">Anomalies</TableHead>
                    <TableHead className="text-right">Alerts</TableHead>
                    <TableHead className="text-right">Anomaly Rate</TableHead>
                    <TableHead className="text-right">Compliance</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {cohorts.map((c) => (
                    <TableRow key={c.agency}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                          {c.agency}
                        </div>
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {c.contract_count}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums text-xs">
                        {c.total_amount_formatted}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge variant={Severity.tone(c.avg_risk_score)} className="font-mono">
                          {c.avg_risk_score}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {c.max_risk_score}
                      </TableCell>
                      <TableCell className="text-right">
                        <span className={c.high_risk_count > 0 ? "text-destructive font-mono" : "font-mono"}>
                          {c.high_risk_count}
                        </span>
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {c.anomaly_count}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {c.alert_count}
                      </TableCell>
                      <TableCell className="text-right">
                        <span
                          className={`font-mono ${
                            c.anomaly_rate > 30
                              ? "text-destructive"
                              : c.anomaly_rate > 10
                                ? "text-amber-500"
                                : "text-green-500"
                          }`}
                        >
                          {c.anomaly_rate}%
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          {c.compliance_rate >= 80 ? (
                            <TrendingUp className="h-3 w-3 text-green-500" />
                          ) : (
                            <TrendingDown className="h-3 w-3 text-destructive" />
                          )}
                          <span
                            className={`font-mono ${
                              c.compliance_rate >= 80
                                ? "text-green-500"
                                : c.compliance_rate >= 50
                                  ? "text-amber-500"
                                  : "text-destructive"
                            }`}
                          >
                            {c.compliance_rate}%
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function round(value: number, decimals: number): number {
  const factor = Math.pow(10, decimals)
  return Math.round(value * factor) / factor
}
