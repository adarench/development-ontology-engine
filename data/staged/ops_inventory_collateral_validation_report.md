# Ops Sources — Validation Report

**Author**: Terminal C
**Run date**: 2026-05-01
**Scope**: Inventory closing report (`Inventory _ Closing Report (4).xlsx`), collateral CSVs (`Collateral Dec2025 ...`), allocation workbooks (Flagship v3, LH 2025.10, Parkway 2025.10, Dehart), and the lot-tagged ClickUp subset already in `data/staged/staged_clickup_tasks.parquet`.

For each file: existence, header offset, row counts, identified columns, and an explicit "ready to stage" / "blocked because X" verdict.

---

## 1. Inventory closing report (Tier 1 — guardrail unblocker)

### File existence

| path | exists | size |
|---|---|---:|
| `data/raw/datarails_unzipped/datarails_raw/Inventory _ Closing Report (2).xlsx` | ✅ | 1,734,557 bytes |
| `data/raw/datarails_unzipped/datarails_raw/Inventory _ Closing Report (3).xlsx` | ✅ | 1,734,294 bytes |
| `data/raw/datarails_unzipped/datarails_raw/Inventory _ Closing Report (4).xlsx` | ✅ | 1,734,239 bytes |

All three workbooks have **identical sheet structure**: 34 sheets per workbook, identical row × column counts on each sheet. Differences are localized to volatile `=TODAY()-SaleDate` cells and 2 lot deltas (see findings doc).

### Per-sheet inventory

The workbook has 34 sheets. Most are not Track A-relevant. Per-lot grain lives in 3 sheets:

| sheet | row × col | header (0-idx) | data start | rows-with-key | grain | Track A relevance |
|---|---:|---:|---:|---:|---|---|
| `INVENTORY` | 1015 × 22 | **0** | 2 | **978** | one row per active lot (BCP-built held + sold-not-closed) | **PRIMARY** for active inventory |
| `CLOSED ` (trailing space) | 3076 × 39 | **1** | 2 | **2,894** | one row per closed lot (historical, 2013→) | **PRIMARY** for closed inventory |
| `CLOSINGS` | 933 × 15 | **1** | 3 | ~700 (929 incl. month section breaks) | pipeline of pending closings | OVERLAY (no phase column) |
| `2026 Lot Inventory KS` | 1006 × 32 | 3 | 5+ | community/phase summary | summary | secondary |
| `Lot Runoff` | 1015 × 35 | 1 | 3 | per-community summary | summary | secondary |
| `INVENTORY` + `CLOSED ` UNION (proposed stage) | — | — | — | **~3,872** | one row per lot (active or closed) | **CANONICAL InventorySnapshot grain** |

### INVENTORY sheet — column identification (header=0)

13 effective columns; cols 13–22 are blank padding. Column 0 has header `' '` (single space) — propose rename to `subdiv` during stage.

| col idx | raw header | proposed canonical name | dtype | fill-rate |
|---:|---|---|---|---:|
| 0 | `' '` | `subdiv` | string | sparse-by-design (vertical-merge in Excel) → **forward-fill required** |
| 1 | `PH` | `phase` | mixed (str/int) | 100% (978/978) |
| 2 | `LOT #` | `lot_num` | mixed (str/int) | 100% |
| 3 | `PLAN` | `plan_name` | string | 74.4% |
| 4 | `'                                                 BUYER'` | `buyer` | string (incl. `SPEC`/`MODEL`) | 65.3% |
| 5 | `SALES PRICE` | `sales_price` | float | 11.6% |
| 6 | `DEPOSITS` | `deposit` | float | 8.4% |
| 7 | `SALE DATE` | `sale_date` | datetime | 8.5% |
| 8 | `DAYS SINCE SALE/SPEC START` | `days_since_sale` (volatile — drop on stage) | int | 8.5% |
| 9 | `'PERMIT PULLED\n'` | `permit_pulled_date` | datetime | 60.9% |
| 10 | `Permit number` | `permit_number` | string | 60.9% |
| 11 | `Margin` | `margin_pct` | float | 7.6% |
| 12 | `Unnamed: 12` | (drop) | mixed | 1.0% |

