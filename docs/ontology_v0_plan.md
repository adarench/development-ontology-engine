# Ontology v0 — Plan

**Owner**: Terminal A (finalizes after worker findings)
**Status**: planning, pre-build
**Builds on**: `ontology/lot_state_v1.md`, `ontology/phase_state_v1.md`, `ontology/data_readiness_audit.md`, `CONTEXT_PACK.md`

This document plans the **first-pass v0 ontology** for Operating State v2. It does not redefine v1 concepts; it extends them. v1 introduced `LotState` (lifecycle + actuals) and `PhaseState` (budget + comparison). v0 promotes those to a small graph of entities and adds the source-system, transaction, allocation, collateral, and inventory entities the new dump now permits.

The ontology is built BCPD-first (Track A). The same shape applies to other entities once they have GL coverage.

## Entity catalog

For each entity: definition, source candidates, required fields, optional fields, likely join keys, confidence rules.

### LegalEntity (a.k.a. Company)
- **Definition**: A legal operating entity that owns/funds projects and against which GL is posted.
- **Source candidates**: GL `CompanyCode/CompanyName` (DataRails 38-col) and `Company/Company Name` (Vertical Financials); filename-implied entity for QB register; future entity master.
- **Required**: `entity_code`, `entity_name`.
- **Optional**: `entity_type` (LLC, etc.), `parent_entity`, `active`.
- **Join keys**: `entity_code` (preferred), `entity_name` (fallback).
- **Confidence rules**: `high` if both code and name agree across sources; `medium` if name-only match; `unmapped` if not seen in any GL source.

### Project (a.k.a. Community)
- **Definition**: A development project (typically a single community / subdivision).
- **Source candidates**: GL `Project` / `ProjectCode` / `ProjectName` (DataRails) and `Project` (Vertical Financials, code only); ClickUp `subdivision`; inventory closing report community column; allocation workbook headers; collateral report rows.
- **Required**: `project_code`, `project_name` (or `community`).
- **Optional**: `parent_entity` (LegalEntity), `start_date`, `total_lots`, `allocation_workbook`.
- **Join keys**: `(entity_code, project_code)`; secondary `project_name` ↔ `subdivision` via crosswalk.
- **Confidence rules**: `high` if appears in GL and inventory and ClickUp under matched names; `medium` if 2-of-3; `low` if only in one source.

### Phase (a.k.a. Plat)
- **Definition**: A phase or plat of a project — a development sub-unit, typically a contiguous lot grouping released as a unit.
- **Source candidates**: GL `Lot/Phase` (combined; DataRails) — phase must be parsed out; allocation workbooks (per-phase tabs); inventory closing report (phase column); collateral report (phase rollups).
- **Required**: `project_code`, `phase_id` (a stable identifier within project), `phase_name` (or `plat_name`).
- **Optional**: `total_lots_in_phase`, `release_date`, `expected_completion`.
- **Join keys**: `(entity_code, project_code, phase_id)`.
- **Confidence rules**: `high` only when phase appears in inventory AND at least one of {GL, allocation, collateral}; otherwise `medium`/`low`. v1 `phase_state_v1.md` defined a `normalize_phase()` rule — extend it.

### Lot
- **Definition**: A single buildable lot within a phase.
- **Source candidates**: ClickUp `lot_num` (lot-tagged subset only); inventory closing report (lot rows); GL `Lot/Phase` (DataRails); GL `Lot` (Vertical Financials); collateral report (lot-level rows where present).
- **Required**: `project_code`, `phase_id`, `lot_number`.
- **Optional**: `lot_type`, `address`, `square_footage`, `assigned_builder`.
- **Join keys**: `(entity_code, project_code, phase_id, lot_number)`.
- **Confidence rules**: `high` if appears in inventory AND at least one of {ClickUp lot-tagged, GL Vertical Financials, allocation per-lot output}; `medium` if 2-of-3; `low` if only in one source.

