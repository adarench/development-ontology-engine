"""
Operating State v1 — REAL ClickUp pipeline.

Input:  /Users/arench/Desktop/development_ontology_engine/Clickup_Sheet_Structure - Sheet1.csv
Output: output/clickup_clean_real.csv
        output/lot_state_real.csv
        output/project_state_real.csv

Robust to messy input. Logs and continues; never hard-fails on parse errors.
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path

import pandas as pd

REPO_ROOT  = Path(__file__).resolve().parent.parent
INPUT_FILE = REPO_ROOT / "Clickup_Sheet_Structure - Sheet1.csv"
OUTPUT_DIR = REPO_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# --- Stage ontology -----------------------------------------------------------

STAGE_ORDER = {
    "Dug": 1, "Footings": 2, "Walls": 3, "Backfill": 4,
    "Spec": 5, "Rough": 6, "Finish": 7, "Complete": 8, "Sold": 9,
}
TOTAL_STAGES = len(STAGE_ORDER)

# Lowercased free-text → canonical stage. "Spec" is its own stage and sits
# between Backfill and Rough in this builder's vocabulary.
STAGE_ALIASES = {
    "dug": "Dug", "excavation": "Dug", "excavate": "Dug",
    "footing": "Footings", "footings": "Footings",
    "wall": "Walls", "walls": "Walls", "foundation": "Walls",
    "backfill": "Backfill",
    "spec": "Spec",
    "rough": "Rough", "rough in": "Rough", "rough-in": "Rough",
    "framing": "Rough",
    "finish": "Finish", "walk": "Finish", "walkthrough": "Finish",
    "walk-through": "Finish", "walk stage": "Finish",
    "complete": "Complete", "completed": "Complete",
    "c_of_o": "Complete", "c of o": "Complete", "cofo": "Complete",
    "co": "Complete", "close": "Complete", "closed": "Complete",
    "sold": "Sold",
}

# Logging — accumulate parse warnings without exploding stderr.
_PARSE_WARNINGS: list[str] = []
def _warn(msg: str) -> None:
    _PARSE_WARNINGS.append(msg)


# --- Parsing helpers ----------------------------------------------------------

def _to_bool(v) -> bool:
    if pd.isna(v): return False
    if isinstance(v, bool): return v
    return str(v).strip().lower() in {"true", "1", "yes", "y", "t"}

def _to_dt(s):
    return pd.to_datetime(s, errors="coerce", utc=False)

def parse_name(name) -> tuple[str | None, str | None, str | None, str | None]:
    """name → (project_code, lot_number, stage_raw, stage_canonical)."""
    if not isinstance(name, str) or not name.strip():
        return None, None, None, None
    tokens = re.split(r"\s+", name.strip())
    digit_idx = [i for i, t in enumerate(tokens) if t.isdigit()]
    if not digit_idx:
        _warn(f"no numeric token: {name!r}")
        return None, None, None, None
    last = digit_idx[-1]
    project_code = " ".join(tokens[:last]).strip() or None
    lot_number   = tokens[last]
    stage_raw    = " ".join(tokens[last + 1:]).strip() or None
    stage_canon  = STAGE_ALIASES.get(stage_raw.lower()) if stage_raw else None
    if stage_raw and not stage_canon:
        _warn(f"unknown stage {stage_raw!r} in {name!r}")
    return project_code, lot_number, stage_raw, stage_canon

def stage_rank(s) -> int:
    return STAGE_ORDER.get(s, 0) if s else 0


# --- Step 1: load + clean -----------------------------------------------------

def load_clean(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=True)
    # Normalize column names (idempotent — file is already snake_case).
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if "name" not in df.columns:
        raise ValueError("input is missing required 'name' column")

    # Drop wholly empty rows + rows with no name.
    df = df.dropna(how="all")
    df["name"] = df["name"].astype("string").str.strip()
    before = len(df)
    df = df[df["name"].notna() & (df["name"].str.len() > 0)]
    dropped = before - len(df)
    if dropped:
        _warn(f"dropped {dropped} rows with empty name")

    # Coerce dates we'll actually use.
    for c in ["date_created", "date_updated", "date_done", "due_date",
              "start_date", "projected_close_date", "sold_date"]:
        if c in df.columns:
            df[c] = _to_dt(df[c])

    # Coerce booleans.
    for c in ["sold", "closed", "cancelled", "C_of_O".lower(), "c_of_o"]:
        if c in df.columns:
            df[c] = df[c].apply(_to_bool)

    # Trim string fields.
    for c in ["top_level_parent_id", "status", "subdivision", "lot_num"]:
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip()

    return df.reset_index(drop=True)


# --- Step 2: parse name -------------------------------------------------------

def parse_structure(df: pd.DataFrame) -> pd.DataFrame:
    parsed = df["name"].apply(parse_name)
    df = df.copy()
    df["project_code"]    = [p for p, _, _, _ in parsed]
    df["lot_number"]      = [n for _, n, _, _ in parsed]
    df["stage_raw"]       = [r for _, _, r, _ in parsed]
    df["stage_canonical"] = [c for _, _, _, c in parsed]
    df["lot_label"] = df.apply(
        lambda r: f"{r['project_code']} {r['lot_number']}".strip()
        if r["project_code"] and r["lot_number"] else None,
        axis=1,
    )
    return df


# --- Lot key + parent reconciliation ------------------------------------------

def assign_lot_keys(df: pd.DataFrame) -> pd.DataFrame:
    """
    lot_key = top_level_parent_id when present.
    Otherwise fall back to a compound (project_code + lot_number) so parent rows
    merge with their child tasks deterministically.
    """
    df = df.copy()
    has_pid = df["top_level_parent_id"].notna() & (df["top_level_parent_id"].str.len() > 0)
    # Build (project_code, lot_number) → canonical pid from rows that have one.
    label_to_pid: dict[tuple, str] = {}
    for (pc, ln), sub in df[has_pid].groupby(["project_code", "lot_number"], dropna=True):
        modes = sub["top_level_parent_id"].mode()
        if len(modes):
            label_to_pid[(pc, ln)] = modes.iat[0]

    def key_for(row):
        if has_pid.loc[row.name]:
            return row["top_level_parent_id"]
        pc, ln = row["project_code"], row["lot_number"]
        if pc and ln:
            return label_to_pid.get((pc, ln), f"FALLBACK_{pc}_{ln}".replace(" ", "_"))
        return f"ROW_{row.name}"  # last-resort unique key

    df["lot_key"] = df.apply(key_for, axis=1)
    return df


# --- Step 4: LotState ---------------------------------------------------------

def build_lot_state(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for lot_key, sub in df.groupby("lot_key", dropna=False):
        proj  = sub["project_code"].dropna().mode()
        lotn  = sub["lot_number"].dropna().mode()
        label = sub["lot_label"].dropna().mode()

        stages = [s for s in sub["stage_canonical"].dropna().tolist() if s]
        stage_set = sorted(set(stages), key=stage_rank)
        ranks = [stage_rank(s) for s in stage_set]
        max_rank = max(ranks) if ranks else 0
        current_stage = stage_set[-1] if stage_set else None

        # Completion = furthest stage achieved / total stages.
        completion_pct = round(max_rank / TOTAL_STAGES, 4)

        # Valid progression = no skipped stages (ranks form 1..max_rank contiguous).
        has_valid_progression = bool(ranks) and ranks == list(range(1, max_rank + 1))

        # Status. completion_pct=1.0 → complete (Sold reached);
        # >= 0.75 → near_complete; > 0 → in_progress; else not_started.
        if completion_pct >= 1.0:
            status = "complete"
        elif completion_pct >= 0.75:
            status = "near_complete"
        elif completion_pct > 0:
            status = "in_progress"
        else:
            status = "not_started"

        started_at = sub["date_created"].min() if "date_created" in sub.columns else pd.NaT
        last_activity = sub["date_updated"].max() if "date_updated" in sub.columns else pd.NaT

        rows.append({
            "lot_key": lot_key,
            "project_code": proj.iat[0] if len(proj) else None,
            "lot_number":   lotn.iat[0] if len(lotn) else None,
            "lot_label":    label.iat[0] if len(label) else None,
            "stage_count": len(stage_set),
            "stages_present": "|".join(stage_set) if stage_set else None,
            "current_stage": current_stage,
            "completion_pct": completion_pct,
            "status": status,
            "has_valid_progression": has_valid_progression,
            "started_at": started_at,
            "last_activity": last_activity,
            "task_count": len(sub),
        })
    return (pd.DataFrame(rows)
              .sort_values(["project_code", "lot_number"], na_position="last")
              .reset_index(drop=True))


# --- Step 5: ProjectState -----------------------------------------------------

def build_project_state(lot_state: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for proj, sub in lot_state.groupby("project_code", dropna=False):
        if proj is None or pd.isna(proj):
            continue
        rows.append({
            "project_code": proj,
            "total_lots":      len(sub),
            "lots_started":    int((sub["status"] != "not_started").sum()),
            "lots_in_progress":int((sub["status"] == "in_progress").sum()),
            "lots_near_complete": int((sub["status"] == "near_complete").sum()),
            "lots_complete":   int((sub["status"] == "complete").sum()),
            "avg_completion_pct": round(sub["completion_pct"].mean(), 4),
            "stage_distribution": "|".join(
                f"{k}:{v}" for k, v in sorted(
                    sub["current_stage"].fillna("(none)").value_counts().items(),
                    key=lambda kv: stage_rank(kv[0]))
            ),
            "last_activity": sub["last_activity"].max(),
        })
    return pd.DataFrame(rows).sort_values("project_code").reset_index(drop=True)


# --- Step 6: data quality report ---------------------------------------------

def quality_report(raw: pd.DataFrame, parsed: pd.DataFrame, lot_state: pd.DataFrame,
                   project_state: pd.DataFrame) -> str:
    n = len(raw)
    pct = lambda a, b: (100.0 * a / b) if b else 0.0
    pid_missing = raw["top_level_parent_id"].isna().sum() if "top_level_parent_id" in raw.columns else n
    parsed_ok = parsed["project_code"].notna() & parsed["lot_number"].notna()
    invalid = lot_state[~lot_state["has_valid_progression"] & lot_state["stage_count"] > 0]

    lines = [
        "=" * 64,
        "OPERATING STATE v1 — REAL CLICKUP DATA QUALITY REPORT",
        "=" * 64,
        f"Source: {INPUT_FILE.name}",
        f"Raw rows:                                {n}",
        f"  rows missing top_level_parent_id:      {pid_missing}  ({pct(pid_missing, n):.1f}%)",
        f"  rows with project_code+lot_number:     {parsed_ok.sum()}  ({pct(parsed_ok.sum(), n):.1f}%)",
        f"  rows with canonical stage:             {parsed['stage_canonical'].notna().sum()}  "
        f"({pct(parsed['stage_canonical'].notna().sum(), n):.1f}%)",
        "",
        f"Unique lots detected:                    {len(lot_state)}",
        f"  with valid stage progression:          {lot_state['has_valid_progression'].sum()}  "
        f"({pct(lot_state['has_valid_progression'].sum(), len(lot_state)):.1f}%)",
        f"  with skipped/invalid sequences:        {len(invalid)}",
        f"Projects detected:                       {len(project_state)}",
        "",
        f"Parser warnings (logged):                {len(_PARSE_WARNINGS)}",
    ]
    if _PARSE_WARNINGS[:5]:
        lines.append("  first 5:")
        for w in _PARSE_WARNINGS[:5]:
            lines.append(f"    - {w}")
    lines.append("=" * 64)
    return "\n".join(lines)


# --- Main ---------------------------------------------------------------------

def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"missing input: {INPUT_FILE}")

    raw = load_clean(INPUT_FILE)
    parsed = parse_structure(raw)
    parsed = assign_lot_keys(parsed)

    keep_cols = [
        "lot_key", "top_level_parent_id", "name", "project_code", "lot_number",
        "lot_label", "stage_raw", "stage_canonical", "status",
        "date_created", "date_updated", "date_done", "due_date",
        "projected_close_date", "sold_date", "sold",
    ]
    keep_cols = [c for c in keep_cols if c in parsed.columns]
    clean_out = parsed[keep_cols].copy()
    clean_out.to_csv(OUTPUT_DIR / "clickup_clean_real.csv", index=False)

    lot_state = build_lot_state(parsed)
    lot_state.to_csv(OUTPUT_DIR / "lot_state_real.csv", index=False)

    project_state = build_project_state(lot_state)
    project_state.to_csv(OUTPUT_DIR / "project_state_real.csv", index=False)

    print(quality_report(raw, parsed, lot_state, project_state))
    print()
    print("--- 10 PARSED ROWS (clickup_clean_real) ---")
    print(clean_out[["lot_key", "name", "project_code", "lot_number",
                     "stage_raw", "stage_canonical", "status",
                     "date_created", "date_updated"]].head(10).to_string(index=False))
    print()
    print("--- LotState (all) ---")
    print(lot_state.to_string(index=False))
    print()
    print("--- ProjectState (all) ---")
    print(project_state.to_string(index=False))


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    main()
