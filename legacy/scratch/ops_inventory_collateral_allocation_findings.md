# Terminal C — Ops / Inventory / Collateral / Allocation Findings

**Author**: Terminal C (Ops worker)
**Date**: 2026-05-01
**Audience**: Terminal A (integrator)
**Scope**: C1 Inventory closing report, C2 Collateral CSVs, C3 ClickUp lot-tagged subset, C4 Allocation workbooks, C5 source→entity feeding map.
**Status**: All four lanes inspected. C1 has an explicit stage proposal that Terminal A can execute as-is.

---

## C1 — Inventory closing report

### File set

`Inventory _ Closing Report (2).xlsx`, `(3).xlsx`, `(4).xlsx`, all under `data/raw/datarails_unzipped/datarails_raw/`. Each is **34 sheets**, byte-different but structurally identical (same sheet names, row counts, column counts on every tab).

### Diff (2) vs (3) vs (4) — which is "latest"

The lane doc said "(4) is canonical, latest of 3." **The data weakly contradicts this.** All three workbooks were saved on 2026-05-01 within seconds of each other (identical filesystem `mtime`), but volatile `=TODAY()-SaleDate` cells reveal the relative refresh order:

| sheet / cell | (2) | (3) | (4) |
|---|---|---|---|
| INVENTORY row 3 `DAYS SINCE SALE` for Harmony Lot 848 | 64 | 63 | **62** |
| INVENTORY row 4 `DAYS SINCE SALE` for Harmony Lot 1028 | 62 | 61 | **60** |

Smaller "days since" → earlier `TODAY()` evaluation. So **(4) was actually saved first (≈ 2026-04-28), (3) on 2026-04-29, (2) on 2026-04-30**. Per-lot static data is also marginally fresher in (2): two new lot events appear in (2) that aren't in (4):

- `PARKWAY G1 Lot 7048` — sold in (2) (sale date 2026-04-29, deposit $4k, margin 14.35%); blank in (4).
- `SCARLET RIDGE Phase 1 Lot 121` — has 2026-03-26 sale + $8k deposit + 13% margin in (4); blank/cancelled in (2).

**Recommendation**: stage from `(4)` per lane doc; flag the diff in the validation report. The two lot deltas are negligible for an `as_of = 2026-04-28` snapshot but Terminal A may want to revisit if intent was "newest export."

### Workbook structure

The lane doc's prior audit note ("title row at row 1 'Flagship Lot Inventory & Development Schedule', headers parse as `Unnamed: N`, header is likely 2 or 3") referred to the **summary** tab (`2026 Lot Inventory KS`), not the per-lot tabs. The per-lot data lives in three different sheets, each with its own header offset.

**Per-lot tabs (canonical for InventorySnapshot ingestion):**

| sheet | header row (0-indexed) | data start row | rows-with-key | total rows | grain |
|---|---:|---:|---:|---:|---|
| `INVENTORY` | 0 | 2 | **978** | 1015 | one row per **active** lot (held + sold-not-closed, BCP-built) |
| `CLOSED ` (trailing space) | 1 | 2 | **2,894** | 3,076 | one row per **closed** lot (historical, 2013-onward) |
| `CLOSINGS` | 1 | 3 | ~700 (~929 incl. month section breaks) | 933 | pipeline of pending closings ("at title", "watching", "C of O", etc.) |

**Phase-level summary tabs** (not per-lot, useful for Project/Phase entities):

| sheet | header row | grain |
|---|---:|---|
| `2026 Lot Inventory KS` | 3 (data starts row 5+ with community group headers like `"Harmony (764)"`) | community + per-phase lot counts by product type, plus delivery dates |
| `Lot Runoff` | 1 | per-community lot/development cost summary |
| `2026 Inventory Run Off`, `2023 Inventory Run Off` | 0 | monthly sales/starts run-off forecast |

**Year-by-year closing tabs** (`2015 Closings` … `2026 Closings`): each has header at row 0, data from row 2; granularity is one row per lot closed in that year. These are subsets of the master `CLOSED ` tab and largely redundant for staging — only useful if you need year-bucketed views.

**Forecast tabs** (`2017 Forecast` … `2023 Forecast`, `Planned Starts`, `Spec Starts`, `Supers Cons. Days`, `Sheet11`, `BCP Prof`, `2018 Tracking`, `dr_control`): not per-lot, not directly needed for InventorySnapshot. `dr_control` is a single-row DataRails control marker (`_dr_saving_platform=mac`).

### Header detection — INVENTORY sheet

