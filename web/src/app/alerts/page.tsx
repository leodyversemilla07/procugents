"use client";

import {
	ArrowLeft,
	Bell,
	CheckCircle,
	Clock,
	FileText,
	Flag,
	ShieldAlert,
	ThumbsDown,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Empty, EmptyDescription, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Pagination,
	PaginationContent,
	PaginationItem,
	PaginationLink,
	PaginationNext,
	PaginationPrevious,
} from "@/components/ui/pagination";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Severity } from "@/lib/severity";

interface AlertItem {
	id: number;
	title: string;
	description: string;
	level: string;
	severity: string;
	contract_id: string;
	status: string;
	resolution_notes: string | null;
	false_positive: boolean;
	fp_category: string | null;
	created_at: string | null;
	resolved_at: string | null;
}

interface AlertsResponse {
	items: AlertItem[];
	total: number;
	limit: number;
	offset: number;
}

const ITEMS_PER_PAGE = 15;

const FP_CATEGORIES = [
	{ value: "threshold_too_low", label: "Threshold too low (legitimate expense)" },
	{ value: "data_stale", label: "Stale market data" },
	{ value: "incorrect_baseline", label: "Wrong market baseline" },
	{ value: "duplicate_alert", label: "Duplicate alert" },
	{ value: "legitimate_competitive", label: "Legitimate competitive process" },
	{ value: "other", label: "Other" },
] as const;

function formatDate(raw: string | null): string {
	if (!raw) return "—";
	try {
		const d = new Date(raw);
		return d.toLocaleDateString("en-PH", {
			year: "numeric",
			month: "short",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		});
	} catch {
		return raw;
	}
}

