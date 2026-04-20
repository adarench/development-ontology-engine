import type { VarianceStatus } from "../lib";

const styles: Record<VarianceStatus, { label: string; text: string; dot: string }> = {
  overrun: {
    label: "Over budget",
    text: "text-red-700",
    dot: "bg-red-500",
  },
  on_track: {
    label: "On track",
    text: "text-emerald-700",
    dot: "bg-emerald-500",
  },
  under_budget: {
    label: "Under budget",
    text: "text-sky-700",
    dot: "bg-sky-500",
  },
};

export function StatusBadge({ status }: { status: VarianceStatus | null }) {
  if (!status) {
    return <span className="text-neutral-400">—</span>;
  }
  const s = styles[status];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${s.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden />
      {s.label}
    </span>
  );
}
