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
import { Separator } from "@/components/ui/separator";

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

// Raw contract detail from the API — all fields optional to handle
// partial / in-flight records.
interface ContractDetail {
	contract_id: string;
	contract_description: string;
	contract_amount: number;
	agency: string;
	source?: string;
	status: string;
	final_risk_score: number;
	alert_triggered: boolean;
	alert_report: string | null;
	legal_findings: Record<string, unknown> | null;
	price_findings: Record<string, unknown> | null;
	scraping_results: Record<string, unknown> | null;
	llm_analysis: Record<string, unknown> | null;
	bid_findings: Record<string, unknown> | null;
	bid_flags: FlagItem[];
	bid_risk_score: number;
	doc_findings: Record<string, unknown> | null;
	doc_flags: FlagItem[];
	doc_risk_score: number;
	all_flags: FlagItem[];
	all_citations: string[];
	anomalies: { type: string; severity: string; description: string }[];
	alerts: { title: string; severity: string; description: string }[];
	created_at: string;
}

function RawJson({ data }: { data: unknown }) {
	const [expanded, setExpanded] = useState(false);
	return (
		<Card>
			<CardHeader>
				<CardTitle className="text-base flex items-center gap-2">
					<FileText className="h-4 w-4" /> Raw API Response
					<Button
						variant="ghost"
						size="sm"
						onClick={() => setExpanded(!expanded)}
						className="ml-auto"
					>
						{expanded ? "Collapse" : "Expand"}
					</Button>
				</CardTitle>
			</CardHeader>
			{expanded && (
				<CardContent>
					<pre className="whitespace-pre-wrap text-xs font-mono bg-muted p-4 rounded-lg overflow-auto max-h-[600px]">
						{JSON.stringify(data, null, 2)}
					</pre>
				</CardContent>
			)}
		</Card>
	);
}

function SectionCard({
	title,
	icon,
	children,
}: {
	title: string;
	icon: React.ReactNode;
	children: React.ReactNode;
}) {
	return (
		<Card>
			<CardHeader>
				<CardTitle className="text-base flex items-center gap-2">
					{icon}
					{title}
				</CardTitle>
			</CardHeader>
			<CardContent>{children}</CardContent>
		</Card>
	);
}

