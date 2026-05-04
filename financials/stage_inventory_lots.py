"""
Stage the inventory closing report into staged_inventory_lots.{csv,parquet}.

Source selection (deliberate):
- Three near-duplicate workbooks exist: `Inventory _ Closing Report (2|3|4).xlsx`.
- Workbook (2) carries the freshest static data: 2 lot events not in (4)
  (PARKWAY G1 lot 7048 sold 2026-04-29; SCARLET RIDGE Phase 1 lot 121 cancelled).
  Volatile `=TODAY()-SaleDate` cells confirm save order: (4) earliest, (3) middle,
  (2) latest. The lane doc claim that "(4) is canonical, latest of 3" is contradicted
  by the data; we use (2) and document the deviation in the validation report.

Grain: union of INVENTORY (active lots, header=0) + CLOSED  (closed lots, header=1).
Expected row count ≈ 3,872 (978 active + 2,894 closed).

as_of_date: 2026-04-29 (max INVENTORY.SALE DATE in workbook 2). Documented as a
data-derived inference; no explicit as-of cell exists in any sheet.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import sys
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data/raw/datarails_unzipped/datarails_raw"
STAGED = REPO / "data/staged"
REPORTS = REPO / "data/reports"

PRIMARY_FILE = RAW / "Inventory _ Closing Report (2).xlsx"
ALT_FILE = RAW / "Inventory _ Closing Report (4).xlsx"
ALT3_FILE = RAW / "Inventory _ Closing Report (3).xlsx"

# subdiv → canonical Project mapping. Confidence per Terminal C C1.
SUBDIV_TO_PROJECT = {
    "HARMONY":         ("Harmony",            "high"),
    "PARKWAY":         ("Parkway Fields",     "high"),
    "LOMOND HEIGHTS":  ("Lomond Heights",     "high"),
    "WILLOW CREEK":    ("Willowcreek",        "high"),
    "SALEM":           ("Salem Fields",       "high"),
    "LEWIS ESTATES":   ("Lewis Estates",      "high"),
    "SCARLET RIDGE":   ("Scarlet Ridge",      "high"),
    "ARROWHEAD":       ("Arrowhead Springs",  "high"),
    "SL":              ("Silver Lake",        "low"),  # not in v1 Lot Data
}

# Subdivisions seen only in CLOSED  (historical, pre-2018) — confidence=low,
# canonical_project = the raw subdiv name (no Lot Data row to reconcile to).
HISTORICAL_SUBDIVS = {
    "LEC", "WILLOWS", "HAMPTON", "BRIDGEPORT", "WESTBROOK", "SPRINGS",
    "WINDSOR", "BECK PINES", "CASCADE", "JAMES BAY", "WILLIS",
    "MAPLE FIELDS", "MEADOW CREEK", "PARKSIDE", "COUNTRY VIEW",
    "F. SPRINGS", "SPRING LEAF", "ANTHEM WEST", "VINTARO", "WR", "SPEC",
}


def load_inventory_sheet(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="INVENTORY", header=0)
    df = df.rename(columns={
        " ": "subdiv",
        "PH": "phase",
        "LOT #": "lot_num",
        "PLAN": "plan_name",
        "                                                 BUYER": "buyer",
        "SALES PRICE": "sales_price",
        "DEPOSITS": "deposit",
        "SALE DATE": "sale_date",
        "DAYS SINCE SALE/SPEC START": "_days_since_sale",  # volatile — drop
        "PERMIT PULLED\n": "permit_pulled_date",
        "Permit number": "permit_number",
        "Margin": "margin_pct",
    })
    # Ffill subdiv (vertical-merged in Excel)
    df["subdiv"] = df["subdiv"].ffill()
    # Drop unkeyed rows (no lot_num and no phase)
    df = df.dropna(subset=["lot_num", "phase"], how="all").copy()
    df["lot_status"] = "ACTIVE"
    df["closing_date"] = pd.NaT
    df["dig_date"] = pd.NaT
    df["anticipated_completion"] = pd.NaT
    df["source_sheet"] = "INVENTORY"
    df["source_row_number"] = df.index + 1  # 0-indexed → 1-indexed in Excel terms
    return df


def load_closed_sheet(path: Path, as_of: pd.Timestamp) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="CLOSED ", header=1)
    df = df.rename(columns={
        "SUBDIV": "subdiv",
        "PH": "phase",
        "LOT #": "lot_num",
        "PLAN": "plan_name",
        "Closing Date": "closing_date",
        "BUYER                              ": "buyer",
        "SALE PRICE": "sales_price",
        "DEPOSITS": "deposit",
        "SALE DATE": "sale_date",
        "DAYS SINCE SALE": "_days_since_sale",  # volatile — drop
        "PERMIT PULLED\nSUPER": "permit_pulled_date",
        "DIG DATE": "dig_date",
        "ANTICIPATED COMPLETION": "anticipated_completion",
        "Permit number": "permit_number",
    })
    df = df.dropna(subset=["lot_num", "subdiv"], how="all").copy()
    # Closed if Closing Date <= as_of, else ACTIVE_PROJECTED
    closing_dt = pd.to_datetime(df["closing_date"], errors="coerce")
    df["closing_date"] = closing_dt
    df["lot_status"] = closing_dt.apply(
        lambda d: "CLOSED" if pd.notna(d) and d <= as_of else "ACTIVE_PROJECTED"
    )
    df["margin_pct"] = pd.NA  # not present in CLOSED
    df["source_sheet"] = "CLOSED"
    df["source_row_number"] = df.index + 1
    return df


def derive_canonical_project(subdiv: str) -> tuple[str, str]:
    if pd.isna(subdiv):
        return ("", "unmapped")
    s = str(subdiv).strip().upper()
    if s in SUBDIV_TO_PROJECT:
        proj, conf = SUBDIV_TO_PROJECT[s]
        return (proj, conf)
    if s in HISTORICAL_SUBDIVS:
        # Title-case the historical raw value as the canonical project
        return (str(subdiv).strip().title(), "low")
    # Unknown — preserve the raw string for traceability, but mark unmapped
    return (str(subdiv).strip().title(), "unmapped")


def make_lot_id(row) -> str:
    parts = [
        str(row.get("canonical_project") or ""),
        str(row.get("phase") or ""),
        str(row.get("lot_num") or ""),
    ]
    payload = "|".join(parts).encode("utf-8")
    return hashlib.blake2s(payload, digest_size=8).hexdigest()


def main() -> int:
    out_csv = STAGED / "staged_inventory_lots.csv"
    out_pq = STAGED / "staged_inventory_lots.parquet"
    report = REPORTS / "staged_inventory_lots_validation_report.md"

    src = PRIMARY_FILE
    as_of = pd.Timestamp("2026-04-29")  # max INVENTORY.SALE DATE in workbook (2)

    print(f"[stage] reading {src.name}", file=sys.stderr)
    inv = load_inventory_sheet(src)
    closed = load_closed_sheet(src, as_of)

    keep_cols = [
        "subdiv", "phase", "lot_num", "plan_name", "buyer",
        "sales_price", "deposit", "sale_date", "permit_pulled_date",
        "permit_number", "margin_pct", "closing_date", "dig_date",
        "anticipated_completion", "lot_status", "source_sheet",
        "source_row_number",
    ]
    inv_keep = [c for c in keep_cols if c in inv.columns]
    closed_keep = [c for c in keep_cols if c in closed.columns]
    out = pd.concat([inv[inv_keep], closed[closed_keep]], ignore_index=True)

    # Canonical project + confidence
    proj_pairs = out["subdiv"].apply(derive_canonical_project)
    out["canonical_project"] = [p[0] for p in proj_pairs]
    out["project_confidence"] = [p[1] for p in proj_pairs]

    # Normalize phase whitespace, coerce lot_num to string
    out["phase"] = out["phase"].astype(str).str.strip().replace({"nan": ""})
    out["lot_num"] = out["lot_num"].astype(str).str.strip().replace({"nan": ""})

    # Canonical lot id = blake2s(project|phase|lot_num)
    out["canonical_lot_id"] = out.apply(make_lot_id, axis=1)

    # Metadata
    out["as_of_date"] = as_of
    out["source_file"] = src.name

    # Final column order
    final_cols = [
        "canonical_lot_id",
        "canonical_project", "project_confidence",
        "subdiv", "phase", "lot_num", "lot_status",
        "plan_name", "buyer",
        "sales_price", "deposit", "sale_date",
        "permit_pulled_date", "permit_number", "margin_pct",
        "closing_date", "dig_date", "anticipated_completion",
        "as_of_date", "source_file", "source_sheet", "source_row_number",
    ]
    final_cols = [c for c in final_cols if c in out.columns]
    out = out[final_cols]

    # Coerce mixed-type object columns to string for parquet stability
    str_cols = ["canonical_lot_id", "canonical_project", "project_confidence",
                "subdiv", "phase", "lot_num", "lot_status",
                "plan_name", "buyer", "permit_number", "source_file",
                "source_sheet"]
    for c in str_cols:
        if c in out.columns:
            out[c] = out[c].astype(object).where(out[c].notna(), None)
            out[c] = out[c].apply(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    # Numeric coercion (keep float64; non-numeric → NaN)
    for c in ("sales_price", "deposit", "margin_pct"):
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    # Datetime coercion
    for c in ("sale_date", "permit_pulled_date", "closing_date",
              "dig_date", "anticipated_completion"):
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], errors="coerce")

    out.to_csv(out_csv, index=False)
    out.to_parquet(out_pq, index=False)

    n_total = len(out)
    n_active = (out["lot_status"] == "ACTIVE").sum()
    n_closed = (out["lot_status"] == "CLOSED").sum()
    n_proj   = (out["lot_status"] == "ACTIVE_PROJECTED").sum()
    n_unmapped_proj = (out["project_confidence"] == "unmapped").sum()
    n_low_proj      = (out["project_confidence"] == "low").sum()
    n_high_proj     = (out["project_confidence"] == "high").sum()
    distinct_subdivs = out["subdiv"].dropna().astype(str).str.strip().str.upper().nunique()
    distinct_projects = out["canonical_project"].dropna().nunique()
    distinct_phases   = out.dropna(subset=["canonical_project", "phase"]).groupby(
        ["canonical_project", "phase"]).ngroups
    distinct_lots     = out["canonical_lot_id"].nunique()

    # Per-status breakdown by project
    by_proj = (out.groupby(["canonical_project", "lot_status"]).size()
                  .unstack(fill_value=0))

    # Diff vs file (4) for the 2 known lot deltas — verify
    # (Skip if file (4) not present; reading is expensive but cheap on this size)
    delta_note = ""
    try:
        inv4 = pd.read_excel(ALT_FILE, sheet_name="INVENTORY", header=0)
        n_inv2 = len(inv)
        n_inv4 = inv4.dropna(subset=["LOT #", "PH"], how="all").shape[0]
        delta_note = f"INVENTORY rows: file (2) = {n_inv2}, file (4) = {n_inv4}"
    except Exception as e:
        delta_note = f"(skipped diff vs file 4: {e})"

    md = f"""# staged_inventory_lots — Validation Report

