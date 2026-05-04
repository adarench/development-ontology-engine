# Ontology v0 — Final

**Owner**: Terminal A (integrator)
**Status**: built (post-worker findings)
**Last updated**: 2026-05-01
**Builds on**: `docs/ontology_v0_plan.md`, `ontology/lot_state_v1.md`, `ontology/phase_state_v1.md`, `ontology/data_readiness_audit.md`, `CONTEXT_PACK.md`
**Companion**: `docs/field_map_v0.csv`, `docs/source_to_field_map.md`, `docs/crosswalk_plan.md`

This document finalizes the v0 ontology for Operating State v2. v1 introduced
`LotState` (lifecycle + actuals) and `PhaseState` (budget + comparison); v0
promotes those to a graph of canonical entities, populated from real source
data via the v0 crosswalks.

v0 is **BCPD-scoped**. The shape of every entity is generic; the population is
BCPD-first. Org-wide remains blocked (Hillcrest, Flagship Belmont) — see
`scratch/bcpd_financial_readiness.md` org-wide blocker paragraph.

---

## 1. Entity catalog (with actual sources and BCPD instance counts)

### LegalEntity
- **Definition**: A legal operating entity that owns/funds projects and against which GL is posted.
- **Sources**: `gl_v2.entity_name` (authoritative), `2025Status.HorzCustomer`, `Lot Data.HorzSeller`, QB-register filename.
- **Required**: `canonical_entity`, `long_name`.
- **Optional**: `role`, `in_scope` (boolean — BCPD v2).
- **Join key**: `canonical_entity`.
- **Confidence**: `high` for GL-corroborated entities; `medium` for `BCPI` (only 12 lots in `Lot Data.HorzSeller`).
- **Implementation**: `data/staged/canonical_legal_entity.{csv,parquet}` (8 rows).
- **BCPD count**: 4 in scope (`BCPD`, `BCPBL`, `ASD`, `BCPI`); 4 out of scope (`Hillcrest`, `Flagship Belmont`, `Lennar`, `EXT`).

### Project
- **Definition**: A development project (typically a single community / subdivision).
- **Sources**: GL `project_code` (DR 38-col + VF 46-col), `inventory.subdiv` (post-stage), `Lot Data.Project`, `2025Status.Project`, `Collateral Report.Project`, `clickup.subdivision`, allocation workbook headers.
- **Required**: `canonical_project`, `canonical_entity`.
- **Optional**: `lot_count_2025status`, `lot_count_inventory`, `gl_row_count`, presence flags per source.
- **Join keys**: `(canonical_entity, canonical_project)`; secondary by `staged_project_crosswalk_v0` lookup of source_value.
- **Confidence**: `high` if appears in 2+ of {inventory, Lot Data, 2025Status} or 1 ops + 1 GL source. Otherwise `medium`/`low`.
- **Implementation**: `data/staged/canonical_project.{csv,parquet}` (42 rows in BCPD scope, includes historical).
- **BCPD count**: **42 distinct canonical projects** (16 active per 2025Status, 17 active w/ Meadow Creek, plus 25 historical pre-2018 communities). High-confidence: 22; medium: 20.

### Phase
- **Definition**: A phase or plat of a project — a development sub-unit.
- **Sources**: `inventory.phase`, `Lot Data.Phase`, `2025Status.Phase`, `clickup.phase` (lot-tagged subset only), allocation workbooks per-phase tabs. **GL does not carry phase grain** (0% fill on all 3 source schemas).
- **Required**: `canonical_entity`, `canonical_project`, `canonical_phase`.
- **Optional**: `lot_count`, presence flags per source.
- **Join key**: `(canonical_entity, canonical_project, canonical_phase)`.
- **Confidence**: `high` for phases appearing in ≥2 of {inventory, Lot Data, 2025Status}; `medium` for 1; `low` for ClickUp-only.
- **Implementation**: `data/staged/canonical_phase.{csv,parquet}` (215 rows; 125 high, 90 medium).
- **BCPD count**: 215 distinct `(project, phase)` pairs in BCPD scope.

