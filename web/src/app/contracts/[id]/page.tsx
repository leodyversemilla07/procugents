"use client";

import {
	AlertTriangle,
	ArrowLeft,
	Building2,
	CheckCircle2,
	ClipboardList,
	FileCheck,
	FileText,
	ShieldAlert,
	TrendingUp,
	Users,
	XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { FlagPanel } from "@/components/flag-panel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface FlagItem {
	flag: string;
	description?: string;
	severity?: number | string;
	iiueeu?: string;
	source_agent?: string;
	bidder_name?: string | null;
	missing_doc?: string | null;
	citation?: string;
}

interface ContractDetail {
	contract_id: string;
	contract_description: string;
	contract_amount: number;
	agency: string;
	status: string;
	final_risk_score: number;
	alert_triggered: boolean;
	alert_report: string | null;
	legal_findings: {
		threshold_compliant: boolean;
		required_process: string;
		threshold: number;
		violations: string[];
		law: string;
	};
	price_findings: {
		flag: string;
		reason: string;
		baseline: number | null;
		inflation_threshold?: number | null;
		amount: number;
	};
	bid_findings: Record<string, unknown>;
	bid_flags: FlagItem[];
	bid_risk_score: number;
	doc_findings: Record<string, unknown>;
	doc_flags: FlagItem[];
	doc_risk_score: number;
	all_flags: FlagItem[];
	all_citations: string[];
	anomalies: { type: string; severity: string; description: string }[];
	alerts: { title: string; severity: string; description: string }[];
	created_at: string;
}

