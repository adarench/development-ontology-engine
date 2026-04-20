"""Bake phase_state.csv into the JSON the demo imports.

Merges Flagship Allocation Workbook direct budgets on top of the pipeline
output so NONE/PARTIAL phases with a Flagship budget surface as FULL in the
demo. Upgraded rows are tagged with `budget_source: "flagship"`.

Run from repo root:
    python3 demo/scripts/bake_data.py
"""
import json
import math
import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = REPO_ROOT / "output" / "phase_state.csv"
DST = REPO_ROOT / "demo" / "src" / "data" / "phases.json"
FLAGSHIP_SRC = REPO_ROOT / "Flagship Allocation Workbook v3.xlsx - Per-Lot Output.csv"

COLUMNS = [
    "project_name",
    "phase_name",
    "lot_count_total",
    "expected_total_cost",
    "actual_cost_total",
    "variance_pct",
    "expected_cost_status",
    "phase_state",
]

# Flagship uses community/phase names that differ from phase_state. Map
# phase_state (project, phase) -> Flagship (community, phase).
PHASE_RENAME = {
    ("Arrowhead Springs", "123"): ("Arrowhead Springs", "AS 1-3"),
    ("Arrowhead Springs", "456"): ("Arrowhead Springs", "AS 4-6"),
    ("Salem Fields", "B"): ("Salem Fields", "SF B"),
    ("Scarlet Ridge", "2"): ("Scarlet Ridge", "02 Phase"),
    ("Scarlet Ridge", "3"): ("Scarlet Ridge", "03 Phase"),
    ("Lomond Heights", "2A"): ("Ben Lomond", "PH 2A"),
    ("Lomond Heights", "2B"): ("Ben Lomond", "PH 2B"),
    ("Lomond Heights", "2D"): ("Ben Lomond", "PH 2D"),
    ("Lomond Heights", "2C"): ("Ben Lomond", "2C"),
    ("Lomond Heights", "5"): ("Ben Lomond", "5"),
    ("Lomond Heights", "6A"): ("Ben Lomond", "6A"),
    ("Lomond Heights", "6B"): ("Ben Lomond", "6B"),
    ("Lomond Heights", "6C"): ("Ben Lomond", "6C"),
    ("Willowcreek", "1"): ("Willowcreek", "WC Phase 1"),
    ("Willowcreek", "2"): ("Willowcreek", "WC Phase 2"),
    ("Willowcreek", "3"): ("Willowcreek", "WC Phase 3"),
    ("Lewis Estates", "1"): ("Lewis Estates", "Lewis Estates1"),
}

PROJECT_ALIAS = {"Lomond Heights": "Ben Lomond"}


def parse_money(raw) -> float:
    if raw is None:
        return 0.0
    s = str(raw).replace("$", "").replace(",", "").strip()
    if not s or s == "-":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_flagship_direct() -> dict[tuple[str, str], float]:
    """Sum Effective Direct Budget per (Community, Phase) across lot-type rows."""
    if not FLAGSHIP_SRC.exists():
        return {}
    totals: dict[tuple[str, str], float] = {}
    df = pd.read_csv(FLAGSHIP_SRC)
    for _, row in df.iterrows():
        community = str(row.get("Community", "")).strip()
        phase = str(row.get("Phase", "")).strip()
        if not community or community == "TOTAL":
            continue
        budget = parse_money(row.get("Effective Direct Budget"))
        if budget <= 0:
            continue
        totals[(community, phase)] = totals.get((community, phase), 0.0) + budget
    return totals


def flagship_budget_for(project: str, phase: str, table: dict[tuple[str, str], float]) -> float:
    if (project, phase) in PHASE_RENAME:
        return table.get(PHASE_RENAME[(project, phase)], 0.0)
    key = (PROJECT_ALIAS.get(project, project), phase)
    return table.get(key, 0.0)


def clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def main() -> None:
    df = pd.read_csv(SRC)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(f"phase_state.csv missing columns: {missing}")

    flagship = load_flagship_direct()

    rows = []
    upgraded = 0
    for _, row in df[COLUMNS].iterrows():
        record = {col: clean(row[col]) for col in COLUMNS}
        record["budget_source"] = None

        project = record["project_name"]
        phase = record["phase_name"]
        fbudget = flagship_budget_for(project, phase, flagship)
        if fbudget > 0:
            actual = record["actual_cost_total"] or 0.0
            record["expected_total_cost"] = fbudget
            record["expected_cost_status"] = "FULL"
            record["variance_pct"] = (
                (actual - fbudget) / fbudget if fbudget else None
            )
            record["budget_source"] = "flagship"
            upgraded += 1

        rows.append(record)

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(rows, indent=2) + "\n")
    print(
        f"wrote {len(rows)} phases ({upgraded} upgraded from Flagship) -> "
        f"{DST.relative_to(REPO_ROOT)}"
    )


if __name__ == "__main__":
    main()