### Lot
- **Definition**: A single buildable lot within a phase.
- **Sources**: `inventory.{subdiv,phase,lot_num}` (UNION of INVENTORY + CLOSED  tabs), `Lot Data.{Project,Phase,LotNo.}`, `2025Status.{Project,Phase,Lot}`, `clickup.{subdivision,phase,lot_num}` (lot-tagged subset only), GL `(project_code,lot)` (DR 38-col + VF 46-col).
- **Required**: `canonical_lot_id` (= `blake2s_8(project|phase|lot_num)`), `canonical_entity`, `canonical_project`, `canonical_phase`, `canonical_lot_number`.
- **Optional**: `lot_status` (from inventory), `horz_customer` (from Lot Data / 2025Status), `horz_seller`, presence flags per source.
- **Join key**: `canonical_lot_id` (preferred) or `(canonical_project, canonical_phase, canonical_lot_number)`.
- **Confidence**: worst-link of project_confidence and source-count. `high` for in_inventory + in_lot_data + in_2025status with HorzCustomer=BCP.
- **Implementation**: `data/staged/canonical_lot.{csv,parquet}` (6,908 rows; 6,087 BCPD-scope).
- **BCPD count**: ~2,797 active BCPD-built lots (HorzCustomer=BCP) per 2025Status; 6,087 total including historical CLOSED-tab lots.

### TaskState (per-lot lifecycle)
- **Definition**: Current lifecycle stage of a lot — extends v1 `LotState` waterfall.
- **Sources**: `staged_clickup_tasks` filtered to `subdivision IS NOT NULL AND lot_num IS NOT NULL` (n=1,177); `inventory.lot_status`; v1 lifecycle waterfall in `pipelines/config.py:LOT_STATE_WATERFALL`.
- **Required**: `canonical_lot_id`, `current_stage`, `as_of_date`.
- **Optional**: `walk_date`, `projected_close_date`, `actual_c_of_o`, `sold_date`, `cancelled_date`, `completion_pct`.
- **Join key**: `canonical_lot_id`.
- **Confidence**: `high` if both ClickUp and inventory agree on stage; `medium` if one source; `low` if waterfall-derived only. Apply v1 `pipelines/config.py:LOT_STATE_TO_PCT_COMPLETE` to derive completion_pct.
- **Implementation**: derived in v2 build (A8); not a separate canonical table.

### FinancialTransaction
- **Definition**: A single posted GL transaction line.
- **Sources**: `data/staged/staged_gl_transactions_v2.{csv,parquet}` (210,440 rows; 197,852 BCPD).
- **Required**: `row_hash` (PK), `posting_date`, `entity_name`, `account_code`, `amount`, `source_schema`, `source_file`.
- **Optional**: every other v2 column.
- **Join key**: `row_hash` for lookup; aggregate by `(entity_name, project_code → canonical_project, canonical_lot_id)`.
- **Confidence**: `high` for VF 46-col detail rows (BCPD 2018-2025); **`high after dedup`** for DR 38-col (raw rows are 2.16× multiplied; see `data/reports/guardrail_check_v0.md` § DataRails dedup decision); `tie-out only` for QB 12-col by default.

### Account
- **Definition**: GL account in the chart of accounts.
- **Sources**: GL `account_code/account_name/account_type/account_group` (per source_schema).
- **Required**: `account_code`, `account_name`, `source_schema`.
- **Optional**: `account_type`, `account_group`, `row_count`, `sum_amount`.
- **Join key**: `(source_schema, account_code)`.
- **Confidence**: `high` for DR 38-col + VF 46-col; `medium` for QB 12-col (parsed from forward-filled headers, no AccountType info).
- **Implementation**: `data/staged/canonical_account.{csv,parquet}` (335 rows: 155 DR + 3 VF + 177 QB).
- **Important**: DR/VF share the legacy 4-digit chart; QB uses a different newer chart. **No account_code overlap between QB and DR/VF** — see `scratch/gl_financials_findings.md` § B5.

