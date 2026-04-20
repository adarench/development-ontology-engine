import { formatPct, phaseLabel, type Phase } from "../lib";

type Props = {
  phase: Phase;
};

export function BiggestRisk({ phase }: Props) {
  const isOverrun = phase.variance_pct !== null && phase.variance_pct > 0.1;
  const isPartial = phase.expected_cost_status === "PARTIAL";

  const accent = isOverrun
    ? { bar: "bg-red-500", label: "text-red-700" }
    : { bar: "bg-sky-500", label: "text-sky-700" };

  const heading = "Largest flagged variance";
  const sourceLine = isPartial ? "Based on partial cost data" : "Based on full cost data";

  return (
    <div className="mb-5 flex rounded-sm border border-neutral-200 bg-white">
      <div className={`w-1 ${accent.bar}`} aria-hidden />
      <div className="flex-1 px-4 py-3">
        <p className="text-[11px] font-medium uppercase tracking-wider text-neutral-500">
          {heading}
        </p>
        <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="text-lg font-semibold text-neutral-900">
            {phaseLabel(phase)}
          </h3>
          <span className={`text-base font-semibold tabular-nums ${accent.label}`}>
            {formatPct(phase.variance_pct)} vs expected cost
          </span>
        </div>
        <p className="mt-0.5 text-xs text-neutral-500">{sourceLine}</p>
      </div>
    </div>
  );
}
