"""
PhaseState_v1 — temporary phase model.

No explicit phase data exists. Cluster lots within a project by lot_number
proximity (gap-based). Two consecutive lot numbers >GAP_THRESHOLD apart start
a new phase.

Input:  output/lot_state_real.csv
Output: output/phase_state_real.csv
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT  = Path(__file__).resolve().parent.parent
INPUT_FILE  = REPO_ROOT / "output" / "lot_state_real.csv"
OUTPUT_FILE = REPO_ROOT / "output" / "phase_state_real.csv"

# Gap (in lot_number) at or above which we cut a new phase.
GAP_THRESHOLD = 10

# Same ordering as clickup_real.py — keep in sync if you change one.
STAGE_ORDER = {
    "Dug": 1, "Footings": 2, "Walls": 3, "Backfill": 4,
    "Spec": 5, "Rough": 6, "Finish": 7, "Complete": 8, "Sold": 9,
}


def stage_rank(s) -> int:
    return STAGE_ORDER.get(s, 0) if isinstance(s, str) else 0


def _to_int(x):
    try:
        return int(str(x).strip())
    except (ValueError, TypeError):
        return None


def assign_phases(lot_state: pd.DataFrame) -> pd.DataFrame:
    """Assign phase_id to each lot via gap-based clustering on lot_number."""
    out = lot_state.copy()
    out["lot_number_int"] = out["lot_number"].apply(_to_int)
    out["phase_id"] = None
    out["phase_label"] = None

    for project, sub in out.groupby("project_code", dropna=False):
        if not isinstance(project, str):
            continue
        # Lots without numeric lot_number → their own bucket per project.
        non_numeric = sub[sub["lot_number_int"].isna()]
        out.loc[non_numeric.index, "phase_id"]    = f"{project} P0"
        out.loc[non_numeric.index, "phase_label"] = f"{project} (no-number)"

        numeric = sub[sub["lot_number_int"].notna()].sort_values("lot_number_int")
        if numeric.empty:
            continue

        phase_idx = 1
        cluster_start = None
        prev = None
        clusters: list[list[int]] = []  # list of indexes per cluster

        for idx, row in numeric.iterrows():
            n = row["lot_number_int"]
            if prev is None or (n - prev) >= GAP_THRESHOLD:
                clusters.append([idx])
                cluster_start = n
            else:
                clusters[-1].append(idx)
            prev = n

        for i, idx_list in enumerate(clusters, start=1):
            phase_id = f"{project} P{i}"
            lot_nums = [out.at[ix, "lot_number_int"] for ix in idx_list]
            label = f"{project} {min(lot_nums)}-{max(lot_nums)}" if min(lot_nums) != max(lot_nums) \
                    else f"{project} {min(lot_nums)}"
            for ix in idx_list:
                out.at[ix, "phase_id"]    = phase_id
                out.at[ix, "phase_label"] = label

    return out


def build_phase_state(lots_with_phase: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (phase_id, project), sub in lots_with_phase.groupby(["phase_id", "project_code"], dropna=False):
        if not isinstance(phase_id, str):
            continue

        nums = sub["lot_number_int"].dropna().astype(int).tolist()
        lot_min = min(nums) if nums else None
        lot_max = max(nums) if nums else None
        label = sub["phase_label"].dropna().iat[0] if sub["phase_label"].notna().any() else phase_id

        avg_pct = round(sub["completion_pct"].mean(), 4)

        # Dominant stage: most common current_stage; tie-break by highest rank.
        stages = sub["current_stage"].fillna("(none)")
        counts = stages.value_counts()
        max_n = counts.iloc[0]
        top = counts[counts == max_n].index.tolist()
        dominant = max(top, key=stage_rank) if top else None

        stage_dist_str = "|".join(
            f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda kv: stage_rank(kv[0]))
        )

        rows.append({
            "phase_id": phase_id,
            "phase_label": label,
            "project_code": project,
            "lots_in_phase": len(sub),
            "lot_min": lot_min,
            "lot_max": lot_max,
            "avg_completion_pct": avg_pct,
            "dominant_stage": dominant,
            "stage_distribution": stage_dist_str,
        })
    return (pd.DataFrame(rows)
              .sort_values(["project_code", "lot_min"], na_position="last")
              .reset_index(drop=True))


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"missing {INPUT_FILE}; run clickup_real.py first")

    lot_state = pd.read_csv(INPUT_FILE)
    with_phase = assign_phases(lot_state)
    phase_state = build_phase_state(with_phase)

    phase_state.to_csv(OUTPUT_FILE, index=False)

    # Write phase_id_estimated back to lot_state_real.csv. Estimated, not real:
    # comes from gap-based clustering, NOT from a plat reference table.
    enriched = lot_state.copy()
    if "phase_id_estimated" in enriched.columns:
        enriched = enriched.drop(columns=["phase_id_estimated"])
    enriched["phase_id_estimated"] = with_phase["phase_id"].values
    enriched.to_csv(INPUT_FILE, index=False)
    print(f"Updated  {INPUT_FILE}  with column 'phase_id_estimated'")

    print(f"Wrote {len(phase_state)} phases → {OUTPUT_FILE}")
    print(f"Gap threshold: {GAP_THRESHOLD}  (consecutive gap ≥ this starts a new phase)")
    print()
    print("--- PhaseState_v1 ---")
    print(phase_state.to_string(index=False))
    print()
    print("--- Lot → phase assignment ---")
    show = with_phase[["project_code", "lot_number", "phase_id", "phase_label",
                       "current_stage", "completion_pct"]]\
            .sort_values(["project_code", "phase_id", "lot_number"])
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
