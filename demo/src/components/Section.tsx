import type { ReactNode } from "react";

type Props = {
  overline?: string;
  title: string;
  count: number;
  footnote?: string;
  children: ReactNode;
};

export function Section({ overline, title, count, footnote, children }: Props) {
  return (
    <section className="mb-8 last:mb-0">
      <header className="mb-2">
        {overline && (
          <p className="text-xs text-neutral-500">{overline}</p>
        )}
        <div className="flex items-baseline gap-2">
          <h2 className="text-base font-semibold text-neutral-900">{title}</h2>
          <span className="text-sm tabular-nums text-neutral-500">({count})</span>
        </div>
        {footnote && (
          <p className="mt-1 max-w-2xl text-xs text-neutral-500">{footnote}</p>
        )}
      </header>
      {children}
    </section>
  );
}
