import { deriveStatus, formatMoney, formatPct, phaseLabel, type Phase } from "../lib";
import { StatusBadge } from "./StatusBadge";

type Props = {
  phases: Phase[];
  muted?: boolean;
  showPartialBadge?: boolean;
  emptyLabel?: string;
};

export function PhaseTable({ phases, muted = false, showPartialBadge = false, emptyLabel }: Props) {
  if (phases.length === 0) {
    return (
      <div className="rounded-sm border border-dashed border-neutral-200 px-4 py-5 text-sm text-neutral-500">
        {emptyLabel ?? "No phases match."}
      </div>
    );
  }

  const rowOpacity = muted ? "opacity-75" : "";

  return (
    <div className="overflow-hidden rounded-sm border border-neutral-200">
      <table className="w-full text-sm">
        <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wider text-neutral-500">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Phase</th>
            <th className="px-3 py-2 text-right font-medium">Budget</th>
            <th className="px-3 py-2 text-right font-medium">Spent</th>
            <th className="border-l border-neutral-200 px-3 py-2 text-right font-medium">
              Variance
            </th>
            <th className="px-3 py-2 text-left font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {phases.map((p) => {
            const status = deriveStatus(p.variance_pct);
            const v = p.variance_pct;
            const vColor =
              v === null
                ? "text-neutral-400"
                : v > 0.1
                  ? "text-red-700"
                  : v < -0.1
                    ? "text-sky-700"
                    : "text-emerald-700";
            return (
              <tr
                key={`${p.project_name}::${p.phase_name}`}
                className={`${rowOpacity} hover:bg-neutral-50`}
              >
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-neutral-900">
                      {phaseLabel(p)}
                    </span>
                    {showPartialBadge && (
                      <span className="text-[10px] font-medium uppercase tracking-wider text-amber-700">
                        partial
                      </span>
                    )}
                    {p.budget_source === "flagship" && (
                      <span className="rounded-sm border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-indigo-700">
                        Allocation
                      </span>
                    )}
                    {p.expected_cost_status === "NONE" && (
                      <span className="rounded-sm border border-rose-200 bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-rose-700">
                        Budget missing
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-neutral-700">
                  {formatMoney(p.expected_total_cost)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-neutral-700">
                  {formatMoney(p.actual_cost_total)}
                </td>
                <td
                  className={`border-l border-neutral-200 bg-neutral-50/30 px-3 py-2 text-right tabular-nums font-semibold ${vColor}`}
                >
                  {formatPct(p.variance_pct)}
                </td>
                <td className="px-3 py-2">
                  <StatusBadge status={status} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
