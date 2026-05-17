from __future__ import annotations

from core.connectors.base import Connector
from core.engine.registry import step
from core.steps.output.base import Renderer


class DashboardRenderer(Renderer):
    """Renders an HTML executive dashboard from operating state data.

    Input:  operating state dict, JSON string, or None (loads from connector)
    Output: self-contained HTML string (no external dependencies)

    Args:
        connector: FileConnector pointing at operating_state_*.json
    """

    output_format = "html"

    def __init__(self, connector: Connector | None = None):
        super().__init__(connector)

    def render(self, data=None, **kwargs) -> str:
        state = self._load(data)
        projects  = state.get("projects", [])
        dq        = state.get("data_quality", {})
        schema    = state.get("schema_version", "unknown")
        generated = state.get("generated_at", "")

        kpis      = self._kpis(projects, dq)
        proj_rows = self._project_rows(projects)
        insights  = self._insights(projects)

        return self._render_html(schema, generated, kpis, proj_rows, insights)

    def _kpis(self, projects: list, dq: dict) -> list[tuple[str, str]]:
        total_lots   = dq.get("lots_total", sum(p.get("lots_total", 0) for p in projects))
        total_proj   = len(projects)
        total_phases = dq.get("phases_estimated", sum(len(p.get("phases", [])) for p in projects))
        avg_comp     = (
            sum(p.get("avg_completion_pct", 0) for p in projects) / len(projects)
            if projects else 0
        )
        proj_with_cost = sum(
            1 for p in projects if p.get("financials", {}).get("project_total_cost", 0) > 0
        )
        return [
            ("Projects", str(total_proj)),
            ("Total lots", str(total_lots)),
            ("Est. phases", str(total_phases)),
            ("Avg completion", f"{avg_comp * 100:.1f}%"),
            ("Projects with cost", f"{proj_with_cost}/{total_proj}"),
        ]

    def _project_rows(self, projects: list) -> list[dict]:
        rows = []
        for p in projects:
            fin  = p.get("financials", {})
            cost = fin.get("project_total_cost", 0)
            rows.append({
                "code":      p["project_code"],
                "lots":      p.get("lots_total", 0),
                "completion": f"{p.get('avg_completion_pct', 0) * 100:.1f}%",
                "stages":    p.get("stage_distribution", "—"),
                "cost":      f"${cost:,.0f}" if cost else "unknown",
                "cost_conf": fin.get("financial_confidence", "—"),
            })
        return rows

    def _insights(self, projects: list) -> list[str]:
        insights = []
        for p in projects:
            for ph in p.get("phases", []):
                if ph.get("lots_in_phase", 0) >= 5 and ph.get("avg_completion_pct", 1) < 0.6:
                    insights.append(
                        f"<strong>{ph['phase_id_estimated']}</strong>: "
                        f"{ph['lots_in_phase']} lots stalled at "
                        f"<code>{ph.get('dominant_stage', '?')}</code> "
                        f"({ph['avg_completion_pct'] * 100:.1f}% complete)"
                    )
        return insights or ["No bottlenecks detected at current thresholds."]

    def _render_html(
        self, schema: str, generated: str,
        kpis: list, proj_rows: list, insights: list,
    ) -> str:
        kpi_html = "".join(
            f'<div class="kpi"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div></div>'
            for label, value in kpis
        )
        proj_row_html = "".join(
            f"<tr><td>{r['code']}</td><td>{r['lots']}</td>"
            f"<td>{r['completion']}</td><td><code>{r['stages']}</code></td>"
            f"<td>{r['cost']}</td><td>{r['cost_conf']}</td></tr>"
            for r in proj_rows
        )
        insights_html = "".join(f"<li>{i}</li>" for i in insights)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Operating State Dashboard — {schema}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; margin-bottom: .25rem; }}
  .meta {{ color: #666; font-size: .85rem; margin-bottom: 1.5rem; }}
  .kpis {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
  .kpi {{ background: #f5f5f5; border-radius: 6px; padding: .75rem 1.25rem; min-width: 120px; }}
  .kpi-label {{ font-size: .75rem; color: #666; text-transform: uppercase; letter-spacing: .05em; }}
  .kpi-value {{ font-size: 1.5rem; font-weight: 700; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; font-size: .9rem; }}
  th {{ background: #f0f0f0; text-align: left; padding: .5rem .75rem; border-bottom: 2px solid #ddd; }}
  td {{ padding: .4rem .75rem; border-bottom: 1px solid #eee; }}
  code {{ background: #f0f0f0; padding: .1em .3em; border-radius: 3px; font-size: .85em; }}
  ul {{ margin: 0; padding-left: 1.25rem; }}
</style>
</head>
<body>
<h1>Operating State Dashboard</h1>
<div class="meta">Schema: {schema} &nbsp;·&nbsp; Generated: {generated}</div>
<div class="kpis">{kpi_html}</div>
<h2>Projects</h2>
<table>
  <thead><tr>
    <th>Project</th><th>Lots</th><th>Avg completion</th>
    <th>Stage distribution</th><th>Cost</th><th>Confidence</th>
  </tr></thead>
  <tbody>{proj_row_html}</tbody>
</table>
<h2>Insights</h2>
<ul>{insights_html}</ul>
</body>
</html>"""


@step(
    name="render_dashboard",
    inputs={"state": dict},
    outputs={"html": str},
    effects=("write",),
    description="Render an executive dashboard HTML page from an operating state dict.",
)
def render_dashboard(state: dict) -> dict[str, str]:
    return {"html": DashboardRenderer().render(state)}