### CLOSED sheet — column identification (header=1)

15 effective columns; cols 15–19 are unlabeled blanks (`Unnamed: 15` … `Unnamed: 19`).

| col idx | raw header | proposed canonical name | fill-rate |
|---:|---|---|---:|
| 0 | `SUBDIV` | `subdiv` | high |
| 1 | `PH` | `phase` | high |
| 2 | `LOT #` | `lot_num` | high |
| 3 | `PLAN` | `plan_name` | medium |
| 4 | `Closing Date` | `closing_date` | medium-high (historical real, plus forward projections) |
| 5 | `'BUYER                              '` (padded) | `buyer` | high |
| 6 | `SALE PRICE` | `sales_price` | medium |
| 7 | `DEPOSITS` | `deposit` | medium |
| 8 | `SALE DATE` | `sale_date` | medium |
| 9 | `DAYS SINCE SALE` | `days_since_sale` (volatile — drop) | low |
| 10 | `'PERMIT PULLED\nSUPER'` | `permit_pulled_or_super` (mixed) | medium |
| 11 | `DIG DATE` | `dig_date` | medium |
| 12 | `ANTICIPATED COMPLETION` | `anticipated_completion_date` | medium |
| 13 | `Permit number` | `permit_number` | medium |
| 14 | `WR LANDSCAPE CHECK RECEIVED` | `wr_landscape_check_date` | low |

`Closing Date` extends to 2027-06-07 — clearly **forward-projected anticipated closings** mixed with actual closings. Recommend: derive `lot_status = CLOSED if Closing Date <= as_of_date else ACTIVE_PROJECTED`.

### CLOSINGS sheet — column identification (header=1)

15 columns. Section breaks at rows where `LOT#` is null and `COMMUNITY` is a month name (`April`, `May`, `June`, …). Filter those during stage.

| col idx | raw header | proposed canonical |
|---:|---|---|
| 0 | `COMMUNITY` | `subdiv` |
| 1 | `LOT#` | `lot_num` |
| 2 | `BUYER NAME` | `buyer` |
| 3 | `RATIFIED SALES DATE` | `ratified_sale_date` |
| 4 | `'DAYS SINCE \nRATIFIED SALE'` | `days_since_ratified` (volatile — drop) |
| 5 | `ESTIMATED CLOSING` | `estimated_closing_date` |
| 6 | `FUNDED` | `funded_flag` |
| 7 | `Final Addendum` | `final_addendum_status` |
| 8 | `NOTES` | `notes` |
| 9 | `C of O` | `c_of_o_date` |
| 10 | `LENDER` | `lender_name` |
| 11 | `FLAGSHIP REALTOR` | `flagship_realtor` |
| 12 | `OUTSIDE REALTOR` | `outside_realtor` |
| 13 | `OUTSIDE PHONE#` | `outside_phone` |
| 14 | `REFERRAL FEE` | `referral_fee` |

CLOSINGS has **no phase column** — must be joined to INVENTORY/CLOSED on `(community, lot_num)` to pick up phase. Treat CLOSINGS as a pipeline-state overlay, not a primary source.

### As-of-date determination

No explicit `as_of_date` cell exists in any sheet. Best inferred value: **2026-04-28**

Evidence:

| signal | value |
|---|---|
| `INVENTORY.SALE DATE` max | 2026-04-28 |
| `INVENTORY.PERMIT PULLED\n` max | 2026-04-28 |
| `CLOSINGS.RATIFIED SALES DATE` max | 2026-04-28 |
| `CLOSINGS.ESTIMATED CLOSING` max | 2026-08-22 (forward projection) |
| `2026 Closings.CLOSED DATE` max | 2026-03-31 (last fully populated month) |
| `CLOSED .Closing Date` max | 2027-06-07 (forward projection — exclude from "real" actuals) |
| File mtime / properties.modified | 2026-04-29 11:16 (file save time, ≈ as-of+1 day) |