### TaskState (per-lot lifecycle)
- **Definition**: The current lifecycle stage of a lot (extends v1 `LotState` waterfall).
- **Source candidates**: ClickUp lot-tagged subset (status + dates: walk_date, projected_close_date, actual_c_of_o, sold_date, cancelled_date); inventory closing report (status column); v1 `LotState` waterfall in `ontology/lot_state_v1.md`.
- **Required**: `lot_join_key`, `current_stage`, `as_of_date`.
- **Optional**: `walk_date`, `projected_close_date`, `actual_c_of_o`, `sold_date`, `cancelled_date`, `completion_pct` (state-derived per v1 `LOT_STATE_TO_PCT_COMPLETE`).
- **Join keys**: lot composite key.
- **Confidence rules**: `high` if both ClickUp and inventory agree on stage; `medium` if one source only; `low` if stage is inferred from a single date with no corroboration.

### FinancialTransaction
- **Definition**: A single posted GL transaction line.
- **Source candidates**: `staged_gl_transactions_v2` (already built; 3 source schemas).
- **Required**: `row_hash` (PK), `posting_date`, `entity_code`, `account_code`, `amount`, `source_schema`, `source_file`.
- **Optional**: every other canonical column from the v2 schema.
- **Join keys**: lookup by `row_hash`; aggregate by `(entity_code, project_code, lot, posting_date)`; `transaction_id` + `line_number` is informative but **not unique** — do not use as PK.
- **Confidence rules**: `high` for DataRails 38-col + Vertical Financials 46-col detail rows; `tie-out only` for QB register 12-col by default.

### Account
- **Definition**: GL account in the chart of accounts.
- **Source candidates**: GL `AccountCode/AccountName/AccountType` (DataRails); `Account/Account Name/Account Type/Account Group` (Vertical Financials); QB register account-header parsed strings.
- **Required**: `account_code`, `account_name`.
- **Optional**: `account_type`, `account_group`, `cost_category` (mapped — see v1 `LOT_STATE_TO_COLLATERAL_BUCKET` analogue).
- **Join keys**: `account_code`; secondary `account_name`.
- **Confidence rules**: `high` if account appears in DataRails + Vertical Financials with matching code; `medium` if code-only match; `low` if QB-register-derived (no AccountType info).

### CostCategory
- **Definition**: A business-level cost grouping (e.g. "Permits and Fees", "Direct Construction - Lot", "Shared Cost Alloc.") that maps a set of accounts to a category for rollup. v1 used `COST_TO_DATE_COMPONENTS` for horizontal cost; v0 generalizes.
- **Source candidates**: v1 `pipelines/config.py` `COST_TO_DATE_COMPONENTS` (extend to include vertical components conditionally); GL `Account Group` (Vertical Financials) for a derived category; allocation workbooks for budget-side categories.
- **Required**: `category_code`, `category_name`, `included_account_codes` (or rule).
- **Optional**: `cost_phase_bucket` (HORIZONTAL / VERTICAL / OVERHEAD), `is_actual_only` flag.
- **Join keys**: `category_code`; rule-based mapping `account_code → category_code`.
- **Confidence rules**: `high` for explicitly enumerated categories; `medium` for rule-derived; `low` for QB-register-only categories.

### Allocation (a.k.a. Budget)
- **Definition**: Estimated/budgeted cost for a project / phase / lot / cost-category combination, sourced from allocation workbooks.
- **Source candidates**: `Flagship Allocation Workbook v3.xlsx - *.csv`, `LH Allocation 2025.10.xlsx - *.csv`, `Parkway Allocation 2025.10.xlsx - *.csv`.
- **Required**: `project_code` (or community), `phase_id` (where granular), `lot_number` (where per-lot), `category_code`, `budget_amount`.
- **Optional**: `allocation_method` (per-lot, per-phase, indirect/land-pool), `vintage` (workbook date), `prod_type`.
- **Join keys**: `(entity_code, project_code, phase_id, lot_number, category_code)`; coarser keys when per-lot grain is unavailable.
- **Confidence rules**: `high` for per-lot output sheets (e.g. `LH Allocation - LH.csv`); `medium` for per-phase totals; `low` for indirect/land-pool allocations that are project-wide.

