# Source → Field Map (v0)

**Owner**: Terminal A (integrator)
**Status**: built (post-worker findings)
**Last updated**: 2026-05-01
**Companion**: `docs/field_map_v0.csv` (canonical CSV — one row per canonical field)

This is the human-readable companion to `docs/field_map_v0.csv`. The CSV is
structured for a builder; this MD is structured for a reader who wants to know
"if I'm answering question X, where does the data come from?"

---

## Identity

### `canonical_entity`
**What it is**: Short canonical legal-entity code. v0 in-scope values: `BCPD`, `BCPBL`, `ASD`, `BCPI`. Out-of-scope: `Hillcrest`, `Flagship Belmont`, `Lennar`, `EXT`.

**Sources, in order of authority**:
1. GL `entity_name` (DataRails 38-col `CompanyName`, Vertical Financials `Company Name`) — authoritative.
2. `2025Status.HorzCustomer` (`BCP` → BCPD, `Lennar`, `EXT`, `Church`) — for vertical builder identity.
3. `Lot Data.HorzSeller` (`BCPD`, `BCPBL`, `ASD`, `BCPI`) — for horizontal developer identity.
4. QB-register filename (`Collateral Dec2025 - BCPD GL Detail.csv` → BCPD) — single-entity by export.

**Crosswalk**: `data/staged/staged_entity_crosswalk_v0.csv`.

### `canonical_project`
**What it is**: Project / community canonical name. 16 active BCPD projects from 2025Status; 17 with Meadow Creek; 42 total including historical.

**Sources, in order of authority**:
1. `2025Status.Project` and `Lot Data.Project` (identical names; identity mapping).
2. `Collateral Report.Project` (adds Meadow Creek).
3. `inventory.subdiv` → canonical via `SUBDIV_TO_PROJECT` map (in `financials/stage_inventory_lots.py`).
4. GL `project_code` (DR 38-col + VF 46-col) → canonical via `staged_project_crosswalk_v0`. Two different code vocabularies between the DR-era (pre-2018) and VF-era (2018-2025) — collapse via xwalk.
5. ClickUp `subdivision` → canonical via xwalk (typo-tolerant).

**Crosswalk**: `data/staged/staged_project_crosswalk_v0.csv` (142 rows).

### `canonical_phase`
**What it is**: Phase / plat label, whitespace-normalized per v1 `pipelines/config.py:normalize_phase`.

**Sources**: `Lot Data.Phase`, `2025Status.Phase`, `inventory.phase`, `clickup.phase`. **Note: GL has 0% phase fill** across all 3 source schemas — phase cannot be derived from GL.

**Crosswalk**: `data/staged/staged_phase_crosswalk_v0.csv` (385 rows).

### `canonical_lot_id`, `canonical_lot_number`
**What it is**: `canonical_lot_id` is an opaque blake2s-8 hash of `(canonical_project | canonical_phase | canonical_lot_number)`. `canonical_lot_number` is the normalized lot string (strip `.0`, strip leading zeros from numeric prefix, preserve alpha suffix).

**Sources**: inventory (primary), Lot Data, 2025Status, ClickUp lot-tagged subset, GL VF/DR. GL VF lot codes encode phase+lot together for some projects (`Harm3` lot `1034` ≠ inventory Harmony lot `1034`); v0 normalizer does not decode this — see `docs/crosswalk_plan.md` § 5.

**Crosswalk**: `data/staged/staged_lot_crosswalk_v0.csv` (14,537 rows).

---

## Lifecycle / state

### `lot_status` (a.k.a. `inventory_status`)
**What it is**: `ACTIVE` (sold-but-not-closed or held), `CLOSED` (closing_date ≤ as_of), `ACTIVE_PROJECTED` (closing_date > as_of, forward projection from CLOSED tab).

**Source**: `staged_inventory_lots.lot_status` — derived at stage time. As-of date 2026-04-29.

### `current_stage`
**What it is**: Canonical lifecycle stage from v1 `LOT_STATE_WATERFALL`. Values: `PROSPECT`, `LAND_OWNED`, `HORIZONTAL_IN_PROGRESS`, `FINISHED_LOT`, `VERTICAL_PURCHASED`, `VERTICAL_IN_PROGRESS`, `VERTICAL_COMPLETE`, `SOLD_NOT_CLOSED`, `CLOSED`.

