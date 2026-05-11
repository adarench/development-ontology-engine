# Source Mapping v1 — BCPD Operating State

**Owner**: Adam Rencher
**Generated**: 2026-05-09
**Scope**: BCPD (Building Construction Partners and horizontal-developer affiliates BCPBL, ASD, BCPI). Org-wide (Hillcrest, Flagship Belmont) is out of scope and refused at the agent layer.
**Companion docs**: `docs/repo_map.md`, `docs/bcpd_operating_state_architecture.md`, `docs/ontology_v0.md`, `docs/source_to_field_map.md`, `docs/field_map_v0.csv`, `output/agent_context_v2_1_bcpd.md`, `data/reports/coverage_improvement_opportunities.md`.

This document is a **source map for retrieval-system design**. It is not a redesign of the architecture. It catalogs what data exists, where it lives, what authority it carries, how it flows into canonical operating state, and how each surface should be treated by an AI retrieval / vectorization layer.

**What this repo actually contains** (anchor before reading): batch Python pipelines (`pandas + pyarrow`) that ingest CSV/XLSX extracts under `data/raw/`, produce normalized + canonical tables under `data/staged/`, and publish a single versioned JSON operating-state document (`output/operating_state_v2_1_bcpd.json`) plus 44 retrieval chunks under `output/agent_chunks_v2_bcpd/`. There is no database, no orchestrator, no service layer, no incremental ingestion. All transforms are batch and idempotent.

**What this repo does NOT contain** (called out so this doc is not generic):
- **Supabase / Postgres** — no DB layer is wired in. The "store" today is parquet + JSON files on disk.
- **MLS / market pricing data** — no MLS feed is staged. `2025Status.csv` carries per-lot sales price and offer data but no external comp data.
- **Land acquisition models** — `Dehart Underwriting(Summary).csv` is in the repo root but **inventoried only**, not wired into any pipeline (per `CONTEXT_PACK.md` § 3 and `ontology/data_readiness_audit.md`).
- **Live ingestion** — every refresh today is a manual export → re-run of `financials/build_*.py`.

---

## 1. Source Inventory

One row per upstream source actually present in the repo. The "owner / system of record" column names the upstream business system; all extracts arrive on disk under `data/raw/` or the repo root.

### 1.1 GL feeds

| # | Source | Type | System of record | Domain | Granularity | Cadence | Authoritative status | Path |
|---|---|---|---|---|---|---|---|---|
| GL-1 | **DataRails GL bundle** (`GL (1..14).csv` + `GL.csv` stub) | CSV, 38 cols | DataRails (which itself extracts from upstream ERPs) | Multi-entity general ledger | Posting line | Manual zip-export (`DataRails_raw.zip`, last 2026-05-01) | **Authoritative for 2016-01 → 2017-02 BCPD GL only** in current dump. **Row-multiplied 2.16× at source — must dedup.** | `data/raw/datarails/gl/` and `data/raw/datarails_unzipped/` |
| GL-2 | **Vertical Financials 46-col** | CSV, 46 cols (large; 26.8 MB) | Internal "Vertical Financials" workbook (legacy chart of accounts; cost-basis only) | BCPD lot-level cost basis 2018-2025 | Posting line, asset-side debit only | Quarterly-ish; last extract within `Collateral Dec2025 01 Claude.xlsx` | **Authoritative for per-lot VF cost 2018-2025.** One-sided (3 account codes: 1535/1540/1547). Not a balanced trial balance. | `Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv` (root) |
| GL-3 | **QuickBooks Register (DataRails-pulled BCPD GL Detail)** | CSV, 12 cols | QuickBooks Online / Desktop (BCPD entity) | 2025 BCPD vendor / cash / AP register | Register line | Single 2025 export | **Tie-out only.** 177 QB account codes; **zero overlap** with VF/DR chart. Never aggregate against VF. | `Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv` (root) |
| GL-4 | **QBO/QBD entity exports** (`GL_QBO_Anderson Geneva LLC`, `GL_QBO_Geneva Project Manager LLC`, `AR_QBD_Uncle Boggys LLC`, `Balance_Sheet_QBO_Anderson Geneva LLC`) | CSV, 33-34 cols | QBO/QBD per-entity exports | Single-entity register or AR aging or Balance Sheet | Single 2026-05 snapshot | **Inventoried; not staged.** Different schemas; would require per-entity normalization. | `data/raw/datarails/{ar,balance_sheet}/`, `data/raw/datarails_unzipped/` |

Combined output: `data/staged/staged_gl_transactions_v2.{csv,parquet}` — **210,440 rows × 46 cols** with normalized schema across DR + VF + QB; **197,852 BCPD-scope** rows. Build script: `financials/build_canonical_tables_v0.py` (and predecessor `data/_stage_v2.py`).

### 1.2 Operational / inventory feeds

