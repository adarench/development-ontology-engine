"""
Operating State v1: ClickUp tasks → LotState → ProjectState (+ GL join).

Input:  ClickUp task export (CSV/XLSX)  — set CLICKUP_INPUT_FILE below
        Falls back to embedded synthetic fixture if input file is missing.
Output: output/clickup_clean.csv
        output/lot_state.csv                          (NOTE: overwrites operational lot_state from ontology pipeline)
        output/project_state.csv
        output/project_state_with_financials.csv
"""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Swap to the real export path when available. If missing → synthetic fixture is used.
CLICKUP_INPUT_FILE = Path("/Users/arench/Desktop/clickup_tasks.csv")

GL_NORMALIZED_FILE = OUTPUT_DIR / "financials_normalized.csv"

# --- Configuration ------------------------------------------------------------

KEEP_COLS = [
    "top_level_parent_id", "name", "status",
    "date_created", "date_updated", "date_closed", "date_done",
    "start_date", "due_date", "projected_close_date",
    "sold", "sold_date",
]

STAGE_ORDER = {
    "Dug": 1, "Footings": 2, "Walls": 3, "Backfill": 4,
    "Spec": 5, "Walk": 6, "C_of_O": 7, "Sold": 8,
}
# Aliases → canonical stage. Lowercase keys.
STAGE_ALIASES = {
    "dug": "Dug", "excavation": "Dug", "excavate": "Dug",
    "footing": "Footings", "footings": "Footings",
    "wall": "Walls", "walls": "Walls", "foundation": "Walls",
    "backfill": "Backfill",
    "spec": "Spec", "framing": "Spec",
    "walk": "Walk", "walkthrough": "Walk", "walk-through": "Walk",
    "c_of_o": "C_of_O", "c of o": "C_of_O", "cofo": "C_of_O", "co": "C_of_O",
    "sold": "Sold", "closed": "Sold",
}

# Approximate project_code → GL entity map (extend as patterns emerge).
PROJECT_CODE_TO_ENTITY = {
    "LE":    "Anderson Geneva LLC",
    "H":     "Flagborough LLC",
    "H MF":  "Flagborough LLC",
    "H A14": "Flagborough LLC",
    "H A13": "Flagborough LLC",
    "AS":    "Arrowhead Springs Development LLC",
}

DATE_COLS = [
    "date_created", "date_updated", "date_closed", "date_done",
    "start_date", "due_date", "projected_close_date", "sold_date",
]


# --- Helpers ------------------------------------------------------------------

def _to_bool(v) -> bool:
    if pd.isna(v):
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"true", "1", "yes", "y", "t"}


def parse_name(name: str | None) -> tuple[str | None, str | None, str | None]:
    """
    Parse 'LE 31 Dug' → (project_code='LE', lot_number='31', stage='Dug').
    Project code = everything before the LAST pure-digit token.
    Lot number   = that pure-digit token.
    Stage        = everything after, canonicalized via STAGE_ALIASES.
    Parent rows like 'LE 31' return (project_code='LE', lot_number='31', stage=None).
    """
    if not name or not isinstance(name, str):
        return None, None, None
    tokens = name.strip().split()
    digit_idx = [i for i, t in enumerate(tokens) if t.isdigit()]
    if not digit_idx:
        return None, None, None
    last = digit_idx[-1]
    project_code = " ".join(tokens[:last]).strip() or None
    lot_number = tokens[last]
    stage_raw = " ".join(tokens[last + 1:]).strip().lower()
    stage = STAGE_ALIASES.get(stage_raw) if stage_raw else None
    return project_code, lot_number, stage


def stage_rank(stage: str | None) -> int:
    return STAGE_ORDER.get(stage, 0) if stage else 0


def derive_lot_key(top_level_parent_id, name: str | None) -> str:
    if pd.notna(top_level_parent_id) and str(top_level_parent_id).strip():
        return str(top_level_parent_id).strip()
    h = hashlib.md5((name or "").encode("utf-8")).hexdigest()[:12]
    return f"derived_{h}"


