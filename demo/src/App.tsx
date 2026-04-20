import { useMemo, useState } from "react";
import phasesData from "./data/phases.json";
import type { Phase } from "./lib";
import { classifyLifecycle, deriveStatus } from "./lib";
import { Section } from "./components/Section";
import { PhaseTable } from "./components/PhaseTable";
import { BudgetTable } from "./components/BudgetTable";
import { NoVisibilityList } from "./components/NoVisibilityList";
import { SummaryBar } from "./components/SummaryBar";
import { BiggestRisk } from "./components/BiggestRisk";
import { Switch } from "./components/Switch";

const ALL = phasesData as Phase[];

function sortByVariance(a: Phase, b: Phase): number {
  const va = a.variance_pct;
  const vb = b.variance_pct;
  if (va === null && vb === null) return 0;
  if (va === null) return 1;
  if (vb === null) return -1;
  return vb - va;
}

function sortByBudgetDesc(a: Phase, b: Phase): number {
  return (b.expected_total_cost ?? 0) - (a.expected_total_cost ?? 0);
}

function sortByLabel(a: Phase, b: Phase): number {
  return (
    a.project_name.localeCompare(b.project_name) ||
    a.phase_name.localeCompare(b.phase_name)
  );
}

function pickBiggestRisk(phases: Phase[]): Phase | null {
  const withVariance = phases.filter((p) => p.variance_pct !== null);
  if (withVariance.length === 0) return null;
  const overruns = withVariance.filter((p) => (p.variance_pct ?? 0) > 0.1);
  if (overruns.length > 0) {
    return overruns.reduce((top, p) =>
      (p.variance_pct ?? 0) > (top.variance_pct ?? 0) ? p : top,
    );
  }
  return withVariance.reduce((top, p) =>
    Math.abs(p.variance_pct ?? 0) > Math.abs(top.variance_pct ?? 0) ? p : top,
  );
}

export default function App() {
  const [onlyOverrun, setOnlyOverrun] = useState(false);

  const active = useMemo(
    () => ALL.filter((p) => classifyLifecycle(p) === "active"),
    [],
  );
  const preConstruction = useMemo(
    () =>
      ALL.filter((p) => classifyLifecycle(p) === "pre_construction").sort(
        sortByBudgetDesc,
      ),
    [],
  );
  const futurePipeline = useMemo(
    () =>
      ALL.filter((p) => classifyLifecycle(p) === "future_pipeline").sort(
        sortByLabel,
      ),
    [],
  );

  const activeFull = useMemo(
    () =>
      active
        .filter((p) => p.expected_cost_status === "FULL")
        .sort(sortByVariance),
    [active],
  );
  const activePartial = useMemo(
    () =>
      active
        .filter((p) => p.expected_cost_status === "PARTIAL")
        .sort(sortByVariance),
    [active],
  );
  const activeMissing = useMemo(
    () =>
      active
        .filter((p) => p.expected_cost_status === "NONE")
        .sort((a, b) => (b.actual_cost_total ?? 0) - (a.actual_cost_total ?? 0)),
    [active],
  );

  const overrunCount = useMemo(
    () =>
      active.filter((p) => deriveStatus(p.variance_pct) === "overrun").length,
    [active],
  );

  const allocationCount = useMemo(
    () => ALL.filter((p) => p.budget_source === "flagship").length,
    [],
  );

  const biggestRisk = useMemo(() => pickBiggestRisk(active), [active]);

  const filteredFull = useMemo(() => {
    if (!onlyOverrun) return activeFull;
    return activeFull.filter((p) => deriveStatus(p.variance_pct) === "overrun");
  }, [onlyOverrun, activeFull]);

  const filteredPartial = useMemo(() => {
    if (!onlyOverrun) return activePartial;
    return activePartial.filter(
      (p) => deriveStatus(p.variance_pct) === "overrun",
    );
  }, [onlyOverrun, activePartial]);

  const summaryCards = [
    {
      tone: "sky" as const,
      count: active.length,
      label: "Active phases (with spend)",
    },
    {
      tone: "red" as const,
      count: overrunCount,
      label: "Overruns flagged",
    },
    {
      tone: "amber" as const,
      count: allocationCount,
      label: "Allocation-workbook coverage",
    },
    {
      tone: "neutral" as const,
      count: futurePipeline.length,
      label: "Future pipeline",
    },
  ];

  return (
    <div className="min-h-full bg-neutral-100 text-neutral-900">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <header className="mb-5 flex items-end justify-between gap-6 border-b border-neutral-200 pb-4">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Phase Risk Board</h1>
            <p className="mt-0.5 text-xs text-neutral-500">
              {ALL.length} phases — {active.length} active, {preConstruction.length}{" "}
              pre-construction, {futurePipeline.length} future pipeline
            </p>
          </div>
          <Switch
            checked={onlyOverrun}
            onChange={setOnlyOverrun}
            label="Show only flagged overruns"
          />
        </header>

        <SummaryBar cards={summaryCards} />
        <p className="mb-5 mt-1 text-xs text-neutral-500">
          Variance is only computed against phases that have recorded spend.
          Pre-construction phases carry a budget but no spend yet; future-pipeline
          phases have neither.
        </p>

        {biggestRisk && <BiggestRisk phase={biggestRisk} />}

        <div className="space-y-5">
          <div className="rounded-sm border border-neutral-200 bg-white p-5">
            <Section
              overline="Phases with recorded spend — variance tracking"
              title="Active Phases"
              count={filteredFull.length + filteredPartial.length + (onlyOverrun ? 0 : activeMissing.length)}
              footnote="Negative variance on early phases is expected — horizontal spend trickles in before vertical construction begins."
            >
              <div className="space-y-4">
                <div>
                  <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-neutral-500">
                    Full budget coverage ({filteredFull.length})
                  </div>
                  <PhaseTable
                    phases={filteredFull}
                    emptyLabel={
                      onlyOverrun
                        ? "No overruns in fully tracked phases."
                        : "No phases in this bucket."
                    }
                  />
                </div>
                <div>
                  <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-amber-700">
                    Incomplete budget — read with caution ({filteredPartial.length})
                  </div>
                  <PhaseTable
                    phases={filteredPartial}
                    muted
                    showPartialBadge
                    emptyLabel={
                      onlyOverrun
                        ? "No overruns in the partial-data bucket."
                        : "No phases in this bucket."
                    }
                  />
                </div>
                {!onlyOverrun && activeMissing.length > 0 && (
                  <div>
                    <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-rose-700">
                      Spend recorded but no budget on file ({activeMissing.length})
                    </div>
                    <PhaseTable
                      phases={activeMissing}
                      emptyLabel="No phases in this bucket."
                    />
                  </div>
                )}
              </div>
            </Section>
          </div>

          {!onlyOverrun && (
            <div className="rounded-sm border border-neutral-200 bg-white p-5">
              <Section
                overline="Budget on file, no spend recorded yet"
                title="Pre-Construction Phases"
                count={preConstruction.length}
                footnote="Phases in PLANNED / LAND_ACQUIRED state with an expected budget. Variance isn't meaningful until horizontal or vertical work begins."
              >
                <BudgetTable
                  phases={preConstruction}
                  emptyLabel="No pre-construction phases."
                />
              </Section>
            </div>
          )}

          {!onlyOverrun && (
            <div className="rounded-sm border border-neutral-200 bg-white p-5">
              <Section
                overline="No expected cost on file"
                title="Future Pipeline"
                count={futurePipeline.length}
              >
                <NoVisibilityList phases={futurePipeline} />
              </Section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
