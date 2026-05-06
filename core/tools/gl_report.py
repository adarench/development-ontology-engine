from __future__ import annotations

import pandas as pd

from core.connectors.base import Connector
from core.steps.gl_clean import GLCleanStep
from core.steps.gl_normalize import GLNormalizeStep, DEFAULT_ENTITY_MAP, DEFAULT_ACCOUNT_RULES, DEFAULT_PHASE_RULES
from core.steps.gl_aggregate import GLAggregateStep
from core.tools.base import Tool


class GLReportTool(Tool):
    """Normalizes a QuickBooks GL export and returns a coverage report string.

    Orchestrates: GLCleanStep → GLNormalizeStep → GLAggregateStep → coverage report.

    Args:
        connector:       QuickBooksConnector (or FileConnector for mocks)
        entity_map:      maps raw entity name → (role, project_id)
        account_rules:   ordered (pattern, bucket) list
        phase_rules:     ordered (pattern, template, confidence) list
        invalid_entities: entity names to drop during cleaning
    """

    output_format = "markdown"
    name = "gl_report"
    description = (
        "Returns a GL coverage report: entity classification, cost bucket breakdown, "
        "phase allocation coverage, and a list of unmapped account IDs."
    )

    def __init__(
        self,
        connector: Connector | None = None,
        entity_map: dict | None = None,
        account_rules: list | None = None,
        phase_rules: list | None = None,
        invalid_entities: set | None = None,
    ):
        super().__init__(connector)
        self._clean     = GLCleanStep(invalid_entities=invalid_entities)
        self._normalize = GLNormalizeStep(
            entity_map=entity_map,
            account_rules=account_rules,
            phase_rules=phase_rules,
        )
        self._aggregate = GLAggregateStep()

    def run(self, data: pd.DataFrame | None = None, **kwargs) -> str:
        raw = data if data is not None else self.connector.fetch()
        clean = self._clean.run(raw)
        norm  = self._normalize.run(clean)
        aggs  = self._aggregate.run(norm)
        return self._render(norm, aggs)

    def _render(self, norm: pd.DataFrame, aggs: dict[str, pd.DataFrame]) -> str:
        total_rows = len(norm)
        total_abs  = norm["amount"].abs().sum()

        proj = norm[norm["entity_role"] == "project"]
        proj_rows = len(proj)
        proj_abs  = proj["amount"].abs().sum()

        phased = proj[proj["phase_id"] != "UNALLOCATED"]
        bucket_unmapped = norm[norm["cost_bucket"] == "unmapped"]

        pct = lambda a, b: (100.0 * a / b) if b else 0.0

        lines = [
            "# GL Coverage Report",
            "",
            f"Activity rows (post-clean): **{total_rows}**",
            f"- cost_bucket mapped: {total_rows - len(bucket_unmapped)} ({pct(total_rows - len(bucket_unmapped), total_rows):.1f}%)",
            f"- cost_bucket unmapped: {len(bucket_unmapped)} ({pct(len(bucket_unmapped), total_rows):.1f}%)",
            "",
            f"Rows assigned to a project entity: {proj_rows} ({pct(proj_rows, total_rows):.1f}%)",
            f"- phase_id resolved: {len(phased)} ({pct(len(phased), proj_rows):.1f}% of project rows)",
            f"- phase_id UNALLOCATED: {proj_rows - len(phased)} ({pct(proj_rows - len(phased), proj_rows):.1f}%)",
            "",
            f"Total |amount|: **${total_abs:,.2f}**",
            f"- on project entities: ${proj_abs:,.2f} ({pct(proj_abs, total_abs):.1f}%)",
            "",
            "## By bucket",
            "",
            aggs["by_bucket"].to_string(index=False),
            "",
            "## By project",
            "",
            aggs["by_project"].to_string(index=False),
        ]

        unmapped = norm[norm["cost_bucket"] == "unmapped"]
        if len(unmapped):
            lines += [
                "",
                "## Unmapped account IDs",
                "",
                unmapped[["account_id", "account_name"]].drop_duplicates().to_string(index=False),
            ]

        return "\n".join(lines)