def reconcile_parent_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parent rows (blank top_level_parent_id, name = 'LE 31') and their children
    ('LE 31 Dug') refer to the same lot. Rebind parent rows to the child group's
    lot_key when (project_code, lot_number) matches.
    """
    df = df.copy()
    has_parent = df["top_level_parent_id"].notna() & (df["top_level_parent_id"].astype(str).str.len() > 0)
    child = df[has_parent].dropna(subset=["project_code", "lot_number"])
    # Most common top_level_parent_id per (project_code, lot_number).
    label_to_key = (child.groupby(["project_code", "lot_number"])["top_level_parent_id"]
                         .agg(lambda s: s.mode().iat[0] if len(s.mode()) else s.iat[0])
                         .to_dict())
    def fix(row):
        if has_parent.loc[row.name]:
            return row["lot_key"]
        key = (row["project_code"], row["lot_number"])
        return label_to_key.get(key, row["lot_key"])
    df["lot_key"] = df.apply(fix, axis=1)
    return df


# --- Step 1: clean ------------------------------------------------------------

def load_clickup() -> tuple[pd.DataFrame, bool]:
    """Returns (df, used_synthetic_fixture)."""
    if CLICKUP_INPUT_FILE.exists():
        if CLICKUP_INPUT_FILE.suffix.lower() in {".xlsx", ".xls"}:
            return pd.read_excel(CLICKUP_INPUT_FILE), False
        return pd.read_csv(CLICKUP_INPUT_FILE), False
    return pd.read_csv(io.StringIO(_SYNTHETIC_CSV)), True


def clean_clickup(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in KEEP_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[KEEP_COLS].copy()

    for c in ["top_level_parent_id", "name", "status"]:
        df[c] = df[c].astype("string").str.strip()
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c], errors="coerce", utc=False)
    df["sold"] = df["sold"].apply(_to_bool)

    df = df[df["name"].notna() & (df["name"].str.len() > 0)]
    return df.reset_index(drop=True)


# --- Step 2: parse structure --------------------------------------------------

def parse_structure(clean: pd.DataFrame) -> pd.DataFrame:
    parsed = clean["name"].apply(parse_name)
    clean["project_code"] = [p for p, _, _ in parsed]
    clean["lot_number"]   = [n for _, n, _ in parsed]
    clean["stage"]        = [s for _, _, s in parsed]
    clean["lot_label"] = clean.apply(
        lambda r: f"{r['project_code']} {r['lot_number']}".strip()
        if pd.notna(r.get("project_code")) and pd.notna(r.get("lot_number")) else None,
        axis=1,
    )
    clean["lot_key"] = clean.apply(
        lambda r: derive_lot_key(r["top_level_parent_id"], r["name"]), axis=1
    )
    clean = reconcile_parent_rows(clean)
    return clean


# --- Step 3: LotState ---------------------------------------------------------

def build_lot_state(parsed: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for lot_key, sub in parsed.groupby("lot_key", dropna=False):
        proj = sub["project_code"].dropna().mode()
        lot_num = sub["lot_number"].dropna().mode()
        label = sub["lot_label"].dropna().mode()
        stages = [s for s in sub["stage"].dropna().tolist() if s]

        tasks_total = len(sub)
        done_mask = sub["date_done"].notna() | sub["status"].fillna("").str.lower().isin(
            {"closed", "complete", "completed", "done"}
        )
        tasks_done = int(done_mask.sum())
        tasks_open = tasks_total - tasks_done

        sold_any = bool(sub["sold"].any())
        completion_pct = (tasks_done / tasks_total) if tasks_total else 0.0

        if sold_any:
            status_rollup = "sold"
        elif completion_pct > 0.8:
            status_rollup = "near complete"
        elif tasks_done > 0:
            status_rollup = "in progress"
        else:
            status_rollup = "not started"

        latest_stage = max(stages, key=stage_rank) if stages else None

        # Confidence
        unique_stages = len(set(stages))
        has_dates = sub["start_date"].notna().any() or sub["due_date"].notna().any() \
                    or sub["date_done"].notna().any()
        if unique_stages >= 2 and has_dates:
            confidence = "HIGH"
        elif unique_stages >= 1 or has_dates:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        sold_dates = sub.loc[sub["sold"], "sold_date"].dropna()
        sold_date = sold_dates.min() if len(sold_dates) else pd.NaT

        rows.append({
            "lot_key": lot_key,
            "project_code": proj.iloc[0] if len(proj) else None,
            "lot_number": lot_num.iloc[0] if len(lot_num) else None,
            "lot_label": label.iloc[0] if len(label) else None,
            "tasks_total": tasks_total,
            "tasks_done": tasks_done,
            "tasks_open": tasks_open,
            "stages_present": "|".join(sorted(set(stages), key=stage_rank)) or None,
            "latest_stage": latest_stage,
            "completion_pct": round(completion_pct, 4),
            "status_rollup": status_rollup,
            "start_date_min": sub["start_date"].min(),
            "due_date_max":   sub["due_date"].max(),
            "projected_close_date": sub["projected_close_date"].max(),
            "sold": sold_any,
            "sold_date": sold_date,
            "last_updated": sub["date_updated"].max(),
            "confidence": confidence,
        })
    return pd.DataFrame(rows).sort_values(["project_code", "lot_number"], na_position="last").reset_index(drop=True)


# --- Step 4: ProjectState -----------------------------------------------------

def build_project_state(lot_state: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for proj, sub in lot_state.groupby("project_code", dropna=False):
        if pd.isna(proj):
            continue
        lots_total = len(sub)
        lots_sold = int(sub["sold"].sum())
        lots_active = int((~sub["sold"] & (sub["status_rollup"] != "not started")).sum())
        avg_pct = round(sub["completion_pct"].mean(), 4)

        stage_dist = sub["latest_stage"].fillna("(none)").value_counts().to_dict()
        stage_dist_str = "|".join(f"{k}:{v}" for k, v in sorted(
            stage_dist.items(), key=lambda kv: stage_rank(kv[0])))

        proj_close = sub["projected_close_date"].dropna()
        rows.append({
            "project_code": proj,
            "lots_total": lots_total,
            "lots_active": lots_active,
            "lots_sold": lots_sold,
            "avg_completion_pct": avg_pct,
            "stage_distribution": stage_dist_str,
            "projected_close_min": proj_close.min() if len(proj_close) else pd.NaT,
            "projected_close_max": proj_close.max() if len(proj_close) else pd.NaT,
            "last_update": sub["last_updated"].max(),
        })
    return pd.DataFrame(rows).sort_values("project_code").reset_index(drop=True)


# --- Step 5: GL join ----------------------------------------------------------

def join_financials(project_state: pd.DataFrame) -> pd.DataFrame:
    if not GL_NORMALIZED_FILE.exists():
        ps = project_state.copy()
        ps["mapped_entity"] = None
        ps["total_cost"] = 0.0
        ps["cost_per_lot_estimate"] = 0.0
        ps["financial_confidence"] = "LOW"
        ps["cost_by_bucket"] = None
        return ps

    gl = pd.read_csv(GL_NORMALIZED_FILE)
    proj_only = gl[gl["entity_role"] == "project"].copy()

    cost_total = (proj_only.groupby("entity")["amount"]
                  .apply(lambda s: s.abs().sum()).to_dict())
    bucket_pivot = (proj_only.groupby(["entity", "cost_bucket"])["amount"]
                    .apply(lambda s: s.abs().sum()).unstack(fill_value=0.0))

    out = project_state.copy()
    out["mapped_entity"] = out["project_code"].map(PROJECT_CODE_TO_ENTITY)
    out["total_cost"] = out["mapped_entity"].map(cost_total).fillna(0.0)

    def bucket_str(ent):
        if ent not in bucket_pivot.index:
            return None
        row = bucket_pivot.loc[ent]
        return "|".join(f"{k}:{v:.0f}" for k, v in row.items() if v)

    out["cost_by_bucket"] = out["mapped_entity"].apply(bucket_str)
    out["cost_per_lot_estimate"] = (out["total_cost"] / out["lots_total"]).round(2)
    out["financial_confidence"] = out.apply(
        lambda r: "HIGH" if r["mapped_entity"] and r["total_cost"] > 0 else "LOW", axis=1
    )
    return out


# --- Step 7: report -----------------------------------------------------------

def report(used_synthetic: bool, clean: pd.DataFrame, parsed: pd.DataFrame,
           lot_state: pd.DataFrame, project_state: pd.DataFrame,
           project_with_fin: pd.DataFrame) -> str:
    n_lots = len(lot_state)
    valid_progression = lot_state["stages_present"].notna() \
        & lot_state["stages_present"].str.contains(r"\|", na=False)
    pct_valid_progression = (100.0 * valid_progression.sum() / n_lots) if n_lots else 0.0

    n_with_proj = lot_state["project_code"].notna().sum()
    n_high_conf = (lot_state["confidence"] == "HIGH").sum()
    n_with_dates = (lot_state["start_date_min"].notna() | lot_state["due_date_max"].notna()).sum()

    fin_high = (project_with_fin["financial_confidence"] == "HIGH").sum()

    lines = [
        "=" * 64,
        "OPERATING STATE v1 — CLICKUP PIPELINE REPORT",
        "=" * 64,
        f"Source: {'SYNTHETIC FIXTURE (no input file present)' if used_synthetic else CLICKUP_INPUT_FILE}",
        f"Cleaned task rows:                       {len(clean)}",
        f"Rows with parsed project_code:           {parsed['project_code'].notna().sum()}",
        f"Rows with parsed lot_number:             {parsed['lot_number'].notna().sum()}",
        f"Rows with parsed stage:                  {parsed['stage'].notna().sum()}",
        "",
        f"Unique lots detected:                    {n_lots}",
        f"  with project_code:                     {n_with_proj}",
        f"  with at least 2 stages (progression):  {valid_progression.sum()}  ({pct_valid_progression:.1f}%)",
        f"  with any dates:                        {n_with_dates}",
        f"  HIGH-confidence lots:                  {n_high_conf}",
        "",
        f"Projects detected:                       {len(project_state)}",
        f"  matched to a GL entity:                {fin_high}",
        f"  with $cost from GL > 0:                {(project_with_fin['total_cost'] > 0).sum()}",
        "",
        "AGENT-READINESS",
        "-" * 64,
        "Sufficient to power an agent for: lot pipeline visibility, stage",
        "rollups, completion %, and project-level cost-per-lot estimates.",
        "",
        "Still missing:",
        "  - Phase mapping (B2, A10, etc.) — not in name; need plat layer",
        "  - Lot-level cost — GL has zero lot signal",
        "  - Reliable project_code → GL entity mapping (currently",
        "    PROJECT_CODE_TO_ENTITY is hand-curated; extend on real data)",
        "",
        "Verdict: yes, this is enough to ship Operating State v1.",
        "         Cost-per-lot is an ESTIMATE (project total / lot count),",
        "         not a measurement. Do not present it as actual lot cost.",
        "=" * 64,
    ]
    return "\n".join(lines)


# --- Main ---------------------------------------------------------------------

def main() -> None:
    raw, used_synthetic = load_clickup()
    cleaned = clean_clickup(raw)
    parsed = parse_structure(cleaned)
    cleaned_out = parsed[KEEP_COLS + ["project_code", "lot_number", "lot_label",
                                      "stage", "lot_key"]].copy()
    cleaned_out.to_csv(OUTPUT_DIR / "clickup_clean.csv", index=False)

    lot_state = build_lot_state(parsed)
    lot_state.to_csv(OUTPUT_DIR / "lot_state.csv", index=False)

    project_state = build_project_state(lot_state)
    project_state.to_csv(OUTPUT_DIR / "project_state.csv", index=False)

    project_with_fin = join_financials(project_state)
    project_with_fin.to_csv(OUTPUT_DIR / "project_state_with_financials.csv", index=False)

    print(report(used_synthetic, cleaned, parsed, lot_state, project_state, project_with_fin))
    print()
    print("--- lot_state (head) ---")
    print(lot_state.to_string(index=False))
    print()
    print("--- project_state_with_financials ---")
    print(project_with_fin.to_string(index=False))


# --- Synthetic fixture (only used if CLICKUP_INPUT_FILE is missing) -----------

_SYNTHETIC_CSV = """top_level_parent_id,name,status,date_created,date_updated,date_closed,date_done,start_date,due_date,projected_close_date,sold,sold_date
,LE 31,open,2025-09-01,2026-04-20,,,2025-09-15,2026-05-30,2026-06-15,false,
LOT_LE31,LE 31 Dug,closed,2025-09-10,2025-09-25,2025-09-25,2025-09-24,2025-09-15,2025-09-25,2026-06-15,false,
LOT_LE31,LE 31 Footings,closed,2025-09-25,2025-10-12,2025-10-12,2025-10-11,2025-09-26,2025-10-12,2026-06-15,false,
LOT_LE31,LE 31 Walls,closed,2025-10-12,2025-11-05,2025-11-05,2025-11-04,2025-10-13,2025-11-05,2026-06-15,false,
LOT_LE31,LE 31 Backfill,in_progress,2025-11-05,2026-04-20,,,2025-11-06,2025-11-20,2026-06-15,false,
,LE 32,open,2025-09-01,2026-04-15,,,2025-09-15,2026-05-30,2026-06-15,false,
LOT_LE32,LE 32 Dug,closed,2025-09-12,2025-09-28,2025-09-28,2025-09-27,2025-09-15,2025-09-28,2026-06-15,false,
LOT_LE32,LE 32 Footings,in_progress,2025-09-28,2026-04-15,,,2025-09-29,2025-10-15,2026-06-15,false,
,H MF 76,open,2025-08-01,2026-04-22,,,2025-08-15,2026-04-30,2026-05-15,false,
LOT_HMF76,H MF 76 Dug,closed,2025-08-15,2025-08-28,2025-08-28,2025-08-27,2025-08-15,2025-08-28,2026-05-15,false,
LOT_HMF76,H MF 76 Footings,closed,2025-08-28,2025-09-15,2025-09-15,2025-09-14,2025-08-29,2025-09-15,2026-05-15,false,
LOT_HMF76,H MF 76 Walls,closed,2025-09-15,2025-10-08,2025-10-08,2025-10-07,2025-09-16,2025-10-08,2026-05-15,false,
LOT_HMF76,H MF 76 Backfill,closed,2025-10-08,2025-10-22,2025-10-22,2025-10-21,2025-10-09,2025-10-22,2026-05-15,false,
LOT_HMF76,H MF 76 Spec,closed,2025-10-22,2026-01-15,2026-01-15,2026-01-14,2025-10-23,2026-01-15,2026-05-15,false,
LOT_HMF76,H MF 76 Walk,closed,2026-01-15,2026-02-10,2026-02-10,2026-02-09,2026-01-16,2026-02-10,2026-05-15,false,
LOT_HMF76,H MF 76 C_of_O,closed,2026-02-10,2026-03-05,2026-03-05,2026-03-04,2026-02-11,2026-03-05,2026-05-15,true,2026-04-22
,H A14 1415,open,2025-10-01,2026-04-25,,,2025-10-15,2026-08-30,2026-09-15,false,
LOT_HA14_1415,H A14 1415 Dug,closed,2025-10-15,2025-11-02,2025-11-02,2025-11-01,2025-10-15,2025-11-02,2026-09-15,false,
LOT_HA14_1415,H A14 1415 Footings,in_progress,2025-11-02,2026-04-25,,,2025-11-03,2025-11-22,2026-09-15,false,
,H A14 1416,open,2025-10-01,2026-04-25,,,2025-10-15,2026-08-30,2026-09-15,false,
LOT_HA14_1416,H A14 1416 Dug,open,2025-10-15,2026-04-25,,,2025-10-15,2025-11-02,2026-09-15,false,
,AS 12,open,2025-11-01,2026-04-26,,,2025-11-15,2026-09-30,2026-10-15,false,
LOT_AS12,AS 12 Dug,open,2025-11-15,2026-04-26,,,2025-11-15,2025-12-05,2026-10-15,false,
"""

if __name__ == "__main__":
    main()