### Diff (2) vs (3) vs (4)

All three byte-different but structurally identical (34 sheets, identical dimensions). 19 of 34 sheets are byte-identical across (2)/(3)/(4) (the older-year Forecast/Closing tabs and Lot Inventory summary tabs). 15 sheets differ — but the differences are dominated by volatile `=TODAY()-SaleDate` formulas in `DAYS SINCE …` columns.

**Refresh order based on volatile cell values**: file (4) saved earliest (`days_since_sale=62` for one lot), then (3) (`=63`), then (2) (`=61` shifted by one day → wait, +1 day → `=63`). Recomputed: (4) ≈ 2026-04-28 → (3) ≈ 2026-04-29 → (2) ≈ 2026-04-30. **(2) is the most recent, NOT (4)** as the lane doc claimed.

Static-data diffs between (4) and (2): 2 lots in INVENTORY have different sold/cancelled status:

| lot | (4) state | (2) state |
|---|---|---|
| `PARKWAY G1 lot 7048` | unsold/blank | sold 2026-04-29, deposit $4,000, margin 14.35% |
| `SCARLET RIDGE Phase 1 lot 121` | sold 2026-03-26, deposit $8,000, margin 13% | unsold/cancelled (blank) |

Net delta is 2 lot events between (4) and (2). All three files are functionally equivalent for an `as_of` snapshot picked anywhere in the 2026-04-28 → 2026-04-30 window.

### Stage proposal — `staged_inventory_lots.{csv,parquet}`

**Verdict: READY TO STAGE.**

| parameter | value |
|---|---|
| Source workbook | `data/raw/datarails_unzipped/datarails_raw/Inventory _ Closing Report (4).xlsx` |
| `as_of_date` | 2026-04-28 |
| Sheets to ingest | `INVENTORY` (header=0) + `CLOSED ` (header=1) — UNION |
| `CLOSINGS` | overlay on join `(subdiv, lot_num)` — optional enrichment, not primary |
| Rename column 0 of INVENTORY | `' '` → `subdiv` |
| Forward-fill `subdiv` in INVENTORY | YES (vertical-merged in Excel) |
| `lot_status` derivation | `INVENTORY` rows → `ACTIVE`; `CLOSED ` rows where `Closing Date <= 2026-04-28` → `CLOSED`, else `ACTIVE_PROJECTED` |
| Drop volatile cols | `days_since_sale` (INVENTORY col 8, CLOSED col 9), `days_since_ratified` (CLOSINGS col 4) |
| Apply community crosswalk | YES (8 high-confidence mappings; flag `SL`/Silver Lake unmapped + pre-2018 historicals) |
| Add metadata cols | `as_of_date`, `source_file`, `source_sheet`, `source_row_number` (row offset within original sheet) |
| Expected output rows | ~3,872 (978 INVENTORY + 2,894 CLOSED, minus a few cross-sheet dups) |
| Expected output cols | ~16 + metadata |
| Output paths | `data/staged/staged_inventory_lots.csv` + `.parquet` |
| Validation report | `data/reports/staged_inventory_lots_validation_report.md` (Terminal A to write) |

**Caveat to flag in the validation report when staged**: file (4) is the *earliest* of the three near-duplicates by ~2 days. Confirm with the human whether the intent was "newest export" before relying on this for production. The 2-lot static-data delta is small but non-zero.

---

## 2. Collateral CSVs (Tier 2)

All under `data/raw/datarails_unzipped/phase_cost_starter/`. Workbook-level `as_of_date = 2025-12-31` (verified via `2025Status.csv` cell A1 + `Collateral Report.csv` `As of Date` column).

