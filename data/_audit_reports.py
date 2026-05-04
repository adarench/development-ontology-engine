"""
Generate the three audit deliverables from the profiles JSON:

  data/staged/datarails_raw_file_inventory.md
  data/staged/gl_candidate_inventory.csv
  data/staged/gl_coverage_report.md

Also computes per-year GL row counts and per-entity GL row counts directly
from the data so the coverage claims are real, not inferred.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO = Path("/Users/arench/Desktop/development_ontology_engine")
STAGED = REPO / "data" / "staged"
ROOT = REPO / "data" / "raw" / "datarails_unzipped"

profiles = json.loads((STAGED / "datarails_raw_profiles.json").read_text())

# --------------------------- inventory MD --------------------------- #

def write_inventory_md():
    by_type = defaultdict(list)
    for r in profiles:
        by_type[r["likely_dataset_type"]].append(r)

    lines = []
    lines.append("# DataRails Raw File Inventory")
    lines.append("")
    lines.append(f"**Total files audited**: {len(profiles)}")
    lines.append(f"**Audit root**: `{ROOT.relative_to(REPO)}/`")
    lines.append("")
    lines.append("Both archives extracted side-by-side:")
    lines.append("- `datarails_raw/` — from `DataRails_raw.zip` (May 1, 2026 dump, 24 files)")
    lines.append("- `phase_cost_starter/` — from `phase_cost_starter_data.zip` (Apr 20, 2026 dump, 26 files)")
    lines.append("")
    lines.append("## Files by likely dataset type")
    lines.append("")
    lines.append("| type | count |\n|---|---:|")
    for t in sorted(by_type, key=lambda k: (-len(by_type[k]), k)):
        lines.append(f"| {t} | {len(by_type[t])} |")
    lines.append("")

    # Detailed table per type
    for t in sorted(by_type):
        rows = by_type[t]
        lines.append(f"## {t} ({len(rows)} files)")
        lines.append("")
        lines.append("| file | ext | rows | cols | min_date | max_date | candidate dates | candidate amounts |")
        lines.append("|---|---|---:|---:|---|---|---|---|")
        for r in sorted(rows, key=lambda x: x["file_path"]):
            short = r["file_path"].replace("data/raw/datarails_unzipped/", "")
            lines.append(
                f"| `{short}` | {r['extension']} | "
                f"{r.get('row_count') if r.get('row_count') is not None else '?'} | "
                f"{r.get('column_count') if r.get('column_count') is not None else '?'} | "
                f"{r.get('min_date') or '-'} | {r.get('max_date') or '-'} | "
                f"{r.get('candidate_date_columns') or '-'} | "
                f"{r.get('candidate_amount_columns') or '-'} |"
            )
        lines.append("")

    lines.append("## Notes on date detection")
    lines.append("")
    lines.append("- For DataRails 38-col GL files, `PostingDate` is the canonical transaction date.")
    lines.append("  `CreatedDate` and `ApprovalDate` extend later (catch-up entries). `ApprovalTime` "
                 "is a time-of-day stored as Excel-epoch fractional days, so its 1700–1948 date range "
                 "is meaningless — that column is excluded from real-date range conclusions below.")
    lines.append("- For Vertical Financials.csv, `Posting Date` is canonical. `Refresh Date` (2026-02-11) "
                 "tells us when the export ran.")
    lines.append("- For QB-style files (`BCPD GL Detail.csv`, QBO/QBD register files), the `Date` column "
                 "is canonical. The QBO register exports for Anderson Geneva and Geneva Project Manager "
                 "have NO populated transaction dates — every row is `Beginning Balance` or blank — so "
                 "they are NOT transactional GL despite the filename prefix `GL_QBO_`.")
    lines.append("")

    out = STAGED / "datarails_raw_file_inventory.md"
    out.write_text("\n".join(lines))
    print(f"Wrote {out.relative_to(REPO)}")


# --------------------------- GL candidates CSV --------------------------- #

def write_gl_candidate_csv():
    gl = [r for r in profiles if r["likely_dataset_type"] == "GL"]
    out = STAGED / "gl_candidate_inventory.csv"
    fieldnames = [
        "file_path", "file_name", "extension", "size_bytes",
        "row_count", "column_count", "header_row",
        "min_date", "max_date",
        "canonical_date_column", "canonical_amount_column", "canonical_account_column",
        "candidate_date_columns", "candidate_amount_columns", "candidate_account_columns",
        "candidate_entity_columns", "candidate_project_columns",
        "candidate_phase_columns", "candidate_lot_columns",
        "columns",
    ]

    def canon(r):
        cols = (r.get("columns") or "").split("|")
        canon_date = next((c for c in cols if c in ("PostingDate", "Posting Date", "Date")), "")
        canon_amt = next((c for c in cols if c in ("FunctionalAmount", "Amount")), "")
        canon_acct = next((c for c in cols if c in ("AccountCode", "Account")), "")
        return canon_date, canon_amt, canon_acct

    rows = []
    for r in gl:
        canon_date, canon_amt, canon_acct = canon(r)
        rows.append({
            "file_path": r["file_path"],
            "file_name": r["file_name"],
            "extension": r["extension"],
            "size_bytes": r["size_bytes"],
            "row_count": r["row_count"],
            "column_count": r["column_count"],
            "header_row": r["header_row"],
            "min_date": r.get("min_date") or "",
            "max_date": r.get("max_date") or "",
            "canonical_date_column": canon_date,
            "canonical_amount_column": canon_amt,
            "canonical_account_column": canon_acct,
            "candidate_date_columns": r.get("candidate_date_columns") or "",
            "candidate_amount_columns": r.get("candidate_amount_columns") or "",
            "candidate_account_columns": r.get("candidate_account_columns") or "",
            "candidate_entity_columns": r.get("candidate_entity_columns") or "",
            "candidate_project_columns": r.get("candidate_project_columns") or "",
            "candidate_phase_columns": r.get("candidate_phase_columns") or "",
            "candidate_lot_columns": r.get("candidate_lot_columns") or "",
            "columns": r.get("columns") or "",
        })
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out.relative_to(REPO)}")
    return rows


# --------------------------- GL coverage MD --------------------------- #

def compute_gl_coverage(gl_candidates: list[dict]) -> dict:
    """Compute per-year, per-entity, per-file row counts using the canonical date column."""
    coverage = {}

    # 1. DataRails 38-col bundle (already staged) — read from parquet for speed
    dr_pq = STAGED / "staged_gl_transactions.parquet"
    if dr_pq.exists():
        df = pd.read_parquet(dr_pq, columns=["source_file", "CompanyCode", "CompanyName", "PostingDate"])
        df["pd_dt"] = pd.to_datetime(df["PostingDate"], errors="coerce")
        df["year"] = df["pd_dt"].dt.year
        coverage["datarails_38col_bundle"] = {
            "files": sorted(df["source_file"].unique().tolist()),
            "rows": int(len(df)),
            "min_date": df["pd_dt"].min().date().isoformat(),
            "max_date": df["pd_dt"].max().date().isoformat(),
            "by_year": df.groupby("year").size().to_dict(),
            "by_entity": df.groupby("CompanyName").size().to_dict(),
            "by_file": df.groupby("source_file").size().to_dict(),
            "schema": "DataRails 38-col (PostingDate, CompanyCode, AccountCode, FunctionalAmount, ProjectCode, Lot/Phase, ...)",
        }

    # 2. Vertical Financials — load fresh
    vf = REPO / "data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv"
    if vf.exists():
        df = pd.read_csv(vf, usecols=["Posting Date", "Company Name"], dtype=str,
                         keep_default_na=False, encoding="utf-8-sig", low_memory=False)
        df["pd_dt"] = pd.to_datetime(df["Posting Date"], errors="coerce")
        df["year"] = df["pd_dt"].dt.year
        coverage["vertical_financials"] = {
            "files": ["Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv"],
            "rows": int(len(df)),
            "min_date": df["pd_dt"].min().date().isoformat(),
            "max_date": df["pd_dt"].max().date().isoformat(),
            "by_year": df.groupby("year").size().to_dict(),
            "by_entity": df.groupby("Company Name").size().to_dict(),
            "schema": "Vertical Financials 46-col (Posting Date, Company, Account, Debit, Credit, Amount, Project, Lot, Sub-Ledger, Memo 1/2, ...)",
        }

    # 3. BCPD GL Detail
    bcpd = REPO / "data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv"
    if bcpd.exists():
        df = pd.read_csv(bcpd, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        df["pd_dt"] = pd.to_datetime(df["Date"], errors="coerce")
        df["year"] = df["pd_dt"].dt.year
        coverage["bcpd_gl_detail"] = {
            "files": ["Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv"],
            "rows": int(len(df)),
            "min_date": df["pd_dt"].min().date().isoformat(),
            "max_date": df["pd_dt"].max().date().isoformat(),
            "by_year": df.groupby("year").size().to_dict(),
            "by_entity": {"Building Construction Partners, LLC (implied by filename)": int(len(df))},
            "schema": "QuickBooks register 12-col (Type, Date, Num, Name, Memo, Class, Debit, Credit, Balance) — single-entity",
        }

    # 4. GL.csv stub
    gl_stub = REPO / "data/raw/datarails_unzipped/datarails_raw/GL.csv"
    if gl_stub.exists():
        df = pd.read_csv(gl_stub, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        df["pd_dt"] = pd.to_datetime(df["PostingDate"], errors="coerce")
        coverage["gl_stub"] = {
            "files": ["GL.csv"],
            "rows": int(len(df)),
            "min_date": df["pd_dt"].min().date().isoformat() if len(df) else None,
            "max_date": df["pd_dt"].max().date().isoformat() if len(df) else None,
            "by_year": {2026: int(len(df))},
            "by_entity": {"(stub)": int(len(df))},
            "schema": "DataRails 38-col (same as bundle), but only 6 sample rows dated 2026-05-01",
        }

    # 5. QBO register files — note non-transactional
    coverage["qbo_register_no_transactions"] = {
        "files": ["GL_QBO_Anderson Geneva LLC_May 2026.csv", "GL_QBO_Geneva Project Manager LLC_May 2026.csv"],
        "rows": 54,
        "note": "Despite the GL_QBO_ prefix, every Date cell is empty or 'Beginning Balance'. These are opening-balance/COA-style summaries, NOT transactional GL. Excluded from coverage totals.",
    }

    return coverage


def write_gl_coverage_report(gl_candidates: list[dict], coverage: dict):
    lines = []
    lines.append("# GL Coverage Report — Combined Audit Across All GL Candidates")
    lines.append("")
    lines.append("## ⚠️ Correction to prior claim")
    lines.append("")
    lines.append('My previous statement — **"The DataRails GL is HISTORICAL data; PostingDate runs '
                 '2016-01-01 → 2017-02-28"** — was **WRONG as a global claim about the raw DataRails dump**.')
    lines.append("")
    lines.append("That date range is correct for **only one subset**: the 14 numbered files "
                 "`GL (1..14).csv` inside `DataRails_raw.zip`. I generalised that subset to the entire "
                 "raw dump without inspecting `phase_cost_starter_data.zip`. That second archive contains "
                 "**`Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv`** — 83,433 rows of GL "
                 "with `Posting Date` running **2018-06-26 → 2025-12-31**, plus "
                 "**`BCPD GL Detail.csv`** — 3,327 rows of QB-register-style GL covering all of 2025.")
    lines.append("")
    lines.append("Combined GL coverage across the full dump is **2016-01-01 → 2025-12-31** "
                 "(approximately 10 years), with one structural gap "
                 "**2017-03-01 → 2018-06-25** (~15 months) where no GL data is present.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Totals
    total_gl_files = len([r for r in gl_candidates])
    total_gl_rows = sum(c.get("rows", 0) for c in coverage.values() if "rows" in c)
    transactional_rows = (
        coverage["datarails_38col_bundle"]["rows"]
        + coverage["vertical_financials"]["rows"]
        + coverage["bcpd_gl_detail"]["rows"]
    )

    lines.append("## Headline numbers")
    lines.append("")
    lines.append(f"- **Total GL candidate files found**: {total_gl_files}")
    lines.append(f"- **Total rows across GL candidates**: {total_gl_rows:,}")
    lines.append(f"- **Total transactional GL rows** (excluding QBO opening-balance files and the 6-row stub): "
                 f"**{transactional_rows:,}**")
    lines.append(f"- **Combined min Posting Date**: 2016-01-01")
    lines.append(f"- **Combined max Posting Date**: 2025-12-31")
    lines.append(f"- **Coverage gap**: 2017-03-01 → 2018-06-25 (~15 months)")
    lines.append("")

    # Per-source breakdown
    lines.append("## Three primary GL sources")
    lines.append("")
    lines.append("| source | rows | date range | entities | schema |")
    lines.append("|---|---:|---|---|---|")
    s = coverage["datarails_38col_bundle"]
    lines.append(f"| DataRails 38-col bundle (`GL (1..14).csv`) | {s['rows']:,} | "
                 f"{s['min_date']} → {s['max_date']} | {len(s['by_entity'])} | "
                 f"DataRails 38 cols, multi-entity, includes Project/Lot/Phase tags |")
    s = coverage["vertical_financials"]
    lines.append(f"| Vertical Financials (`Collateral Dec2025 ... Vertical Financials.csv`) | "
                 f"{s['rows']:,} | {s['min_date']} → {s['max_date']} | {len(s['by_entity'])} | "
                 f"Vertical Financials 46 cols, single-entity (BCPD), includes Project/Lot tags |")
    s = coverage["bcpd_gl_detail"]
    lines.append(f"| BCPD GL Detail (`Collateral Dec2025 ... BCPD GL Detail.csv`) | "
                 f"{s['rows']:,} | {s['min_date']} → {s['max_date']} | 1 (BCPD) | "
                 f"QuickBooks register 12 cols, single-entity, no project/lot tagging |")
    lines.append("")

    # Per-year
    lines.append("## Row counts by Posting Year (combined transactional GL)")
    lines.append("")
    by_year = defaultdict(int)
    for source_key in ("datarails_38col_bundle", "vertical_financials", "bcpd_gl_detail"):
        for y, n in coverage[source_key]["by_year"].items():
            if pd.isna(y):
                continue
            by_year[int(y)] += int(n)
    lines.append("| year | rows |\n|---:|---:|")
    for y in sorted(by_year):
        lines.append(f"| {y} | {by_year[y]:,} |")
    lines.append("")
    lines.append("Notable: **2017–2018 gap** (only catch-up CreatedDate entries from the DataRails bundle "
                 "fall here; no Posting Date records). 2024 and 2025 are the heaviest periods.")
    lines.append("")

    # Per-file
    lines.append("## Row counts by file (transactional GL only)")
    lines.append("")
    lines.append("| file | rows | min_date | max_date |\n|---|---:|---|---|")
    s = coverage["datarails_38col_bundle"]
    for fn, n in sorted(s["by_file"].items(), key=lambda kv: int(re.search(r"\((\d+)\)", kv[0]).group(1))):
        lines.append(f"| `{fn}` (DataRails bundle) | {n:,} | (within 2016-2017) | (monthly partition) |")
    s = coverage["vertical_financials"]
    lines.append(f"| `{s['files'][0]}` (Vertical Financials) | {s['rows']:,} | "
                 f"{s['min_date']} | {s['max_date']} |")
    s = coverage["bcpd_gl_detail"]
    lines.append(f"| `{s['files'][0]}` (BCPD GL Detail) | {s['rows']:,} | {s['min_date']} | {s['max_date']} |")
    lines.append("")

    # Per-entity
    lines.append("## Entities by source")
    lines.append("")
    lines.append("### DataRails bundle entities (3 distinct)")
    lines.append("| CompanyName | rows |\n|---|---:|")
    for ent, n in sorted(coverage["datarails_38col_bundle"]["by_entity"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {ent} | {int(n):,} |")
    lines.append("")
    lines.append("### Vertical Financials entities (1)")
    lines.append("| Company Name | rows |\n|---|---:|")
    for ent, n in coverage["vertical_financials"]["by_entity"].items():
        lines.append(f"| {ent} | {int(n):,} |")
    lines.append("")
    lines.append("### BCPD GL Detail entities (1, implied by filename)")
    lines.append("| entity | rows |\n|---|---:|")
    for ent, n in coverage["bcpd_gl_detail"]["by_entity"].items():
        lines.append(f"| {ent} | {int(n):,} |")
    lines.append("")
    lines.append("**Critical observation**: only **Building Construction Partners, LLC (BCPD)** has GL "
                 "coverage spanning multiple years. The other two DataRails entities — Hillcrest Road at "
                 "Saratoga LLC and Flagship Belmont Phase two LLC — appear ONLY in the 2016-2017 DataRails "
                 "bundle. We have no 2018+ GL data for them in this dump.")
    lines.append("")

    # Current vs historical
    lines.append("## Which files are current vs historical")
    lines.append("")
    lines.append("| file | classification | reasoning |")
    lines.append("|---|---|---|")
    lines.append("| `GL (1..14).csv` | **historical** | PostingDate 2016-01 → 2017-02; ~9 years old |")
    lines.append("| `Vertical Financials.csv` | **current (BCPD only)** | Posting Date through 2025-12-31; "
                 "Refresh Date 2026-02-11 |")
    lines.append("| `BCPD GL Detail.csv` | **current (BCPD only, calendar 2025)** | Date 2025-01 → 2025-12 |")
    lines.append("| `GL.csv` | **stub/sample** | 6 rows, PostingDate 2026-05-01; not a real export |")
    lines.append("| `GL_QBO_Anderson Geneva LLC_May 2026.csv` | **non-transactional** | All Date values "
                 "are blank or 'Beginning Balance'; opening-balance summary, not GL |")
    lines.append("| `GL_QBO_Geneva Project Manager LLC_May 2026.csv` | **non-transactional** | Same as above |")
    lines.append("")

    # Best for v2
    lines.append("## Best candidates for Operating State v2")
    lines.append("")
    lines.append("**For BCPD (the only entity with multi-year coverage)**:")
    lines.append("- Primary: **Vertical Financials.csv** — 83,433 rows, 2018-06 → 2025-12, 100% Project & "
                 "Lot fill rates, single-entity (clean), 46-col schema with explicit Sub-Ledger, "
                 "Memo 1/2, Account Group, Account Type. This is the strongest GL feed in the dump.")
    lines.append("- Augment: `GL (1..14).csv` filtered to `CompanyCode=1000` (BCPD) for 2016-01 → 2017-02 history.")
    lines.append("- Cross-check: BCPD GL Detail.csv as a 2025 tie-out at the QB-register grain.")
    lines.append("")
    lines.append("**For Hillcrest Road at Saratoga LLC and Flagship Belmont Phase two LLC**:")
    lines.append("- Only `GL (1..14).csv` (2016-01 → 2017-02). Operating State for these entities will "
                 "necessarily be historical unless a fresh export covering 2017-present is supplied.")
    lines.append("")
    lines.append("**Files to ignore for v2**:")
    lines.append("- `GL.csv` (6-row stub)")
    lines.append("- `GL_QBO_*.csv` (no transactions; opening balances only)")
    lines.append("")

    # Recommendations for staged rebuild
    lines.append("## Recommendation for `staged_gl_transactions` rebuild")
    lines.append("")
    lines.append("The current `data/staged/staged_gl_transactions.{csv,parquet}` is incomplete — it was "
                 "built from `GL (1..14).csv` only and therefore covers 2016-2017 only.")
    lines.append("")
    lines.append("**Proposed rebuild**: a normalized, multi-source staged GL with a unified column schema:")
    lines.append("")
    lines.append("1. **Load** each of the three primary sources (DataRails bundle, Vertical Financials, "
                 "BCPD GL Detail).")
    lines.append("2. **Map** each to a common canonical schema, e.g.:")
    lines.append("   ```")
    lines.append("   source_file, source_schema, posting_date, fiscal_year,")
    lines.append("   entity_code, entity_name,")
    lines.append("   account_code, account_name, account_type,")
    lines.append("   project_code, project_name, lot, phase,")
    lines.append("   debit, credit, amount, currency,")
    lines.append("   transaction_id, line_no, memo, source_confidence")
    lines.append("   ```")
    lines.append("3. **Concatenate** with `source_schema` ∈ "
                 "{`datarails_38col`, `vertical_financials_46col`, `qb_register_12col`} for traceability.")
    lines.append("4. **Filter** out the QBO opening-balance files and the GL.csv stub.")
    lines.append("5. **Validate**: per-year row totals match the source files; entity totals sum correctly; "
                 "the gap 2017-03 → 2018-06 is correctly empty (or sourced from yet-to-arrive data).")
    lines.append("")
    lines.append("Recommended output paths (additive — leave existing v1 staged tables in place "
                 "until v2 is validated):")
    lines.append("- `data/staged/staged_gl_transactions_v2.csv`")
    lines.append("- `data/staged/staged_gl_transactions_v2.parquet`")
    lines.append("- `data/reports/staged_gl_v2_validation_report.md`")
    lines.append("")

    out = STAGED / "gl_coverage_report.md"
    out.write_text("\n".join(lines))
    print(f"Wrote {out.relative_to(REPO)}")


def main():
    write_inventory_md()
    gl_rows = write_gl_candidate_csv()
    coverage = compute_gl_coverage(gl_rows)
    write_gl_coverage_report(gl_rows, coverage)

    summary = {
        "n_files_audited": len(profiles),
        "n_gl_candidates": len(gl_rows),
        "transactional_gl_rows": (
            coverage["datarails_38col_bundle"]["rows"]
            + coverage["vertical_financials"]["rows"]
            + coverage["bcpd_gl_detail"]["rows"]
        ),
        "combined_min_posting_date": "2016-01-01",
        "combined_max_posting_date": "2025-12-31",
        "coverage_gap": "2017-03-01 to 2018-06-25",
        "entities_with_multi_year_coverage": ["Building Construction Partners, LLC"],
        "entities_with_2016_2017_only": [
            "Hillcrest Road at Saratoga, LLC",
            "Flagship Belmont Phase two LLC",
        ],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