Pandas `read_excel(..., sheet_name='INVENTORY', header=0)` produces clean column names. The sheet has 13 effective columns (cols 13–22 are blank padding). Column 0 has no label (header is a single space `' '`) but contains the SUBDIV value (`'SL'`, `'HARMONY'`, `'PARKWAY'`, etc.). Recommend renaming column 0 → `subdiv`.

| col 0-idx | header (raw) | meaning | fill rate (978 keyed rows) |
|---:|---|---|---:|
| 0 | `' '` | subdiv (community) | — (varies; see below) |
| 1 | `PH` | phase | 100% |
| 2 | `LOT #` | lot number | 100% |
| 3 | `PLAN` | plan/model name | 74.4% |
| 4 | `'                                                 BUYER'` (heavily padded) | buyer name OR `SPEC`/`MODEL` placeholder | 65.3% |
| 5 | `SALES PRICE` | sales price (numeric) | 11.6% |
| 6 | `DEPOSITS` | deposit amount | 8.4% |
| 7 | `SALE DATE` | sale date | 8.5% |
| 8 | `DAYS SINCE SALE/SPEC START` | volatile formula (=TODAY()-SaleDate) | 8.5% |
| 9 | `'PERMIT PULLED\n'` | permit-pulled date | 60.9% |
| 10 | `Permit number` | permit ID string | 60.9% |
| 11 | `Margin` | gross margin % | 7.6% |
| 12 | `Unnamed: 12` | sparse, mostly empty | 1.0% |

Column 0 (`subdiv`) is sparse because Excel uses **vertical-merge** of subdiv labels visually — only the first row of each subdiv group has the label set; subsequent rows in the same group are blank. Per-row inspection: **only ~110 rows have an explicit subdiv value; ~868 rows inherit from the previous non-blank row**. **Forward-fill is required** during stage.

### `as_of_date` for the inventory snapshot

There is **no explicit `as_of` cell** in any sheet. Best signals:

