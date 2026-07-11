"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Severity } from "@/lib/severity";

interface RedFlag {
	flag: string;
	description?: string;
	citation?: string;
	severity?: number | string;
	iiueeu?: string;
	source_agent?: string;
	bidder_name?: string | null;
	missing_doc?: string | null;
}

export function FlagItem({ flag }: { flag: RedFlag }) {
	const tone = Severity.tone(flag.severity);
	const iiueeu = flag.iiueeu && flag.iiueeu !== "n/a" ? flag.iiueeu : null;

	return (
		<Alert variant={tone === "destructive" ? "destructive" : "default"} className="items-start">
			<div className="flex items-start gap-2 w-full">
				<Badge variant={tone === "destructive" ? "destructive" : "secondary"} className="shrink-0">
					{tone === "destructive" ? "HIGH" : (flag.severity?.toString() ?? "?")}
				</Badge>
				<div className="flex-1 min-w-0">
					<AlertTitle className="font-medium flex items-center gap-2">
						<span>{flag.flag}</span>
						{iiueeu && (
							<Badge variant="outline" className="font-mono text-[10px]">
								IIUEEU · {iiueeu}
							</Badge>
						)}
						{flag.source_agent && (
							<Badge variant="ghost" className="text-[10px] uppercase">
								{flag.source_agent}
							</Badge>
						)}
					</AlertTitle>
					<AlertDescription>
						{flag.description}
						{flag.bidder_name && (
							<span className="block text-xs text-muted-foreground mt-1">
								Affected bidder: {flag.bidder_name}
							</span>
						)}
						{flag.missing_doc && (
							<span className="block text-xs text-muted-foreground mt-1">
								Missing document: {flag.missing_doc}
							</span>
						)}
						{flag.citation && flag.citation !== "n/a" && (
							<span className="block text-xs text-muted-foreground mt-1">
								Citation: {flag.citation}
							</span>
						)}
					</AlertDescription>
				</div>
			</div>
		</Alert>
	);
}

export function FlagPanel({
	title,
	flags,
	emptyMessage,
}: {
	title: string;
	flags: RedFlag[];
	emptyMessage: string;
}) {
	return (
		<div>
			<h3 className="text-sm font-medium mb-2">
				{title} {flags.length > 0 ? `(${flags.length})` : ""}
			</h3>
			{flags.length === 0 ? (
				<p className="text-xs text-muted-foreground">{emptyMessage}</p>
			) : (
				<div className="space-y-2">
					{flags.map((f, i) => (
						<FlagItem key={`${f.flag}-${i}`} flag={f} />
					))}
				</div>
			)}
		</div>
	);
}
