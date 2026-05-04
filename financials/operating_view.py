"""
Operating View v1 — joined lot/project/(financial) view.

Joins:
  Step 1: lot_state_real.csv  ⨝ project_state_real.csv     (project_code)
  Step 2: optional ⨝ financials_normalized.csv             (PROJECT_CODE_TO_ENTITY)

Output: output/operating_view_v1.csv
Columns (per spec): project_code, lot_number, stage, completion_pct, status,
                    phase_id_estimated
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT  = Path(__file__).resolve().parent.parent
LOT_FILE     = REPO_ROOT / "output" / "lot_state_real.csv"
PROJECT_FILE = REPO_ROOT / "output" / "project_state_real.csv"
GL_FILE      = REPO_ROOT / "output" / "financials_normalized.csv"
OUT_FILE     = REPO_ROOT / "output" / "operating_view_v1.csv"

# project_code → GL entity (extend as patterns emerge from real data)
PROJECT_CODE_TO_ENTITY = {
    "LE":    "Anderson Geneva LLC",
    "H":     "Flagborough LLC",
    "H MF":  "Flagborough LLC",
    "H A14": "Flagborough LLC",
    "H A13": "Flagborough LLC",
    "AS":    "Arrowhead Springs Development LLC",
}

OUTPUT_COLS = [
    "project_code", "lot_number", "stage", "completion_pct", "status",
    "phase_id_estimated",
]


def load_lots() -> pd.DataFrame:
    df = pd.read_csv(LOT_FILE)
    if "phase_id_estimated" not in df.columns:
        raise ValueError(
            f"{LOT_FILE} missing 'phase_id_estimated' — run phase_state.py first"
        )
    return df


def join_project(lots: pd.DataFrame) -> pd.DataFrame:
    proj = pd.read_csv(PROJECT_FILE)
    # Suffix to keep namespacing clear; only kept for validation/printing.
    return lots.merge(proj, on="project_code", how="left", suffixes=("", "_project"))


def join_financials(joined: pd.DataFrame) -> pd.DataFrame:
    if not GL_FILE.exists():
        joined["gl_entity"] = None
        joined["project_total_cost"] = 0.0
        return joined

    gl = pd.read_csv(GL_FILE)
    proj_only = gl[gl["entity_role"] == "project"]
    cost_total = (proj_only.groupby("entity")["amount"]
                  .apply(lambda s: s.abs().sum()).to_dict())

    joined = joined.copy()
    joined["gl_entity"] = joined["project_code"].map(PROJECT_CODE_TO_ENTITY)
    joined["project_total_cost"] = joined["gl_entity"].map(cost_total).fillna(0.0)
    return joined


def main() -> None:
    lots = load_lots()
    j1 = join_project(lots)
    j2 = join_financials(j1)

    # Project the spec-defined output. 'stage' = current_stage from lot_state.
    out = pd.DataFrame({
        "project_code":       j2["project_code"],
        "lot_number":         j2["lot_number"],
        "stage":              j2["current_stage"],
        "completion_pct":     j2["completion_pct"],
        "status":             j2["status"],
        "phase_id_estimated": j2["phase_id_estimated"],
    })[OUTPUT_COLS].sort_values(
        ["project_code", "phase_id_estimated", "lot_number"], na_position="last"
    ).reset_index(drop=True)

    out.to_csv(OUT_FILE, index=False)

    # --- Validation prints ---------------------------------------------------
    n_lots = len(out)
    join_proj_ok = j1["total_lots"].notna().sum()
    matched_gl   = (j2["gl_entity"].notna() & (j2["project_total_cost"] > 0)).sum()

    print(f"Wrote {n_lots} rows → {OUT_FILE}")
    print()
    print("=" * 60)
    print("JOIN VALIDATION")
    print("=" * 60)
    print(f"Lots after project join:                {join_proj_ok}/{n_lots}")
    print(f"Lots after GL join (cost > 0):          {matched_gl}/{n_lots}")
    print()
    print("Per-project rollup (joined view):")
    summary = (j2.groupby("project_code")
                 .agg(lots=("lot_number", "size"),
                      avg_completion=("completion_pct", "mean"),
                      project_total_cost=("project_total_cost", "first"),
                      gl_entity=("gl_entity", "first"))
                 .reset_index())
    summary["avg_completion"] = summary["avg_completion"].round(4)
    print(summary.to_string(index=False))
    print()
    print("--- operating_view_v1 (head 20) ---")
    print(out.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