export default function ContractDetailPage() {
	const params = useParams();
	const id = params?.id as string;
	const [contract, setContract] = useState<ContractDetail | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");

	useEffect(() => {
		if (!id) return;
		fetch(`/api/analyses/${id}`)
			.then((res) => res.json())
			.then((data) => {
				setContract(data);
				setLoading(false);
			})
			.catch((err) => {
				setError(String(err));
				setLoading(false);
			});
	}, [id]);

	if (loading) {
		return (
			<div className="min-h-screen bg-background p-6">
				<div className="animate-pulse space-y-4">
					<div className="h-8 w-32 bg-muted rounded" />
					<div className="h-64 bg-muted rounded" />
				</div>
			</div>
		);
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
		);
	}

	const anomalies = contract.anomalies || [];
	const hasAnomalies = anomalies.length > 0;
	const allFlags = contract.all_flags || [];
	const totalFlags = allFlags.length;

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
					<div className="flex items-center justify-between flex-wrap gap-2">
						<div>
							<CardTitle className="text-xl flex items-center gap-2">
								{hasAnomalies && <ShieldAlert className="h-5 w-5 text-destructive" />}
								{contract.contract_id}
							</CardTitle>
							<CardDescription>{contract.contract_description}</CardDescription>
						</div>
						<div className="flex items-center gap-2">
							<Badge variant={contract.alert_triggered ? "destructive" : "secondary"}>
								{contract.alert_triggered ? "Alert Triggered" : "Clean"}
							</Badge>
							<Badge variant="outline" className="font-mono">
								俘获 Risk {contract.final_risk_score || 1}/5
							</Badge>
						</div>
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

			{/* Tabs */}
			<Tabs defaultValue="overview" className="space-y-6">
				<TabsList className="w-full">
					<TabsTrigger value="overview" className="flex-1">
						Overview
					</TabsTrigger>
					<TabsTrigger value="legal" className="flex-1">
						Legal
					</TabsTrigger>
					<TabsTrigger value="price" className="flex-1">
						Price
					</TabsTrigger>
					<TabsTrigger value="bid" className="flex-1">
						Bid
					</TabsTrigger>
					<TabsTrigger value="doc" className="flex-1">
						Doc
					</TabsTrigger>
					{contract.alert_report && (
						<TabsTrigger value="coa" className="flex-1">
							COA Report
						</TabsTrigger>
					)}
				</TabsList>

				{/* Overview */}
				<TabsContent value="overview" className="space-y-6">
					<Card>
						<CardHeader>
							<CardTitle className="text-base flex items-center gap-2">
								<ClipboardList className="h-4 w-4" /> All Flags
								{totalFlags > 0 && <Badge variant="destructive">{totalFlags}</Badge>}
							</CardTitle>
						</CardHeader>
						<CardContent>
							{totalFlags === 0 ? (
								<Alert className="bg-green-500/10 border-green-500/20">
									<CheckCircle2 className="h-4 w-4 text-green-500" />
									<AlertTitle className="text-green-500">No Flags Detected</AlertTitle>
									<AlertDescription>
										This procurement passed all automated checks with no anomalies.
									</AlertDescription>
								</Alert>
							) : (
								<div className="space-y-2">
									<FlagPanel title="" flags={allFlags} emptyMessage="" />
								</div>
							)}
						</CardContent>
					</Card>

					{hasAnomalies && (
						<Card>
							<CardHeader>
								<CardTitle className="text-base">Anomalies ({anomalies.length})</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="space-y-3">
									{anomalies.map((anomaly, i) => (
										<Alert
											key={i}
											variant={anomaly.severity === "high" ? "destructive" : "default"}
										>
											<Badge
												variant={anomaly.severity === "high" ? "destructive" : "secondary"}
												className="mr-2"
											>
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

					{contract.alerts && contract.alerts.length > 0 && (
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
											<span>
												{alert.title}: {alert.description}
											</span>
										</div>
									))}
								</div>
							</CardContent>
						</Card>
					)}
				</TabsContent>

				{/* Legal */}
				<TabsContent value="legal">
					<Card>
						<CardHeader>
							<CardTitle className="text-base flex items-center gap-2">
								<FileText className="h-4 w-4" /> Legal Compliance (RA 12009)
							</CardTitle>
						</CardHeader>
						<CardContent className="space-y-4">
							{contract.legal_findings?.threshold_compliant ? (
								<Alert className="bg-green-500/10 border-green-500/20">
									<CheckCircle2 className="h-4 w-4 text-green-500" />
									<AlertTitle className="text-green-500">Compliant</AlertTitle>
									<AlertDescription>{contract.legal_findings?.required_process}</AlertDescription>
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
							<p className="text-sm text-muted-foreground">
								SVP Threshold: PHP {contract.legal_findings?.threshold?.toLocaleString()}
							</p>
						</CardContent>
					</Card>
				</TabsContent>

				{/* Price */}
				<TabsContent value="price">
					<Card>
						<CardHeader>
							<CardTitle className="text-base flex items-center gap-2">
								<TrendingUp className="h-4 w-4" /> Price Analysis
							</CardTitle>
						</CardHeader>
						<CardContent className="space-y-4">
							{contract.price_findings?.flag === "normal" ? (
								<Alert className="bg-green-500/10 border-green-500/20">
									<CheckCircle2 className="h-4 w-4 text-green-500" />
									<AlertTitle className="text-green-500">Normal Price</AlertTitle>
									<AlertDescription>Within market baseline</AlertDescription>
								</Alert>
							) : contract.price_findings?.flag === "potential_inflation" ? (
								<Alert variant="destructive">
									<AlertTriangle className="h-4 w-4" />
									<AlertTitle>Potential Inflation</AlertTitle>
									<AlertDescription>{contract.price_findings?.reason}</AlertDescription>
								</Alert>
							) : (
								<Alert>
									<AlertTriangle className="h-4 w-4" />
									<AlertTitle>Market Data Unavailable</AlertTitle>
									<AlertDescription>
										{contract.price_findings?.reason ||
											"No market baseline available for comparison"}
									</AlertDescription>
								</Alert>
							)}
							<p className="text-sm text-muted-foreground">
								Baseline: PHP {contract.price_findings?.baseline?.toLocaleString()}
							</p>
						</CardContent>
					</Card>
				</TabsContent>

				{/* Bid */}
				<TabsContent value="bid">
					<Card className="mb-6">
						<CardHeader>
							<CardTitle className="text-base flex items-center gap-2">
								<Users className="h-4 w-4" /> Bid Analysis
							</CardTitle>
						</CardHeader>
						<CardContent>
							<FlagPanel
								title="Bid Flags"
								flags={contract.bid_flags || []}
								emptyMessage="No bid irregularities detected."
							/>
						</CardContent>
					</Card>
				</TabsContent>

				{/* Doc */}
				<TabsContent value="doc">
					<Card className="mb-6">
						<CardHeader>
							<CardTitle className="text-base flex items-center gap-2">
								<FileCheck className="h-4 w-4" /> Document Compliance
							</CardTitle>
						</CardHeader>
						<CardContent>
							<FlagPanel
								title="Missing Documents"
								flags={contract.doc_flags || []}
								emptyMessage="All mandatory documents are present."
							/>
						</CardContent>
					</Card>
				</TabsContent>

				{/* COA Report */}
				{contract.alert_report && (
					<TabsContent value="coa">
						<Card>
							<CardHeader>
								<CardTitle>COA Disallowance Report</CardTitle>
							</CardHeader>
							<CardContent>
								<pre className="whitespace-pre-wrap text-sm font-mono bg-muted p-4 rounded-lg overflow-auto">
									{contract.alert_report}
								</pre>
							</CardContent>
						</Card>
					</TabsContent>
				)}
			</Tabs>
		</div>
	);
}
