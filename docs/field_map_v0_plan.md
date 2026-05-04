# Field Map v0 — Plan

**Owner**: Terminal A
**Status**: planning, pre-build
**Companion to**: `docs/ontology_v0_plan.md`

This document plans the canonical field map for Operating State v2. The actual map (`docs/field_map_v0.csv` + `docs/source_to_field_map.md`) is produced by Terminal A after worker findings.

## Field-map row format

Each row in the final `docs/field_map_v0.csv` will carry:

| column | meaning |
|---|---|
| `canonical_field` | The v0 canonical name (snake_case). |
| `business_definition` | Plain-English meaning, written for an analyst, not a developer. |
| `source_candidates` | Pipe-separated source files / tables that may provide the field. |
| `source_columns_by_schema` | Per source schema: which raw column maps in. |
| `expected_type` | `string`, `int`, `float`, `date`, `bool`, `currency_usd`, `enum:<...>`. |
| `confidence_rule` | When does the canonical value qualify as `high` / `medium` / `low` / `unmapped`. |
| `fallback_rule` | If the primary source is missing or null, what is the order of fallbacks (and what confidence drop applies). |
| `owner_source_system` | Authoritative system for this field (DataRails, QuickBooks, ClickUp, Inventory, Allocation, Crosswalk). |
| `nullable` | Whether null is a valid value (some fields must be present, like `posting_date` for a transaction). |
| `notes` | Edge cases, gotchas, links to validation. |

## Required fields (v0)

The fields below MUST appear in the final field map. Each is sketched here with the planned mapping; Terminal A finalizes after worker findings.

### Identity / scope

| canonical_field | business definition | sources (per schema) | confidence rule (sketch) |
|---|---|---|---|
| `legal_entity` | The LLC that owns/funds the project. | DataRails `CompanyName`; Vertical Financials `Company Name`; QB register `constant 'Building Construction Partners, LLC'`; ClickUp via crosswalk. | `high` if appears in GL with a populated `entity_code`; `medium` if name-only; `unmapped` otherwise. |
| `entity_code` | Short numeric/code form of the entity. | DataRails `CompanyCode`; Vertical Financials `Company`; QB register `constant '1000'`. | `high` if matches across ≥2 GL sources. |
| `project_code` | Project / community code. | DataRails `ProjectCode`; Vertical Financials `Project` (single col); ClickUp via crosswalk; allocation workbook headers. | `high` if exists in GL + appears in inventory; `medium` if GL-only or inventory-only. |
| `project_name` | Project / community readable name. | DataRails `ProjectName`; ClickUp `subdivision`; inventory column; collateral report. | `high` if matches `project_code` resolution; `medium` if name-only. |
| `community` | Same as `project_name` for now (alias). | Same as `project_name`. | Same. |
| `phase_id` | Stable phase identifier within project. | DataRails `Lot/Phase` (parsed); allocation tabs; inventory phase column; collateral phase rollup. | `high` if appears in inventory + at least one of {GL, allocation}. |
| `phase_name` | Phase readable name (e.g. "Phase 2"). | Allocation workbooks; inventory; v1 `normalize_phase()`. | `high` if normalized form matches v1 rule. |
| `plat_name` | Plat name (often a synonym for phase). | Inventory; collateral. | `medium` if plat ≠ phase under v1 normalization. |
| `lot_number` | Lot identifier within phase. | ClickUp `lot_num` (lot-tagged subset only); inventory; GL `Lot/Phase` (DataRails) and `Lot` (Vertical Financials); allocation per-lot output. | `high` if appears in inventory + at least one of {ClickUp, GL, allocation}; `medium` if 2-of-3. |
| `lot_type` | Lot type / product type. | Allocation per-lot output (`prod_type`); inventory `lot_type`. | `medium` baseline; promote to `high` if both agree. |

### Lifecycle / state

| canonical_field | business definition | sources | confidence rule (sketch) |
|---|---|---|---|
| `lot_status` | High-level lot status (e.g. AVAILABLE, UNDER_CONSTRUCTION, SOLD, CLOSED, CANCELLED). | Inventory column; ClickUp `status` (lot-tagged subset). | `high` if both agree; `medium` if one source; if disagreement, prefer inventory and flag. |
| `task_stage` | ClickUp stage label (raw). | ClickUp `status`. | `high` for the lot-tagged subset. |
| `current_stage` | Canonical lifecycle stage from v1 waterfall (`pipelines/config.py LOT_STATE_WATERFALL`). | Derived from date fields. | `high` if waterfall converges; `medium` if only one date is populated. |
| `completion_pct` | Approximate % complete from current_stage. | Derived via v1 `LOT_STATE_TO_PCT_COMPLETE`. | Inherits confidence of `current_stage`. |

### Financial — actuals