| file | exists | size (bytes) | header (0-idx) | data start | rows-with-key | grain | as_of | ready to stage? |
|---|---|---:|---:|---:|---:|---|---|---|
| `Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv` | ✅ | 21,036 | **8** | 9 | 41 of 51 | per (project, phase, product_type, status) | 12/31/2025 | **YES** for CollateralSnapshot at phase grain |
| `Collateral Dec2025 01 Claude.xlsx - Combined BS.csv` | ✅ | 6,299 | 2 | 3 | 80 (label-driven) | balance sheet line × entity | implicit 12/31/2025 | NO — entity-only, label-driven; not lot/phase grain. **Defer.** |
| `Collateral Dec2025 01 Claude.xlsx - 2025Status.csv` | ✅ | 465,533 | **2** | 3 | 3,627 (3,618 unique keys) | per (project, phase, lot) | 12/31/2025 (cell A1=`As of Date:`, B1=date) | **YES** (already wired in v1) |
| `Collateral Dec2025 01 Claude.xlsx - IA Breakdown.csv` | ✅ | 2,475 | **0** | 1 | 37 | per customer/job/phase Inventory Asset balance | implicit | partial — **YES for entity-level reconciliation only**. Subtotal rows need filtering. |
| `Collateral Dec2025 01 Claude.xlsx - PriorCR.csv` | ✅ | 18,418 | **8** | 9 | 41 | same schema as Collateral Report — prior period | 6/30/2025 | **YES** for CollateralSnapshot delta computation |
| `Collateral Dec2025 01 Claude.xlsx - RBA-TNW.csv` | ✅ | 1,105 | **1** | 3 | 9 numeric value rows of 20 | per collateral bucket aggregate | implicit 12/31/2025 | partial — aggregate-only; useful for tie-out, not an entity input |
| `Collateral Dec2025 01 Claude.xlsx - Cost to Complete Summary.csv` | ✅ | 367 | n/a (values in col 8) | n/a | 5 numeric rows | global aggregates | implicit | partial — aggregate-only. **Defer for direct entity ingestion.** |
| `Collateral Dec2025 01 Claude.xlsx - Lot Data.csv` | ✅ | 645,048 | **0** | 1 | 3,627 (3,618 unique keys) | per (project, phase, LotNo.) lifecycle dates | implicit 12/31/2025 | **YES** (already wired in v1) |
| `Collateral Dec2025 01 Claude.xlsx - OfferMaster.csv` | ✅ | 1,291 | **0** | 1 | 14 (+ 1 `Average` row) | per (community, product_type) reference cost | static (no date) | **YES** as a community×product-type cost reference / fallback |

### Collateral Report — column listing (header=8)

64 cols total. Subset most relevant for CollateralSnapshot:

`Project, Phase, Product Type, Status, Location, In Collateral Pool?, Flagship, External, Total, Check, # of Lots, Lot Type, Raw Land Allocation, Offsites Allocation, ITD Dev Costs, Paper Lot Value, Finished Lot Value, Value generation via dev cost, Total Lot Value, Advance %, Loan $, Remaining Dev Costs, Total Dev Cost (Spent + Remaining), Remaining Dev Costs per Lot, Total Dev Cost per Lot, All-in Cost per Lot, Avg Cost per Home (excl. Lot), Total Vertical Costs for Homes, Total Dev Costs + Vertical Costs to Complete Homes, # of Lots.1, Production Unit WIP, Production Unit WIP (excl. Lot), As of Date, ...` plus Model/Home/Sold home columns and lender-advance summary.

The .1/.2/.3 suffix columns are pandas auto-suffixes for repeated headers (the source has multiple `# of Lots`, `Advance %`, `Loan $`, etc. in different sub-categories). Confidence: high — schema is stable across PriorCR.

### 2025Status — column listing (header=2)

26 cols total. Cols 0–15 are the canonical per-lot data; cols 16–25 are pivot-table sidebar (drop on stage, as v1 does).

`Project, Phase, Lot, Product Type, Lot Count, Status, Status Date, Vert Sold, Collateral Bucket, Permits and Fees, Direct Construction - Lot, Direct Construction, Vertical Costs, Shared Cost Alloc., Lot Cost, HorzCustomer, [Unnamed: 16, Sum of Lot Count, Collateral Bucket.1, Unnamed: 19..25 — sidebar pivot, ignore]`