export default function AlertsPage() {
	const [alerts, setAlerts] = useState<AlertItem[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [statusFilter, setStatusFilter] = useState<string | null>(null);
	const [severityFilter, setSeverityFilter] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [resolveTarget, setResolveTarget] = useState<AlertItem | null>(null);
	const [resolveNotes, setResolveNotes] = useState("");
	const [resolveOpen, setResolveOpen] = useState(false);
	const [resolveIsFP, setResolveIsFP] = useState(false);
	const [resolveFPCategory, setResolveFPCategory] = useState<string | null>(null);
	const [resolving, setResolving] = useState(false);

	const fetchAlerts = useCallback(async () => {
		setLoading(true);
		try {
			const params = new URLSearchParams();
			params.set("limit", String(ITEMS_PER_PAGE));
			params.set("offset", String((page - 1) * ITEMS_PER_PAGE));
			if (statusFilter) params.set("status", statusFilter);
			if (severityFilter) params.set("severity", severityFilter);

			const res = await fetch(`/api/alerts?${params.toString()}`);
			const data: AlertsResponse = await res.json();
			setAlerts(data.items);
			setTotal(data.total);
		} catch (error) {
			console.error(error);
		} finally {
			setLoading(false);
		}
	}, [page, statusFilter, severityFilter]);

	useEffect(() => {
		void fetchAlerts();
	}, [fetchAlerts]);

	const openResolveDialog = (alert: AlertItem) => {
		setResolveTarget(alert);
		setResolveNotes(alert.resolution_notes || "");
		setResolveIsFP(false);
		setResolveFPCategory(null);
		setResolveOpen(true);
	};

	const handleResolve = async () => {
		if (!resolveTarget) return;
		setResolving(true);
		try {
			await fetch(`/api/alerts/${resolveTarget.id}`, {
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					resolution_notes: resolveNotes,
					false_positive: resolveIsFP,
					fp_category: resolveIsFP ? resolveFPCategory || "other" : null,
				}),
			});
			setResolveOpen(false);
			setResolveTarget(null);
			void fetchAlerts();
		} catch (error) {
			console.error(error);
		} finally {
			setResolving(false);
		}
	};

	const fpCount = alerts.filter((a) => a.false_positive).length;
	const totalPages = Math.ceil(total / ITEMS_PER_PAGE);

	return (
		<div className="min-h-screen bg-background p-6">
			{/* Header */}
			<header className="mb-6">
				<div className="flex items-center gap-3 mb-2">
					<Link href="/">
						<Button variant="ghost" size="sm">
							<ArrowLeft className="size-4 mr-1" /> Dashboard
						</Button>
					</Link>
				</div>
				<h1 className="text-2xl font-semibold flex items-center gap-3">
					<Bell className="size-6" />
					Alert Management
				</h1>
				<p className="text-muted-foreground mt-1">
					Review, filter, resolve, and mark false-positive procurement anomaly alerts
				</p>
			</header>

			{/* Stats */}
			<div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
				<Card>
					<CardHeader className="pb-2 flex flex-row items-center gap-3">
						<ShieldAlert className="size-5 text-muted-foreground" />
						<div>
							<CardDescription className="text-xs uppercase">Total Alerts</CardDescription>
						</div>
					</CardHeader>
					<CardContent>
						<div className="text-3xl font-bold">{total}</div>
					</CardContent>
				</Card>
				<Card>
					<CardHeader className="pb-2 flex flex-row items-center gap-3">
						<Clock className="size-5 text-amber-500" />
						<div>
							<CardDescription className="text-xs uppercase">Open</CardDescription>
						</div>
					</CardHeader>
					<CardContent>
						<div className="text-3xl font-bold text-amber-500">
							{total - alerts.filter((a) => a.status === "resolved").length}
						</div>
					</CardContent>
				</Card>
				<Card>
					<CardHeader className="pb-2 flex flex-row items-center gap-3">
						<CheckCircle className="size-5 text-green-500" />
						<div>
							<CardDescription className="text-xs uppercase">Resolved</CardDescription>
						</div>
					</CardHeader>
					<CardContent>
						<div className="text-3xl font-bold text-green-500">
							{alerts.filter((a) => a.status === "resolved" && !a.false_positive).length}
						</div>
					</CardContent>
				</Card>
				<Card>
					<CardHeader className="pb-2 flex flex-row items-center gap-3">
						<ThumbsDown className="size-5 text-orange-500" />
						<div>
							<CardDescription className="text-xs uppercase">False Positives</CardDescription>
						</div>
					</CardHeader>
					<CardContent>
						<div className="text-3xl font-bold text-orange-500">
							{fpCount}
							{total > 0 && (
								<span className="text-sm text-muted-foreground ml-2 font-normal">
									({((fpCount / total) * 100).toFixed(1)}%)
								</span>
							)}
						</div>
					</CardContent>
				</Card>
			</div>

			{/* Filters */}
			<Card className="mb-6">
				<CardHeader className="pb-3">
					<CardTitle className="text-sm flex items-center gap-2">
						<FileText className="size-4" />
						Filters
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="flex flex-wrap items-center gap-4">
						<div>
							<Label className="text-xs text-muted-foreground block mb-1">Status</Label>
							<Tabs
								value={statusFilter ?? ""}
								onValueChange={(v) => {
									setStatusFilter(v || null);
									setPage(1);
								}}
							>
								<TabsList>
									<TabsTrigger value="">All</TabsTrigger>
									<TabsTrigger value="pending">Pending</TabsTrigger>
									<TabsTrigger value="resolved">Resolved</TabsTrigger>
								</TabsList>
							</Tabs>
						</div>
						<div>
							<Label className="text-xs text-muted-foreground block mb-1">Severity</Label>
							<div className="flex gap-1">
								{[
									{ value: null, label: "All" },
									{ value: "high", label: "High" },
									{ value: "medium", label: "Medium" },
									{ value: "low", label: "Low" },
								].map((opt) => (
									<Badge
										key={opt.label}
										variant={severityFilter === opt.value ? "default" : "outline"}
										className="cursor-pointer"
										onClick={() => {
											setSeverityFilter(opt.value);
											setPage(1);
										}}
									>
										{opt.label}
									</Badge>
								))}
							</div>
						</div>
					</div>
				</CardContent>
			</Card>

			{/* Alerts Table */}
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<ShieldAlert className="size-4" />
						Alerts
					</CardTitle>
					<CardDescription>
						{total} alert{total !== 1 ? "s" : ""}
						{statusFilter ? ` (${statusFilter})` : ""}
						{severityFilter ? ` / ${severityFilter} severity` : ""}
					</CardDescription>
				</CardHeader>
				<CardContent>
					{loading ? (
						<div className="text-center py-12 text-muted-foreground">Loading alerts...</div>
					) : alerts.length === 0 ? (
						<Empty className="min-h-[300px]">
							<EmptyTitle>No alerts found</EmptyTitle>
							<EmptyDescription>
								{statusFilter || severityFilter
									? "Try changing your filters above."
									: "No alerts have been created yet. Run an analysis to generate alerts."}
							</EmptyDescription>
						</Empty>
					) : (
						<>
							<Table>
								<TableHeader>
									<TableRow>
										<TableHead className="w-[60px]">ID</TableHead>
										<TableHead>Title</TableHead>
										<TableHead>Severity</TableHead>
										<TableHead>Contract</TableHead>
										<TableHead>Status</TableHead>
										<TableHead>FP?</TableHead>
										<TableHead>Created</TableHead>
										<TableHead className="w-[160px]">Actions</TableHead>
									</TableRow>
								</TableHeader>
								<TableBody>
									{alerts.map((a) => (
										<TableRow key={a.id}>
											<TableCell className="font-mono text-xs text-muted-foreground">
												{a.id}
											</TableCell>
											<TableCell
												className="font-medium max-w-[280px] truncate"
												title={a.description || a.title}
											>
												{a.title}
											</TableCell>
											<TableCell>
												<Badge variant={Severity.tone(a.severity)}>{a.severity}</Badge>
											</TableCell>
											<TableCell>
												{a.contract_id ? (
													<span className="font-mono text-sm">{a.contract_id}</span>
												) : (
													<span className="text-muted-foreground">—</span>
												)}
											</TableCell>
											<TableCell>
												{a.status === "resolved" ? (
													<Badge variant="outline" className="text-green-500 border-green-500/30">
														<CheckCircle data-icon /> Resolved
													</Badge>
												) : (
													<Badge variant="secondary">
														<Clock data-icon /> Pending
													</Badge>
												)}
											</TableCell>
											<TableCell>
												{a.false_positive ? (
													<Badge variant="outline" className="text-orange-500 border-orange-500/30">
														<ThumbsDown data-icon /> FP
													</Badge>
												) : (
													<span className="text-muted-foreground text-xs">—</span>
												)}
											</TableCell>
											<TableCell className="text-xs text-muted-foreground whitespace-nowrap">
												{formatDate(a.created_at)}
											</TableCell>
											<TableCell>
												{/* Only show Resolve button for non-resolved alerts */}
												{a.status !== "resolved" && (
													<Button variant="ghost" size="sm" onClick={() => openResolveDialog(a)}>
														<CheckCircle data-icon />
														Resolve
													</Button>
												)}
											</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>

							{/* Resolve / Mark-False-Positive Dialog */}
							<Dialog
								open={resolveOpen}
								onOpenChange={(open) => {
									if (!open) {
										setResolveTarget(null);
										setResolveNotes("");
										setResolveIsFP(false);
										setResolveFPCategory(null);
									}
									setResolveOpen(open);
								}}
							>
								{resolveTarget && (
									<DialogContent>
										<DialogHeader>
											<DialogTitle>Resolve Alert #{resolveTarget.id}</DialogTitle>
											<DialogDescription>{resolveTarget.title}</DialogDescription>
										</DialogHeader>
										<div className="space-y-4 py-4">
											{/* Mark as false positive toggle */}
											<div className="flex items-center gap-2 p-3 bg-muted rounded">
												<Flag className="size-4 text-orange-500 shrink-0" />
												<div className="flex items-center gap-2">
													<button
														type="button"
														className={`text-sm font-medium cursor-pointer px-2 py-0.5 rounded transition-colors ${
															resolveIsFP
																? "bg-orange-500/20 text-orange-500"
																: "text-muted-foreground hover:text-foreground"
														}`}
														onClick={() => setResolveIsFP(!resolveIsFP)}
													>
														{resolveIsFP ? "✓ False Positive" : "Mark as False Positive"}
													</button>
												</div>
											</div>

											{/* FP category selector */}
											{resolveIsFP && (
												<div>
													<Label className="text-sm font-medium">Reason category</Label>
													<Select value={resolveFPCategory} onValueChange={setResolveFPCategory}>
														<SelectTrigger className="w-full mt-1">
															<SelectValue placeholder="Select a reason..." />
														</SelectTrigger>
														<SelectContent>
															<SelectGroup>
																{FP_CATEGORIES.map((cat) => (
																	<SelectItem key={cat.value} value={cat.value}>
																		{cat.label}
																	</SelectItem>
																))}
															</SelectGroup>
														</SelectContent>
													</Select>
												</div>
											)}

											{/* Resolution notes */}
											<div>
												<Label className="text-sm font-medium">Resolution notes (optional)</Label>
												<Input
													placeholder={
														resolveIsFP
															? "e.g. Verified with end-user, amount reflects actual market rate"
															: "e.g. Verified with COA, amount was within threshold"
													}
													value={resolveNotes}
													onChange={(e) => setResolveNotes(e.target.value)}
													className="mt-1"
												/>
											</div>

											{/* Alert details */}
											{resolveTarget.description && (
												<div>
													<Label className="text-sm font-medium">Description</Label>
													<p className="text-sm text-muted-foreground mt-1">
														{resolveTarget.description}
													</p>
												</div>
											)}
											<div className="grid grid-cols-2 gap-4 text-sm">
												<div>
													<span className="text-muted-foreground">Contract:</span>{" "}
													<span className="font-mono">{resolveTarget.contract_id || "—"}</span>
												</div>
												<div>
													<span className="text-muted-foreground">Severity:</span>{" "}
													<Badge variant={Severity.tone(resolveTarget.severity)} className="ml-1">
														{resolveTarget.severity}
													</Badge>
												</div>
												<div>
													<span className="text-muted-foreground">Created:</span>{" "}
													{formatDate(resolveTarget.created_at)}
												</div>
											</div>
										</div>
										<DialogFooter className="gap-2">
											<Button variant="outline" onClick={() => setResolveOpen(false)}>
												Cancel
											</Button>
											{resolveIsFP ? (
												<Button
													variant="secondary"
													className="bg-orange-500/20 text-orange-500 hover:bg-orange-500/30"
													onClick={handleResolve}
													disabled={resolving || !resolveFPCategory}
												>
													{resolving ? "Saving..." : "Dismiss as False Positive"}
												</Button>
											) : (
												<Button onClick={handleResolve} disabled={resolving}>
													{resolving ? "Resolving..." : "Mark as Resolved"}
												</Button>
											)}
										</DialogFooter>
									</DialogContent>
								)}
							</Dialog>

							{/* Pagination */}
							{totalPages > 1 && (
								<div className="mt-4">
									<Pagination>
										<PaginationContent>
											<PaginationItem>
												<PaginationPrevious
													onClick={() => setPage((p) => Math.max(1, p - 1))}
													className={
														page === 1 ? "pointer-events-none opacity-50" : "cursor-pointer"
													}
												/>
											</PaginationItem>
											{Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
												const p = i + 1;
												return (
													<PaginationItem key={p}>
														<PaginationLink onClick={() => setPage(p)} isActive={page === p}>
															{p}
														</PaginationLink>
													</PaginationItem>
												);
											})}
											<PaginationItem>
												<PaginationNext
													onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
													className={
														page === totalPages
															? "pointer-events-none opacity-50"
															: "cursor-pointer"
													}
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
	);
}
