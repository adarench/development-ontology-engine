from __future__ import annotations

import pandas as pd

from core.engine.registry import step
from core.steps.base import DeterministicToolStep
from core.steps.lot_state import DEFAULT_STAGE_ORDER, _stage_rank


class ProjectStateStep(DeterministicToolStep):
    """Aggregates lot-state data to one row per project.

    Input:  lot state DataFrame from LotStateStep
    Output: project state DataFrame

    Args:
        stage_order: maps canonical stage name → rank (used for stage_distribution ordering)
    """

    def __init__(self, stage_order: dict[str, int] | None = None):
        self.stage_order = stage_order if stage_order is not None else DEFAULT_STAGE_ORDER

    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for proj, sub in data.groupby("project_code", dropna=False):
            if proj is None or pd.isna(proj):
                continue
            stage_counts = sub["current_stage"].fillna("(none)").value_counts()
            rows.append({
                "project_code":        proj,
                "total_lots":          len(sub),
                "lots_started":        int((sub["status"] != "not_started").sum()),
                "lots_in_progress":    int((sub["status"] == "in_progress").sum()),
                "lots_near_complete":  int((sub["status"] == "near_complete").sum()),
                "lots_complete":       int((sub["status"] == "complete").sum()),
                "avg_completion_pct":  round(sub["completion_pct"].mean(), 4),
                "stage_distribution":  "|".join(
                    f"{k}:{v}" for k, v in sorted(
                        stage_counts.items(),
                        key=lambda kv: _stage_rank(kv[0], self.stage_order),
                    )
                ),
                "last_activity":       sub["last_activity"].max() if "last_activity" in sub.columns else pd.NaT,
            })
        return pd.DataFrame(rows).sort_values("project_code").reset_index(drop=True)


@step(
    name="project_state",
    inputs={"lot_state": pd.DataFrame},
    outputs={"project_state": pd.DataFrame},
    effects=(),
    description="Aggregate lot state to one row per project with completion summary and stage distribution.",
)
def project_state(lot_state: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"project_state": ProjectStateStep().run(lot_state)}