function keyValue(label: string, value: unknown): string {
	if (value === null || value === undefined) return "—";
	if (typeof value === "boolean") return value ? "Yes" : "No";
	if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
	if (typeof value === "object") return JSON.stringify(value);
	return String(value);
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
	const allFlags = contract.all_flags || [];
	const totalFlags = allFlags.length;

	return (
		<div className="min-h-screen bg-background p-6 space-y-6">
			{/* Back link */}
			<Link href="/">
				<Button variant="ghost" className="mb-4">
					<ArrowLeft className="h-4 w-4 mr-2" /> Back to Dashboard
				</Button>
			</Link>

			{/* Header card — always visible */}
			<Card>
				<CardHeader>
					<div className="flex items-center justify-between flex-wrap gap-2">
						<div>
							<CardTitle className="text-xl flex items-center gap-2">
								{contract.alert_triggered && <ShieldAlert className="h-5 w-5 text-destructive" />}
								{contract.contract_id}
							</CardTitle>
							<CardDescription>{contract.contract_description}</CardDescription>
						</div>
						<div className="flex items-center gap-2">
							<Badge variant={contract.alert_triggered ? "destructive" : "secondary"}>
								{contract.alert_triggered ? "Alert Triggered" : "Clean"}
							</Badge>
							<Badge variant="outline" className="font-mono">
								Risk {contract.final_risk_score || 1}/5
							</Badge>
						</div>
					</div>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
						<div>
							<span className="text-muted-foreground">Amount</span>
							<p className="text-2xl font-bold">
								PHP {contract.contract_amount?.toLocaleString() ?? "—"}
							</p>
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
							<p className="text-sm">
								{contract.created_at ? new Date(contract.created_at).toLocaleString() : "—"}
							</p>
						</div>
					</div>
				</CardContent>
			</Card>

			{/* All Flags section */}
			<SectionCard title="All Flags" icon={<ClipboardList className="h-4 w-4" />}>
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
			</SectionCard>

			{/* Citations */}
			{contract.all_citations && contract.all_citations.length > 0 && (
				<SectionCard title="Citations" icon={<FileText className="h-4 w-4" />}>
					<ul className="list-disc list-inside space-y-1 text-sm">
						{contract.all_citations.map((c, i) => (
							<li key={i} className="font-mono text-xs">
								{c}
							</li>
						))}
					</ul>
				</SectionCard>
			)}

			{/* Anomalies */}
			{anomalies.length > 0 && (
				<SectionCard
					title={`Anomalies (${anomalies.length})`}
					icon={<AlertTriangle className="h-4 w-4" />}
				>
					<div className="space-y-3">
						{anomalies.map((a, i) => (
							<Alert key={i} variant={a.severity === "high" ? "destructive" : "default"}>
								<Badge
									variant={a.severity === "high" ? "destructive" : "secondary"}
									className="mr-2"
								>
									{a.severity}
								</Badge>
								<AlertTitle>{a.type}</AlertTitle>
								<AlertDescription>{a.description}</AlertDescription>
							</Alert>
						))}
					</div>
				</SectionCard>
			)}

			{/* Alerts */}
			{contract.alerts && contract.alerts.length > 0 && (
				<SectionCard
					title={`Alerts Created (${contract.alerts.length})`}
					icon={<ShieldAlert className="h-4 w-4" />}
				>
					<div className="space-y-2">
						{contract.alerts.map((a, i) => (
							<div key={i} className="flex items-center gap-2 p-3 bg-muted rounded">
								<Badge variant={a.severity === "high" ? "destructive" : "secondary"}>
									{a.severity}
								</Badge>
								<span>
									{a.title}: {a.description}
								</span>
							</div>
						))}
					</div>
				</SectionCard>
			)}

			<Separator />

			{/* Agent findings — flat, no tabs */}
			<h2 className="text-lg font-semibold">Agent Findings</h2>

			{/* Legal */}
			<SectionCard title="Legal (RA 12009)" icon={<FileText className="h-4 w-4" />}>
				{contract.legal_findings && Object.keys(contract.legal_findings).length > 0 ? (
					<div className="space-y-4">
						{contract.legal_findings.threshold_compliant === false ? (
							<Alert variant="destructive">
								<XCircle className="h-4 w-4" />
								<AlertTitle>Violations Detected</AlertTitle>
								<AlertDescription>
									{Array.isArray(contract.legal_findings.violations)
										? contract.legal_findings.violations.join(", ")
										: "SVP threshold exceeded"}
								</AlertDescription>
							</Alert>
						) : (
							<Alert className="bg-green-500/10 border-green-500/20">
								<CheckCircle2 className="h-4 w-4 text-green-500" />
								<AlertTitle className="text-green-500">Compliant</AlertTitle>
								<AlertDescription>
									{String(contract.legal_findings.required_process ?? "")}
								</AlertDescription>
							</Alert>
						)}
						<div className="grid grid-cols-2 gap-4 text-sm">
							<div>
								<span className="text-muted-foreground">Threshold Compliant</span>
								<p className="font-medium">
									{keyValue("", contract.legal_findings.threshold_compliant)}
								</p>
							</div>
							<div>
								<span className="text-muted-foreground">Required Process</span>
								<p className="font-medium">
									{keyValue("", contract.legal_findings.required_process)}
								</p>
							</div>
							<div>
								<span className="text-muted-foreground">SVP Threshold</span>
								<p className="font-medium">
									PHP {Number(contract.legal_findings.threshold ?? 0).toLocaleString()}
								</p>
							</div>
							<div>
								<span className="text-muted-foreground">Law</span>
								<p className="font-medium">{keyValue("", contract.legal_findings.law)}</p>
							</div>
						</div>
					</div>
				) : (
					<p className="text-sm text-muted-foreground">
						Legal check not completed or data unavailable.
					</p>
				)}
			</SectionCard>

			{/* Price */}
			<SectionCard title="Price Analysis" icon={<TrendingUp className="h-4 w-4" />}>
				{contract.price_findings && Object.keys(contract.price_findings).length > 0 ? (
					<div className="space-y-4">
						{contract.price_findings.flag === "normal" ? (
							<Alert className="bg-green-500/10 border-green-500/20">
								<CheckCircle2 className="h-4 w-4 text-green-500" />
								<AlertTitle className="text-green-500">Normal Price</AlertTitle>
							</Alert>
						) : contract.price_findings.flag === "potential_inflation" ? (
							<Alert variant="destructive">
								<AlertTriangle className="h-4 w-4" />
								<AlertTitle>Potential Inflation</AlertTitle>
								<AlertDescription>{keyValue("", contract.price_findings.reason)}</AlertDescription>
							</Alert>
						) : (
							<Alert>
								<AlertTriangle className="h-4 w-4" />
								<AlertTitle>Market Data Unavailable</AlertTitle>
								<AlertDescription>
									{keyValue("", contract.price_findings.reason || "No market baseline")}
								</AlertDescription>
							</Alert>
						)}
						<div className="grid grid-cols-2 gap-4 text-sm">
							{Object.entries(contract.price_findings).map(([k, v]) => (
								<div key={k}>
									<span className="text-muted-foreground">{k}</span>
									<p className="font-medium">
										{k === "amount" || k === "baseline" || k === "inflation_threshold"
											? `PHP ${Number(v ?? 0).toLocaleString()}`
											: keyValue(k, v)}
									</p>
								</div>
							))}
						</div>
					</div>
				) : (
					<p className="text-sm text-muted-foreground">
						Price analysis not completed or data unavailable.
					</p>
				)}
			</SectionCard>

			{/* Scraping */}
			{contract.scraping_results && Object.keys(contract.scraping_results).length > 0 && (
				<SectionCard title="PhilGEPS Scraping" icon={<FileText className="h-4 w-4" />}>
					<pre className="text-xs font-mono bg-muted p-3 rounded overflow-auto max-h-48">
						{JSON.stringify(contract.scraping_results, null, 2)}
					</pre>
				</SectionCard>
			)}

			{/* Bid */}
			<SectionCard title="Bid Analysis" icon={<Users className="h-4 w-4" />}>
				{contract.bid_findings && Object.keys(contract.bid_findings).length > 0 && (
					<div className="mb-4">
						<pre className="text-xs font-mono bg-muted p-3 rounded overflow-auto max-h-40">
							{JSON.stringify(contract.bid_findings, null, 2)}
						</pre>
					</div>
				)}
				<FlagPanel
					title="Bid Flags"
					flags={contract.bid_flags || []}
					emptyMessage="No bid irregularities detected."
				/>
				<p className="text-xs text-muted-foreground mt-2">
					Bid Risk Score: {contract.bid_risk_score ?? 1}/5
				</p>
			</SectionCard>

			{/* Doc */}
			<SectionCard title="Document Compliance" icon={<FileCheck className="h-4 w-4" />}>
				{contract.doc_findings && Object.keys(contract.doc_findings).length > 0 && (
					<div className="mb-4">
						<pre className="text-xs font-mono bg-muted p-3 rounded overflow-auto max-h-40">
							{JSON.stringify(contract.doc_findings, null, 2)}
						</pre>
					</div>
				)}
				<FlagPanel
					title="Document Flags"
					flags={contract.doc_flags || []}
					emptyMessage="All mandatory documents are present."
				/>
				<p className="text-xs text-muted-foreground mt-2">
					Doc Risk Score: {contract.doc_risk_score ?? 1}/5
				</p>
			</SectionCard>

			{/* LLM */}
			{contract.llm_analysis && Object.keys(contract.llm_analysis).length > 0 && (
				<SectionCard title="LLM Analysis" icon={<FileText className="h-4 w-4" />}>
					<pre className="text-xs font-mono bg-muted p-3 rounded overflow-auto max-h-48">
						{JSON.stringify(contract.llm_analysis, null, 2)}
					</pre>
				</SectionCard>
			)}

			{/* COA Report */}
			{contract.alert_report && (
				<SectionCard title="COA Disallowance Report" icon={<ShieldAlert className="h-4 w-4" />}>
					<pre className="whitespace-pre-wrap text-sm font-mono bg-muted p-4 rounded-lg overflow-auto">
						{contract.alert_report}
					</pre>
				</SectionCard>
			)}

			{/* Raw JSON dump at the bottom */}
			<RawJson data={contract} />

			{/* Footer */}
			<p className="text-xs text-muted-foreground text-center pb-4">
				Contract #{id} · {contract.contract_id} · API data as of page load
			</p>
		</div>
	);
}
