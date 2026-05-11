from __future__ import annotations

import pandas as pd

from core.steps.base import DeterministicToolStep

DEFAULT_STAGE_ORDER: dict[str, int] = {
    "Dug": 1, "Footings": 2, "Walls": 3, "Backfill": 4,
    "Spec": 5, "Rough": 6, "Finish": 7, "Complete": 8, "Sold": 9,
}


def _stage_rank(stage, stage_order: dict) -> int:
    return stage_order.get(stage, 0) if stage else 0


class LotStateStep(DeterministicToolStep):
    """Builds a one-row-per-lot state table from a parsed ClickUp DataFrame.

    Input:  parsed DataFrame from LotParseStep (must have lot_key, stage_canonical)
    Output: lot state DataFrame with completion_pct, status, stages_present, etc.

    Args:
        stage_order: maps canonical stage name → integer rank (1 = earliest)
    """

    def __init__(self, stage_order: dict[str, int] | None = None):
        self.stage_order = stage_order if stage_order is not None else DEFAULT_STAGE_ORDER
        self._total_stages = len(self.stage_order)

    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for lot_key, sub in data.groupby("lot_key", dropna=False):
            proj  = sub["project_code"].dropna().mode()
            lotn  = sub["lot_number"].dropna().mode()
            label = sub["lot_label"].dropna().mode() if "lot_label" in sub.columns else pd.Series(dtype=str)

            stages = [s for s in sub["stage_canonical"].dropna().tolist() if s]
            stage_set = sorted(set(stages), key=lambda s: _stage_rank(s, self.stage_order))
            ranks = [_stage_rank(s, self.stage_order) for s in stage_set]
            max_rank = max(ranks) if ranks else 0
            current_stage = stage_set[-1] if stage_set else None

            completion_pct = round(max_rank / self._total_stages, 4) if self._total_stages else 0.0
            has_valid = bool(ranks) and ranks == list(range(1, max_rank + 1))

            if completion_pct >= 1.0:
                status = "complete"
            elif completion_pct >= 0.75:
                status = "near_complete"
            elif completion_pct > 0:
                status = "in_progress"
            else:
                status = "not_started"

            started_at    = sub["date_created"].min() if "date_created" in sub.columns else pd.NaT
            last_activity = sub["date_updated"].max() if "date_updated" in sub.columns else pd.NaT

            rows.append({
                "lot_key":               lot_key,
                "project_code":          proj.iat[0] if len(proj) else None,
                "lot_number":            lotn.iat[0] if len(lotn) else None,
                "lot_label":             label.iat[0] if len(label) else None,
                "stage_count":           len(stage_set),
                "stages_present":        "|".join(stage_set) if stage_set else None,
                "current_stage":         current_stage,
                "completion_pct":        completion_pct,
                "status":                status,
                "has_valid_progression": has_valid,
                "started_at":            started_at,
                "last_activity":         last_activity,
                "task_count":            len(sub),
            })

        return (
            pd.DataFrame(rows)
            .sort_values(["project_code", "lot_number"], na_position="last")
            .reset_index(drop=True)
        )
