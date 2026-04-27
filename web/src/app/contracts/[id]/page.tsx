"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import { ArrowLeft, ShieldAlert, CheckCircle2, XCircle, AlertTriangle, TrendingUp, Building2, FileText } from "lucide-react"
import Link from "next/link"

interface ContractDetail {
  contract_id: string
  contract_description: string
  contract_amount: number
  agency: string
  status: string
  legal_findings: {
    threshold_compliant: boolean
    required_process: string
    threshold: number
    violations: string[]
    law: string
  }
  price_findings: {
    flag: string
    reason: string
    baseline: number
    amount: number
  }
  anomalies: { type: string; severity: string; description: string }[]
  alerts: { title: string; severity: string; description: string }[]
  created_at: string
}

export default function ContractDetailPage() {
  const params = useParams()
  const id = params?.id as string
  const [contract, setContract] = useState<ContractDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!id) return
    fetch(`/api/contracts/${id}`)
      .then(res => res.json())
      .then(data => {
        setContract(data)
        setLoading(false)
      })
      .catch(err => {
        setError(String(err))
        setLoading(false)
      })
  }, [id])

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-32 bg-muted rounded" />
          <div className="h-64 bg-muted rounded" />
        </div>
      </div>
    )
  }

  if (error || !contract) {
    return (
      <div className="min-h-screen bg-background p-6">
        <Link href="/">
          <Button variant="ghost" className="mb-4">
            <ArrowLeft className="h-4 w-4 mr-2" /> Back
          </Button>
        </Link>
        <Alert variant="destructive">
          <XCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error || "Contract not found"}</AlertDescription>
        </Alert>
      </div>
    )
  }

  const hasAnomalies = contract.anomalies && contract.anomalies.length > 0

  return (
    <div className="min-h-screen bg-background p-6">
      <Link href="/">
        <Button variant="ghost" className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" /> Back to Dashboard
        </Button>
      </Link>

      {/* Header */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl flex items-center gap-2">
                {hasAnomalies && <ShieldAlert className="h-5 w-5 text-destructive" />}
                {contract.contract_id}
              </CardTitle>
              <CardDescription>
                {contract.contract_description}
              </CardDescription>
            </div>
            <Badge variant={hasAnomalies ? "destructive" : "secondary"}>
              {hasAnomalies ? `${contract.anomalies.length} Anomalies` : "Clean"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Amount</span>
              <p className="text-2xl font-bold">PHP {contract.contract_amount?.toLocaleString()}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Agency</span>
              <p className="font-medium flex items-center gap-2">
                <Building2 className="h-4 w-4" /> {contract.agency || "N/A"}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Status</span>
              <p className="font-medium">{contract.status}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Analyzed</span>
              <p className="text-sm">{new Date(contract.created_at).toLocaleDateString()}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Analysis Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Legal Findings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4" /> Legal Compliance (RA 12009)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {contract.legal_findings?.threshold_compliant ? (
              <Alert className="bg-green-500/10 border-green-500/20">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <AlertTitle className="text-green-500">Compliant</AlertTitle>
                <AlertDescription>
                  {contract.legal_findings?.required_process}
                </AlertDescription>
              </Alert>
            ) : (
              <Alert variant="destructive">
                <XCircle className="h-4 w-4" />
                <AlertTitle>Violations Detected</AlertTitle>
                <AlertDescription>
                  {contract.legal_findings?.violations?.join(", ")}
                </AlertDescription>
              </Alert>
            )}
            <p className="text-sm text-muted-foreground mt-2">
              SVP Threshold: PHP {contract.legal_findings?.threshold?.toLocaleString()}
            </p>
          </CardContent>
        </Card>

        {/* Price Analysis */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4" /> Price Analysis
            </CardTitle>
          </CardHeader>
          <CardContent>
            {contract.price_findings?.flag === "normal" ? (
              <Alert className="bg-green-500/10 border-green-500/20">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <AlertTitle className="text-green-500">Normal Price</AlertTitle>
                <AlertDescription>
                  Within market baseline
                </AlertDescription>
              </Alert>
            ) : (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Potential Inflation</AlertTitle>
                <AlertDescription>
                  {contract.price_findings?.reason}
                </AlertDescription>
              </Alert>
            )}
            <p className="text-sm text-muted-foreground mt-2">
              Baseline: PHP {contract.price_findings?.baseline?.toLocaleString()}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Anomalies */}
      {hasAnomalies && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Detected Anomalies ({contract.anomalies.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {contract.anomalies.map((anomaly, i) => (
                <Alert key={i} variant={anomaly.severity === "high" ? "destructive" : "default"}>
                  <Badge variant={anomaly.severity === "high" ? "destructive" : "secondary"} className="mr-2">
                    {anomaly.severity}
                  </Badge>
                  <AlertTitle>{anomaly.type}</AlertTitle>
                  <AlertDescription>{anomaly.description}</AlertDescription>
                </Alert>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Alerts */}
      {contract.alerts && contract.alerts.length > 0 && (
        <>
          <Separator className="my-6" />
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Alerts Created</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {contract.alerts.map((alert, i) => (
                  <div key={i} className="flex items-center gap-2 p-3 bg-muted rounded">
                    <Badge variant={alert.severity === "high" ? "destructive" : "secondary"}>
                      {alert.severity}
                    </Badge>
                    <span>{alert.title}: {alert.description}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}