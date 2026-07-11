/**
 * Severity helpers used by the analysis dashboard.
 *
 * The backend stores risk scores as 1..5 (with higher = more concerning)
 * but the legacy UI also passes string severities like "high"/"medium".
 * Maps both forms to shadcn Badge / Alert variants.
 */

export type SeverityTone = "destructive" | "secondary" | "outline";

export const Severity = {
	/**
	 * Convert a numeric or string severity to a Badge/Alert variant.
	 * >=4 (or "high"/"critical") -> destructive
	 * 3   (or "medium")           -> secondary
	 * else                        -> outline
	 */
	tone(value: unknown): SeverityTone {
		if (typeof value === "number") {
			if (value >= 4) return "destructive";
			if (value >= 3) return "secondary";
			return "outline";
		}
		if (typeof value === "string") {
			const normalized = value.toLowerCase();
			if (normalized === "high" || normalized === "critical") return "destructive";
			if (normalized === "medium") return "secondary";
			return "outline";
		}
		return "outline";
	},
};
