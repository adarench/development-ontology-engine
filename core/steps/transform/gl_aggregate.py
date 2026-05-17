from __future__ import annotations

import pandas as pd

from core.engine.registry import step
from core.steps.base import DeterministicToolStep


class GLAggregateStep(DeterministicToolStep):
    """Rolls up a normalized GL DataFrame into three aggregate views.

    Input:  normalized DataFrame from GLNormalizeStep
    Output: dict with keys "by_project", "by_phase", "by_bucket"
            each containing a summary DataFrame.

    Uses absolute amounts for spend rollups so that offsetting credits
    (cash CR / liability DR) do not cancel real activity.
    """

    def run(self, data: pd.DataFrame) -> dict[str, pd.DataFrame]:
        n = data.copy()
        n["abs_amount"] = n["amount"].abs()

        by_project = (
            n.groupby(["entity_role", "project_id", "entity"], dropna=False)
             .agg(
                 rows=("amount", "size"),
                 net_amount=("amount", "sum"),
                 abs_amount=("abs_amount", "sum"),
             )
             .reset_index()
             .sort_values("abs_amount", ascending=False)
        )

        proj_only = n[n["entity_role"] == "project"]
        by_phase = (
            proj_only.groupby(["project_id", "phase_id", "phase_confidence"], dropna=False)
                     .agg(
                         rows=("amount", "size"),
                         net_amount=("amount", "sum"),
                         abs_amount=("abs_amount", "sum"),
                     )
                     .reset_index()
                     .sort_values(["project_id", "abs_amount"], ascending=[True, False])
        )

        by_bucket = (
            n.groupby("cost_bucket", dropna=False)
             .agg(
                 rows=("amount", "size"),
                 net_amount=("amount", "sum"),
                 abs_amount=("abs_amount", "sum"),
             )
             .reset_index()
             .sort_values("abs_amount", ascending=False)
        )

        return {"by_project": by_project, "by_phase": by_phase, "by_bucket": by_bucket}


@step(
    name="gl_aggregate",
    inputs={"gl_normalized": pd.DataFrame},
    outputs={"by_project": pd.DataFrame, "by_phase": pd.DataFrame, "by_bucket": pd.DataFrame},
    effects=(),
    description="Roll up normalized GL into by_project, by_phase, by_bucket aggregate DataFrames.",
)
def gl_aggregate(gl_normalized: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return GLAggregateStep().run(gl_normalized)