### CostCategory
- **Definition**: A business-level cost grouping (e.g. "Permits and Fees", "Direct Construction - Lot") that maps a set of accounts to a category for rollup.
- **Sources**: v1 `pipelines/config.py:COST_TO_DATE_COMPONENTS` extended with vertical components from VF; allocation workbooks for budget-side categories.
- **Required**: `category_code`, `category_name`, `cost_phase_bucket`.
- **Optional**: `matches_status_column`, `vf_account_codes`, `dr_account_codes`, `is_actual_only`.
- **Join key**: `category_code`; rule-based mapping `(source_schema, account_code) → category_code`.
- **Confidence**: `high` for explicitly enumerated categories; `medium` for rule-derived; `low` for QB-only.
- **Implementation**: `data/staged/canonical_cost_category.{csv,parquet}` (9 rows).

### Allocation (a.k.a. Budget)
- **Definition**: Estimated/budgeted cost for a project/phase/lot/cost-category combination, sourced from allocation workbooks.
- **Sources**: `LH Allocation 2025.10 - LH.csv` (Lomond Heights, 12 phase×prod_type rows), `Parkway Allocation 2025.10 - PF.csv` (Parkway Fields, 14 rows), Flagship Allocation Workbook v3 (framework — currently mostly empty), Dehart Underwriting (out of scope).
- **Required**: `canonical_project`, `canonical_phase` or `canonical_lot_id`, `category_code`, `budget_amount`.
- **Optional**: `allocation_method`, `vintage`, `prod_type`.
- **Join key**: same as the grain.
- **Confidence**: `high` for per-lot or per-phase output sheets (LH, PF); `low` for indirect/land-pool aggregations or Flagship-empty cells.
- **Implementation**: not built as a separate canonical table in v0 — read live from v1's existing builders. v1 already wires LH and PF; v0 makes no changes.

### CollateralSnapshot
- **Definition**: Point-in-time view of project/phase financial position used by lenders.
- **Sources**: `Collateral Dec2025 - Collateral Report.csv` (41 phase rows), `... - PriorCR.csv` (prior period 2025-06-30, 41 rows), `... - 2025Status.csv` (3,627 lot rows), `... - IA Breakdown.csv`, `... - RBA-TNW.csv`.
- **Required**: `as_of_date`, `canonical_project`, `canonical_phase` (where granular), `total_dev_cost`, `borrowing_base`, `advance_pct`.
- **Optional**: `collateral_bucket`, `lot_count`, `paper_lot_value`, `finished_lot_value`.
- **Confidence**: `high` for as-of date 2025-12-31; **9 of 16 BCPD active projects have rows** (7 missing: Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge; per `scratch/bcpd_ops_readiness.md`).

### InventorySnapshot
- **Definition**: Point-in-time inventory of lots, status, and key dates from `Inventory _ Closing Report (2).xlsx`.
- **Source**: `data/staged/staged_inventory_lots.{csv,parquet}` (3,872 rows).
- **Required**: `as_of_date`, `canonical_lot_id`, `lot_status` (`ACTIVE` / `CLOSED` / `ACTIVE_PROJECTED`).
- **Optional**: `subdiv`, `phase`, `lot_num`, `plan_name`, `buyer`, `sales_price`, `deposit`, `sale_date`, `permit_pulled_date`, `permit_number`, `margin_pct`, `closing_date`, `dig_date`, `anticipated_completion`.
- **Confidence**: `high` for the as-of date 2026-04-29.

### SourceFile / SourceSystem
- **Definition**: Provenance metadata for every derived field.
- **Sources**: `data/staged/datarails_raw_file_inventory.{csv,md}`, `staged_gl_transactions_v2.{source_file, source_row_id}`, every staged table carries source columns.
- **Confidence**: `high` whenever provenance is single-source; `medium` when multi-source coalesce.

---

## 2. Key relationships

```
LegalEntity ──(funds/owns)──> Project ──(contains)──> Phase ──(contains)──> Lot
                                                                              │
                                                                              ├──> TaskState (current_stage)
                                                                              ├──> InventoryStatus (lot_status)
                                                                              └──> CollateralSnapshot (via Phase rollup)

FinancialTransaction ──(may be tagged with)──> {LegalEntity, Project, Phase=∅, Lot}
                                                                  │
                                                                  └─ phase tag is empty in GL — derive from Lot or Inventory
Allocation ──(estimates cost for)──> {Project, Phase, Lot, CostCategory}
Account ──(belongs to)──> CostCategory
SourceFile ──(provides provenance for)──> every derived field
```

