import { PLANNING_ONLY_PROJECTS, type Phase } from "../lib";

function groupByProject(phases: Phase[]): { project: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const p of phases) {
    counts.set(p.project_name, (counts.get(p.project_name) ?? 0) + 1);
  }
  return Array.from(counts, ([project, count]) => ({ project, count })).sort(
    (a, b) => a.project.localeCompare(b.project),
  );
}

function ProjectList({ phases }: { phases: Phase[] }) {
  const groups = groupByProject(phases);
  return (
    <ul className="divide-y divide-neutral-100 text-sm">
      {groups.map((g) => (
        <li
          key={g.project}
          className="flex items-center justify-between px-3 py-1.5"
        >
          <span className="text-neutral-700">{g.project}</span>
          <span className="tabular-nums text-neutral-500">
            {g.count} {g.count === 1 ? "phase" : "phases"}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function NoVisibilityList({ phases }: { phases: Phase[] }) {
  if (phases.length === 0) {
    return (
      <div className="rounded-sm border border-dashed border-neutral-200 px-4 py-5 text-sm text-neutral-500">
        No phases without visibility.
      </div>
    );
  }

  const planning = phases.filter((p) => PLANNING_ONLY_PROJECTS.has(p.project_name));
  const active = phases.filter((p) => !PLANNING_ONLY_PROJECTS.has(p.project_name));

  const activeProjectCount = new Set(active.map((p) => p.project_name)).size;
  const planningProjectCount = new Set(planning.map((p) => p.project_name)).size;

  return (
    <div className="space-y-3">
      {active.length > 0 && (
        <div className="overflow-hidden rounded-sm border border-neutral-200">
          <div className="border-b border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs font-medium uppercase tracking-wider text-neutral-600">
            Active projects — budget gaps
          </div>
          <ProjectList phases={active} />
          <p className="border-t border-neutral-100 bg-neutral-50 px-3 py-1.5 text-xs text-neutral-500">
            {active.length} phases across {activeProjectCount}{" "}
            {activeProjectCount === 1 ? "project" : "projects"}. Budget owners
            should assign expected cost.
          </p>
        </div>
      )}
      {planning.length > 0 && (
        <div className="overflow-hidden rounded-sm border border-neutral-200">
          <div className="border-b border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs font-medium uppercase tracking-wider text-neutral-600">
            Planning-only projects — future pipeline
          </div>
          <ProjectList phases={planning} />
          <p className="border-t border-neutral-100 bg-neutral-50 px-3 py-1.5 text-xs text-neutral-500">
            {planning.length} phases across {planningProjectCount}{" "}
            {planningProjectCount === 1 ? "project" : "projects"}. Budget is not
            expected yet.
          </p>
        </div>
      )}
    </div>
  );
}
