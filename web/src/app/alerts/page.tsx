"use client";

import { ArrowLeft, Bell, CheckCircle, Clock, FileText, ShieldAlert } from "lucide-react";
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
import {
	Pagination,
	PaginationContent,
	PaginationItem,
	PaginationLink,
	PaginationNext,
	PaginationPrevious,
} from "@/components/ui/pagination";
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
		setResolveOpen(true);
	};

	const handleResolve = async () => {
		if (!resolveTarget) return;
		setResolving(true);
		try {
			await fetch(`/api/alerts/${resolveTarget.id}`, {
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ resolution_notes: resolveNotes }),
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

	const totalPages = Math.ceil(total / ITEMS_PER_PAGE);

	const stats = {
		total,
		open: alerts.filter((a) => a.status !== "resolved").length,
		resolved: total - alerts.filter((a) => a.status !== "resolved").length,
	};

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
				</div>
				<h1 className="text-2xl font-semibold flex items-center gap-3">
					<Bell className="h-6 w-6" />
					Alert Management
				</h1>
				<p className="text-muted-foreground mt-1">
					Review, filter, and resolve procurement anomaly alerts
				</p>
			</header>

			{/* Stats */}
			<div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
				<Card>
					<CardHeader className="pb-2 flex flex-row items-center gap-3">
						<ShieldAlert className="h-5 w-5 text-muted-foreground" />
						<div>
							<CardDescription className="text-xs uppercase">Total Alerts</CardDescription>
						</div>
					</CardHeader>
					<CardContent>
						<div className="text-3xl font-bold">{stats.total}</div>
					</CardContent>
				</Card>
				<Card>
					<CardHeader className="pb-2 flex flex-row items-center gap-3">
						<Clock className="h-5 w-5 text-amber-500" />
						<div>
							<CardDescription className="text-xs uppercase">Open</CardDescription>
						</div>
					</CardHeader>
					<CardContent>
						<div className="text-3xl font-bold text-amber-500">{stats.open}</div>
					</CardContent>
				</Card>
				<Card>
					<CardHeader className="pb-2 flex flex-row items-center gap-3">
						<CheckCircle className="h-5 w-5 text-green-500" />
						<div>
							<CardDescription className="text-xs uppercase">Resolved</CardDescription>
						</div>
					</CardHeader>
					<CardContent>
						<div className="text-3xl font-bold text-green-500">{stats.resolved}</div>
					</CardContent>
				</Card>
			</div>

			{/* Filters */}
			<Card className="mb-6">
				<CardHeader className="pb-3">
					<CardTitle className="text-sm flex items-center gap-2">
						<FileText className="h-4 w-4" />
						Filters
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="flex flex-wrap items-center gap-4">
						<div>
							<label className="text-xs text-muted-foreground block mb-1">Status</label>
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
							<label className="text-xs text-muted-foreground block mb-1">Severity</label>
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
						<ShieldAlert className="h-4 w-4" />
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
										<TableHead>Created</TableHead>
										<TableHead className="w-[140px]">Actions</TableHead>
									</TableRow>
								</TableHeader>
								<TableBody>
									{alerts.map((a) => (
										<TableRow key={a.id}>
											<TableCell className="font-mono text-xs text-muted-foreground">
												{a.id}
											</TableCell>
											<TableCell
												className="font-medium max-w-[300px] truncate"
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
														<CheckCircle className="h-3 w-3 mr-1" /> Resolved
													</Badge>
												) : (
													<Badge variant="secondary">
														<Clock className="h-3 w-3 mr-1" /> Pending
													</Badge>
												)}
											</TableCell>
											<TableCell className="text-xs text-muted-foreground whitespace-nowrap">
												{formatDate(a.created_at)}
											</TableCell>
											<TableCell>
												<div className="flex gap-1">
													<Button
														variant="ghost"
														size="sm"
														disabled={a.status === "resolved"}
														onClick={() => openResolveDialog(a)}
													>
														<CheckCircle className="h-3 w-3 mr-1" />
														Resolve
													</Button>
												</div>
											</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>

							{/* Resolve Dialog — controlled via page-level state */}
							<Dialog
								open={resolveOpen}
								onOpenChange={(open) => {
									if (!open) {
										setResolveTarget(null);
										setResolveNotes("");
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
											<div>
												<label className="text-sm font-medium">Resolution notes (optional)</label>
												<Input
													placeholder="e.g. Verified with COA, amount was within threshold"
													value={resolveNotes}
													onChange={(e) => setResolveNotes(e.target.value)}
													className="mt-1"
												/>
											</div>
											{resolveTarget.description && (
												<div>
													<label className="text-sm font-medium">Description</label>
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
										<DialogFooter>
											<Button variant="outline" onClick={() => setResolveOpen(false)}>
												Cancel
											</Button>
											<Button onClick={handleResolve} disabled={resolving}>
												{resolving ? "Resolving..." : "Mark as Resolved"}
											</Button>
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