Fill rates within 3,627 keyed rows: `Project/Phase/Lot/Lot Cost ≈ 100%`, `Status Date ≈ 99%`, `Shared Cost Alloc. = 19%` (sparse).

### Lot Data — column listing (header=0)

26 cols, all relevant:

`Project, Phase, ProdType, HorzSeller, HorzCustomer, LotNo., LotArea(sqft), LotCount, SHComb, HorzPurchase, HorzMDA, HorzPrelimPlat, HorzFinalPlat, HorzStart, HorzEnd, HorzFinInv, HorzRecord, HorzWEnter, HorzWExit, HorzContract, HorzSale, VertPurchase, VertStart, VertCO, VertSale, VertClose`

Confidence: high. Already wired in v1.

---

## 3. ClickUp lot-tagged subset (Tier 3)

| asset | path | exists |
|---|---|---|
| ClickUp staged parquet | `data/staged/staged_clickup_tasks.parquet` | ✅ |
| ClickUp staged CSV | `data/staged/staged_clickup_tasks.csv` | ✅ |
| Existing validation report | `data/reports/staged_clickup_validation_report.md` | ✅ (don't modify) |

| metric | value |
|---|---:|
| Total rows | 5,509 |
| `subdivision` populated (non-blank) | 1,590 (28.86%) |
| `lot_num` populated | 1,177 (21.37%) |
| BOTH `subdivision` AND `lot_num` populated | **1,177** ← lot-tagged subset target |
| `phase` populated within both-keys subset | 1,093 of 1,177 = 92.86% |
| Distinct `(subdivision, lot_num)` pairs in both-keys subset | 1,091 |
| Tasks per (sub, lot) pair: mean / median / max | 1.08 / 1 / **75** (Arrowhead lot 173 outlier) |

### Status distribution (both-keys subset, n=1177)

`Open=640, under construction=265, walk stage=264, ready close=7, waiting for new starts=1`

### Date-field coverage uplift (lot-tagged vs full)

| field | full | both-keys |
|---|---:|---:|
| `actual_c_of_o` | 4.88% | 22.77% |
| `date_done` | 4.96% | 23.02% |
| `due_date` | 14.72% | 45.54% |
| `sold_date` | 1.02% | 4.76% |
| `projected_close_date` | 1.02% | 4.76% |
| `walk_date` | 0.38% | 1.78% |

### Subdivision crosswalk needed (typo + casing variants)

`Aarowhead`/`Aarrowhead` → `Arrowhead Springs`; `Park Way` → `Parkway Fields`; `Willow Creek` → `Willowcreek`; `Scarlett Ridge` → `Scarlet Ridge`; `Salem Fields` → `Salem Fields`; `Lewis Estates` → `Lewis Estates`; `P2 14` → unmapped (likely Harmony Phase A Plat 14 — needs human review).

### Verdict for TaskState

**READY** — filter `subdivision NOT NULL AND lot_num NOT NULL` (1,177 rows), apply subdivision crosswalk, flag Arrowhead lot 173 outlier (75 tasks), propagate `phase` where present (92.86%), null otherwise. Already-staged file is reusable as-is — no re-staging needed; the canonical TaskState load is just a filter + crosswalk.

---

## 4. Allocation workbooks (Tier 4)

All under `data/raw/datarails_unzipped/phase_cost_starter/` (plus `Dehart` at root).

### Flagship Allocation Workbook v3 (5 sheets)

| file | exists | header (0-idx) | grain | rows | ready? |
|---|---|---:|---|---:|---|
| `Flagship Allocation Workbook v3.xlsx - Instructions.csv` | ✅ | n/a | narrative text | 29 | NO — reference text, not data |
| `Flagship Allocation Workbook v3.xlsx - Lot Mix & Pricing.csv` | ✅ | **0** | per (community, phase, lot_type) revenue projection | 89 | YES for ProjectState revenue input |
| `Flagship Allocation Workbook v3.xlsx - Indirect & Land Pools.csv` | ✅ | **0** | per pool row (Type=INDIRECT/LAND, Community, Job Id, Job Name, Budget) | 36 | YES for budget pool input |
| `Flagship Allocation Workbook v3.xlsx - Allocation Engine.csv` | ✅ | **0** | per (community, phase, lot_type) sales-basis allocation | 80 | YES for engine logic but driven by other tabs |
| `Flagship Allocation Workbook v3.xlsx - Per-Lot Output.csv` | ✅ | **0** | per (community, phase, lot_type) total cost / direct / indirect / land | 81 | **MOSTLY EMPTY in current snapshot** — 8 communities × 67 (community, phase) pairs framework, but most cells are $0 |

Coverage: 8 communities (`Arrowhead Springs, Ben Lomond, Harmony, Lewis Estates, Parkway Fields, Salem Fields, Scarlet Ridge, Willowcreek`).

### LH Allocation 2025.10 (6 sheets)

| file | exists | header layout | grain | useable rows | ready? |
|---|---|---|---|---:|---|
| `LH Allocation 2025.10.xlsx - LH.csv` | ✅ | "Summary per lot" section uses cols 5–17 (phase=5, prod=6, lots=7, sales=12, land=13, direct=14, water=15, indirect=16, total=17). Data rows 12–25. | per (phase, prod_type) for Lomond Heights | 12 | **YES** (already in v1; reconstruct Total from land+direct+water+indirect) |
| `LH Allocation 2025.10.xlsx - AAJ.csv` | ✅ | rows 0-1 header (phase names + community labels), wide format | per GL line × per phase (Ben Lomond) | ~50 | partial — entity-level wide format; not stageable as Allocation rows directly |
| `LH Allocation 2025.10.xlsx - BCPBL SB.csv` | ✅ | static loan terms | reference | n/a | NO — static loan reference |
| `LH Allocation 2025.10.xlsx - BSJ.csv` | ✅ | rows 0-1 header, wide format | per GL line × per phase (Salem) | ~25 | partial — entity-level wide format |
| `LH Allocation 2025.10.xlsx - JCSList.csv` | ✅ | header **6** | per QB Job × project × phase | 53 | YES for QB-Job → phase crosswalk |
| `LH Allocation 2025.10.xlsx - PLJ.csv` | ✅ | rows 0-1 header, wide format | per P&L line × per Harmony phase | ~38 | partial — entity-level P&L wide format |

### Parkway Allocation 2025.10 (3 sheets)

| file | exists | header layout | grain | useable rows | ready? |
|---|---|---|---|---:|---|
| `Parkway Allocation 2025.10.xlsx - PF.csv` | ✅ | same shape as `LH.csv`. Data rows 5–22, with section break between rows 9 and 13 | per (phase, prod_type) for Parkway Fields | 14 | **YES** (already in v1) |
| `Parkway Allocation 2025.10.xlsx - AAJ.csv` | ✅ | wide format (phase columns) | per GL line × phase (Parkway) | ~50 | partial — entity-level wide format |
| `Parkway Allocation 2025.10.xlsx - JCSList.csv` | ✅ | header **6** | per QB Job × project × phase | 53 | YES (overlaps with LH JCSList) |

### Dehart Underwriting

| file | exists | header layout | grain | useable rows | ready? |
|---|---|---|---|---:|---|
| `Dehart Underwriting(Summary).csv` | ✅ (loose at repo root) | scattered labels rows 1–15, no consistent header | one-project underwriting model (Payson Larsen) | 0 (not tabular) | NO — wide-formatted summary, not stageable as-is. **Defer.** |

### Allocation entity rows usable today

| project | source | usable rows | confidence |
|---|---|---:|---|
| Lomond Heights | `LH.csv` Summary per lot | 12 | high (already in v1) |
| Parkway Fields | `Parkway PF.csv` Summary per lot | 14 | high (already in v1) |
| Arrowhead Springs / Ben Lomond / Harmony / Lewis Estates / Salem Fields / Scarlet Ridge / Willowcreek | `Flagship Per-Lot Output.csv` framework | 0 effectively | low — framework exists, cells are $0 |
| Dehart / Payson Larsen | `Dehart Underwriting (Summary).csv` | 0 | low — not stageable |

**Verdict for Allocation entity**: ready to **replicate v1** (LH + PF). Expanding org-wide is **blocked** on either populating the Flagship Allocation Workbook v3 or wiring `OfferMaster.csv` as a community×product-type fallback.

---

## 5. Summary verdict table — by Track A entity

| entity | primary source(s) | secondary source(s) | ready? | as_of |
|---|---|---|---|---|
| **InventorySnapshot** | `Inventory _ Closing Report (4).xlsx` (INVENTORY + CLOSED  union) | CLOSINGS (overlay on join key) | **YES** — proposal in C1 | 2026-04-28 |
| **LotState (lifecycle)** | `Lot Data.csv` | `2025Status.csv` (status overlay) | **YES** (already in v1) | 2025-12-31 |
| **CollateralSnapshot** | `Collateral Report.csv` (current) + `PriorCR.csv` (prior) | `IA Breakdown.csv`, `RBA-TNW.csv` (entity tie-out) | **YES** for 9 BCPD projects | 2025-12-31 / 2025-06-30 |
| **Allocation** | `LH.csv` (Lomond Heights) + `Parkway PF.csv` (Parkway Fields) | OfferMaster (community-level fallback), Flagship Per-Lot Output (mostly empty) | **PARTIAL** — replicates v1 only | mixed (workbook export dates) |
| **TaskState** | `staged_clickup_tasks.parquet` filtered to lot-tagged subset (n=1,177) | — | **YES** with subdivision crosswalk | "current" (no explicit as_of) |
| **PhaseState** (rollup) | derived from LotState + Collateral Report + Allocation | — | YES (v1 logic applies) | composite |
| **ProjectState** (rollup) | derived from PhaseState + INVENTORY/CLOSED summary tabs | OfferMaster, Lot Mix & Pricing | partial | composite |

---

## 6. Files inspected but not slated for direct ingestion

These were inspected and are useful for future v2 work or entity-level reconciliation, but should NOT be ingested into Track A entity tables now:

| file | reason |
|---|---|
| `Combined BS.csv` | entity-level balance sheet; label-driven; not lot/phase grain |
| `Cost to Complete Summary.csv` | aggregate global totals only |
| `RBA-TNW.csv` | aggregate-only (collateral bucket totals) |
| `LH AAJ/BSJ/PLJ.csv`, `Parkway AAJ.csv` | wide-format per-GL-line × phase; useful for Terminal B's GL crosswalk, not for Allocation entity |
| `LH BCPBL SB.csv` | static loan terms |
| `Dehart Underwriting (Summary).csv` | non-tabular underwriting model |
| `Flagship Allocation Workbook v3 - Instructions.csv` | narrative text |
| `Inventory _ Closing Report (4).xlsx` — `Planned Starts`, `Forecast` tabs (5x), `Spec Starts`, `Supers Cons. Days`, `Sheet11`, `BCP Prof`, `2018 Tracking`, `dr_control` | non-per-lot grain or out of Track A scope |
| `Inventory _ Closing Report (4).xlsx` — `2015 Closings`…`2026 Closings` (year-by-year tabs) | redundant with `CLOSED ` master tab |

---

## 7. Hard guardrail unblock status

**Guardrail prereq #1**: `data/staged/staged_inventory_lots.{csv,parquet}` exists with validation.

**Status**: **READY for Terminal A to execute.** This report + the C1 proposal in `scratch/ops_inventory_collateral_allocation_findings.md` provide everything needed to stage. Terminal A action item: implement the stage call (sketch in C1), write outputs, draft `data/reports/staged_inventory_lots_validation_report.md`. After that, the guardrail's first prerequisite is green.

---