- `INVENTORY.SALE DATE` max = 2026-04-28
- `INVENTORY.PERMIT PULLED` max = 2026-04-28
- `CLOSINGS.RATIFIED SALES DATE` max = 2026-04-28
- `2026 Closings.CLOSED DATE` max = 2026-03-31 (March-bucket closings are the most recent fully populated)
- `CLOSED .Closing Date` max = 2027-06-07 — **forward-projected** anticipated closings included in `CLOSED `, **not** actual closing dates. Treat with caution: `CLOSED ` is a mix of actual + projected.
- xlsx `properties.modified` = 2026-04-29 11:16:20 UTC (file metadata — author's last save).

**Recommendation for `as_of_date`**: **2026-04-28** (the most recent date appearing in static inventory data of file (4)). Stage as a pipeline parameter / file-level metadata column.

### Grain of `staged_inventory_lots`

Two grain options for the canonical entity. Recommendation: **option B, union of INVENTORY + CLOSED **.

**Option A — active inventory only**: source = `INVENTORY` sheet, ~978 rows. Misses every closed lot. Inadequate for InventorySnapshot if downstream queries need historical context (e.g., "what was the absorption rate in 2024?").

**Option B (recommended) — full lot universe**: union of `INVENTORY` (~978 active) + `CLOSED ` (~2,894 closed) = **~3,872 lots**, with a derived `lot_status` ∈ {ACTIVE, CLOSED}. This is broader than v1's `Lot Data` (3,618 rows) because it includes Lennar lots and historical closings v1 doesn't track. Add `CLOSINGS` data as a join (matched on `(community, lot_num)`) to enrich active-lot rows with pipeline state (RATIFIED_SALE_DATE, ESTIMATED_CLOSING).

**Caveat**: `CLOSED .Closing Date` contains forward-projected dates (max 2027-06-07). Treat any `Closing Date > as_of_date` as `lot_status=ACTIVE_PROJECTED` rather than `CLOSED`. Better: use `CLOSED .Closing Date <= as_of_date` as the closure filter and flip the rest into ACTIVE.

### Stage proposal — `staged_inventory_lots.{csv,parquet}`

Proposed Terminal A stage call signature:

```python
import pandas as pd
SRC = 'data/raw/datarails_unzipped/datarails_raw/Inventory _ Closing Report (4).xlsx'
AS_OF = pd.Timestamp('2026-04-28')

# Active lots
inv = pd.read_excel(SRC, sheet_name='INVENTORY', header=0)
inv = inv.rename(columns={
    ' ': 'subdiv',
    'PH': 'phase',
    'LOT #': 'lot_num',
    'PLAN': 'plan_name',
    '                                                 BUYER': 'buyer',
    'SALES PRICE': 'sales_price',
    'DEPOSITS': 'deposit',
    'SALE DATE': 'sale_date',
    'DAYS SINCE SALE/SPEC START': 'days_since_sale',  # volatile; can drop
    'PERMIT PULLED\n': 'permit_pulled_date',
    'Permit number': 'permit_number',
    'Margin': 'margin_pct',
})
inv = inv.dropna(subset=['lot_num', 'phase'], how='all')
inv['subdiv'] = inv['subdiv'].ffill()             # vertical-merged labels
inv['lot_status'] = 'ACTIVE'
inv = inv[['subdiv','phase','lot_num','plan_name','buyer','sales_price',
          'deposit','sale_date','permit_pulled_date','permit_number',
          'margin_pct','lot_status']]

# Closed lots
closed = pd.read_excel(SRC, sheet_name='CLOSED ', header=1)
closed = closed.rename(columns={
    'SUBDIV': 'subdiv',
    'PH': 'phase',
    'LOT #': 'lot_num',
    'PLAN': 'plan_name',
    'Closing Date': 'closing_date',
    'BUYER                              ': 'buyer',
    'SALE PRICE': 'sales_price',
    'DEPOSITS': 'deposit',
    'SALE DATE': 'sale_date',
    'DAYS SINCE SALE': 'days_since_sale',
    'PERMIT PULLED\nSUPER': 'permit_pulled_or_super',
    'DIG DATE': 'dig_date',
    'ANTICIPATED COMPLETION': 'anticipated_completion',
    'Permit number': 'permit_number',
    'WR LANDSCAPE CHECK RECEIVED': 'wr_landscape_check',
})
closed = closed.dropna(subset=['lot_num', 'subdiv'], how='all')
closed['lot_status'] = closed['closing_date'].apply(
    lambda d: 'CLOSED' if pd.notna(d) and d <= AS_OF else 'ACTIVE_PROJECTED')
keep_closed = ['subdiv','phase','lot_num','plan_name','closing_date','buyer',
               'sales_price','deposit','sale_date','permit_number',
               'dig_date','anticipated_completion','lot_status']
closed = closed[keep_closed]

# Union (closed has cols active doesn't and vice versa — pd.concat handles)
out = pd.concat([inv, closed], ignore_index=True)
out['as_of_date'] = AS_OF
out['source_file'] = SRC.rsplit('/',1)[-1]

# Pipeline: write csv + parquet to data/staged/staged_inventory_lots.{csv,parquet}
```

Expected output: **3,872 ± 50 rows** (978 ACTIVE + 2,894 CLOSED, minus a few dups where the same lot appears in both), 16-ish columns + 2 metadata. Write a validation report under `data/reports/staged_inventory_lots_validation_report.md` with row counts, fill rates, and the as-of-date selection rationale.

### Crosswalk caveats — INVENTORY ↔ Lot Data

The INVENTORY sheet's `subdiv` values (`HARMONY`, `PARKWAY`, `SL`, `WILLOW CREEK`, `LOMOND HEIGHTS`, `SCARLET RIDGE`, `LEWIS ESTATES`, `ARROWHEAD`, `SALEM`) do not match the `Lot Data.Project` casing/wording (`Harmony`, `Parkway Fields`, `Willowcreek`, `Lomond Heights`, `Scarlet Ridge`, `Lewis Estates`, `Arrowhead Springs`, `Salem Fields`). And `SL` (= "Silver Lake"?) does not appear in `Lot Data.Project` at all — so `SL` lots are a separate community not represented in v1. **Crosswalk required**:

| INVENTORY.subdiv | Lot Data.Project (canonical) | confidence |
|---|---|---|
| `HARMONY` | `Harmony` | high |
| `PARKWAY` | `Parkway Fields` | high |
| `LOMOND HEIGHTS` | `Lomond Heights` | high |
| `WILLOW CREEK` | `Willowcreek` | high |
| `SALEM` | `Salem Fields` | high |
| `LEWIS ESTATES` | `Lewis Estates` | high |
| `SCARLET RIDGE` | `Scarlet Ridge` | high |
| `ARROWHEAD` | `Arrowhead Springs` | high |
| `SL` (Silver Lake) | (no v1 Lot Data row) | **unmapped** — historical Flagship community not in collateral source; investigate before staging |
| (blank, fwd-fill resolves it) | n/a | fixable in stage |

Same crosswalk applies to `CLOSED .SUBDIV` and `CLOSINGS.COMMUNITY`. CLOSED has additional historical communities (`LEC`, `WILLOWS`, `HAMPTON`, `BRIDGEPORT`, `WESTBROOK`, `SPRINGS`, `WINDSOR`, `BECK PINES`, `CASCADE`, `JAMES BAY`, `WILLIS`, `MAPLE FIELDS`, `MEADOW CREEK`, `PARKSIDE`, `COUNTRY VIEW`, `F. SPRINGS`, `SPRING LEAF`, `ANTHEM WEST`, `VINTARO`, `WR`, `SPEC`, etc.) — these are pre-2018 communities not in current Lot Data. Many of these will be unmapped in the crosswalk and should be flagged confidence=`low`.

**Confidence: high** that header offsets, grain, and stage proposal are correct. **Confidence: medium** on the `as_of_date = 2026-04-28` choice (no explicit cell; based on data-content max).

---

## C2 — Collateral reports

All files are CSV exports of tabs from `Collateral Dec2025 01 Claude.xlsx`, located at `data/raw/datarails_unzipped/phase_cost_starter/`. As a workbook collection they share a single `as_of_date = 12/31/2025` (per cell B1 of `2025Status` and per the `As of Date` column of `Collateral Report`).

### File-by-file matrix

| file | header (0-idx) | data start | rows-with-key | grain | as_of_date | confidence |
|---|---:|---:|---:|---|---|---|
| `Collateral Report.csv` | **8** | 9 | **41** (51 raw incl. trailing summary) | one row per **(project, phase, product_type, status)** in the borrowing-base universe | 12/31/2025 (col `As of Date`) | high |
| `2025Status.csv` | **2** | 3 | **3,627** | one row per **(project, phase, lot)** (3,618 unique keys; 9 dups are `Lot=0` aggregate placeholders, same as v1) | 12/31/2025 (cell A1=`As of Date:`, B1=`12/31/2025`) | high |
| `Lot Data.csv` | **0** | 1 | **3,627** | one row per **(project, phase, LotNo.)** lifecycle dates (3,618 unique keys) | 12/31/2025 (implicit; aligned with 2025Status) | high |
| `PriorCR.csv` | **8** | 9 | **41** | identical schema to Collateral Report — **prior period snapshot** | 6/30/2025 (col `As of Date`) | high |
| `IA Breakdown.csv` | **0** | 1 | 37 | one row per **customer/job/phase** with Inventory Asset (GL acct 132-187) balance + GL alloc account string | (implicit 12/31/2025) | high |
| `RBA-TNW.csv` | **1** | 3 | 11 (with 9 numeric value rows) | one row per **collateral bucket** (Sold-Not-Closed, Finished Homes, Model Homes, WIP, Unentitled, Paper Lots, Lots Under Dev, etc.) with GAAP/at-value/advance-rate/borrowing-base. Aggregate-only. | 12/31/2025 (implicit) | high |
| `Cost to Complete Summary.csv` | (no clean header — values in col 8) | n/a | 6 numeric rows | global totals only: `Land Dev To Go = $61.3M`, `Vert Construction To Go = $421.4M`, `Total = $482.8M`, `Homes Under Construction Vert To Go = $55.4M`, `TOTAL = $538.2M`. | 12/31/2025 | medium (no per-project allocation; aggregate-only) |
| `OfferMaster.csv` | **0** | 1 | 14 (+1 `Average` row) | one row per **(community, product_type)** with `Permit + Base + Option = Total` per-home reference cost. Static price reference, **not** a snapshot. | static (no date) | high |
| `Combined BS.csv` | **2** but mostly Unnamed | 3 | ~80 rows of label+value pairs | balance sheet at **entity level** (BCP/Adjustments/BCP-Adj/Consolidated). Not lot-level; useful only for entity-level financial tie-out. | 12/31/2025 (implicit) | low (sparse, label-driven structure) |

### Grain for canonical entities

- **CollateralSnapshot (per-phase)** ← `Collateral Report.csv` (primary, 41 phase rows). Has Total Lot Value, Borrowing Base, Advance %, Loan $, Total Dev Cost, Remaining Dev Costs, Production Unit WIP. PriorCR is its 6-mo-prior twin (same schema; useful for delta).
- **InventorySnapshot (per-lot)** ← `2025Status.csv` (primary, 3,618 lots). Has Status, Status Date, Vert Sold, Collateral Bucket, plus per-lot horizontal cost fields (Permits and Fees, Direct Construction - Lot, Shared Cost Alloc., Lot Cost, Vertical Costs, Direct Construction). v1 already wires this in.
- **LotState lifecycle dates** ← `Lot Data.csv` (3,618 lots). Already wired in v1.
- **Cost reference table** ← `OfferMaster.csv` (per community × product type — base+option+permit). Useful as a fallback for projects with no allocation workbook.
- **Aggregate borrowing base** ← `RBA-TNW.csv` — useful for high-level reconciliation, not per-entity.

### Caveats for collateral

- `Collateral Report` has 9 distinct projects (`ARROWHEAD SPRINGS, DRY CREEK, HARMONY, LOMOND HEIGHTS, MEADOW CREEK, PARKWAY FIELDS, SALEM FIELDS, SCARLET RIDGE, WILLOWCREEK`) — narrower than `2025Status` (16 projects). The 7 projects missing from Collateral Report (`Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Lewis Estates, Santaquin Estates, Westbridge`) are exactly the projects v1 flagged as having no expected-cost source. **Confirms v1's gap analysis.** Lewis Estates is in 2025Status (34 lots) but absent from Collateral Report.
- `2025Status` `Direct Construction` column ($61.7M global) is mixed vertical+horizontal (per CONTEXT_PACK). `Direct Construction - Lot` is horizontal-only and is what v1 uses. Don't change this.
- `2025Status` has `Shared Cost Alloc.` filled on only 696 of 3,627 rows (~19%) — sparse but populated where it exists.
- `IA Breakdown` mixes Customer-level and phase-level rows in a flat list (Subtotal rows like `Total Ault Farms aka Parkway Fields`, `Total Harmony`, etc.); ingestion needs row-typing logic.

**Confidence: high** for the per-file matrix. **Confidence: medium** for the cross-source reconciliation (the 7-project gap is a real Track A constraint — Lewis Estates can be partial via OfferMaster; the other 6 may need a `lot-count × OfferMaster total cost` rough-cut estimate).

---

## C3 — ClickUp lot-tagged subset

### Subset profile

`data/staged/staged_clickup_tasks.parquet`:

- **Total rows**: 5,509
- **`subdivision` populated** (non-blank): **1,590** (28.86%)
- **`lot_num` populated**: **1,177** (21.37%)
- **BOTH `subdivision` AND `lot_num` populated**: **1,177** (21.37%) ← matches lane's expected ~1,177 ✓
- **`phase` populated within both-keys subset**: **1,093** of 1,177 = **92.86%** (vs 19.86% in full file)

The **(subdivision, lot_num) join key** is the right grain for TaskState ingestion. Phase is reliably present when both keys are populated, so the canonical TaskState join key can be `(subdivision, lot_num, phase)` for joins to inventory/2025Status, with `phase` optional.

### Status distribution within both-keys subset (n=1177)

| status | count | comment |
|---|---:|---|
| Open | 640 | not started / pending |
| under construction | 265 | active vertical |
| walk stage | 264 | pre-CofO |
| ready close | 7 | imminent closing |
| waiting for new starts | 1 | edge case |

Compare to full file (n=5509): `Open=4826, walk stage=266, under construction=265, waiting for new starts=65, pulled=27, pay fees=26, collecting data=19, at city=8, ready close=7`. Notice: `walk stage` and `under construction` are **almost entirely lot-tagged** (264/266 and 265/265 respectively). `Open` is split: 4826 total, only 640 lot-tagged. The 4,186 `Open` un-tagged tasks are likely template/parent tasks at the project or phase level, not actionable lot work.

### Date-field coverage in lot-tagged subset

Date coverage is **3-5x better** in the lot-tagged subset than in the full file:

| field | full file | lot-tagged (subdiv OR lot) | both-keys |
|---|---:|---:|---:|
| `actual_c_of_o` | 4.88% | 16.86% | 22.77% |
| `date_done` | 4.96% | 17.04% | 23.02% |
| `due_date` | 14.72% | 35.35% | 45.54% |
| `sold_date` | 1.02% | 3.52% | 4.76% |
| `projected_close_date` | 1.02% | 3.52% | 4.76% |
| `walk_date` | 0.38% | 1.32% | 1.78% |

**Recommendation**: TaskState entity ingestion should filter to `subdivision IS NOT NULL AND lot_num IS NOT NULL` (n=1,177). Untagged tasks are not lot-actionable.

### (subdivision, lot_num) cardinality

- 1,091 distinct `(subdivision, lot_num)` pairs from 1,177 tasks.
- Mean tasks per pair: 1.08; median 1; max **75** (`Arrowhead` lot 173 — almost certainly a misuse / template parent; flag for human review).
- 13 pairs have >1 task. After excluding the Arrowhead-173 outlier, the others all have just 2 tasks each.

### Subdivision spelling normalization (required)

| ClickUp.subdivision | canonical | confidence |
|---|---|---|
| `Harmony` | `Harmony` | high |
| `Arrowhead` | `Arrowhead Springs` | high |
| `Aarowhead` | `Arrowhead Springs` | medium (typo) |
| `Aarrowhead` | `Arrowhead Springs` | medium (typo) |
| `Park Way` | `Parkway Fields` | high (with space normalization) |
| `Lomond Heights` | `Lomond Heights` | high |
| `Salem Fields` | `Salem Fields` | high |
| `Willow Creek` | `Willowcreek` | high |
| `Scarlett Ridge` | `Scarlet Ridge` | medium (one extra 't') |
| `Lewis Estates` | `Lewis Estates` | high |
| `P2 14` | (project / phase identifier — likely Harmony Phase A Plat 14) | low — needs human review |

**Recommendation for TaskState ingestion**: apply the crosswalk above to a `subdivision_canonical` column; preserve raw `subdivision` for audit; emit a typo-flag column where corrections were made.

### TaskState filtering rule

- Include tasks where: `subdivision IS NOT NULL AND lot_num IS NOT NULL`.
- Exclude Arrowhead-173 (or flag it as data-quality outlier).
- Recompute or trust the `phase` column (92.86% populated; for the missing 7%, fall back to `top_level_parent_id` lookup or leave NULL).

**Confidence: high** for filter rules and join-key. **Confidence: medium** for phase-derivation in the 7% gap. **Out of scope** to reconstruct intermediate `parent_id` from ClickUp API (per existing validation report — `parent_id` was not exported).

---

## C4 — Allocation workbooks

### Flagship Allocation Workbook v3 (5 tabs)

| sheet | header | grain | recommended use |
|---|---:|---|---|
| `Instructions.csv` | n/a | narrative text only | reference only — do not ingest |
| `Lot Mix & Pricing.csv` | 0 | one row per `(community, phase, lot_type)` with `Lots (LotData)`, `Lots (Manual Input)`, `Tie-Out`, `Avg Projected Sales Price`, `Total Projected Sales` | revenue projection input — not cost; useful for ProjectState revenue forecast |
| `Indirect & Land Pools.csv` | 0 | one row per pool row `(Type=INDIRECT or LAND, Community, Job Id, Job Name, Current Budget, Override, Effective Budget)` | per-community pool budgets that get allocated by Allocation Engine |
| `Allocation Engine.csv` | 0 | 80 rows × 10 cols, one row per `(community, phase, lot_type)` with `Total Proj Sales, Sales Basis %, Community Indirect Pool, Indirect Allocated, Community Land Pool, Land Allocated` | the engine that drives Per-Lot Output |
| `Per-Lot Output.csv` | 0 | 81 rows × 15 cols, one row per `(community, phase, lot_type)` with `Lots, Direct Budget, Indirect Allocated, Land Allocated, Total Cost, Direct/Lot, Indirect/Lot, Land/Lot` | **canonical Allocation entity at phase × lot_type grain** — but **most rows are $0** in this snapshot (only Arrowhead Springs etc. partially populated; v1 finds zero useful rows from this file currently) |

The Flagship workbook covers 8 communities (`Arrowhead Springs, Ben Lomond, Harmony, Lewis Estates, Parkway Fields, Salem Fields, Scarlet Ridge, Willowcreek`), 67 distinct (community, phase) pairs. **However — most rows are empty/$0 in the current snapshot.** The Allocation Engine populates output only when both `Lot Mix & Pricing` (sales) and `Indirect & Land Pools` (pool budgets) are filled, and most communities have one or both blank. **The workbook is a budgeting framework — the data isn't there yet.**

### LH Allocation 2025.10 (6 tabs)

| sheet | header | grain | recommended use |
|---|---:|---|---|
| `LH.csv` (v1's primary source) | row 4 effective; "Summary per lot" section uses cols 5-17 with phase/prod/lots in cols 5,6,7 | one row per `(phase, prod_type)` × Lomond Heights project | **primary LH allocation source** — already wired into v1. Total column blank; reconstruct from land+direct+water+indirect (per CONTEXT_PACK note). |
| `AAJ.csv` (After-Acquisition Journal) | 0 (multi-row header rows 0-1: phase names + community labels) | per-GL-line × per-phase **wide-format** — phases as columns, GL lines as rows | balance-sheet style detail by phase for Ben Lomond — useful for entity-level reconciliation, **not per-lot** |
| `BCPBL SB.csv` (Sundance Bay loan) | 0 | static loan terms (Principal, Loan Date, Maturity, etc.) | reference; not lot-level |
| `BSJ.csv` (Salem-related, Balance Sheet Journal?) | 0 | wide-format like AAJ — phases as columns, GL/balance lines as rows | per-phase Salem entity-level data; not per-lot |
| `JCSList.csv` (Job Cost Summary) | row 6 effective | one row per **QB Job × project × phase** with `Orig Budget, LAND ACQUISITION, INTEREST EXPENSE, Adj Budget, ITD Actuals` | useful for v2 GL-to-job-to-phase crosswalk |
| `PLJ.csv` (Profit & Loss Journal — Harmony) | 0 (multi-row header) | per-P&L-line × per-Harmony-phase wide format | Harmony entity-level P&L by phase; not per-lot |

### Parkway Allocation 2025.10 (3 tabs)

| sheet | header | grain | recommended use |
|---|---:|---|---|
| `PF.csv` (v1's primary source) | row 4 effective; same shape as `LH.csv` | one row per `(phase, prod_type)` × Parkway Fields | **primary Parkway allocation** — already wired into v1. Has full sales/cost-of-land/direct-dev/water/indirects columns. |
| `AAJ.csv` | wide-format (phases as cols) | per-GL-line × per-phase | Parkway entity-level data |
| `JCSList.csv` | row 6 | per-QB-Job × project × phase | duplicate-ish of LH JCSList (covers same job universe) |

### Dehart Underwriting (Summary).csv

- Loose root-level CSV (not in either zip).
- 122 rows × 200 cols — heavy formatting, sparse.
- Header is **scattered across rows 1-15** — labels like `SUMMARY OF INVESTMENT`, `MODEL SETUP`, `Project name`, `Address`, `City`, `Country`, `Model Type=Commercial Land Development`, `INVESTMENT DESCRIPTION`. No consistent tabular grain.
- This is an **underwriting model** for one specific project (Payson Larsen / Dehart), exported as a wide-formatted summary. **Not directly stageable** as a per-lot or per-phase Allocation entity row.
- Recommend: parse opportunistically into a single `Project=Dehart, scenario_summary={…}` row OR **defer entirely** until v2 needs Dehart specifically. Per CONTEXT_PACK, Dehart is "inventoried but not wired in."

### Allocation entity recommendation

**For BCPD Track A**, the Allocation entity has at most these rows from the four workbooks combined:

| source | project | phase rows usable | confidence |
|---|---|---:|---|
| `LH.csv` (Summary per lot section) | Lomond Heights | 12 phase × prod_type rows (2A SFR, 2A TH, 2B SFR, 2B TH, 2C SFR, 2C TH, 2D SFR, 3 Comm, 5 MF, 6A SFR, 6B SFR, 6C SFR) | high (already in v1; Total reconstruction works) |
| `Parkway Allocation - PF.csv` | Parkway Fields | 14 phase × prod_type rows (B2 SFR x2, D1 SFR x2, G1 Church, D2 SFR x2, E1 SFR x2, E2 SFR, F SFR, G1 SFR, G1 Comm, G2 SFR, H SFR) | high (already in v1) |
| `Flagship Allocation v3 - Per-Lot Output.csv` | 8 communities | 81 rows but ~0 currently populated | low — workbook is mostly empty |
| `Dehart Underwriting.csv` | Dehart | 0 (not stageable as-is) | low |

**Recommendation**: stage Allocation entity from LH and PF only (matches v1). The Flagship Allocation Workbook v3 is a v2-relevant *framework* but the data isn't filled in. For Lewis Estates, Salem Fields, Harmony, Arrowhead Springs, Scarlet Ridge, Willowcreek, etc. (the projects the Flagship workbook *would* cover), expected cost will remain unsourced for v2 unless someone fills in the workbook or we use OfferMaster as a rough proxy.

**Confidence: high** for v1-equivalent ingestion (LH + PF). **Confidence: low** for any expansion beyond — the framework exists but the cells are empty.

---

## C5 — Per-source feeding map

| source | LotState | PhaseState | ProjectState | AllocationState | CollateralSnapshot | InventorySnapshot | TaskState |
|---|---|---|---|---|---|---|---|
| `Inventory _ Closing Report (4).xlsx` — `INVENTORY` sheet | partial (status, sale_date, permit_pulled) | — | partial (community-level) | — | — | **primary** (active lots) | — |
| `Inventory _ Closing Report (4).xlsx` — `CLOSED ` sheet | partial (closed status, closing_date) | — | — | — | — | **primary** (closed lots, historical) | — |
| `Inventory _ Closing Report (4).xlsx` — `CLOSINGS` sheet | — | — | — | — | — | partial (pending pipeline overlay) | — |
| `Inventory _ Closing Report (4).xlsx` — `2026 Lot Inventory KS` sheet | — | partial (planned lot count by phase) | partial (community-level summary) | — | — | partial (planned vs platted lots) | — |
| `Collateral Dec2025 - 2025Status.csv` | **primary** (status code, status date, vert sold, costs) | — | — | — | partial (collateral_bucket per lot) | partial (status overlay on InventorySnapshot) | — |
| `Collateral Dec2025 - Lot Data.csv` | **primary** (lifecycle dates) | — | — | — | — | — | — |
| `Collateral Dec2025 - Collateral Report.csv` | — | partial (Total Dev Cost = expected cost; PARTIAL fidelity) | partial (per-project totals) | — | **primary** (borrowing base, advance %, loan $) | — | — |
| `Collateral Dec2025 - PriorCR.csv` | — | partial (prior period expected cost) | — | — | **primary** (prior snapshot for delta) | — | — |
| `Collateral Dec2025 - IA Breakdown.csv` | — | partial (per-phase Inventory Asset balance) | partial | — | partial | — | — |
| `Collateral Dec2025 - RBA-TNW.csv` | — | — | — | — | aggregate-only | — | — |
| `Collateral Dec2025 - Cost to Complete Summary.csv` | — | — | aggregate-only | — | — | — | — |
| `Collateral Dec2025 - OfferMaster.csv` | — | — | partial (per-community-product cost reference) | partial (fallback when no allocation workbook) | — | — | — |
| `Collateral Dec2025 - Combined BS.csv` | — | — | — | — | — | — | — (entity-only; not lot/phase) |
| `LH Allocation 2025.10 - LH.csv` | — | partial (expected cost per phase × prod_type) | — | **primary** (Lomond Heights) | — | — | — |
| `LH Allocation 2025.10 - JCSList.csv` | — | partial (job ↔ phase mapping) | — | partial (job-cost actuals) | — | — | — |
| `LH Allocation - AAJ/BSJ/PLJ/BCPBL SB` | — | — | — | — | partial (entity-level GL detail) | — | — |
| `Parkway Allocation 2025.10 - PF.csv` | — | partial | — | **primary** (Parkway Fields) | — | — | — |
| `Parkway Allocation - AAJ/JCSList` | — | — | — | partial | — | — | — |
| `Flagship Allocation Workbook v3 - Per-Lot Output.csv` | — | — | — | partial (framework — currently mostly empty) | — | — | — |
| `Flagship Allocation v3 - Lot Mix & Pricing.csv` | — | — | partial (revenue projection) | — | — | — | — |
| `Flagship Allocation v3 - Indirect & Land Pools.csv` | — | — | — | partial (input pool budgets) | — | — | — |
| `Dehart Underwriting (Summary).csv` | — | — | — | (not stageable as-is) | — | — | — |
| `staged_clickup_tasks` (lot-tagged subset, n=1177) | partial (status overlay) | — | — | — | — | partial (active-task signal per lot) | **primary** |
| `Clickup_Naming_Struct - Sheet1.csv` | — | — | — | — | — | — | reference (naming convention) |

**Legend**: *primary* = canonical source for that entity. *partial* = contributes some fields or partial coverage. *aggregate-only* = useful for tie-out / sanity, not row-level. *reference* = documentation, not data. Blank = no contribution.

**Confidence: high** for the C5 map across inventory + collateral + allocation. **Confidence: medium** for ClickUp's TaskState contribution (need ontology decision on what TaskState should be — see Terminal A).

---

## Recommendations to Terminal A — prioritized

1. **Stage `staged_inventory_lots` per the C1 proposal** (use file (4) with as_of=2026-04-28; union INVENTORY + CLOSED ; add `lot_status`; ffill `subdiv`; apply community crosswalk). Estimated output: ~3,872 rows. **This unblocks the guardrail.**
2. **Apply the `subdiv → Project` crosswalk** in stage (8 high-confidence mappings + Silver Lake unmapped + ClickUp typo variants → flag as `confidence` column).
3. **Defer `Combined BS`, `Cost to Complete Summary`, `Dehart Underwriting`** — entity/aggregate level, not lot/phase grain. Useful for tie-out, not for Track A entity ingestion.
4. **Allocation expansion is gated on Flagship workbook population** — for now, replicate v1 (LH + PF only). For other projects, OfferMaster-based fallback is feasible at community×product-type grain (not per-lot).
5. **Use `PriorCR` to compute snapshot deltas** in CollateralSnapshot — same schema as Collateral Report at as_of=2025-06-30.
6. **TaskState ingestion**: filter to `(subdivision NOT NULL AND lot_num NOT NULL)`; n=1,177 after filter. Apply subdivision crosswalk; flag Arrowhead-173 outlier.
7. **`(2)/(3)/(4) inventory file** — the lane doc claim that (4) is latest is weakly false (4 is earliest by ~1 day, with 2 lot deltas). Confirm with the human if intent was "newest data" before staging; otherwise (4) is fine.

---
