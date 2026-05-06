from __future__ import annotations

import pandas as pd

from core.steps.base import ProbabilisticToolStep


class PhaseClusterStep(ProbabilisticToolStep):
    """Assigns estimated phase IDs to lots using gap-based lot_number clustering.

    Input:  lot state DataFrame from LotStateStep
    Output: same DataFrame with added columns: phase_id, phase_label

    Lots within a project are sorted by numeric lot_number. A new phase starts
    whenever the gap between consecutive lot numbers meets or exceeds gap_threshold.
    Lots without a numeric lot_number land in phase P0 per project.

    This is a heuristic — replace assign_phases() once a real plat→lot table
    exists.

    Args:
        gap_threshold: gap between consecutive lot numbers that starts a new phase
    """

    probabilistic_type = "heuristic"
    confidence_level = 0.5
    method_description = "gap-based lot_number clustering (configurable threshold)"
    result_caveats = [
        "phase_id is estimated, not from a real plat reference",
        "phase boundaries change if gap_threshold is retuned",
    ]

    def __init__(self, gap_threshold: int = 10):
        self.gap_threshold = gap_threshold

    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        out = data.copy()
        out["lot_number_int"] = out["lot_number"].apply(self._to_int)
        out["phase_id"]    = None
        out["phase_label"] = None

        for project, sub in out.groupby("project_code", dropna=False):
            if not isinstance(project, str):
                continue

            non_numeric = sub[sub["lot_number_int"].isna()]
            out.loc[non_numeric.index, "phase_id"]    = f"{project} P0"
            out.loc[non_numeric.index, "phase_label"] = f"{project} (no-number)"

            numeric = sub[sub["lot_number_int"].notna()].sort_values("lot_number_int")
            if numeric.empty:
                continue

            clusters: list[list[int]] = []
            prev = None
            for idx, row in numeric.iterrows():
                n = row["lot_number_int"]
                if prev is None or (n - prev) >= self.gap_threshold:
                    clusters.append([idx])
                else:
                    clusters[-1].append(idx)
                prev = n

            for i, idx_list in enumerate(clusters, start=1):
                phase_id = f"{project} P{i}"
                lot_nums = [out.at[ix, "lot_number_int"] for ix in idx_list]
                label = (
                    f"{project} {min(lot_nums)}-{max(lot_nums)}"
                    if min(lot_nums) != max(lot_nums)
                    else f"{project} {min(lot_nums)}"
                )
                for ix in idx_list:
                    out.at[ix, "phase_id"]    = phase_id
                    out.at[ix, "phase_label"] = label

        return out.reset_index(drop=True)

    @staticmethod
    def _to_int(x):
        try:
            return int(str(x).strip())
        except (ValueError, TypeError):
            return None