**Sources** (in order of authority):
1. `Lot Data.{horz_*_date, vert_*_date}` — apply v1 waterfall.
2. `inventory.lot_status` — coarse but corroborates.
3. `clickup.status` (where lot-tagged) — corroborates.

### `completion_pct`
**What it is**: Approximate % complete from `current_stage`, per v1 `LOT_STATE_TO_PCT_COMPLETE` map (e.g. `LAND_OWNED=0.05`, `VERTICAL_IN_PROGRESS=0.55`, `VERTICAL_COMPLETE=0.85`, `SOLD_NOT_CLOSED=0.95`). `PROSPECT` and `CLOSED` return null.

---

## Financial — actuals

### `actual_cost`
**What it is**: Realized cost, sum of GL `amount` filtered by category and scope.

**Sources, by era**:
- 2018-2025 BCPD: `vertical_financials_46col` rows. **Primary.** 100% project + lot fill; 1,306 distinct (project, lot) pairs; legacy chart of accounts; one-sided cost-accumulation feed (asset-side debit only).
- 2016-02 → 2017-02 BCPD: `datarails_38col` rows, **after row-multiplication dedup** on key `(entity_name, posting_date, account_code, amount, project, lot, memo_1, description, batch_description)`. DR is 2.16× row-multiplied at source.
- 2017-03 → 2018-06 BCPD: **GAP**. Zero rows. Cannot be reconstructed from the dump.
- 2025 BCPD QB register: **excluded** from primary rollups; tie-out only. Different chart of accounts; would double-count if naively summed against VF.

See `data/reports/guardrail_check_v0.md` § BCPD cost-source hierarchy and § DataRails dedup decision.

### `posting_date`, `account_code`, `account_name`, `amount`
Direct passthroughs from `staged_gl_transactions_v2`. `amount` is signed (positive = debit, negative = credit).

### `cost_category`
**What it is**: Business cost grouping (e.g. `PERMITS_FEES`, `DIRECT_CONSTRUCTION_LOT`, `VERTICAL_COSTS`).

**Source**: rule-based mapping `(source_schema, account_code) → category_code`. Defined in `data/staged/canonical_cost_category.csv` (9 v0 categories).

---

## Financial — budget / allocation

### `budget_cost`, `allocation_amount`
**Sources, by project**:
- Lomond Heights: `LH Allocation 2025.10 - LH.csv` (12 phase × prod_type rows). Already wired in v1.
- Parkway Fields: `Parkway Allocation 2025.10 - PF.csv` (14 rows). Already wired in v1.
- Other BCPD projects (Arrowhead Springs, Ben Lomond, Harmony, Lewis Estates, Salem Fields, Scarlet Ridge, Willowcreek): `Flagship Allocation Workbook v3 - Per-Lot Output.csv` framework is in place but cells are **mostly empty**. Don't promise expanded coverage yet.
- Dehart / Payson Larsen: out of scope for v0 (not stageable as-is).

### `remaining_cost`
`= budget_cost − actual_cost`. Inherits worst confidence of the two.

---

## Collateral

### `collateral_value`, `borrowing_base`, `advance_pct`, `lot_count`
**Source**: `Collateral Dec2025 - Collateral Report.csv` (41 phase rows, as_of 2025-12-31). **9 of 16 active BCPD projects have rows**. The 7 missing (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge — plus Lewis Estates with 34 lots) are not pledged collateral and have no row. Document the gap; do not estimate.

### `collateral_bucket`
**Source**: `2025Status.Collateral Bucket` (per-lot) or derived from `current_stage` via `pipelines/config.py:LOT_STATE_TO_COLLATERAL_BUCKET`. Drives advance-rate weighted exposure.

### Prior period
`Collateral Dec2025 - PriorCR.csv` (as_of 2025-06-30). Same schema as Collateral Report; useful for delta computations.

---

## Inventory

### `sale_date`, `closing_date_actual`, `closing_date_projected`, `permit_pulled_date`, `sales_price`, `deposit`, `margin_pct`, `buyer`, `plan_name`
**Source**: `staged_inventory_lots` (3,872 rows; as_of 2026-04-29).