**Cardinalities (BCPD scope)**:
- 1 BCPD entity → 42 canonical projects (17 active including Meadow Creek + 25 historical)
- 1 active BCPD project → 1-13 phases (Parkway Fields has 13; Harmony has 8)
- 1 BCPD phase → 1-N lots (mean ≈ 13 lots/phase per 2025Status)
- 1 BCPD lot → ≤ N FinancialTransactions across DR + VF (BCPD has 1,306 distinct (project, lot) in VF; lots without VF coverage rely on inventory + ClickUp only)
- 1 BCPD lot → ≤ 1 InventorySnapshot row (3,872 rows in `staged_inventory_lots`; ~2,800 BCPD-built per HorzCustomer=BCP)
- 1 BCPD lot → 0 or 1 ClickUp lot-tagged tasks (1,091 distinct lots in lot-tagged subset; 75 max tasks/lot — Arrowhead-173 outlier flagged)

**Edge confidence**:
- `FinancialTransaction → Lot` is **partial**: VF gives 100% lot fill on BCPD 2018-2025; DR gives 49.5% lot fill on BCPD 2016-2017. Cost rollups must account for the unattributed remainder.
- `Lot → TaskState` depends on the lot-tagged ClickUp subset (~1,177 of 5,509 tasks). Lots not in that subset have no TaskState from ClickUp; rely on inventory + GL inference.
- `Allocation → Lot` grain varies: per-lot output for LH and PF (high); per-phase totals for the rest (medium); indirect/land pools project-wide (low).

---

## 3. BCPD instance counts (headline)

| entity | count | notes |
|---|---:|---|
| LegalEntity (in scope) | 4 | BCPD, BCPBL, ASD, BCPI |
| Project (canonical, all-confidence) | 42 | 22 high-confidence + 20 medium/low historical |
| Project (high-confidence, active in 2025Status) | 16 | + Meadow Creek = 17 with collateral |
| Phase (BCPD, all-confidence) | 215 | 125 high + 90 medium |
| Lot (canonical, BCPD scope) | 6,087 | includes historical CLOSED  rows |
| Lot (active BCPD-built, HorzCustomer=BCP) | 2,797 | per Lot Data + 2025Status filter |
| Account (DR + VF + QB) | 335 | 155 + 3 + 177 |
| CostCategory | 9 | v0 mapping |
| GL FinancialTransaction (BCPD) | 197,852 | DR raw 111,497 / VF 83,433 / QB 2,922; DR is 2.16× multiplied at source |
| GL FinancialTransaction (BCPD, post-DR-dedup) | ~141,752 | DR dedup → 51,694; VF 83,433; QB 2,922 |

---

## 4. Versioning

- This is **v0**. Future iterations should add (in order): phase-aware lot
  decoder for GL VF → inventory matching; chart-of-accounts crosswalk for
  QB ↔ legacy chart tie-out; project-code crosswalk between DR-era and
  VF-era for cross-era project rollups (low priority — most use cases work
  era-by-era).
- v0 is BCPD-scoped. The shape of every entity is generic; populating other
  legal entities (Hillcrest, Flagship Belmont) is gated on fresh GL pulls
  covering 2017-03 onward — see `scratch/bcpd_financial_readiness.md`.
- `ontology/lot_state_v1.md` and `ontology/phase_state_v1.md` are referenced,
  not replaced. Their definitions still apply for the BCPD lots that have
  v1-compatible data.

## 5. Out of scope for v0

- Org-wide v2 (Hillcrest, Flagship Belmont): blocked on fresh GL pulls.
- Phase-aware lot decoder for GL VF: a v1 follow-up.
- Vendor analysis outside 2025 BCPD: QB register is single-entity-single-year only.
- Subledger analysis: effectively absent (DR 0.22% / VF 0% / QB 0% fill).
- Dehart underwriting: not stageable as-is; defer.
- Flagship Allocation Workbook v3 expansion: framework exists but cells are mostly empty; replicate v1 (LH + PF only) until populated.
