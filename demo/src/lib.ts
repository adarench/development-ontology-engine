export type ExpectedCostStatus = "FULL" | "PARTIAL" | "NONE";

export type BudgetSource = "flagship" | null;

export type Phase = {
  project_name: string;
  phase_name: string;
  lot_count_total: number;
  expected_total_cost: number | null;
  actual_cost_total: number | null;
  variance_pct: number | null;
  expected_cost_status: ExpectedCostStatus;
  phase_state: string | null;
  budget_source?: BudgetSource;
};

export type VarianceStatus = "overrun" | "on_track" | "under_budget";

export type Lifecycle = "active" | "pre_construction" | "future_pipeline";

export const PLANNING_ONLY_PROJECTS: ReadonlySet<string> = new Set([
  "Ammon",
  "Cedar Glen",
  "Eastbridge",
  "Erda",
  "Ironton",
  "Santaquin Estates",
  "Westbridge",
]);

export function classifyLifecycle(p: Phase): Lifecycle {
  const actual = p.actual_cost_total ?? 0;
  if (actual > 0) return "active";
  if (p.expected_cost_status === "FULL" || p.expected_cost_status === "PARTIAL") {
    return "pre_construction";
  }
  return "future_pipeline";
}

export function deriveStatus(variance_pct: number | null): VarianceStatus | null {
  if (variance_pct === null || variance_pct === undefined) return null;
  if (variance_pct > 0.1) return "overrun";
  if (variance_pct < -0.1) return "under_budget";
  return "on_track";
}

const moneyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function formatMoney(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return moneyFmt.format(v);
}

export function formatPct(v: number | null): string {
  if (v === null || v === undefined) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${Math.round(v * 100)}%`;
}

export function phaseLabel(p: Phase): string {
  return `${p.project_name} · ${p.phase_name}`;
}