`closing_date_actual` is `closing_date` where `closing_date <= as_of_date`; `closing_date_projected` is `closing_date > as_of_date` from CLOSED tab + `CLOSINGS.ESTIMATED CLOSING`. Excel sentinel `1899-12-30` is treated as null.

---

## Task / ClickUp

### `clickup_status`, `walk_date`, `projected_close_date_clickup`, `actual_c_of_o`, `sold_date_clickup`, `due_date`
**Source**: `staged_clickup_tasks` filtered to lot-tagged subset (`subdivision IS NOT NULL AND lot_num IS NOT NULL`, n=1,177).

Date coverage in lot-tagged subset:
- `actual_c_of_o`: 22.77%
- `due_date`: 45.54%
- `projected_close_date`: 4.76%
- `walk_date`: 1.78%

Apply subdivision crosswalk (typo-tolerant: `Aarowhead → Arrowhead Springs`, `Scarlett Ridge → Scarlet Ridge`, etc.). Flag the Arrowhead-173 outlier (75 tasks on one lot — likely template parent).

---

## Provenance

### `source_file`, `source_row_id`
Always populated. For GL rows: `staged_gl_transactions_v2.{source_file, source_row_id}`. For inventory: `source_file = 'Inventory _ Closing Report (2).xlsx'`, `source_row_number` = row position in the source sheet. For ClickUp: index in the staged file.

### `source_confidence`
Per-row rollup of all field confidences contributing to the canonical value. **Worst-link semantics**: the minimum of contributing-field confidences. Values: `high` / `medium` / `low` / `unmapped`. Consumers SHOULD filter by this when answering business questions.

### `as_of_date`
- Inventory: `2026-04-29` (data-derived; max INVENTORY.SALE DATE in workbook 2).
- Collateral Report: `2025-12-31`.
- Collateral PriorCR: `2025-06-30`.
- GL VF: max posting_date `2025-12-31`.
- ClickUp: "current" (no explicit as-of in source; downstream agents should not over-claim).

---

## Cross-source field availability matrix (BCPD scope)

| field | inventory | LotData | 2025Status | Collateral | GL VF | GL DR | ClickUp |
|---|---|---|---|---|---|---|---|
| canonical_entity | derived | yes (HorzSeller) | yes (HorzCustomer) | implicit | yes (entity_name) | yes (entity_name) | derived |
| canonical_project | yes (subdiv→) | yes (Project) | yes (Project) | yes (Project) | yes (project_code→xwalk) | yes (project_code→xwalk) | yes (subdivision→) |
| canonical_phase | yes (phase) | yes (Phase) | yes (Phase) | yes (Phase) | **NO** (0% fill) | **NO** (0% fill) | sparse (~93% within lot-tagged) |
| canonical_lot_number | yes (lot_num) | yes (LotNo.) | yes (Lot) | n/a | yes (lot, 100% in BCPD) | yes (lot, 49.5% in BCPD) | yes (lot_num, in lot-tagged) |
| current_stage | derived (lot_status) | derived (waterfall) | derived | derived | derived | derived | yes (status) |
| actual_cost | n/a | n/a | partial (status sums) | n/a | **YES** (primary) | yes (after dedup) | n/a |
| budget_cost | n/a | n/a | n/a | yes (Total Dev Cost) | n/a | n/a | n/a |
| collateral_value | n/a | n/a | yes (Lot Cost) | **YES** (primary) | n/a | n/a | n/a |
| sale_date | yes | yes (HorzSale, VertSale) | yes (Status Date) | n/a | n/a | n/a | yes (sold_date) |
| closing_date_actual | yes | yes (VertClose) | yes | n/a | n/a | n/a | yes (actual_c_of_o) |

---

## Versioning notes

- `canonical_phase` and `canonical_lot_number` may need a v1 follow-up to add a phase-aware decoder for GL VF lot codes (e.g. `Harm3` lot `1034` → Harmony Phase 3 Lot 34). v0 collapses VF codes to project level only.
- `cost_category` mapping is a v0 starter; expect refinement as Terminal B's account inventory is reviewed.
- New v2 fields can be added without breaking v0 consumers as long as the worst-link `source_confidence` rule is preserved.