### CollateralSnapshot
- **Definition**: A point-in-time view of project/phase/lot financial position used by lenders (collateral value, advance rate, borrowing-base).
- **Source candidates**: `Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv`, `... - Combined BS.csv`, `... - 2025Status.csv`, `... - IA Breakdown.csv`, `... - PriorCR.csv`, `... - RBA-TNW.csv`. v1 `CONTEXT_PACK.md` describes `LOT_STATE_TO_COLLATERAL_BUCKET` and `ADVANCE_RATES`.
- **Required**: `as_of_date`, `project_code`, `phase_id` (where granular), `collateral_value`, `borrowing_base`.
- **Optional**: `collateral_bucket` (Raw Land … Sold Inventory), `advance_rate`, `lot_count`, `total_dev_cost`.
- **Join keys**: `(entity_code, project_code, phase_id, as_of_date)`.
- **Confidence rules**: `high` for the as-of date the report was generated; snapshots cannot be trended without multiple as-of dates.

### InventorySnapshot
- **Definition**: A point-in-time inventory of lots, their status, and key dates from the inventory closing report.
- **Source candidates**: `Inventory _ Closing Report (4).xlsx` (latest of 3 near-duplicates).
- **Required**: `as_of_date`, lot composite key, `status`, `closing_date_projected`.
- **Optional**: `closing_date_actual`, `address`, `lot_type`, `community`, `builder`.
- **Join keys**: `(entity_code, project_code, phase_id, lot_number, as_of_date)`.
- **Confidence rules**: `high` if the report's as-of date is well-defined; `medium` if header-offset issue is unresolved.

### SourceFile / SourceSystem
- **Definition**: Provenance metadata for every derived field. Every canonical row should be traceable to one or more source files.
- **Source candidates**: `data/manifests/raw_export_manifest.csv`, `data/staged/datarails_raw_file_inventory.csv`, `staged_gl_transactions_v2.source_file` + `source_row_id`.
- **Required**: `source_file`, `source_row_id` (or `row_hash`), `source_system` (DataRails / QuickBooks / ClickUp / etc.), `source_schema`.
- **Join keys**: by `row_hash` for transactions; by file path for everything else.
- **Confidence rules**: `high` whenever provenance is single-source; `medium` when the canonical value coalesces from multiple sources (record both).

## Key relationships

```
LegalEntity ──(funds/owns)──> Project ──(contains)──> Phase ──(contains)──> Lot
                                                                              │
                                                                              ├──> TaskState (current_stage)
                                                                              ├──> InventoryStatus
                                                                              └──> CollateralSnapshot (via Phase rollup)

FinancialTransaction ──(may be tagged with)──> {LegalEntity, Project, Phase, Lot}
                                                                  │
Allocation ──(estimates cost for)──> {Project, Phase, Lot, CostCategory}
                                                                  │
Account ──(belongs to)──> CostCategory
                                                                  │
SourceFile ──(provides provenance for)──> every derived field
```

Important properties of these edges:
- The `FinancialTransaction → Lot` edge is **partial**. v2 GL has 100% lot fill on Vertical Financials (BCPD 2018-2025) and ~50% on DataRails 38-col. Cost rollups must account for the unattributed remainder.
- The `Lot → TaskState` edge depends on the **lot-tagged ClickUp subset** (~1,177 rows of 5,509). Lots not in that subset have no TaskState from ClickUp and must rely on inventory + GL inference.
- `Allocation → Lot` grain varies by workbook. Track A treats per-lot allocations as `high` confidence and project-wide indirect pools as `low`.

## Versioning

- This is **v0**. The ontology will iterate as worker findings land, the crosswalk is built, and the inventory is staged.
- v0 is BCPD-scoped. The shape of every entity is generic; the population is BCPD-first.
- `ontology/lot_state_v1.md` and `ontology/phase_state_v1.md` are **referenced**, not replaced. Their definitions still apply for the BCPD lots that have v1-compatible data.

## What this doc does not do

- It does not define the field-level mapping (see `docs/field_map_v0_plan.md`).
- It does not define the crosswalk between source vocabularies (Terminal A's later `docs/crosswalk_plan.md`).
- It does not enumerate the actual entities (e.g. the list of BCPD projects) — that comes from the integration step after worker findings.
