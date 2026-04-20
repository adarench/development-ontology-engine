type Tone = "red" | "amber" | "neutral" | "sky";

type Card = {
  tone: Tone;
  count: number;
  label: string;
};

const dotColor: Record<Tone, string> = {
  red: "bg-red-500",
  amber: "bg-amber-500",
  neutral: "bg-neutral-400",
  sky: "bg-sky-500",
};

export function SummaryBar({ cards }: { cards: Card[] }) {
  return (
    <div className="mb-3 grid grid-cols-2 gap-px overflow-hidden rounded-sm border border-neutral-200 bg-neutral-200 md:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="bg-white px-4 py-3">
          <div className="flex items-baseline gap-2">
            <span
              className={`h-2 w-2 rounded-full ${dotColor[c.tone]}`}
              aria-hidden
            />
            <span className="text-2xl font-semibold tabular-nums text-neutral-900">
              {c.count}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-neutral-600">{c.label}</p>
        </div>
      ))}
    </div>
  );
}