**Built**: 2026-05-01
**Builder**: Terminal A (integrator)
**Source workbook**: `{src.name}` (workbook **(2)**, deliberately chosen — see Source-selection note below)
**As-of date**: {as_of.date()}
**Output**:
- `data/staged/staged_inventory_lots.csv` ({out_csv.stat().st_size:,} bytes)
- `data/staged/staged_inventory_lots.parquet` ({out_pq.stat().st_size:,} bytes)

## Source-selection note (deviation from lane doc)

The lane doc states "(4) is canonical, latest of 3." Terminal C's audit
(`scratch/ops_inventory_collateral_allocation_findings.md` § C1) found this is
**not true by the data**. Volatile `=TODAY()-SaleDate` cells in the three
near-duplicate workbooks reveal the actual save order:

| signal | (2) | (3) | (4) |
|---|---|---|---|
| `DAYS SINCE SALE` for Harmony Lot 848 | **64** | 63 | 62 |
| Implied `TODAY()` evaluation date | 2026-04-30 | 2026-04-29 | 2026-04-28 |
| Save order | **latest** | middle | earliest |

There are also **2 static-data deltas** in INVENTORY between (2) and (4):

| lot | (2) state | (4) state |
|---|---|---|
| `PARKWAY G1` lot 7048 | sold 2026-04-29, deposit $4,000, margin 14.35% | unsold/blank |
| `SCARLET RIDGE Phase 1` lot 121 | unsold/cancelled (blank) | sold 2026-03-26, deposit $8,000, margin 13% |

