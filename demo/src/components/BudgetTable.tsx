import { formatMoney, phaseLabel, type Phase } from "../lib";

type Props = {
  phases: Phase[];
  emptyLabel?: string;
};

function formatPhaseState(s: string | null): string {
  if (!s) return "—";
  return s
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function BudgetTable({ phases, emptyLabel }: Props) {
  if (phases.length === 0) {
    return (
      <div className="rounded-sm border border-dashed border-neutral-200 px-4 py-5 text-sm text-neutral-500">
        {emptyLabel ?? "No phases match."}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-sm border border-neutral-200">
      <table className="w-full text-sm">
        <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wider text-neutral-500">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Phase</th>
            <th className="px-3 py-2 text-right font-medium">Budget</th>
            <th className="px-3 py-2 text-left font-medium">Phase state</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {phases.map((p) => (
            <tr
              key={`${p.project_name}::${p.phase_name}`}
              className="hover:bg-neutral-50"
            >
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-neutral-900">
                    {phaseLabel(p)}
                  </span>
                  {p.budget_source === "flagship" && (
                    <span className="rounded-sm border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-indigo-700">
                      Allocation
                    </span>
                  )}
                  {p.expected_cost_status === "PARTIAL" && (
                    <span className="text-[10px] font-medium uppercase tracking-wider text-amber-700">
                      partial
                    </span>
                  )}
                </div>
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-neutral-700">
                {formatMoney(p.expected_total_cost)}
              </td>
              <td className="px-3 py-2 text-xs text-neutral-600">
                {formatPhaseState(p.phase_state)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
