from __future__ import annotations

import pandas as pd

from core.engine.registry import step
from core.steps.base import DeterministicToolStep
from core.steps.lot_state import DEFAULT_STAGE_ORDER, _stage_rank


class PhaseStateStep(DeterministicToolStep):
    """Aggregates lot-phase data to one row per phase.

    Input:  DataFrame from PhaseClusterStep (must have phase_id, phase_label,
            lot_number_int, current_stage, completion_pct)
    Output: phase state DataFrame

    Args:
        stage_order: maps canonical stage name → rank
    """

    def __init__(self, stage_order: dict[str, int] | None = None):
        self.stage_order = stage_order if stage_order is not None else DEFAULT_STAGE_ORDER

    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for (phase_id, project), sub in data.groupby(
            ["phase_id", "project_code"], dropna=False
        ):
            if not isinstance(phase_id, str):
                continue

            nums = sub["lot_number_int"].dropna().astype(int).tolist() if "lot_number_int" in sub.columns else []
            lot_min = min(nums) if nums else None
            lot_max = max(nums) if nums else None
            label = (
                sub["phase_label"].dropna().iat[0]
                if "phase_label" in sub.columns and sub["phase_label"].notna().any()
                else phase_id
            )

            avg_pct = round(sub["completion_pct"].mean(), 4)

            stages = sub["current_stage"].fillna("(none)")
            counts = stages.value_counts()
            max_n  = counts.iloc[0] if len(counts) else 0
            top    = counts[counts == max_n].index.tolist() if len(counts) else []
            dominant = max(top, key=lambda s: _stage_rank(s, self.stage_order)) if top else None

            stage_dist = "|".join(
                f"{k}:{v}" for k, v in sorted(
                    counts.items(),
                    key=lambda kv: _stage_rank(kv[0], self.stage_order),
                )
            )

            rows.append({
                "phase_id":           phase_id,
                "phase_label":        label,
                "project_code":       project,
                "lots_in_phase":      len(sub),
                "lot_min":            lot_min,
                "lot_max":            lot_max,
                "avg_completion_pct": avg_pct,
                "dominant_stage":     dominant,
                "stage_distribution": stage_dist,
            })

        return (
            pd.DataFrame(rows)
            .sort_values(["project_code", "lot_min"], na_position="last")
            .reset_index(drop=True)
        )


@step(
    name="phase_state",
    inputs={"clustered_lots": pd.DataFrame},
    outputs={"phase_state": pd.DataFrame},
    effects=(),
    description="Aggregate clustered lot data to one row per phase with dominant stage and completion.",
)
def phase_state(clustered_lots: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"phase_state": PhaseStateStep().run(clustered_lots)}