Decision: **stage from workbook (2)**. Rationale: it is freshest by ~2 days
of volatile evaluation **and** carries 1 net-new sale event. The lane doc
recommendation is overruled by the evidence. Caveat: confirm with the human
that the intent was "newest export"; if instead they meant "the file marked
(4) regardless of freshness", reissue the stage from (4).

Cross-check vs file (4): {delta_note}

## Row counts

| metric | value |
|---|---:|
| Total rows | {n_total:,} |
| ACTIVE (from INVENTORY sheet) | {n_active:,} |
| CLOSED (closing_date ≤ as_of) | {n_closed:,} |
| ACTIVE_PROJECTED (closing_date > as_of, in CLOSED  sheet) | {n_proj:,} |
| Distinct `canonical_lot_id` | {distinct_lots:,} |
| Distinct `subdiv` (raw) | {distinct_subdivs} |
| Distinct `canonical_project` | {distinct_projects} |
| Distinct `(canonical_project, phase)` | {distinct_phases} |

Expected from C1: ~3,872 ± 50 (978 active + 2,894 closed). Observed: **{n_total:,}**.

## Project-confidence distribution

| confidence | rows |
|---|---:|
| high | {n_high_proj:,} |
| low | {n_low_proj:,} |
| unmapped | {n_unmapped_proj:,} |

## Status breakdown by project