| # | Source | Type | System of record | Domain | Granularity | Cadence | Authoritative status | Path |
|---|---|---|---|---|---|---|---|---|
| OP-1 | **Inventory \_ Closing Report (2..4).xlsx** | XLSX, 84 rows × 13 cols (3 near-duplicate workbooks; #4 is canonical) | Internal lot inventory tracker | ACTIVE / CLOSED / ACTIVE_PROJECTED lots, sales price, deposit, sale/closing/permit/dig dates, plan name, buyer | Lot | Periodic save; latest as_of_date 2026-04-29 | **Authoritative for current lot inventory + sale/close/permit/dig dates.** Workbook #4 chosen; #2 / #3 archived. | `data/raw/datarails/inventory_closing/` |
| OP-2 | **2025Status** (`Collateral Dec2025 01 Claude.xlsx - 2025Status.csv`) | CSV, ~3,627 rows | Internal status workbook (header row=3, `as_of_date` in cell B1) | Per-lot lifecycle + horizontal cost components + collateral bucket + HorzCustomer | Lot | Periodic; as_of cell-stored | **Authoritative for per-lot horizontal actuals (Permits and Fees, Direct Construction - Lot, Shared Cost Alloc.) and HorzCustomer/HorzSeller identity.** | repo root |
| OP-3 | **Lot Data** (`Collateral Dec2025 01 Claude.xlsx - Lot Data.csv`) | CSV, ~3,627 rows | Internal lot dates workbook | Per-lot lifecycle dates (horiz_purchase/start/record, vert_purchase/start/co/sale/close), HorzSeller | Lot, primary key (Project, Phase, LotNo.) | Periodic | **Authoritative for v1 LotState lifecycle waterfall.** Excel sentinel `1899-12-30` = null. | repo root |
| OP-4 | **ClickUp api-upload.csv** | CSV, 5,509 tasks × 32 cols | ClickUp (workspace export) | Operational tasks; date_created/closed/done, status, walk_date, projected_close_date, actual_c_of_o, sold_date, subdivision, lot_num, phase | Task; lot-tagged subset = 1,177 (~21%) | Manual export via ClickUp API; near-duplicate `api-upload (1).csv` exists and is byte-identical (ignore) | **Authoritative for task-level operations**, but lot-tagged subset is sparse. **Cannot drive comprehensive operating state alone.** | `data/raw/datarails/clickup/api-upload.csv` |

### 1.3 Collateral / pricing feeds

| # | Source | Type | System of record | Domain | Granularity | Cadence | Authoritative status | Path |
|---|---|---|---|---|---|---|---|---|
| CL-1 | **Collateral Report** (`Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv`) | CSV, 41 phase rows (header at row 9) | Lender collateral package | Per-phase total dev cost, borrowing base, advance %, lot count | Phase, as_of 2025-12-31 | Quarterly | **Authoritative for collateral position on the 9 pledged BCPD projects.** 7 active BCPD projects + Lewis Estates **have no row** — they are not pledged. | repo root |
| CL-2 | **PriorCR** (`Collateral Dec2025 01 Claude.xlsx - PriorCR.csv`) | CSV, 41 rows | Same as CL-1 | Prior-period collateral snapshot (as_of 2025-06-30) | Phase | One per cycle | **Authoritative for delta computation against CL-1.** | repo root |
| CL-3 | **IA Breakdown / RBA-TNW / Combined BS / Cost to Complete Summary / OfferMaster** | CSV, supporting tabs | Lender package side tabs | Various (advance rates, balance-sheet tieout, offer pricing) | Mixed | Each Collateral cycle | Reporting only; **not staged into canonical entities.** | repo root |
| CL-4 | **Offer pricing** (`OfferMaster.csv`) | CSV | Internal offer log | Per-offer pricing | Offer | Per-offer | Reporting only; not wired in. | repo root |

### 1.4 Allocation / budget feeds

| # | Source | Type | System of record | Domain | Granularity | Cadence | Authoritative status | Path |
|---|---|---|---|---|---|---|---|---|
| AL-1 | **LH Allocation 2025.10** | XLSX (CSV per tab) | Internal allocation workbook | Lomond Heights expected per-lot cost (12 phase × prod_type rows) | Phase × prod_type | Periodic refresh | **Authoritative for LH expected cost.** Total column blank — pipeline reconstructs as `land + direct + water + indirect`. | `LH Allocation 2025.10.xlsx - {LH,BCPBL SB,JCSList,PLJ,BSJ,AAJ}.csv` (root) |
| AL-2 | **Parkway Allocation 2025.10** | XLSX (CSV per tab) | Same | Parkway Fields expected per-lot cost (14 rows) | Phase × prod_type | Periodic | **Authoritative for PF expected cost.** Full column set available. | `Parkway Allocation 2025.10.xlsx - {AAJ,JCSList,PF}.csv` (root) |
| AL-3 | **Flagship Allocation Workbook v3** | CSV per tab | Internal | Allocation framework: Engine, Indirect & Land Pools, Lot Mix & Pricing, Per-Lot Output | Per-lot framework | One-shot v3 spec | **Framework only — cells mostly empty for projects beyond LH/PF.** Don't promise expanded coverage. | `Flagship Allocation Workbook v3.xlsx - *.csv` (root) |
| AL-4 | **Dehart Underwriting (Summary)** | CSV | Underwriting model | Land acquisition summary | Mixed | One-shot | **Inventoried only; not stageable as-is** (semi-structured workbook export). | `Dehart Underwriting(Summary).csv` (root) |
| AL-5 | **FInancials_Sample_Struct.xlsx** / **PriorCR.csv** / **Collateral Report.csv** | XLSX/CSV | Internal | Schema samples | n/a | One-shot | **Schema reference, not a data source.** | repo root |

### 1.5 Supporting source-of-truth files

| # | Source | Type | Purpose |
|---|---|---|---|
| ST-1 | `Clickup_Naming_Struct - Sheet1.csv` | CSV | Stage-vocabulary naming dictionary; consumed by `financials/stage_dictionary.py` to validate ClickUp stage aliases. |
| ST-2 | `Clickup_Sheet_Structure - Sheet1.csv` | CSV | Earlier ClickUp dump (predates `api-upload.csv`); kept for backref. v1 `clickup_pipeline.py` consumed this; v1.5+ uses `api-upload.csv`. |
| ST-3 | `Collateral Dec2025 - Cost to Complete Summary.csv`, `... - Combined BS.csv`, `... - PriorCR.csv` | CSV | Collateral package side tabs (see CL-3). |

### 1.6 Sources NOT present (called out explicitly)

- **DataRails as a live system** — only zip/CSV exports. No API integration is wired in this repo.
- **Supabase / Postgres** — no DB layer. No `.sql` / migrations / connection strings exist anywhere.
- **MLS / external market pricing** — no MLS feed staged. The closest internal proxy is `2025Status.SalesPrice` and `OfferMaster.csv`.
- **Vendor master / chart-of-accounts dictionary** — only what is implicit in GL feeds. The 335 distinct accounts in `canonical_account.csv` are derived bottom-up from posted lines; there is no upstream COA reference table.
- **Anderson Geneva LLC activity** — present in QBO single-entity exports but **not staged** into v2 GL. Lewis Estates shows $0 because the GL sample lacks Anderson Geneva activity rows (per `README.md` § Confidence model).

---

## 2. Canonical Entity Mapping

Canonical entities are the small graph that operating state v2.1 publishes. Each section below names the entity, its physical canonical-table file, the upstream sources that contribute, the join path, and its retrieval relevance.

### 2.1 LegalEntity

- **File**: `data/staged/canonical_legal_entity.{csv,parquet}` (8 rows; 4 in scope: BCPD, BCPBL, ASD, BCPI; 4 out of scope: Hillcrest, Flagship Belmont, Lennar, EXT).
- **Schema**: `canonical_entity, long_name, role, in_scope`.
- **Upstream sources, in authority order**: GL `entity_name` (DR + VF) → 2025Status.HorzCustomer → Lot Data.HorzSeller → QB-register filename.
- **Crosswalk**: `data/staged/staged_entity_crosswalk_v0.csv` (13 mappings).
- **Canonical identifier**: `canonical_entity` (short code).
- **Join key**: `canonical_entity` flowing down to Project / Phase / Lot / FinancialTransaction.
- **Semantic aliases**: GL CompanyName variants (e.g. "Building Construction Partners LLC", "BCP, LLC") all collapse to `BCPD`. BCPI is medium-confidence (only 12 lots in `Lot Data.HorzSeller`).
- **Ambiguity risk**: `Hillcrest Road at Saratoga LLC` and `Flagship Belmont Phase Two LLC` are recognized but explicitly out of scope — **don't include in any retrieval result for BCPD-scope questions** (Guardrail 1).
- **Retrieval relevance**: **retrieval-critical** — every other entity is keyed on it.

### 2.2 Project (Community)

- **File**: `data/staged/canonical_project.{csv,parquet}` (42 rows in BCPD scope: 22 high-confidence + 20 historical/medium).
- **Schema**: `canonical_project, canonical_entity, in_inventory, in_lot_data, in_2025status, in_gl_dr_38col, in_gl_vf_46col, gl_row_count, lot_count_2025status, lot_count_inventory, source_confidence`.
- **Upstream sources**: 2025Status.Project + Lot Data.Project (identity); Collateral Report.Project (adds Meadow Creek); inventory.subdiv via `SUBDIV_TO_PROJECT` map in `financials/stage_inventory_lots.py`; GL `project_code` via crosswalk; ClickUp `subdivision` via crosswalk.
- **Crosswalk**: `data/staged/staged_project_crosswalk_v0.csv` (142 rows). Two distinct project-code vocabularies — DR-era (pre-2018) and VF-era (2018-2025) — both collapse into `canonical_project`.
- **Canonical identifier**: `(canonical_entity, canonical_project)`.
- **Semantic aliases (worked examples)**: `PWFS2`, `Park Way`, `PARKWAY`, `Parkway Fields` → `Parkway Fields`. `SctLot` → `Scattered Lots` (NOT Scarlet Ridge — see Guardrail 5). `Aarowhead` → `Arrowhead Springs` (typo). `Scarlett Ridge` → `Scarlet Ridge`.
- **Ambiguity risks**:
  - **SctLot identity** is `inferred-unknown`. Canonical name "Scattered Lots" is pending source-owner confirmation. (Open ask #5 in `PROJECT_STATE.md`.)
  - **HarmCo X-X parcels** are commercial; isolated under `commercial_parcels_non_lot`, not residential `phases.lots` (Guardrail 3).
  - **17 active projects per 2025Status** vs 16 with collateral vs 42 canonical (incl. historical). Be explicit about which counter you're using.
- **Retrieval relevance**: **retrieval-critical** — top-level navigational entity for the JSON state.

### 2.3 Phase (Plat)

- **File**: `data/staged/canonical_phase.{csv,parquet}` (215 rows; 125 high + 90 medium).
- **Schema**: `canonical_entity, canonical_project, canonical_phase, in_inventory, in_lot_data, in_2025status, lot_count, source_count, source_confidence`.
- **Upstream sources**: inventory.phase, Lot Data.Phase, 2025Status.Phase, ClickUp.phase (lot-tagged subset only), allocation workbook tabs. **GL has 0% phase fill** across all 3 schemas — phase is **not derivable from GL**; it must come from operational sources or be inferred via the VF lot-code decoder.
- **Crosswalk**: `data/staged/staged_phase_crosswalk_v0.csv` (385 rows). Whitespace normalization via `pipelines/config.py:normalize_phase`.
- **Canonical identifier**: `(canonical_entity, canonical_project, canonical_phase)`.
- **Semantic aliases**: phase names like `2-A`, `2A`, `2 A` collapse via normalize_phase; `B1` is a phase string, distinct from `B2` (AultF B-suffix correction in v2.1 reroutes $4.0M from B2 → B1).
- **Ambiguity risks**:
  - **Harmony 3-tuple discipline** — flat `(project, lot)` join collapses MF1 lot 101 with B1 lot 101 (~$6.75M error). Always join on the 3-tuple (Guardrail 4 / Rule 4).
  - **DR 38-col phase recovery** is open (Open ask #8) — pre-2018 GL has 0% phase fill at source.
- **Retrieval relevance**: **retrieval-critical**. `phase_id = "{project}::{phase}"` is the join key for cost rollups against VF.

### 2.4 Lot

- **File**: `data/staged/canonical_lot.{csv,parquet}` (6,908 rows; 6,087 BCPD-scope; ~2,797 active BCPD-built per `HorzCustomer=BCP`).
- **Schema**: `canonical_lot_id, canonical_entity, canonical_project, canonical_phase, canonical_lot_number, in_inventory, in_lot_data, in_2025status, lot_status, horz_customer, horz_seller, project_confidence, bcpd_scope, source_count, source_confidence`.
- **Upstream sources**: inventory.lot_num (UNION of INVENTORY + CLOSED tabs), Lot Data.LotNo., 2025Status.Lot, ClickUp lot-tagged subset, GL VF/DR `lot` field.
- **Crosswalk**: `data/staged/staged_lot_crosswalk_v0.csv` (14,537 rows).
- **Canonical identifier**: `canonical_lot_id = blake2s_8(project | phase | lot_num)` — opaque hash so the join key cannot be confused with a business identifier. Secondary key `(canonical_entity, canonical_project, canonical_phase, canonical_lot_number)`.
- **VF lot-string decoder**: `data/staged/vf_lot_code_decoder_v1.csv` (17 decoder rules across VF project codes Harm3, HarmCo, HarmTo, AultF, ArroS1, ArroT1, LomHS1, LomHT1, MCreek, PWFS2, PWFT1, ScaRdg, SctLot, SaleTT, SaleTR, WilCrk, plus the VF code `Harm3` lot 1034 ≠ inventory lot 1034 case). Every rule ships `confidence='inferred'` and `validated_by_source_owner=False`. **Do not promote without source-owner sign-off.**
- **Semantic aliases**: VF lot string `'1034'` under `Harm3` → `(canonical_phase='A10', canonical_lot_number='1044')`. `0000A-A` ... `0000K-K` under `HarmCo` → commercial parcels (non-lot).
- **Ambiguity risks** (the live ones):
  - **Harm3 lot-range routing** — phase recoverable only via lot range (Open ask #1).
  - **AultF SR-suffix** (`0139SR`, `0140SR`) — semantics unknown, $1.18M unattributed (Open ask #2).
  - **AultF B-suffix range** — confirm B1 max lot = 211 (Open ask #3).
  - **MF1 vs B1 overlap 101-116** — sample for SFR/B1 to confirm no MF1 leakage (Open ask #4).
- **Retrieval relevance**: **retrieval-critical** for lot-grain questions; **retrieval-secondary** when only project- or phase-grain is needed.

### 2.5 FinancialTransaction

- **File**: `data/staged/staged_gl_transactions_v2.{csv,parquet}` (210,440 rows; 197,852 BCPD-scope; **post-DR-dedup** ≈ 141,752: DR 51,694 + VF 83,433 + QB 2,922).
- **Schema (46 cols)**: `source_file, source_schema, source_row_id, transaction_id, transaction_number, line_number, company_code, company_name, entity_name, posting_date, fiscal_year, fiscal_period, source_date_column, amount, debit_amount, credit_amount, debit_credit, currency, functional_amount, functional_currency, account_code, account_name, account_type, account_group, major, minor, project, project_code, project_name, phase, lot, job_phase_stage, division_code, division_name, operating_unit, subledger_code, subledger_name, vendor, memo, memo_1, memo_2, description, batch_description, source_system, ingested_at, raw_column_map_json, row_hash`.
- **Authority by era**:
  - **2018-2025 BCPD** → VF 46-col is **primary** (100% project+lot fill on BCPD; 1,306 distinct (project, lot) pairs; one-sided asset-DR feed — 3 account codes 1535/1540/1547).
  - **2016-01 → 2017-02 BCPD** → DR 38-col post-dedup (49.5% lot fill on BCPD, **0% phase fill**).
  - **2017-03 → 2018-06 BCPD** → **GAP**. Zero rows. Cannot be reconstructed from current dump.
  - **2025 BCPD** → QB Register is **tie-out only** (different chart of accounts; 177 codes; zero overlap with VF/DR — Guardrail 8).
- **Canonical identifier**: `row_hash` (PK); aggregate by `(entity_name, project_code → canonical_project, canonical_lot_id)`.
- **Critical transformation**: **DataRails dedup** on the 9-field canonical key `(entity_name, posting_date, account_code, amount, project, lot, memo_1, description, batch_description)`. Raw DR rows are **2.16× multiplied at source**. Any sum against raw DR is wrong by ~2× (Guardrail 7). The build pipeline does this; consumers reading the staged parquet must apply the dedup themselves before any aggregation.
- **Ambiguity risks**: VF lot-code decoder outputs are `inferred`; range/shell rows like `'3001-06'` and `'0009-12'` are **not lot-grain** (Guardrail 4 — kept at project+phase via `vf_unattributed_shell_dollars`).
- **Retrieval relevance**: **retrieval-useful at the row level** (provenance), **retrieval-critical at the rolled-up level** (per-lot/per-phase/per-project totals are what most questions ask for). Raw rows generally should NOT be vectorized — vectorize the rolled-up summaries instead.

### 2.6 Account

- **File**: `data/staged/canonical_account.{csv,parquet}` (335 rows: 155 DR + 3 VF + 177 QB).
- **Schema**: `account_code, account_name, account_type, account_group, row_count, sum_amount, source_schema, source_confidence`.
- **Upstream**: GL `account_code/account_name/account_type/account_group` per source schema.
- **Critical fact**: DR/VF share a legacy 4-digit chart; **QB uses a different newer chart with zero overlap**. Cross-schema aggregation is unsafe.
- **Retrieval relevance**: **retrieval-secondary** — used to label cost categories; rarely the answer subject itself.

### 2.7 CostCategory

- **File**: `data/staged/canonical_cost_category.{csv,parquet}` (9 rows).
- **Schema**: `category_code, category_name, cost_phase_bucket, matches_status_column, vf_account_codes, dr_account_codes, is_actual_only, source_confidence, notes`.
- **Source**: rule-based mapping `(source_schema, account_code) → category_code`. Extends v1 `pipelines/config.py:COST_TO_DATE_COMPONENTS` (Permits and Fees, Direct Construction - Lot, Shared Cost Alloc.) with vertical components from VF.
- **Retrieval relevance**: **retrieval-useful** — anchor for cost-bucket questions.

### 2.8 Allocation / Budget

- **File**: not built as a separate canonical table in v0 — read live from v1's existing builders.
- **Source**: AL-1 (LH 12 rows), AL-2 (PF 14 rows), AL-3 (Flagship v3 — framework, mostly empty), AL-4 (Dehart — out of scope).
- **Coverage caveat**: per-lot allocation exists **only for Lomond Heights and Parkway Fields**. Other BCPD projects have allocation workbook framework but unpopulated cells. Per-lot expected cost for them is `unknown`, not zero.
- **Retrieval relevance**: **retrieval-useful** for LH/PF questions; **retrieval-secondary** elsewhere; **explicit refusal** on per-lot expected for non-LH/PF projects.

### 2.9 InventorySnapshot

- **File**: `data/staged/staged_inventory_lots.{csv,parquet}` (3,872 rows; as_of 2026-04-29).
- **Schema**: `canonical_lot_id, canonical_project, project_confidence, subdiv, phase, lot_num, lot_status, plan_name, buyer, sales_price, deposit, sale_date, permit_pulled_date, permit_number, margin_pct, closing_date, dig_date, anticipated_completion, as_of_date, source_file, source_sheet, source_row_number`.
- **Critical normalization**: `lot_status` derived at stage time — `ACTIVE` / `CLOSED` (closing_date ≤ as_of) / `ACTIVE_PROJECTED` (closing_date > as_of from CLOSED tab).
- **Retrieval relevance**: **retrieval-critical** for lot universe + sale/close/permit dates.

### 2.10 CollateralSnapshot

- **File**: not built as separate canonical in v0; consumed at state-build time.
- **Source**: CL-1 (Collateral Report 41 phase rows, as_of 2025-12-31), CL-2 (PriorCR 41 rows, as_of 2025-06-30).
- **Coverage**: 9 of 16 active BCPD projects have rows; **7 active projects + Lewis Estates have no collateral row** (not pledged) — document the gap, do not estimate.
- **Retrieval relevance**: **retrieval-useful** for collateral-position questions on the 9 pledged projects; **explicit refusal** on the 7 unpledged.

### 2.11 TaskState

- **File**: derived at state-build time; not a separate canonical table.
- **Source**: `staged_clickup_tasks` filtered to lot-tagged subset (~1,177 of 5,509). Plus inventory.lot_status as a corroborator. Plus v1 `pipelines/config.py:LOT_STATE_WATERFALL`.
- **Coverage caveat**: lot-tagged subset is **~21% of all ClickUp tasks**. Date fields within the subset are sparse (`actual_c_of_o` 22.77%, `due_date` 45.54%, `projected_close_date` 4.76%, `walk_date` 1.78%).
- **Retrieval relevance**: **retrieval-useful** for the lot-tagged subset; **low-confidence / archival** for non-lot-tagged tasks.

### 2.12 Range / Shell rows (operational, not an entity)

- **Surface**: `vf_unattributed_shell_dollars` and `vf_unattributed_shell_rows` per phase in `operating_state_v2_1_bcpd.json`.
- **Source**: VF rows where the lot string is a range form (e.g. `'3001-06'`, `'0009-12'`) — represents shared-shell or shared-infrastructure cost spanning multiple lots.
- **Total exposure**: $45.75M / 4,020 rows / 8 VF codes (most affected: PWFT1, MCreek, HarmTo, SaleTT, SaleTR).
- **Retrieval relevance**: **retrieval-useful at project+phase grain only**. **Explicit refusal** on per-lot allocation until source-owner sign-off on allocation method (Open ask #6 — single highest-dollar gate).

### 2.13 CommercialParcel

- **Surface**: `commercial_parcels_non_lot` per project in v2.1 state.
- **Source**: HarmCo X-X parcels (`0000A-A` ... `0000K-K`, 11 parcels, 205 rows, ~$2.6M).
- **Retrieval relevance**: **retrieval-useful** for commercial-parcel questions; **explicit refusal** on rolling them into residential lot cost (Guardrail 3).
- **Future**: candidate for a `CommercialParcel` ontology entity in v2.2.

---

## 3. Data Flow Mapping

### 3.1 End-to-end flow (textual)

```
Raw extracts (data/raw/, repo root)
   │
   ▼
Stage layer (data/staged/staged_*)
   ├─ staged_gl_transactions_v2 (DR+VF+QB unified, 210,440 rows)
   │      ↑ build_canonical_tables_v0.py + DataRails dedup logic
   ├─ staged_inventory_lots (3,872 rows)
   │      ↑ stage_inventory_lots.py
   ├─ staged_clickup_tasks (5,509 rows; lot-tagged subset 1,177)
   │      ↑ data/_stage.py (or clickup_pipeline.py for v1)
   └─ vf_lot_code_decoder_v1.csv (17 rules; all `inferred`)
          ↑ build_vf_lot_decoder_v1.py
   │
   ▼
Crosswalk layer (data/staged/staged_*_crosswalk_v0)
   ├─ staged_entity_crosswalk_v0           (13 mappings)
   ├─ staged_entity_project_crosswalk_v0   (133 mappings — Entity↔Project)
   ├─ staged_project_crosswalk_v0          (142 mappings — source value → canonical_project)
   ├─ staged_phase_crosswalk_v0            (385 mappings)
   └─ staged_lot_crosswalk_v0              (14,537 rows)
          ↑ build_crosswalks_v0.py + build_crosswalk_audit_v1.py
   │
   ▼
Canonical entity layer (data/staged/canonical_*)
   ├─ canonical_legal_entity      (8 rows)
   ├─ canonical_project           (42 BCPD rows)
   ├─ canonical_phase             (215 BCPD rows)
   ├─ canonical_lot               (6,087 BCPD rows)
   ├─ canonical_account           (335 rows: 155 DR + 3 VF + 177 QB)
   └─ canonical_cost_category     (9 rows)
          ↑ build_canonical_tables_v0.py
   │
   ▼
Operating state document (output/operating_state_v2_1_bcpd.json)
   - 26 projects × N phases × M lots in body
   - every value carries: source_confidence, caveats, source_files
   - companion: state_quality_report_v2_1_bcpd.md, state_query_examples_v2_1_bcpd.md, change_log v2.0→v2.1
          ↑ build_operating_state_v2_1_bcpd.py (incorporates dedup + decoder + 3-tuple discipline + range-row policy + SctLot + HarmCo split + AultF B→B1 fix)
   │
   ▼
Retrieval surface
   ├─ output/agent_chunks_v2_bcpd/    (44 markdown chunks + index.json)
   │     ├─ projects/      (18 per-project chunks)
   │     ├─ sources/       (7 per-source chunks)
   │     ├─ cost_sources/  (6 cost-source chunks)
   │     ├─ coverage/      (5 coverage chunks)
   │     └─ guardrails/    (8 guardrail chunks)
   │       ↑ build_agent_chunks_v2_bcpd.py
   ├─ output/agent_context_v2_1_bcpd.md  (5 enforced rules + citation pattern)
   └─ financials/qa/                  (read-only Q&A harness — 15 questions, 10 guardrails)
         ↑ bcpd_state_qa.py + guardrails.py + question_set.py
```

### 3.2 Key transformation flows (named)

Each is a meaningful, named pipeline step that downstream consumers should treat as a contract.

1. **DataRails 2.16× dedup** — `build_operating_state_v2_1_bcpd.py` collapses raw DR rows on `(entity_name, posting_date, account_code, amount, project, lot, memo_1, description, batch_description)`. Without this, all DR rollups are wrong by ~2×. The raw `staged_gl_transactions_v2.parquet` is preserved unchanged.
2. **VF lot-code decoder v1** — `build_vf_lot_decoder_v1.py` produces `vf_lot_code_decoder_v1.csv`: 17 rules that route VF lot strings to `(canonical_phase, canonical_lot_number)` per project. Every rule is `inferred`. Rule examples:
   - `harmony_lot_range_to_phase` (Harm3): phase routed by lot-number range. 9,234 rows, 100% lot-data match.
   - `harmony_mf2_residential` (HarmCo residential): `0000<X><NN>` pattern → MF2 lot. 169 rows.
   - `harmony_commercial_xx_nonlot` (HarmCo X-X): isolated to `commercial_parcels_non_lot`.
   - AultF B-suffix → B1 (was B2 in v2.0). $4.0M / 1,499 rows.
   - SctLot → 'Scattered Lots' project. $6.55M / 1,130 rows.
3. **Harmony 3-tuple join discipline** — every lot in JSON state carries `vf_actual_cost_3tuple_usd` computed at `(canonical_project, canonical_phase, canonical_lot_number)` AND `vf_actual_cost_join_key` as a constant string declaring the contract. This prevents flat-2-tuple double counts (~$6.75M risk on Harmony alone).
4. **Range / shell row surfacing** — VF rows with range-form lot strings are explicitly tagged as `range` and aggregated to phase grain in `vf_unattributed_shell_dollars`. They never enter per-lot rollups.
5. **Inventory lot-status derivation** — `stage_inventory_lots.py` derives `ACTIVE / CLOSED / ACTIVE_PROJECTED` from closing_date vs as_of_date.
6. **v1 LotState waterfall** — `pipelines/build_lot_state.py` applies `LOT_STATE_WATERFALL` (top-down first match: vert_close → CLOSED, vert_sale → SOLD_NOT_CLOSED, vert_co → VERTICAL_COMPLETE, ...). Future-dated dates (planned starts) are treated as unset.
7. **v1 Phase aggregation + variance** — `pipelines/build_phase_state.py` rolls LotState to phase, attaches LH/PF allocation as expected, computes variance, sets `is_queryable` only for FULL coverage with denominator match.
8. **Agent chunk synthesis** — `build_agent_chunks_v2_bcpd.py` slices the JSON state into per-project / per-source / per-cost-source / per-guardrail chunks with index metadata (keywords, safe_question_types, caveat_tags, allowed_uses, source_files, confidence).

### 3.3 Generated outputs (what the retrieval system actually queries)

- **`output/operating_state_v2_1_bcpd.json`** (~5MB) — single canonical state document. **The thing.** Every consumer should read this, not the raw extracts.
- **`output/agent_context_v2_1_bcpd.md`** — 5 enforced rules + citation patterns. Always loaded into agent context.
- **`output/agent_chunks_v2_bcpd/index.json`** + 44 chunk markdown files — retrieval-time chunks.
- **`output/state_quality_report_v2_1_bcpd.md`** — per-field fill rate + open source-owner questions.
- **`output/state_query_examples_v2_1_bcpd.md`** — worked queries that respect the rules.
- **`output/operating_state_v1.json`** + companions — older v1 lot/phase scope, still produced; consumers should migrate.
- **`output/phase_cost_query.{csv,parquet}`** — v1 curated queryable subset (3 phases meet the FULL+meaningful gate).

### 3.4 Downstream consumers

- **Read-only Q&A harness** (`financials/qa/`) — 15 fixed questions, 10 guardrails. Deterministic, no API.
- **Three Claude A/B evals** (`financials/qa/llm_eval/`) — technical, business, workflow. Workflow eval Mode B passes 8/8.
- **Lexical RAG eval** (`financials/qa/rag_eval/`) — deterministic retrieval over chunks.
- **Demo app** (`demo/`) — Vite + React + Tailwind exec demo over `output/phase_state.csv` (v1-era data, independent npm package).
- **HTML dashboards** (v1-era): `operating_dashboard_v1.html`, `operating_state_console_v1.html`.

---

## 4. DataRails-Specific Documentation

DataRails is the most-cited upstream system in the prompt. It deserves its own section because **what arrives from DataRails is a zip of CSVs, not a live integration**, and the data has known structural issues that any retrieval layer must respect.

### 4.1 What currently originates from DataRails

DataRails delivers `DataRails_raw.zip` (~5.8 MB, last 2026-05-01). Contents:

- 17 GL files: `GL.csv` (6 rows — stub, ignore), `GL (1..14).csv` (~124,085 rows total, 38-col schema), plus per-entity QBO-format exports `GL_QBO_Anderson Geneva LLC_May 2026.csv` and `GL_QBO_Geneva Project Manager LLC_May 2026.csv` (different 33–34 col schema).
- 2 ClickUp files: `api-upload.csv` (5,509 rows × 32 cols), `api-upload (1).csv` (byte-identical duplicate).
- 3 Inventory closing reports: `Inventory _ Closing Report (2..4).xlsx` (84 rows × 13 cols, near-duplicates; #4 canonical).
- 1 Balance Sheet: `Balance_Sheet_QBO_Anderson Geneva LLC_May 2026.csv` (109 rows × 2 cols).
- 1 AR aging: `AR_QBD_Uncle Boggys LLC_May 2026.csv` (8 rows).

There is also a parallel set of **non-DataRails** Excel exports that arrive directly (likely emailed or shared-drive): `Collateral Dec2025 01 Claude.xlsx - *.csv` family, `LH Allocation 2025.10.xlsx - *.csv`, `Parkway Allocation 2025.10.xlsx - *.csv`, etc. These are CSVs derived from internal Excel workbooks and **are not part of DataRails per se**.

### 4.2 How exports occur

- **Manual.** A human exports the zip from DataRails, drops it in the repo root, and reruns the staging scripts. There is **no automation** in this repo.
- The unzip is preserved at `data/raw/datarails_unzipped/` and snapshot-archived to `data/raw/datarails/snapshots/{date}/`.
- Provenance metadata recorded in `data/manifests/raw_export_manifest.csv`, `data/manifests/profiles.json`, `data/manifests/hashes.json`.

### 4.3 Known limitations — DR 38-col GL

1. **2.16× row-multiplied at source.** Every posting line carries 2-3 times consecutively. Naive `SUM(amount)` is wrong by ~2×. **The dedup is mandatory** before any rollup. Done by `build_operating_state_v2_1_bcpd.py` before VF/DR aggregation. Raw `staged_gl_transactions_v2.parquet` preserves the multiplied rows for traceability — **consumers reading this directly are responsible for deduping themselves**.
2. **0% phase fill.** The DR `phase` column is empty across all DR rows. Phase cannot be derived from DR alone. Must come from inventory + Lot Data + 2025Status, or be inferred via VF lot-code decoder for VF rows.
3. **49.5% lot fill on BCPD.** Half of DR-era BCPD GL rows have no lot tag. These are presumably overhead/admin entries; correctly modeled at the entity level.
4. **Historical period** (2016-01 → 2017-02) — the current dump is **not a present-day snapshot** for DR. Operating-state v2 against DR-only would describe 2016-2017, not today.
5. **15-month gap 2017-03 → 2018-06** — zero rows for any entity. Cannot be filled from existing files. Any time-series answer must state this gap.

### 4.4 Spreadsheet dependencies (DataRails-related)

- **Vertical Financials** is itself an internal spreadsheet (`Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv`, 26.8 MB), not strictly a DataRails feed. But it is the **primary BCPD lot-cost feed for 2018-2025** and is loaded into `staged_gl_transactions_v2` alongside DR.
- **2025Status** is the per-lot horizontal cost + collateral-bucket workbook; carries `as_of_date` in cell B1 (header at row 3). Treat the workbook header parsing as critical pipeline contract.
- **Allocation workbooks** (LH, PF, Flagship v3) are CSV-per-tab from XLSX, semi-structured, with `Budgeting`/`Allocation` section headers and "Summary per lot" sections. Parser locates the section header and stops at the first non-summary section.

### 4.5 Semantic transformations (DR-specific)

- DR `CompanyName` → `entity_name` → `canonical_entity` via `staged_entity_crosswalk_v0`.
- DR `ProjectCode/ProjectName` → `canonical_project` via `staged_project_crosswalk_v0` (DR-era vocabulary collapses with VF-era — different chart of project codes).
- DR `lot` field → `canonical_lot_number` directly (no decoder needed for DR — decoder only applies to VF). DR lot fields are sparse (49.5%) but unambiguous when present.
- DR `account_code` → `canonical_account` directly. **DR/VF share the legacy 4-digit chart**, so cross-feed account aggregation is safe within DR/VF (but never against QB).

### 4.6 Joins / mappings

| from | to | via | notes |
|---|---|---|---|
| DR `entity_name` | `canonical_entity` | `staged_entity_crosswalk_v0` | 13 mappings; high confidence |
| DR `project_code` + `project_name` | `canonical_project` | `staged_project_crosswalk_v0` | 142 mappings; collapses DR-era ↔ VF-era project codes |
| DR `account_code` | `canonical_account` | direct (legacy chart) | 155 DR accounts |
| DR `lot` | `canonical_lot_number` | direct | 49.5% fill on BCPD; rest stay project-grain |
| DR (phase) | — | **NOT POSSIBLE** | 0% phase fill; must come from operational sources |

### 4.7 Friction points

1. **Manual zip handoff** — every refresh requires a human extract, copy, unzip, re-stage, re-build. No incremental ingestion.
2. **DR row-multiplication at source** is a DataRails artifact. Vendor support hasn't been contacted; we live with it via dedup.
3. **DR vs VF era project-code drift** — same project may have different DR-era and VF-era codes. Only the crosswalk knows.
4. **Historical-only DR** — current dump's date range is fixed 2016-01 → 2017-02. A fresh DR pull post-2017-02 is what would unblock org-wide v2 (Hillcrest, Flagship Belmont).

### 4.8 Authoritative vs derived (DR-specific)

| field | authority |
|---|---|
| DR `posting_date`, `amount`, `account_code`, `entity_name` | **authoritative** (source-native) |
| DR-derived per-lot cost (post-dedup) | **authoritative for 2016-02 → 2017-02 BCPD** at lot-grain only where lot is populated |
| DR-derived per-phase cost | **derived (impossible)** — phase fill is 0% |
| `staged_gl_transactions_v2` raw row counts | **misleading without dedup** |
| DR-era project-code mapping | **derived** (via crosswalk; high confidence) |

### 4.9 What should remain in DataRails (vs canonical state)

**Should remain in DataRails (upstream system of record):**
- All raw GL postings — the source-native record stays canonical upstream.
- The DataRails refresh cadence (whenever monthly close happens) — no need to replicate.
- Per-entity QBO/QBD register exports — these are DataRails's per-entity slices.

**Should move into canonical operating state (downstream of DR):**
- All cost rollups by `(canonical_entity, canonical_project, canonical_phase, canonical_lot)` — done.
- Dedup application and provenance (`row_hash` + `source_file` + `source_row_id`) — done.
- Range / shell row policy — done in v2.1.
- 3-tuple Harmony discipline — done in v2.1.
- VF lot-code decoder rule set — done in v2.1.
- Confidence labels per field — done.

**Open questions (be explicit):**
- Is a fresh DR pull post-2017-02 expected? If so, on what cadence? (Determines whether v2.2 can unblock org-wide.)
- Will DataRails ever expose phase grain at source? (Open ask #8 — currently 0% phase fill on DR 38-col.)

---

## 5. Retrieval Relevance Classification

For every named source / object below, classify retrieval relevance and explain *why*.

### 5.1 Retrieval-critical (must be in retrieval surface)

| object | why |
|---|---|
| `output/operating_state_v2_1_bcpd.json` body | The single canonical state document. Most answers come from here. |
| `output/agent_chunks_v2_bcpd/projects/*.md` (18 chunks) | Per-project canonical view; entry point for project-grain questions. |
| `output/agent_context_v2_1_bcpd.md` | 5 enforced rules + citation pattern. **Always loaded** into agent context — defines what the agent will and won't say. |
| `output/agent_chunks_v2_bcpd/guardrails/*.md` (8 chunks) | Refusal / safety rules. Retrieval system MUST have these available so the agent can cite refusal reasons. |
| `output/agent_chunks_v2_bcpd/cost_sources/*.md` (6 chunks) | Provenance for cost questions (VF / DR-dedup / QB tie-out / range / commercial / missing≠zero). |
| `canonical_project / canonical_phase / canonical_lot` | Entity navigation; required to disambiguate "Parkway Fields" vs "PWFS2". |
| `vf_lot_code_decoder_v1.csv` (17 rules) | Required to explain why a lot-cost number is `inferred` and not `validated`. |
| `staged_inventory_lots` (current snapshot fields) | Lot universe + sale/close/permit dates. |

### 5.2 Retrieval-useful (should be in retrieval surface)

| object | why |
|---|---|
| `output/agent_chunks_v2_bcpd/sources/*.md` (7 chunks) | Per-source provenance — answers "where does this number come from". |
| `output/agent_chunks_v2_bcpd/coverage/*.md` (5 chunks) | Coverage and gap explanations. |
| `output/state_quality_report_v2_1_bcpd.md` | Per-field fill rate + open source-owner questions. |
| `output/state_query_examples_v2_1_bcpd.md` | Worked queries — retrieval anchor for "how do I ask for X?" |
| `data/reports/v2_0_to_v2_1_change_log.md` | Explains the v2.0 → v2.1 deltas; useful when an answer would otherwise differ. |
| `staged_clickup_tasks` lot-tagged subset (1,177 rows) | Task-level operational signal where lot is tagged. |
| Allocation workbook outputs (LH 12 rows + PF 14 rows) | Expected-cost answers for those two projects. |
| `CollateralSnapshot` (Collateral Report + PriorCR) | Lender-position questions on the 9 pledged projects. |

### 5.3 Retrieval-secondary (use only when explicitly asked)

| object | why |
|---|---|
| `staged_gl_transactions_v2` raw rows | Provenance / drilldown only. **Do not vectorize raw rows.** |
| `canonical_account` (335 codes) | Anchors for cost-bucket explanation; rarely the answer subject. |
| `canonical_cost_category` (9 rows) | Same. |
| `staged_*_crosswalk_v0` tables | Used to explain alias resolution; not user-facing answers. |
| v1 outputs (`operating_state_v1.json`, `lot_state_real.csv`, etc.) | Older era, smaller scope; consumers migrate to v2.1. |

### 5.4 Reporting-only (not retrieval-relevant)

| object | why |
|---|---|
| HTML dashboards (`operating_dashboard_v1.html`, `operating_state_console_v1.html`) | Visual-only; data is already in JSON. |
| `Collateral Dec2025 - Combined BS.csv`, `... - IA Breakdown.csv`, `... - RBA-TNW.csv` | Lender-package side tabs; not staged. |
| `OfferMaster.csv` | Reporting only; not wired in. |

### 5.5 Archival-only

| object | why |
|---|---|
| Source extracts under `data/raw/datarails/snapshots/{date}/` | Provenance archive. Don't read at retrieval time. |
| `Inventory _ Closing Report (2).xlsx` and `(3).xlsx` | Superseded by `(4).xlsx`. |
| `api-upload (1).csv` | Byte-identical duplicate of `api-upload.csv`. |
| `GL.csv` (6-row stub) | Sample/preview, not real data. |

### 5.6 Low-confidence (require explicit caveats if surfaced)

| object | why |
|---|---|
| All VF-decoder-derived per-lot cost | `confidence='inferred'`, `validated_by_source_owner=False`. Surface only with the inferred caveat. |
| SctLot canonical name "Scattered Lots" | `inferred-unknown`. Pending source-owner confirmation. |
| AultF SR-suffix rows (401 rows / ~$1.2M) | Semantics unknown. Excluded from lot-level cost. |
| ClickUp non-lot-tagged tasks (~79% of all tasks) | Lot-identity sparse. Use only for project-grain task counts. |
| DR-era project-code → canonical for historical-only entities | Medium-low confidence; era boundary issues. |

### 5.7 Derived-only (don't surface as authoritative)

| object | why |
|---|---|
| `vf_actual_cost_3tuple_usd` per lot in JSON | Derived from VF + decoder + 3-tuple join. **Always cite as "per VF v1 decoder (inferred)".** |
| `vf_unattributed_shell_dollars` per phase | Derived from range-row policy. **Cite as "phase-grain shared-shell, not lot cost".** |
| v1 `current_stage`, `completion_pct` | Derived via waterfall. Cite the waterfall. |
| `lot_status_projected` flag | Derived from closing_date vs as_of. |

---

## 6. Lineage + Authority Documentation

For each important metric / object, name: authoritative source, derivation chain, transformation logic, historical tracking, confidence, ambiguity risks. **Critical distinctions: actuals vs forecasts, inferred vs confirmed, source-native vs synthesized.**

### 6.1 Per-lot actual cost (VF era 2018-2025) — the most important metric

- **Authoritative source**: `Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv` rows where `(canonical_entity ∈ BCPD-scope, account_code ∈ {1535, 1540, 1547}, posting_date ∈ 2018-01 .. 2025-12)`.
- **Derivation chain**: VF raw → `staged_gl_transactions_v2` (no row multiplication for VF) → VF lot-string decode via `vf_lot_code_decoder_v1.csv` → `(canonical_phase, canonical_lot_number)` → 3-tuple join key with `canonical_lot_id` → `vf_actual_cost_3tuple_usd` field on lot in JSON.
- **Transformation logic**: per-row dollar amount summed by 3-tuple. Range-form lot strings excluded and routed to `vf_unattributed_shell_dollars`. HarmCo X-X commercial parcels routed to `commercial_parcels_non_lot`.
- **Historical tracking**: not currently snapshotted. Re-running the pipeline overwrites with current state. (`as_of_date` is in schema; **no snapshot store**.)
- **Confidence**: `inferred` — every decoder rule is `validated_by_source_owner=False`. Even at `inferred`, v2.1 is strictly more accurate than v2.0.
- **Ambiguity risks**: AultF SR-suffix unknown ($1.18M); SctLot identity unconfirmed ($6.55M); MF1/B1 lot 101-116 overlap (sample needed); Harm3 phase routing relies on lot-range table.
- **Citation pattern**: "per VF v1 decoder (inferred), Parkway Fields Phase B1 Lot 112: $X across N rows."

### 6.2 Per-lot actual cost (DR era 2016-02 → 2017-02)

- **Authoritative source**: `staged_gl_transactions_v2` filtered to `source_schema='datarails_38col'`, **post-dedup** on the 9-field key.
- **Derivation chain**: DR raw → unified GL stage (with row-multiplication preserved) → dedup on `(entity_name, posting_date, account_code, amount, project, lot, memo_1, description, batch_description)` → per-lot sum.
- **Transformation logic**: dedup BEFORE any sum. Lot fill is 49.5% on BCPD; the 50.5% remainder stays at entity grain.
- **Historical tracking**: same — not snapshotted.
- **Confidence**: `high after dedup`. **Phase grain not derivable** (0% phase fill).
- **Ambiguity risks**: era boundary against VF (don't double-count if a project's GL straddles 2016-2017 DR and 2018-2025 VF).
- **Citation**: "per DR 38-col post-dedup (2016-17), Cascade Lot 8: $X (no phase available)."

### 6.3 Per-lot expected cost (allocation / budget)

- **Authoritative source**: AL-1 (LH) or AL-2 (PF). **Only those two projects.**
- **Derivation chain**: allocation workbook → `parse_allocation_sheet()` → reconstruct total if blank (`land + direct + water + indirect`) → `expected_total_cost_per_lot = total / lot_count_total`.
- **Transformation logic**: see `pipelines/build_phase_state.py`. `is_queryable` only set when `cost_data_completeness=FULL` AND `expected_lot_count == lot_count_total` AND `variance_meaningful=True`.
- **Historical tracking**: no budget versioning — re-forecasts overwrite originals. v1 known issue.
- **Confidence**: `high` for LH/PF per-lot rows; `medium` for indirect/land pools; `low` for Flagship-empty cells.
- **Ambiguity risk**: LH planned phases (2C, 5, 6A, 6B, 6C) have allocation lot counts but Lot Data has only `Lot=0` aggregate — denominator mismatch demotes them to PARTIAL.

### 6.4 Lot lifecycle stage (current_stage)

- **Authoritative source**: `Collateral Dec2025 01 Claude.xlsx - Lot Data.csv` lifecycle date columns.
- **Derivation chain**: Lot Data dates (filtered by Excel sentinel `1899-12-30`) → `LOT_STATE_WATERFALL` (top-down first match, **only dates ≤ as_of_date**) → state ∈ {PROSPECT, LAND_OWNED, HORIZONTAL_IN_PROGRESS, FINISHED_LOT, VERTICAL_PURCHASED, VERTICAL_IN_PROGRESS, VERTICAL_COMPLETE, SOLD_NOT_CLOSED, CLOSED}.
- **Critical detail**: future-dated dates (planned starts) are treated as unset. This distinguishes forecast-state from actual-state.
- **Confidence**: `high` if both ClickUp and inventory agree on stage; `medium` if one corroborator; `low` if waterfall-derived only.
- **Ambiguity risk**: ClickUp `status` may use non-canonical aliases — `stage_dictionary.py` validates against `CANONICAL_ALIASES`.

### 6.5 Phase-level total dev cost (Collateral Report fallback)

- **Authoritative source**: CL-1 `Collateral Dec2025 - Collateral Report.csv` `Total Dev Cost (Spent + Remaining)`.
- **Derivation chain**: CR header at row 9 → parse_collateral_report() → normalize project Title Case → normalize_phase → set `expected_total_cost`.
- **Confidence**: PARTIAL (no direct/indirect split). **Open question**: CR shows $0 on many active phases; produces 3.6–3.9× variance on Salem Fields::A and Willowcreek::1 even after horizontal-only alignment. May be a remaining-budget figure, not a true total. Worth confirming with source before trusting.
- **Ambiguity risk**: 9 of 16 active BCPD projects have CR rows; 7 + Lewis Estates **have no row** — these are not pledged collateral, document the gap, do not estimate.

### 6.6 Lifecycle group / collateral bucket / advance rate

- **Authoritative source**: derivation from `current_stage` via maps in `pipelines/config.py` (`LOT_STATE_TO_GROUP`, `LOT_STATE_TO_COLLATERAL_BUCKET`, `ADVANCE_RATES`, `LOT_STATE_TO_PCT_COMPLETE`).
- **Derivation chain**: stage → group → bucket → rate / pct.
- **Confidence**: derived; high when stage is high-confidence.

### 6.7 Range / shell dollars per phase

- **Authoritative source**: VF rows where lot string matches range pattern (`'3001-06'`, `'0009-12'`).
- **Derivation chain**: VF → lot-string parser flags `range` → aggregate to phase.
- **Total**: $45.75M / 4,020 rows / 8 VF codes.
- **Critical rule**: **NOT lot-grain.** Allocating to lots requires source-owner sign-off on allocation method (Open ask #6 — single highest-dollar gate).

### 6.8 Source-system confidence rollup

- **Rule**: every canonical row's `source_confidence` is the **worst-link** of contributing field confidences (min). Values: `high` / `medium` / `low` / `unmapped`.
- **Consumers**: should filter by this when answering business questions; should NOT silently downgrade to a higher confidence.

### 6.9 Inferred vs confirmed (the v2.1 honesty contract)

- v2.1 ships with `confidence='inferred'` and `validated_by_source_owner=False` for every decoder-derived per-lot cost. **None of the three Claude evals change that label** — they show the system answers correctly *given* the inferred status.
- Promotion to `validated` requires explicit source-owner sign-off recorded in the decoder CSV `validated_by_source_owner=True` per row.
- **Open ask queue (8 items, the actual blocker)**: see `PROJECT_STATE.md` § Open source-owner asks.

### 6.10 Source-native vs synthesized state

- **Source-native**: every value where the upstream system populated it directly (DR amount, VF amount, inventory closing_date, ClickUp status, Lot Data dates).
- **Synthesized**: every value derived by this pipeline (LotState waterfall result, phase aggregation, decoder-derived phase, range-vs-lot classification, 3-tuple join result, `canonical_*` IDs, confidence labels).
- **Retrieval rule**: synthesized values must always be cited *with* their derivation chain. Never present a synthesized value as if it were source-native.

---

## 7. Vectorization Readiness

For every entity / source: should it be vectorized? at what granularity? what should the embedding payload look like? what metadata is required? what retrieval namespace?

### 7.1 Vectorize (recommended)

| object | granularity | embedding payload (recommended) | metadata | namespace |
|---|---|---|---|---|
| **Per-project chunk** (`agent_chunks_v2_bcpd/projects/*.md`) | one chunk per project (18 BCPD projects) | full chunk markdown body (already curated; ~1-3 KB each) | `chunk_type='project'`, `canonical_project`, `confidence`, `caveat_tags`, `safe_question_types`, `source_files` | `bcpd.projects.v2_1` |
| **Per-source chunk** (`agent_chunks_v2_bcpd/sources/*.md`) | one chunk per upstream source (7 chunks) | chunk markdown body | `chunk_type='source'`, `source_name`, `confidence`, `safe_question_types` | `bcpd.sources.v2_1` |
| **Cost-source chunk** (`agent_chunks_v2_bcpd/cost_sources/*.md`) | one chunk per cost source (6 chunks: VF, DR-dedup, QB tieout, range/shell, commercial, missing≠zero) | chunk body | `chunk_type='cost_source'`, `confidence`, `caveat_tags` | `bcpd.cost_sources.v2_1` |
| **Coverage chunk** (`agent_chunks_v2_bcpd/coverage/*.md`) | 5 chunks (decoder coverage, allocation coverage, GL coverage, inventory coverage, ClickUp coverage) | chunk body | `chunk_type='coverage'` | `bcpd.coverage.v2_1` |
| **Guardrail chunk** (`agent_chunks_v2_bcpd/guardrails/*.md`) | 8 chunks | chunk body | `chunk_type='guardrail'`, `rule_id` | `bcpd.guardrails.v2_1` |
| **Worked query examples** (`state_query_examples_v2_1_bcpd.md` split per query) | one chunk per worked example | example body + answer | `chunk_type='example'`, `answer_kind` | `bcpd.examples.v2_1` |
| **Lot lifecycle definitions** (LotState waterfall + states) | one chunk for the waterfall ontology | waterfall body + state→bucket maps | `chunk_type='ontology'`, `version='v1'` | `bcpd.ontology.v0` |
| **Decoder rule catalog** (each row of `vf_lot_code_decoder_v1.csv`) | one chunk per decoder rule (17 rules) | rule pattern + evidence + match rates + confidence + caveat | `chunk_type='decoder_rule'`, `vf_project_code`, `confidence='inferred'`, `validated_by_source_owner=False` | `bcpd.decoder.v1` |
| **Open source-owner questions** (8 items) | one chunk per open question | question body + dollar gate + owner | `chunk_type='open_question'`, `question_id`, `dollar_gate_usd` | `bcpd.open_questions.v2_1` |

### 7.2 Do NOT vectorize

| object | why |
|---|---|
| `staged_gl_transactions_v2` raw rows (210,440) | Row-level GL postings are not retrieval-grain. Aggregate first. |
| Raw allocation workbook rows | Use parsed per-lot allocation summaries instead. |
| ClickUp non-lot-tagged tasks (~4,332 tasks) | Lot-identity sparse; not retrievable to lot-grain questions. |
| Crosswalk rows (`staged_*_crosswalk_v0.csv`) | Reference data; consume via direct lookup, not similarity search. |
| `canonical_account`, `canonical_cost_category` | Reference data; small; load fully. |
| `canonical_lot` rows (6,087) | Too granular — vectorize per-project chunks that summarize lot-level data instead. Per-lot vectors would explode the index without lifting answer quality. |
| HTML dashboards / `operating_dashboard_v1.html` | Visual-only; underlying data is already chunked. |
| Plan docs (`docs/*_plan.md`) | Working docs from build phase; not user docs. |

### 7.3 Embedding payload strategy

For each chunk, the embedding text should include:

1. **Chunk title** (e.g. "Project: Parkway Fields").
2. **Canonical identifier** (`canonical_project`, `canonical_phase`, etc.) — so similarity-only retrievers can still hit by ID.
3. **Confidence + caveats** prepended ("CONFIDENCE: inferred. CAVEATS: not source-owner-validated. ...") — pulls these into the embedding space so confidence-aware retrieval works.
4. **Body**: the markdown chunk content.
5. **Source files** as suffix (filenames as text) — supports "where does this come from?" queries.

### 7.4 Required retrieval-time metadata (filterable, not just embedded)

- `chunk_type` ∈ {project, source, cost_source, coverage, guardrail, example, ontology, decoder_rule, open_question}
- `state_version` (`v2.1`)
- `confidence` ∈ {high, medium, low, inferred, inferred-unknown}
- `caveat_tags` (list)
- `safe_question_types` (list)
- `bcpd_scope` (boolean — drives Guardrail 1 enforcement)
- `source_files` (list)

### 7.5 Namespace strategy

- One namespace per `state_version` so v2.1 chunks don't collide with v2.0 or future v2.2.
- Sub-namespaces by `chunk_type` for filtered retrieval (`bcpd.projects.v2_1` vs `bcpd.guardrails.v2_1`).
- Guardrail chunks are **always** retrieved alongside any answer — they are never the answer alone, but they shape every answer. The Q&A harness already uses `route_retrieval.py` (16 routing rules + lexical fallback).

### 7.6 Query → namespace routing (cribbed from `financials/qa/llm_eval/route_retrieval.py`)

| question shape | preferred namespace(s) |
|---|---|
| "What is total cost of project X?" | projects, cost_sources, coverage |
| "What is lot X's cost?" | projects, decoder, cost_sources, guardrails |
| "Why is range/shell cost not allocated?" | guardrails (range_rows_not_lot_level), cost_sources (range_shell_rows) |
| "Why does Harmony need 3-tuple?" | guardrails (harmony_3tuple_join), projects (harmony) |
| "What sources back this number?" | sources, cost_sources, examples |
| "Org-wide totals?" | guardrails (orgwide_unavailable, bcpd_only) — refuse |
| Free-form input | **today: NOT validated**. Workflow eval Mode B is strong on curated questions only. |

---

## 8. Ambiguity / Risk Analysis

The 10 highest-impact ambiguities and risks the retrieval system must handle, ranked by dollar exposure where applicable.

| # | Risk | Dollar / Scope | Status | Mitigation in v2.1 |
|---|---|---|---|---|
| 1 | **Range / shell row per-lot allocation** | $45.75M / 4,020 rows / 8 VF codes | Open (Open ask #6) | Surfaced at project+phase grain via `vf_unattributed_shell_dollars`. Refused at lot grain. |
| 2 | **Harmony MF1/B1 lot 101-116 overlap** | ~$6.75M double-count risk | Mitigated via 3-tuple discipline (Guardrail 4) | `vf_actual_cost_3tuple_usd` + `vf_actual_cost_join_key='canonical_project|canonical_phase|canonical_lot_number'` |
| 3 | **SctLot canonical name 'Scattered Lots'** | $6.55M / 1,130 rows | Open (Open ask #5) | Moved out of Scarlet Ridge (-46% inflation). New project `Scattered Lots`, project-grain only. |
| 4 | **AultF B-suffix routing (was B2, now B1)** | $4.0M / 1,499 rows | Mitigated in v2.1 | Routing fix applied; pending source-owner confirmation max lot=211 (Open ask #3) |
| 5 | **HarmCo X-X commercial parcels** | $2.6M / 205 rows | Mitigated via `commercial_parcels_non_lot` (Guardrail 3) | Isolated from residential. Ontology entity `CommercialParcel` is a v2.2 candidate (Open ask #7). |
| 6 | **AultF SR-suffix semantics** (`0139SR`, `0140SR`) | $1.18M / 401 rows / 2 lots | Open (Open ask #2) | Excluded from lot-level cost. `inferred-unknown`. |
| 7 | **DR 38-col 2.16× row multiplication** | All DR rollups | Mitigated via dedup (Guardrail 7) | Build pipeline dedupes on 9-field key before sum. Raw parquet preserved unchanged — consumers reading directly are responsible. |
| 8 | **DR 0% phase fill** | All DR-era phase questions | Open (Open ask #8) | Phase derived from operational sources; refuse phase-grain answers from DR alone. |
| 9 | **2017-03 → 2018-06 GL gap** | Dump-wide blind spot, 15 months | Structural | Document gap; refuse time-series answers that span it without disclosure. |
| 10 | **7 active BCPD projects + Lewis Estates have no GL coverage** (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge) | Cost is `unknown`, not zero | Structural (needs fresh GL pull) | Refuse cost questions for these projects per Guardrail 2 (missing≠zero). |
| 11 | **QB ↔ VF chart-of-accounts disjoint** (177 codes vs 4-digit legacy) | Cross-feed aggregation = double count | Mitigated (Guardrail 8) | QB tie-out only. |
| 12 | **Org-wide v2 (Hillcrest, Flagship Belmont)** | Frozen at 2017-02 | Blocked (Guardrail 1, 3) | Refused at agent layer until fresh GL pulls land. |
| 13 | **ClickUp lot-tagging sparse (~21%)** | ~4,332 of 5,509 tasks | Structural | Lot-grain ClickUp answers limited to the 1,177 tagged tasks across 1,091 distinct lots. |
| 14 | **Free-form chat readiness** | All free-form input | Open (eng) | Workflow eval Mode B is good on curated routing rules; not validated for arbitrary input. Stay on the curated path for the demo. |
| 15 | **No incremental ingestion / no snapshot store** | Historical replay impossible | Structural | `as_of_date` is in schema but re-runs overwrite; v1 known issue. |

### 8.1 Risk classes (for the retrieval system to recognize)

- **Type A — Wrong answer if violated** (Harmony 3-tuple, DR dedup, range-row policy, commercial-parcel split, SctLot routing).
- **Type B — Refusal required** (org-wide rollup, no-GL project cost, free-form input today, range-row per-lot, MF1/B1 ambiguity past the 3-tuple guard).
- **Type C — Caveat required** (decoder-derived inferred, SctLot identity, AultF SR semantics, phase from DR).
- **Type D — Structural gap** (15-month gap, 7 no-GL projects, Lewis Estates, no snapshot store).

---

## 9. Normalization Recommendations

Each item below is something to do (or hold) before promoting v2.1 to a production retrieval target.

### 9.1 Apply now (no source-owner gate)

1. **Vectorize the 44 chunks under `output/agent_chunks_v2_bcpd/`** with the metadata schema in §7.4. Use the chunk path as a stable doc ID.
2. **Always co-retrieve relevant guardrail chunks** with any answer chunk. The agent context already enforces this — the retrieval system should mirror it (e.g. retrieve `harmony_3tuple_join` whenever a Harmony cost question hits).
3. **Embed confidence + caveats into the embedding text** (not just metadata). This catches cases where the retriever surfaces a chunk but the consumer ignores metadata.
4. **One namespace per state_version**; never let v2.0 and v2.1 chunks coexist in the same retrieval target.
5. **Reject any retrieval result without `source_files` populated** — provenance is a contract.
6. **Add a `bcpd_scope` filter** at retrieval time. Out-of-scope entities (Hillcrest, Flagship Belmont) should never appear in BCPD answers.

### 9.2 Hold (gate on source-owner sign-off)

1. **Do NOT promote VF decoder rules from `inferred` to `validated`** without per-row source-owner sign-off recorded as `validated_by_source_owner=True`.
2. **Do NOT expand range-row dollars to specific lots** without allocation-method sign-off (Open ask #6, $45.75M gate).
3. **Do NOT promote SctLot to "Scattered Lots" canonical** without explicit source-owner confirmation (Open ask #5).

### 9.3 Pipeline-side (engineering)

1. **Snapshot the operating state** so historical replay is possible. Today every re-run overwrites; `as_of_date` is in schema but no snapshot store exists. Recommend: write each `output/operating_state_v2_*` to a date-stamped path AND a `latest` pointer.
2. **Refresh DataRails extract on a known cadence** (monthly?). Today the dump is from 2026-05-01 and contains 2016-02 → 2017-02 only — fresh DR is what unblocks org-wide v2.
3. **Stage the QBO/QBD entity exports** (`GL_QBO_*.csv`, `Balance_Sheet_QBO_*.csv`, `AR_QBD_*.csv`). Currently inventoried only.
4. **Stage `Dehart Underwriting(Summary).csv`** if land acquisition is in scope (currently out of scope per `ontology/data_readiness_audit.md`).
5. **Add a `vendor` canonical** if vendor analysis becomes a use case (`staged_gl_transactions_v2.vendor` is populated; no canonical_vendor exists yet).

### 9.4 Stop doing

- Don't read `staged_gl_transactions_v2.parquet` directly without dedup. The build pipeline does it; downstream consumers must too.
- Don't aggregate QB amounts against VF / DR — different chart of accounts.
- Don't surface v1-era dashboards as if they were the current state. The demo/ app and the v1 HTML pages cover a smaller scope.
- Don't promise per-lot allocation for projects beyond LH and PF. Flagship Allocation Workbook v3 framework is mostly empty.

---

## 10. Gaps / Missing Operational State Analysis

What the operating state does NOT cover today, ranked by what would most lift retrieval quality if filled.

### 10.1 Hard data gaps (need new data, not more code)

| gap | scope | what it would unlock | blocker |
|---|---|---|---|
| **Fresh GL pull post-2017-02 for Hillcrest, Flagship Belmont** | Org-wide | Org-wide v2 (currently blocked at Guardrail 1) | Awaiting upstream extract |
| **GL coverage for 7 active no-GL BCPD projects** + Lewis Estates (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge) | 8 projects | Per-project + per-lot cost answers for these projects (currently `unknown`) | Awaiting fresh GL pull |
| **2017-03 → 2018-06 GL gap fill** | Dump-wide, 15 months | Time-series answers across the gap | Likely not recoverable from existing files |
| **Multi-entity Balance Sheet + AR aging exports** | Currently only Anderson Geneva LLC for BS, only Uncle Boggy's for AR | Lender-position questions across all entities | Awaiting upstream extract |
| **DataRails phase grain** | DR 38-col has 0% phase fill | Pre-2018 phase-grain answers | Open ask #8 — source-system attribute investigation |
| **Scattered Lots inventory feed** | 1,130 SctLot rows / $6.55M, project-grain only | Per-lot answers for scattered/custom-build lots | Awaiting data acquisition |

### 10.2 Source-owner validation gaps (the 8 open asks)

The actual blocker, not engineering — see `PROJECT_STATE.md` § Open source-owner asks. Recurring across all three Claude evals: every Mode B answer's `data_needed_next` lands on this list.

1. Harm3 lot-range routing — phase recoverable only via lot range? (unlocks Harmony confidence)
2. AultF SR-suffix semantics — what do `0139SR` / `0140SR` mean? ($1.18M unattributed)
3. AultF B-suffix range — confirm B1 max lot = 211 ($4.0M routing)
4. MF1 vs B1 overlap 101-116 — sample SFR/B1, no MF1 leakage (Harmony confidence)
5. SctLot canonical name — confirm "Scattered Lots" identity ($6.55M project identity)
6. Range-entry allocation method — equal / sales-weighted / fixed (**$45.75M** per-lot expansion — single highest gate)
7. HarmCo X-X commercial parcel ontology decision (205 rows / $2.6M)
8. DR 38-col phase recovery — source-system attribute? (pre-2018 phase fill)

### 10.3 Ontology / schema gaps

- **`CommercialParcel` entity** for HarmCo X-X — surfaced as a v2.2 candidate.
- **`Vendor` canonical** — `staged_gl_transactions_v2.vendor` is populated but no canonical_vendor exists.
- **Budget versioning** — re-forecasts overwrite originals; historical variance comparisons impossible (v1 known issue).
- **Per-lot-type budgets** — current per-lot averages are `total / count`, masking mix effects (50' vs 60' lots blended). Deferred to v2.

### 10.4 Operational state gaps the retrieval layer should be aware of

- **No transaction-level vendor analysis** outside 2025 (QB-only / 2025-only).
- **Phase-level cost from GL alone is impossible** (0% phase fill across DR/VF/QB at source for the phase column). Phase comes from operational sources (inventory, Lot Data, 2025Status, ClickUp lot-tagged) or via VF lot-code decoder.
- **No live MLS / market-pricing feed** — internal `2025Status.SalesPrice` and `OfferMaster` are the only price proxies.
- **No live DataRails / Supabase / Postgres integration** — the retrieval system today reads files on disk, not a database or live API.
- **No incremental ingestion** — every refresh is a full rebuild from raw extracts.

### 10.5 Coverage headline

From `data/reports/coverage_improvement_opportunities.md`:

- GL coverage v0 63.0% → v1 66.6% (+3.6pp; +46 lots)
- Triangle coverage v0 37.0% → v1 37.2% (+0.2pp; +2 lots)
- GL VF rows newly attached at lot grain in v2.1: 44,244
- GL VF dollars newly attached at lot grain: $154,977,943
- Range rows isolated from lot denominator: 1,746 rows (~$45.75M kept at project+phase grain)
- Commercial parcels isolated: 205 rows
- SctLot moved off Scarlet Ridge: 1,130 rows / ~$6.55M

The binary delta v2.0 → v2.1 is modest. **The win is correctness**, not coverage expansion.

---

## Appendix A — File-to-canonical-entity quick reference

| file (raw or staged) | feeds canonical |
|---|---|
| `data/raw/datarails/gl/GL (1..14).csv` | `staged_gl_transactions_v2` (DR slice) → FinancialTransaction, Account |
| `Collateral Dec2025 - Vertical Financials.csv` | `staged_gl_transactions_v2` (VF slice) → FinancialTransaction, Account |
| `Collateral Dec2025 - BCPD GL Detail.csv` | `staged_gl_transactions_v2` (QB slice) — tie-out only |
| `Collateral Dec2025 - Lot Data.csv` | LegalEntity (HorzSeller), Project, Phase, Lot, lifecycle waterfall |
| `Collateral Dec2025 - 2025Status.csv` | LegalEntity (HorzCustomer), Project, Phase, Lot, per-lot horizontal cost components, collateral bucket |
| `Collateral Dec2025 - Collateral Report.csv` | CollateralSnapshot (as_of 2025-12-31) |
| `Collateral Dec2025 - PriorCR.csv` | CollateralSnapshot (as_of 2025-06-30) |
| `Inventory _ Closing Report (4).xlsx` | `staged_inventory_lots` → InventorySnapshot, Lot lot_status |
| `data/raw/datarails/clickup/api-upload.csv` | `staged_clickup_tasks` → TaskState (lot-tagged subset) |
| `LH Allocation 2025.10 - LH.csv` | Allocation (Lomond Heights, 12 rows) |
| `Parkway Allocation 2025.10 - PF.csv` | Allocation (Parkway Fields, 14 rows) |
| `Flagship Allocation Workbook v3 - *.csv` | Allocation framework (mostly empty) |
| `Dehart Underwriting(Summary).csv` | inventoried only; not staged |
| `Clickup_Naming_Struct - Sheet1.csv` | stage vocabulary validation (`stage_dictionary.py`) |

## Appendix B — Confidence value vocabulary

- `high` — corroborated by ≥ 2 independent sources OR is source-native from an authoritative feed.
- `medium` — single-source or partial corroboration; usable but cite the single source.
- `low` — single weak source (e.g. ClickUp-only without inventory or Lot Data corroboration).
- `inferred` — derived by a documented rule (e.g. VF lot-code decoder); not source-owner-validated. Always cite as inferred.
- `inferred-unknown` — derived rule whose semantics are not yet confirmed (SctLot identity, AultF SR).
- `unmapped` — source value has no crosswalk row; surface but do not aggregate.
- `tie-out only` — usable for reconciliation against an authoritative feed; never aggregate as primary.

## Appendix C — Citation pattern (carry into every retrieval answer)

| number type | cite as |
|---|---|
| Per-lot VF cost (decoder-derived) | "per VF v1 decoder (inferred), `<project>` Phase `<phase>` Lot `<lot>`: $X across N rows" |
| Per-lot VF cost (no decoder needed; project pre-100%) | "per VF, `<project>` Phase `<phase>` Lot `<lot>`: $X" |
| Per-lot DR cost (2016-17 only) | "per DR 38-col post-dedup (2016-17), `<project>` Lot `<lot>`: $X (no phase available)" |
| Project-level total | "per VF v2.1 totals, `<project>` 2018-2025 cost basis: $X. Includes $Y of unattributed shell costs at project+phase grain." |
| Range / shell cost | "Phase `<phase>` has $X of unattributed shell-allocation cost (range-form GL rows) not yet expanded to specific lots." |
| Commercial parcel | "`<project>` has 11 commercial parcels (A-A through K-K) totaling $X. These are non-lot inventory; not residential lot cost." |
| Scattered Lots | "Scattered Lots (formerly attributed to Scarlet Ridge in v2.0) carries $6.55M across 1,130 rows, project-grain only." |

---

_End — Source Mapping v1._