| canonical_field | business definition | sources | confidence rule (sketch) |
|---|---|---|---|
| `posting_date` | GL posting date for the transaction. | DataRails `PostingDate`; Vertical Financials `Posting Date`; QB register `Date`. | `high` for all 3 source schemas. **NOT NULL** for any FinancialTransaction row. |
| `account_code` | GL account code. | DataRails `AccountCode`; Vertical Financials `Account`; QB register parsed from forward-filled header. | `high` for DataRails + Vertical Financials; `medium` for QB register (parsed). |
| `account_name` | GL account name. | DataRails `AccountName`; Vertical Financials `Account Name`; QB register parsed. | DataRails has 53.77% fill; Vertical Financials 100%; QB register parsed always. |
| `cost_category` | Business cost grouping (extends v1 `COST_TO_DATE_COMPONENTS`). | Rule on `account_code` + `account_group`. | `high` for explicitly enumerated categories; `medium` for rule-derived. |
| `actual_cost` | Realized cost — sum of GL `amount` filtered by category and scope. | `staged_gl_transactions_v2.amount`. | `high` for the in-scope (BCPD-tagged) rows; `tie-out only` for QB register overlap. |

### Financial — budget

| canonical_field | business definition | sources | confidence rule (sketch) |
|---|---|---|---|
| `budget_cost` | Budgeted/expected cost from allocation workbooks. | Per-lot output sheets (LH, Parkway, Flagship); per-phase totals; indirect/land-pool allocations. | `high` for per-lot output; `medium` for per-phase; `low` for indirect pools. |
| `remaining_cost` | `budget_cost - actual_cost` (signed). | Derived. | Inherits min(budget, actual) confidence. |
| `allocation_amount` | Raw allocation row amount before category mapping. | Allocation workbooks. | Same as `budget_cost`. |

### Collateral / inventory

| canonical_field | business definition | sources | confidence rule (sketch) |
|---|---|---|---|
| `collateral_value` | Lender-recognized value (raw or per-bucket × advance rate). | Collateral Report; v1 `ADVANCE_RATES`. | `high` for the as-of date of the report; not trendable without multiple snapshots. |
| `collateral_bucket` | Lender bucket per `LOT_STATE_TO_COLLATERAL_BUCKET`. | Derived from `current_stage`. | Inherits `current_stage`. |
| `inventory_status` | Status from the inventory closing report. | Inventory closing report. | `high` after header offset is fixed and column mapping verified. |
| `closing_date_projected` | Projected closing date. | Inventory closing report; ClickUp `projected_close_date`. | `high` if both agree; ClickUp authoritative for the lot-tagged subset. |
| `closing_date_actual` | Actual close-of-O date. | Inventory; ClickUp `actual_c_of_o`. | Same. |

### Provenance (every row carries these)

| canonical_field | business definition | source | confidence rule |
|---|---|---|---|
| `source_file` | File the value originated from. | Always populated. | n/a (provenance) |
| `source_row_id` | Row identifier within the source file. | `staged_gl_transactions_v2.source_row_id` for GL; index for others. | n/a |
| `source_confidence` | Per-row rollup of all field confidences contributing to the canonical value. | Computed in canonical builder. | One of `high`, `medium`, `low`, `unmapped`. |

## Confidence semantics (project-wide)

- `high` — value is corroborated by ≥2 sources OR comes from the authoritative source for that field.
- `medium` — single-source value where the source is reliable for the field type but not the authoritative one.
- `low` — derived/inferred value, or single-source value where the source is known to be partial.
- `unmapped` — field could not be populated; the row carries `null` and the consumer must handle it explicitly.

`source_confidence` on a canonical row is the **min** of contributing-field confidences (worst-link semantics). This prevents a single low-confidence dimension from being washed out in rollups.

## Sources of truth (preliminary, subject to worker findings)

| canonical field family | preferred source for BCPD 2018-2025 | preferred source for BCPD 2016-2017 | notes |
|---|---|---|---|
| Identity (entity, project, phase, lot) | Vertical Financials (`Project`, `Lot`) + Inventory | DataRails 38-col + Inventory (where dates overlap) | Crosswalk required regardless. |
| Lifecycle (`lot_status`, `current_stage`) | Inventory + ClickUp lot-tagged | v1 lifecycle waterfall (date-based) | ClickUp dates only exist for ~5% of tasks; degrade gracefully. |
| Actuals (`actual_cost`) | Vertical Financials | DataRails 38-col | QB register tie-out only. |
| Budget (`budget_cost`) | Allocation workbooks | Allocation workbooks | Vintage matters; treat as point-in-time. |
| Collateral | Collateral Report (Dec 2025) | n/a (no 2016-17 collateral file in dump) | Single snapshot only. |

## What this doc does not do

- It does not enumerate the final list of canonical columns in the v2 output schema; that's `docs/operating_state_v2_build_plan.md` (Terminal A, later).
- It does not specify the actual rule for `account_code → cost_category` mapping; that requires Terminal B's account inventory.
- It does not specify the per-row confidence math beyond "min of contributing fields"; the implementation is Terminal A's later work.