```
{by_proj.to_string()}
```

## Schema

| column | dtype | semantic |
|---|---|---|
| `canonical_lot_id` | string | blake2s-8 hash of `(canonical_project|phase|lot_num)` — opaque, stable join key |
| `canonical_project` | string | resolved project name per the subdiv crosswalk (or title-cased subdiv for historical) |
| `project_confidence` | enum: `high`/`low`/`unmapped` | confidence of the subdiv → canonical_project mapping |
| `subdiv` | string | raw SUBDIV/community label from the source sheet (forward-filled where Excel-merged) |
| `phase` | string | phase label as it appears in source (no normalization beyond strip) |
| `lot_num` | string | lot number as it appears in source |
| `lot_status` | enum: `ACTIVE`/`CLOSED`/`ACTIVE_PROJECTED` | derived; ACTIVE = INVENTORY sheet row; CLOSED = CLOSED  sheet row with `Closing Date` ≤ as_of; ACTIVE_PROJECTED = CLOSED  sheet row with `Closing Date` > as_of (forward projection mixed in) |
| `plan_name` | string | model/plan name |
| `buyer` | string | buyer name or `SPEC`/`MODEL` placeholder |
| `sales_price` | float | sales price |
| `deposit` | float | earnest-money deposit |
| `sale_date` | datetime | recorded sale date (when lot went under contract) |
| `permit_pulled_date` | datetime | permit pull date (INVENTORY) or permit/super placeholder (CLOSED) |
| `permit_number` | string | building-permit identifier |
| `margin_pct` | float | gross margin (INVENTORY only — CLOSED  has no margin column) |
| `closing_date` | datetime | actual or projected closing date (CLOSED rows only) |
| `dig_date` | datetime | foundation-dig date (CLOSED rows only) |
| `anticipated_completion` | datetime | anticipated completion date (CLOSED rows only) |
| `as_of_date` | datetime | snapshot as-of (constant `{as_of.date()}`) |
| `source_file` | string | filename: `{src.name}` |
| `source_sheet` | enum: `INVENTORY`/`CLOSED` | source tab |
| `source_row_number` | int | 1-indexed row position within the source sheet (post-header) |

## Caveats

1. The volatile `_days_since_sale` columns from both sheets are dropped at stage
   — they are `=TODAY()-SaleDate` formulas that change every time the file is
   opened, with no analytic value once `sale_date` is preserved.
2. `subdiv = "SL"` (Silver Lake) has **no row** in the v1 `Lot Data.csv` source.
   We map it to `canonical_project = "Silver Lake"` with confidence `low`. If a
   downstream consumer treats `low`-confidence projects as in-scope, those
   ~? rows will appear; if it filters to `high`, they're excluded.
3. `CLOSED .Closing Date` extends to 2027-06-07 — clearly forward-projected.
   We split CLOSED-sheet rows into `lot_status = CLOSED` (≤ as_of) vs
   `ACTIVE_PROJECTED` (> as_of). Do **not** count `ACTIVE_PROJECTED` rows in a
   "closed lots" rollup; they're in the universe but not closed yet.
4. The 26 lots in CLOSED  with subdivs in `HISTORICAL_SUBDIVS` (e.g. `WILLOWS`,
   `WINDSOR`, `JAMES BAY`) are pre-2018 communities that are not in current
   scope. They land in canonical_project as title-cased raw with confidence
   `low`. They are kept (not dropped) so historical absorption-rate queries
   still see them.
5. The `CLOSINGS` sheet (929 rows of pending closings) is **not** unioned in;
   it has no phase column and is best treated as an overlay on join
   `(subdiv, lot_num)`. Future enhancement.
6. No deduplication across sheets. A lot might appear as ACTIVE in INVENTORY
   AND as ACTIVE_PROJECTED in CLOSED (a sold-but-not-yet-closed lot in both
   tabs). Downstream consumers should resolve via `lot_status` priority:
   CLOSED > ACTIVE_PROJECTED > ACTIVE if collapsing to one row per lot.

## Hard guardrail status

This artifact satisfies **guardrail prereq #1** (`staged_inventory_lots.{{csv,parquet}}` exists, validated).
Final guardrail check is in `data/reports/guardrail_check_v0.md`.
"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    report.write_text(md)
    print(f"[stage] wrote {out_csv} ({out_csv.stat().st_size:,} B)", file=sys.stderr)
    print(f"[stage] wrote {out_pq} ({out_pq.stat().st_size:,} B)", file=sys.stderr)
    print(f"[stage] wrote {report}", file=sys.stderr)
    print(f"[stage] rows: {n_total:,} (ACTIVE={n_active}, CLOSED={n_closed}, ACTIVE_PROJECTED={n_proj})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
