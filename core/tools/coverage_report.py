from __future__ import annotations

from core.connectors.base import Connector
from core.steps.coverage_metrics import CoverageMetricsStep
from core.tools.base import Tool


class CoverageReportTool(Tool):
    """Measures and reports GL ↔ inventory ↔ ClickUp join coverage.

    Input:  dict with keys "inventory", "gl", "clickup" (DataFrames)
            OR fetch separately via inv_connector / gl_connector / ck_connector
    Output: markdown coverage report string

    Args:
        inv_connector:  connector for inventory lots
        gl_connector:   connector for staged GL
        ck_connector:   connector for ClickUp tasks (optional)
    """

    output_format = "markdown"
    name = "coverage_report"
    description = (
        "Measures how many lots in the inventory have matching GL transactions and "
        "ClickUp tasks (the 'full triangle'). Returns a per-project coverage table "
        "and headline percentages. Use this to understand data completeness before "
        "drawing cost or stage conclusions."
    )

    def __init__(
        self,
        connector: Connector | None = None,
        inv_connector: Connector | None = None,
        gl_connector: Connector | None = None,
        ck_connector: Connector | None = None,
    ):
        super().__init__(connector)
        self.inv_connector = inv_connector
        self.gl_connector  = gl_connector
        self.ck_connector  = ck_connector
        self._step         = CoverageMetricsStep()

    def run(self, data: dict | None = None, **kwargs) -> str:
        import pandas as pd

        if data is None:
            data = {
                "inventory": self.inv_connector.fetch() if self.inv_connector else pd.DataFrame(),
                "gl":        self.gl_connector.fetch()  if self.gl_connector  else pd.DataFrame(),
                "clickup":   self.ck_connector.fetch()  if self.ck_connector  else pd.DataFrame(),
            }

        metrics = self._step.run(data)
        return self._render(metrics)

    def _render(self, m: dict) -> str:
        pct = lambda v: f"{v:.1f}%"
        lines = [
            "# Coverage Report",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Inventory lots | {m['inventory_lots']} |",
            f"| GL lot-pairs | {m['gl_lot_pairs']} |",
            f"| ClickUp lot-pairs | {m['clickup_lot_pairs']} |",
            f"| GL coverage | {pct(m['gl_coverage_pct'])} |",
            f"| ClickUp coverage | {pct(m['clickup_coverage_pct'])} |",
            f"| Full triangle (GL + ClickUp + inventory) | {pct(m['full_triangle_pct'])} |",
            "",
            "## Per-project breakdown",
            "",
            "| Project | Inv lots | GL match | CU match | Triangle | GL % | CU % |",
            "|---------|----------|----------|----------|----------|------|------|",
        ]
        for p in m.get("per_project", []):
            lines.append(
                f"| {p['project_code']} | {p['inventory_lots']} | "
                f"{p['gl_matched']} | {p['clickup_matched']} | {p['full_triangle']} | "
                f"{pct(p['gl_coverage_pct'])} | {pct(p['clickup_coverage_pct'])} |"
            )
        return "\n".join(lines)
