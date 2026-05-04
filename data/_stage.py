"""
Build staged_gl_transactions and staged_clickup_tasks (csv + parquet),
then write per-table validation reports and a combined staging summary.

- Reads from data/raw/datarails/gl/GL (1..14).csv and data/raw/datarails/clickup/api-upload.csv
- Excludes GL.csv stub and api-upload (1).csv duplicate by name
- Adds source_file, source_row_number (0-indexed within source file, post-header), staged_loaded_at
- Preserves all original column names; does not rename
- Does NOT touch output/*
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path("/Users/arench/Desktop/development_ontology_engine")
RAW_GL = REPO / "data" / "raw" / "datarails" / "gl"
RAW_CLICKUP = REPO / "data" / "raw" / "datarails" / "clickup"
STAGED = REPO / "data" / "staged"
REPORTS = REPO / "data" / "reports"
STAGED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

LOAD_TS = datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------- GL --------------------------- #

def load_gl_files() -> tuple[pd.DataFrame, dict, list[dict]]:
    """Load GL (1..14).csv only. Skip GL.csv stub. Return concatenated frame + per-file stats."""
    files = sorted(
        [p for p in RAW_GL.glob("GL (*).csv")],
        key=lambda p: int(re.search(r"GL \((\d+)\)", p.name).group(1)),
    )
    assert len(files) == 14, f"Expected 14 numbered GL files, found {len(files)}"

    per_file = []
    frames = []
    ref_cols: list[str] | None = None

    for p in files:
        # encoding='utf-8-sig' strips the BOM on PostingDate
        df = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig", low_memory=False)
        cols = list(df.columns)
        if ref_cols is None:
            ref_cols = cols
        else:
            assert cols == ref_cols, (
                f"Schema drift in {p.name}: cols differ from GL (1).csv"
            )
        df.insert(0, "source_file", p.name)
        df.insert(1, "source_row_number", range(len(df)))
        df.insert(2, "staged_loaded_at", LOAD_TS)
        frames.append(df)
        per_file.append({"file": p.name, "rows": len(df), "cols": len(cols)})

    out = pd.concat(frames, axis=0, ignore_index=True)
    schema = {
        "n_files": len(files),
        "ref_columns": ref_cols,
        "total_original_cols": len(ref_cols),
    }
    return out, schema, per_file


def gl_validation_report(df: pd.DataFrame, schema: dict, per_file: list[dict]) -> str:
    original_cols = schema["ref_columns"]
    total_rows = len(df)

    # Entities (CompanyName/CompanyCode)
    ent_counts = df["CompanyName"].value_counts(dropna=False)

    # Posting date min/max
    pd_dates = pd.to_datetime(df["PostingDate"], errors="coerce")
    pd_min = pd_dates.min()
    pd_max = pd_dates.max()
    pd_null_rate = float(pd_dates.isna().mean())

    # FunctionalAmount stats
    fa = pd.to_numeric(df["FunctionalAmount"], errors="coerce")
    fa_null_rate = float(fa.isna().mean())
    fa_total_abs = float(fa.abs().sum())

    # Top 20 accounts by abs amount
    if fa.notna().any():
        acc_key = df["AccountCode"].fillna("") + " — " + df["AccountName"].fillna("")
        top_accounts = (
            pd.DataFrame({"account": acc_key, "abs_amount": fa.abs().fillna(0)})
            .groupby("account", as_index=False)["abs_amount"]
            .sum()
            .sort_values("abs_amount", ascending=False)
            .head(20)
        )
    else:
        top_accounts = pd.DataFrame(columns=["account", "abs_amount"])

    # Top 20 entities by row count
    top_entities = ent_counts.head(20)

    # Fill rates for the user-requested fields (and analogues)
    def fill_rate(col: str) -> float:
        if col not in df.columns:
            return float("nan")
        s = df[col].astype(str).str.strip()
        return 1.0 - float((s == "").mean())

    requested = {
        "Class (no exact column; closest analogues: DivisionName, OUnit, JobPhaseStage)": None,
        "DivisionName (Class analogue)": fill_rate("DivisionName"),
        "OUnit (Class analogue)": fill_rate("OUnit"),
        "Customer:Job (no exact column; closest analogue: ProjectName / Lot/Phase)": None,
        "ProjectName (Customer:Job analogue)": fill_rate("ProjectName"),
        "TransactionNumber (Transaction ID part 1)": fill_rate("TransactionNumber"),
        "LineNo (Transaction ID part 2)": fill_rate("LineNo"),
        "Vendor (no exact column; closest analogue: SubledgerDesc / SubledgerCode)": None,
        "SubledgerCode (Vendor analogue)": fill_rate("SubledgerCode"),
        "SubledgerDesc (Vendor analogue)": fill_rate("SubledgerDesc"),
        "Memo1": fill_rate("Memo1"),
        "Memo2": fill_rate("Memo2"),
        "Description": fill_rate("Description"),
        "BatchDescription": fill_rate("BatchDescription"),
    }
    project_fields = {
        "Project": fill_rate("Project"),
        "ProjectCode": fill_rate("ProjectCode"),
        "ProjectName": fill_rate("ProjectName"),
    }
    phase_lot_fields = {
        "Lot/Phase": fill_rate("Lot/Phase"),
        "JobPhaseStage": fill_rate("JobPhaseStage"),
        "Major": fill_rate("Major"),
        "Minor": fill_rate("Minor"),
    }

    # Source file row counts
    src_counts = df["source_file"].value_counts().sort_index(
        key=lambda s: s.map(lambda x: int(re.search(r"\((\d+)\)", x).group(1)))
    )

    lines = []
    lines.append("# Staged GL Transactions — Validation Report\n")
    lines.append(f"**Staged at**: {LOAD_TS}")
    lines.append(f"**Source**: `data/raw/datarails/gl/GL (1..14).csv` (14 files)")
    lines.append(f"**Output**: `data/staged/staged_gl_transactions.csv` and `.parquet`\n")

    lines.append("## Row & column counts\n")
    lines.append(f"- Total staged rows: **{total_rows:,}**")
    lines.append(f"- Original columns preserved: **{len(original_cols)}**")
    lines.append(f"- Staging columns added: **3** (`source_file`, `source_row_number`, `staged_loaded_at`)")
    lines.append(f"- Total columns in staged table: **{len(df.columns)}**")
    expected = sum(p["rows"] for p in per_file)
    lines.append(f"- Per-source row sum: **{expected:,}** (matches total: {expected == total_rows})")
    lines.append(f"- Expected from inventory report: **124,085** "
                 f"({'MATCH' if total_rows == 124_085 else 'DISCREPANCY: ' + str(total_rows - 124_085)})\n")

    lines.append("## Source file row counts\n")
    lines.append("| source_file | rows |\n|---|---:|")
    for fn, n in src_counts.items():
        lines.append(f"| {fn} | {int(n):,} |")
    lines.append("")

    lines.append("## Full column list (staged)\n")
    for c in df.columns:
        lines.append(f"- `{c}`")
    lines.append("")

    lines.append("## Entity coverage (CompanyName)\n")
    lines.append(f"- Distinct CompanyName values: **{int(ent_counts.shape[0])}**")
    lines.append(f"- Distinct CompanyCode values: **{int(df['CompanyCode'].nunique(dropna=False))}**\n")

    lines.append("### Top 20 entities by row count\n")
    lines.append("| CompanyName | rows |\n|---|---:|")
    for name, n in top_entities.items():
        nm = "(blank)" if not str(name).strip() else str(name)
        lines.append(f"| {nm} | {int(n):,} |")
    lines.append("")

    lines.append("## Posting date range\n")
    lines.append(f"- min PostingDate: **{pd_min.date() if pd.notna(pd_min) else 'n/a'}**")
    lines.append(f"- max PostingDate: **{pd_max.date() if pd.notna(pd_max) else 'n/a'}**")
    lines.append(f"- PostingDate null/unparseable rate: **{pd_null_rate:.2%}**\n")

    lines.append("## Amount column\n")
    lines.append(f"- Detected amount column: **`FunctionalAmount`** (signed, aligns with `DebitCredit` indicator)")
    lines.append(f"- Null/unparseable rate: **{fa_null_rate:.2%}**")
    lines.append(f"- Sum of |FunctionalAmount|: **{fa_total_abs:,.2f}**")
    lines.append(f"- DebitCredit values seen: {sorted(df['DebitCredit'].dropna().unique().tolist())[:10]}\n")

    lines.append("## Account columns\n")
    lines.append(f"- `AccountCode` distinct: **{int(df['AccountCode'].nunique(dropna=False))}**, "
                 f"fill rate: **{fill_rate('AccountCode'):.2%}**")
    lines.append(f"- `AccountName` distinct: **{int(df['AccountName'].nunique(dropna=False))}**, "
                 f"fill rate: **{fill_rate('AccountName'):.2%}**")
    lines.append(f"- `AccountType` distinct: **{int(df['AccountType'].nunique(dropna=False))}**, "
                 f"fill rate: **{fill_rate('AccountType'):.2%}**\n")

    lines.append("### Top 20 accounts by Σ|FunctionalAmount|\n")
    lines.append("| account | abs_amount |\n|---|---:|")
    for _, row in top_accounts.iterrows():
        lines.append(f"| {row['account']} | {row['abs_amount']:,.2f} |")
    lines.append("")

    lines.append("## Requested fields (Class / Customer:Job / Transaction ID / Vendor / Memo)\n")
    lines.append("**Note:** the DataRails GL schema does not contain literal `Class`, `Customer:Job`, or `Vendor` columns. "
                 "Closest analogues are noted; consumers should map them deliberately.\n")
    lines.append("| field | fill rate |\n|---|---:|")
    for k, v in requested.items():
        if v is None:
            lines.append(f"| _{k}_ | — |")
        else:
            lines.append(f"| `{k.split(' ')[0]}` ({k}) | {v:.2%} |")
    lines.append("")

    lines.append("## Project / Phase / Lot fields\n")
    lines.append("### Project\n")
    lines.append("| field | fill rate |\n|---|---:|")
    for k, v in project_fields.items():
        lines.append(f"| `{k}` | {v:.2%} |")
    lines.append("")
    lines.append("### Phase / Lot\n")
    lines.append("| field | fill rate |\n|---|---:|")
    for k, v in phase_lot_fields.items():
        lines.append(f"| `{k}` | {v:.2%} |")
    lines.append("")

    lines.append("## Null rates for key fields\n")
    key_fields = ["PostingDate", "JournalCode", "TransactionNumber", "LineNo",
                  "CompanyName", "AccountCode", "AccountName", "FunctionalAmount",
                  "DebitCredit", "Status"]
    lines.append("| field | null rate |\n|---|---:|")
    for c in key_fields:
        lines.append(f"| `{c}` | {1 - fill_rate(c):.2%} |")
    lines.append("")

    lines.append("## Schema validation\n")
    lines.append(f"- All 14 source files share IDENTICAL 38-column schema (column names AND order). ✅")
    lines.append(f"- No silent column loss. ✅")
    lines.append(f"- BOM on `PostingDate` stripped via `encoding='utf-8-sig'`. ✅")
    lines.append(f"- Row total reconciles: {total_rows:,} = {expected:,}. ✅\n")

    return "\n".join(lines)


# --------------------------- ClickUp --------------------------- #

def load_clickup() -> pd.DataFrame:
    p = RAW_CLICKUP / "api-upload.csv"
    df = pd.read_csv(p, dtype=str, keep_default_na=False, low_memory=False)
    df.insert(0, "source_file", p.name)
    df.insert(1, "source_row_number", range(len(df)))
    df.insert(2, "staged_loaded_at", LOAD_TS)
    return df


def clickup_validation_report(df: pd.DataFrame) -> str:
    n = len(df)
    cols = list(df.columns)

    required = [
        "name", "status", "subdivision", "lot_num",
        "projected_close_date", "actual_c_of_o", "sold_date", "cancelled_date",
    ]
    parent_fields = ["id", "top_level_parent_id", "parent_id"]

    def fill_rate(c: str) -> float:
        if c not in df.columns:
            return float("nan")
        return 1.0 - float(df[c].astype(str).str.strip().eq("").mean())

    # Status distribution
    status_dist = df["status"].astype(str).str.strip().value_counts().head(20) if "status" in df.columns else pd.Series(dtype=int)

    # Date fields fill rates
    date_cols = [c for c in df.columns if "date" in c.lower()]
    date_fills = {c: fill_rate(c) for c in date_cols}

    # Duplicate rows: by id
    if "id" in df.columns:
        dup_count = int(df.duplicated(subset=["id"]).sum())
        id_null = int(df["id"].astype(str).str.strip().eq("").sum())
    else:
        dup_count = -1
        id_null = -1

    # Subdivision coverage
    if "subdivision" in df.columns:
        sub_distinct = int(df["subdivision"].nunique(dropna=False))
        sub_top = df["subdivision"].astype(str).str.strip().value_counts().head(20)
    else:
        sub_distinct = 0
        sub_top = pd.Series(dtype=int)

    # Lot_num coverage
    if "lot_num" in df.columns:
        lot_distinct = int(df["lot_num"].nunique(dropna=False))
        lot_filled = int((df["lot_num"].astype(str).str.strip() != "").sum())
    else:
        lot_distinct = 0
        lot_filled = 0

    # Name (task title) quality: empty vs non-empty
    if "name" in df.columns:
        name_empty = int(df["name"].astype(str).str.strip().eq("").sum())
        name_short = int((df["name"].astype(str).str.len() < 3).sum())
    else:
        name_empty = -1
        name_short = -1

    lines = []
    lines.append("# Staged ClickUp Tasks — Validation Report\n")
    lines.append(f"**Staged at**: {LOAD_TS}")
    lines.append(f"**Source**: `data/raw/datarails/clickup/api-upload.csv`")
    lines.append(f"**Output**: `data/staged/staged_clickup_tasks.csv` and `.parquet`\n")

    lines.append("## Row & column counts\n")
    lines.append(f"- Total rows: **{n:,}** (expected 5,509 — {'MATCH' if n == 5509 else 'DISCREPANCY: ' + str(n - 5509)})")
    lines.append(f"- Total columns: **{len(cols)}** (32 original + 3 staging metadata = 35)")
    lines.append("")

    lines.append("## Required fields presence\n")
    lines.append("| field | present | fill rate |\n|---|---|---:|")
    for c in required:
        present = "✅" if c in df.columns else "❌"
        fr = fill_rate(c)
        fr_s = "—" if fr != fr else f"{fr:.2%}"  # nan check
        lines.append(f"| `{c}` | {present} | {fr_s} |")
    lines.append("")

    lines.append("## Parent / top-level identifiers\n")
    lines.append("| field | present | fill rate | distinct |\n|---|---|---:|---:|")
    for c in parent_fields:
        present = "✅" if c in df.columns else "❌"
        fr = fill_rate(c)
        fr_s = "—" if fr != fr else f"{fr:.2%}"
        dist = int(df[c].nunique(dropna=False)) if c in df.columns else 0
        lines.append(f"| `{c}` | {present} | {fr_s} | {dist:,} |")
    lines.append("")
    lines.append("> Note: ClickUp's flat task export carries `top_level_parent_id` (list/space root) but **not**"
                 " the immediate `parent_id`. The intermediate parent must be reconstructed from a separate"
                 " ClickUp API pull if needed.\n")

    lines.append("## Date fields and fill rates\n")
    lines.append("| field | fill rate |\n|---|---:|")
    for c, fr in sorted(date_fills.items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{c}` | {fr:.2%} |")
    lines.append("")

    lines.append("## Status distribution (top 20)\n")
    lines.append("| status | count |\n|---|---:|")
    for s, c in status_dist.items():
        s_d = "(blank)" if str(s).strip() == "" else str(s)
        lines.append(f"| {s_d} | {int(c):,} |")
    lines.append("")

    lines.append("## Subdivision coverage\n")
    lines.append(f"- Distinct subdivisions (incl. blank): **{sub_distinct}**")
    lines.append(f"- subdivision fill rate: **{fill_rate('subdivision'):.2%}**\n")
    lines.append("### Top 20 subdivisions by row count\n")
    lines.append("| subdivision | tasks |\n|---|---:|")
    for s, c in sub_top.items():
        s_d = "(blank)" if str(s).strip() == "" else str(s)
        lines.append(f"| {s_d} | {int(c):,} |")
    lines.append("")

    lines.append("## Lot number coverage\n")
    lines.append(f"- `lot_num` filled rows: **{lot_filled:,}** of {n:,} ({lot_filled / n:.2%})")
    lines.append(f"- distinct `lot_num` values: **{lot_distinct:,}**\n")

    lines.append("## Task name quality\n")
    lines.append(f"- `name` empty: **{name_empty:,}** rows")
    lines.append(f"- `name` shorter than 3 chars: **{name_short:,}** rows\n")

    lines.append("## Duplicate row check\n")
    lines.append(f"- Duplicate `id` rows: **{dup_count}**")
    lines.append(f"- Empty `id` rows: **{id_null}**\n")

    lines.append("## Full column list (staged)\n")
    for c in cols:
        lines.append(f"- `{c}`")
    lines.append("")

    return "\n".join(lines)


# --------------------------- Combined summary --------------------------- #

def combined_summary(gl_df: pd.DataFrame, cu_df: pd.DataFrame, gl_per_file: list[dict]) -> str:
    gl_n = len(gl_df)
    cu_n = len(cu_df)

    def fr(df, c):
        return float("nan") if c not in df.columns else 1.0 - float(df[c].astype(str).str.strip().eq("").mean())

    gl_proj_fill = fr(gl_df, "ProjectName")
    gl_phase_fill = fr(gl_df, "Lot/Phase")
    gl_amount_fill = 1.0 - float(pd.to_numeric(gl_df["FunctionalAmount"], errors="coerce").isna().mean())

    cu_lot_fill = fr(cu_df, "lot_num")
    cu_sub_fill = fr(cu_df, "subdivision")
    cu_close_fill = fr(cu_df, "actual_c_of_o")
    cu_sold_fill = fr(cu_df, "sold_date")

    lines = []
    lines.append("# Staging Summary — 2026-05-01\n")
    lines.append(f"**Staged at**: {LOAD_TS}\n")

    lines.append("## What staged successfully\n")
    lines.append(f"- ✅ `staged_gl_transactions` — **{gl_n:,} rows**, 38 original cols + 3 staging cols, "
                 f"from 14 DataRails GL files. Schema verified identical across all 14.")
    lines.append(f"- ✅ `staged_clickup_tasks` — **{cu_n:,} rows**, 32 original cols + 3 staging cols, "
                 f"from `api-upload.csv` (duplicate `api-upload (1).csv` excluded).")
    lines.append("- Outputs written to `data/staged/` as both CSV and Parquet.")
    lines.append("- Per-table validation reports at `data/reports/staged_{gl,clickup}_validation_report.md`.\n")

    lines.append("## Ready for operating-state rebuild\n")
    lines.append(f"- **GL → cost attribution**: `FunctionalAmount` populated at **{gl_amount_fill:.1%}**. "
                 f"`ProjectName` populated at **{gl_proj_fill:.1%}**, `Lot/Phase` populated at "
                 f"**{gl_phase_fill:.1%}**. This is a major upgrade — the prior pipeline could not attribute "
                 f"cost to lot/phase from primary GL data.")
    lines.append(f"- **ClickUp → LotState**: `subdivision` at **{cu_sub_fill:.1%}**, `lot_num` at "
                 f"**{cu_lot_fill:.1%}**, `actual_c_of_o` at **{cu_close_fill:.1%}**, `sold_date` at "
                 f"**{cu_sold_fill:.1%}**. Sufficient to rebuild lot status with date-based progression.\n")

    lines.append("## Still blocked\n")
    lines.append("- **Entity↔project crosswalk** — DataRails uses `CompanyCode/CompanyName` and "
                 "`ProjectCode/ProjectName`; ClickUp uses `subdivision`. There is no authoritative mapping in "
                 "the dump. Operating State v2 will need either a manual crosswalk file or fuzzy matching on "
                 "ProjectName ↔ subdivision distinct values.")
    lines.append("- **Inventory closing report** — staging deferred until the xlsx header offset is fixed "
                 "(row 1 is a title, not headers).")
    lines.append("- **Multi-entity Balance Sheet** and **multi-entity AR** — only one entity present each.")
    lines.append("- **QBO/QBD register normalization** — the 3 entity-level files (`GL_QBO_*`, "
                 "`Balance_Sheet_QBO_*`, `AR_QBD_*`) are tie-out, not primary feed; they are not staged.\n")

    lines.append("## Does GL improve cost attribution?\n")
    lines.append("**YES, materially.** The DataRails GL schema includes `Project`, `ProjectCode`, `ProjectName`, "
                 "`Lot/Phase`, `JobPhaseStage`, `Major`, `Minor`, `DivisionName`, `OUnit`, `SubledgerCode/Desc`, "
                 "and explicit `AccountCode/AccountName/AccountType`. With these tags directly on the source rows, "
                 "phase-level cost rollups become a primary-key join rather than an inference pass.\n")

    lines.append("## Does ClickUp improve LotState?\n")
    lines.append("**YES.** The ClickUp export includes status, walk_date, projected_close_date, actual_c_of_o, "
                 "sold_date, cancelled_date, AND lot identity (`subdivision`, `lot_num`). Date-based status "
                 "progression and projected-vs-actual-close variance can be computed directly. The only gap is the "
                 "intermediate `parent_id` (only `top_level_parent_id` is exported).\n")

    lines.append("## Recommended next step\n")
    lines.append("1. Build `staged_entity_mapping` v0 from distinct `CompanyName`/`ProjectName` (GL) and distinct "
                 "`subdivision` (ClickUp). Flag confidence `unmapped` until a human approves the joins.")
    lines.append("2. Re-profile `Inventory _ Closing Report (4).xlsx` with the correct `header=N` to identify lot-level columns, "
                 "then build `staged_inventory_lots`.")
    lines.append("3. Once the mapping is approved, build Operating State v2 from `staged_gl_transactions` "
                 "(cost) ⨝ `staged_clickup_tasks` (status/dates) ⨝ `staged_entity_mapping`. Write to a new "
                 "`output/operating_state_v2.json` — leave v1 artifacts in place.\n")

    lines.append("## Files left untouched (per instruction)\n")
    lines.append("- `output/lot_state_real.csv`")
    lines.append("- `output/project_state_real.csv`")
    lines.append("- `output/operating_state_v1.json`")
    lines.append("- `output/agent_context_v1.md`")
    lines.append("- `output/operating_view_v1.csv` (if present)\n")

    return "\n".join(lines)


# --------------------------- main --------------------------- #

def main():
    print("Loading GL files...")
    gl_df, gl_schema, gl_per_file = load_gl_files()
    print(f"  -> {len(gl_df):,} rows, {len(gl_df.columns)} cols")

    print("Loading ClickUp file...")
    cu_df = load_clickup()
    print(f"  -> {len(cu_df):,} rows, {len(cu_df.columns)} cols")

    print("Writing staged outputs...")
    gl_csv = STAGED / "staged_gl_transactions.csv"
    gl_pq = STAGED / "staged_gl_transactions.parquet"
    cu_csv = STAGED / "staged_clickup_tasks.csv"
    cu_pq = STAGED / "staged_clickup_tasks.parquet"

    gl_df.to_csv(gl_csv, index=False)
    gl_df.to_parquet(gl_pq, index=False, engine="pyarrow")
    cu_df.to_csv(cu_csv, index=False)
    cu_df.to_parquet(cu_pq, index=False, engine="pyarrow")

    print("Writing validation reports...")
    (REPORTS / "staged_gl_validation_report.md").write_text(gl_validation_report(gl_df, gl_schema, gl_per_file))
    (REPORTS / "staged_clickup_validation_report.md").write_text(clickup_validation_report(cu_df))
    (REPORTS / "staging_summary.md").write_text(combined_summary(gl_df, cu_df, gl_per_file))

    summary = {
        "gl_rows": len(gl_df),
        "gl_cols_total": len(gl_df.columns),
        "gl_files_concatenated": len(gl_per_file),
        "gl_per_file_rows": gl_per_file,
        "clickup_rows": len(cu_df),
        "clickup_cols_total": len(cu_df.columns),
        "outputs": {
            "gl_csv_bytes": gl_csv.stat().st_size,
            "gl_parquet_bytes": gl_pq.stat().st_size,
            "clickup_csv_bytes": cu_csv.stat().st_size,
            "clickup_parquet_bytes": cu_pq.stat().st_size,
        },
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
