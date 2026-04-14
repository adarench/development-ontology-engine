# Data Readiness Audit — LotState + PhaseState v1

**Audit date:** 2026-04-10
**Data as of:** 12/31/2025
**Verdict:** PARTIAL — LotState ready with ingestion rules; PhaseState ready for actuals, partially ready for expected costs

---

## 1. Data Sources Inventoried

| Source | File(s) | Rows | Description |
|---|---|---|---|
| Lot lifecycle sheet | `Collateral Dec2025 01 Claude.xlsx - Lot Data.csv` | ~3,627 lots | Project/Phase/Lot + all horizontal and vertical lifecycle dates |
| Lot status + costs | `Collateral Dec2025 01 Claude.xlsx - 2025Status.csv` | ~3,630 rows | Per-lot status, collateral bucket, cost breakdown, product type |
| Vertical financials (GL) | `Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv` | ~83,433 transactions | Transaction-level GL detail with project/lot codes, accounts, amounts |
| Collateral report | `Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv` | ~30 phases | Phase-level borrowing base: lot counts, costs, advance rates, remaining dev costs |
| Allocation (Lomond Heights) | `LH Allocation 2025.10.xlsx - LH.csv` + supporting sheets | Per-phase | Expected cost per lot: land, direct dev, water, indirects, total cost, margin |
| Allocation (Parkway Fields) | `Parkway Allocation 2025.10.xlsx - PF.csv` + supporting sheets | Per-phase | Same structure as LH allocation |
| Underwriting (Dehart) | `Dehart Underwriting(Summary).csv` | 1 project | Project-level investment summary: sources/uses, P&L, IRR, lot counts |
| Cost to complete | `Collateral Dec2025 01 Claude.xlsx - Cost to Complete Summary.csv` | Summary | Aggregate remaining costs: land dev, vertical construction |
| Other supporting | IA Breakdown, BCPD GL Detail, PriorCR, Combined BS, RBA-TNW, OfferMaster | Various | Supplementary financial data |

**Projects covered:** Arrowhead Springs, Harmony, Ironton, Lewis Estates, Lomond Heights, Parkway Fields, Salem Fields, Santaquin Estates, Scarlet Ridge, Willowcreek, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ammon, Westbridge (~16 projects)

---

## 2. Field Mapping: LotState

| Ontology Field | Source File | Source Column(s) | Confidence | Notes |
|---|---|---|---|---|
| `canonical_lot_id` | Lot Data | Project + Phase + LotNo. | HIGH | Also available as `SHComb` (e.g., "Arrowhead Springs1231") |
| `project_name` | Lot Data / 2025Status | `Project` | HIGH | Consistent across files |
| `phase_name` | Lot Data / 2025Status | `Phase` | HIGH | Mix of numeric (123) and alpha (B1, MF1) |
| `lot_number` | Lot Data / 2025Status | `LotNo.` / `Lot` | HIGH | Different column names, same values |
| `project_id` | — | — | LOW | No explicit ID. Derive from project_name. |
| `phase_id` | — | — | LOW | No explicit ID. Construct as project_name::phase_name. |
| `customer_name` | Lot Data | `HorzCustomer` | MEDIUM | Pre-sale entity (e.g., "BCP"). No post-sale buyer name. |
| `buyer_id` | — | — | NONE | Not in any source file. |
| `horiz_purchase_date` | Lot Data | `HorzPurchase` | HIGH | Direct mapping |
| `horiz_mda_date` | Lot Data | `HorzMDA` | HIGH | NEW — not in original ontology. Direct mapping. |
| `horiz_prelim_plat_date` | Lot Data | `HorzPrelimPlat` | HIGH | Ontology split: was single `horiz_plat_date`, now two fields. |
| `horiz_final_plat_date` | Lot Data | `HorzFinalPlat` | HIGH | Ontology split. Direct mapping. |
| `horiz_start_date` | Lot Data | `HorzStart` | HIGH | Direct mapping |
| `horiz_end_date` | Lot Data | `HorzEnd` | HIGH | Direct mapping |
| `horiz_fin_inv_date` | Lot Data | `HorzFinInv` | HIGH | NEW — financial inventory date. Direct mapping. |
| `horiz_record_date` | Lot Data | `HorzRecord` | HIGH | Drives FINISHED_LOT state. Direct mapping. |
| `horiz_w_enter_date` | Lot Data | `HorzWEnter` | HIGH | NEW — warranty enter date. Direct mapping. |
| `horiz_w_exit_date` | Lot Data | `HorzWExit` | HIGH | NEW — warranty exit date. Direct mapping. |
| `horiz_contract_date` | Lot Data | `HorzContract` | HIGH | NEW — horizontal contract date. Direct mapping. |
| `horiz_sale_date` | Lot Data | `HorzSale` | HIGH | NEW — horizontal sale/disposition date. Direct mapping. |
| `vert_purchase_date` | Lot Data | `VertPurchase` | HIGH | Direct mapping. Real event (confirmed). |
| `vert_start_date` | Lot Data | `VertStart` | HIGH | Direct mapping |
| `vert_co_date` | Lot Data | `VertCO` | HIGH | Direct mapping |
| `vert_sale_date` | Lot Data | `VertSale` | HIGH | Direct mapping. **1899 sentinel = null.** |
| `vert_close_date` | Lot Data | `VertClose` | HIGH | Direct mapping. **1899 sentinel = null.** |
| `lot_state` | Derived | Waterfall from dates | HIGH | Cross-validate against 2025Status `Status` column (e.g., "13 - Vert Purchase") |
| `lot_type` | 2025Status | `Vert Sold` + inference | MEDIUM | Vert Sold=Yes → PRESOLD, else SPEC. MODEL = manual. |
| `lot_state_group` | Derived | From lot_state | HIGH | Deterministic |
| `days_in_state` | Derived | Dates + as_of_date | HIGH | |
| `days_since_purchase` | Derived | horiz_purchase_date | HIGH | |
| `pct_complete` | — | — | LOW | No expected cost per lot for cost-based %. State-based fallback possible. |
| `collateral_bucket` | Derived / 2025Status | `Collateral Bucket` | HIGH | 2025Status has pre-computed (e.g., "3 - Finished Lots"). Derive AND validate. |
| `cost_to_date` | 2025Status | Sum of: Permits and Fees + Direct Construction - Lot + Direct Construction + Shared Cost Alloc. | HIGH | Explicit component sum (confirmed). |
| `remaining_cost` | Collateral Report | `Remaining Dev Costs` | MEDIUM | Per-phase, not per-lot. Requires allocation. |
| `advance_rate` | Collateral Report | Per-bucket rates in header | HIGH | Entitled 50%, Dev WIP 55%, Finished 60%, Vert WIP 70%, Models 75%, Complete 80%, Sold 90% |
| `capital_exposure` | Derivable | cost_to_date | MEDIUM | |
| `as_of_date` | 2025Status | Header: "As of Date: 12/31/2025" | HIGH | |

### Field Mapping: PhaseState

| Ontology Field | Source File | Source Column(s) | Confidence | Notes |
|---|---|---|---|---|
| `canonical_phase_id` | Derived | Project + Phase | HIGH | |
| `project_name` | Lot Data / 2025Status | `Project` | HIGH | |
| `phase_name` | Lot Data / 2025Status | `Phase` | HIGH | |
| `lot_count_total` | 2025Status | Count rows | HIGH | Cross-validate against Collateral Report |
| `lot_count_by_state` | 2025Status | Group by `Status` | HIGH | |
| `lot_count_by_type` | 2025Status | Group by `Product Type` | HIGH | SFR, TH, MF |
| `product_mix_pct` | Derived | lot_count_by_type | HIGH | |
| `expected_direct_cost_total` | Allocation sheets (LH, PF) | `Cost of direct dev` | MEDIUM | **Only 2 of ~16 projects have allocation sheets.** |
| `expected_indirect_cost_total` | Allocation sheets (LH, PF) | `Cost of indirects` | MEDIUM | Same coverage gap. |
| `expected_total_cost` | Allocation sheets / Collateral Report | `Total cost` / `Total Dev Cost` | MEDIUM | Collateral Report has `Total Dev Cost (Spent + Remaining)` as fallback for all phases. |
| `expected_total_cost_per_lot` | Collateral Report | `All-in Cost per Lot` / `Total Dev Cost per Lot` | HIGH | Pre-computed in Collateral Report for most phases. |
| `expected_cost_source` | — | — | NONE | Must be set manually. |
| `actual_cost_total` | 2025Status | Sum cost_to_date per phase | HIGH | |
| `actual_cost_per_lot` | Derived | actual_cost_total / lot_count | HIGH | |
| `actual_direct_cost_total` | 2025Status | Sum(Permits + Direct Construction cols) | MEDIUM | "Direct" definition needs mapping. |
| `actual_indirect_cost_total` | 2025Status | Sum(Shared Cost Alloc.) | MEDIUM | May not capture full indirect. |
| `cost_data_completeness` | — | — | NONE | Must be manually assessed per phase. |
| `variance_total` | Derived | actual - expected | MEDIUM | Depends on expected cost availability. |
| `variance_per_lot` | Derived | | MEDIUM | |
| `variance_pct` | Derived | | MEDIUM | |
| `phase_state` | Derived | Waterfall from lot_state distribution | HIGH | |
| `phase_majority_state` | Derived | Plurality of lot_state_group | HIGH | |
| `is_transitioning` | Derived | phase_state vs majority | HIGH | |
| `avg_days_in_state` | Derived | From lot-level | HIGH | |
| `avg_days_since_purchase` | Derived | From lot-level | HIGH | |
| `expected_duration_days` | Underwriting (Dehart) | Construction Start/End | LOW | Only 1 project. |
| `phase_start_date` | Derived | Min(horiz_purchase_date) per phase | HIGH | |
| `as_of_date` | 2025Status | Header | HIGH | |

---

## 3. Gaps

### Cannot Populate (No Source)
- `buyer_id` — no buyer identifier in any file
- `expected_cost_source` — no structured source tracking
- `cost_data_completeness` — no source; must be assessed manually
- `expected_duration_days` — only exists for 1 project (Dehart/Payson Larsen)

### Requires Transformation / Assumptions
- **1899 sentinel dates** — `12/30/1899` must be treated as null. Appears in VertSale, VertClose, and possibly other fields.
- **VF project code mapping** — Vertical Financials uses abbreviated codes (SctLot, HB, Hmny, PkF). Lot Data uses full names. A mapping table is required.
- **lot_type inference** — `Vert Sold` = "Yes" → PRESOLD; else SPEC. MODEL has no flag; requires manual designation.
- **pct_complete** — no expected total per lot for cost-based calculation. State-based fallback (fixed % per lot_state) is the only option.
- **Expected costs for ~14 projects** — allocation sheets only cover Lomond Heights and Parkway Fields. Other projects must use Collateral Report figures (different fidelity).

### Ontology Updates Required
- **Split `horiz_plat_date`** into `horiz_prelim_plat_date` + `horiz_final_plat_date`
- **Add 6 horizontal date fields**: `horiz_mda_date`, `horiz_fin_inv_date`, `horiz_w_enter_date`, `horiz_w_exit_date`, `horiz_contract_date`, `horiz_sale_date`
- **Clarify `cost_to_date` definition**: sum of Permits and Fees + Direct Construction - Lot + Direct Construction + Shared Cost Alloc.

---

## 4. Data Quality Risks

### CRITICAL: Sentinel Dates (12/30/1899)
Date fields contain `12/30/1899` as a null placeholder (Excel epoch artifact). If not filtered, the state waterfall will incorrectly compute lots as SOLD_NOT_CLOSED or CLOSED. **Must be handled in ingestion.**

### CRITICAL: Project Name Mismatch
Vertical Financials uses abbreviated project codes (`SctLot`, `HB`, `MCreek`, `Hmny`, `PkF`). Lot Data / 2025Status use full names (`Scarlet Ridge`, `Harmony`, `Parkway Fields`). The 2025Status reconciliation section confirms unmapped projects exist: "Meadow Creek (VF: MCreek), Scout Lot (VF: SctLot)." **A mapping table is required before GL data can be joined to lots.**

### HIGH: Multiple Cost Columns
2025Status has 6 cost-related columns: `Permits and Fees`, `Direct Construction - Lot`, `Direct Construction`, `Vertical Costs`, `Shared Cost Alloc.`, `Lot Cost`. The confirmed formula is: `cost_to_date = Permits and Fees + Direct Construction - Lot + Direct Construction + Shared Cost Alloc.` The `Vertical Costs` column appears to be a pre-computed sum but should be validated against the component sum. `Lot Cost` is a separate concept (often $0 or a uniform land cost value).

### HIGH: Allocation Sheet Coverage
Only 2 of ~16 projects have structured allocation sheets with expected direct/indirect cost per lot. For the remaining projects, the Collateral Report provides phase-level expected costs (`Total Dev Cost per Lot`, `All-in Cost per Lot`) but these are lender-facing estimates, not original underwriting budgets. Variance analysis for these phases will have lower fidelity.

### MEDIUM: Lot Count Discrepancies
Collateral Report shows lot counts that may differ from row counts in Lot Data / 2025Status. Some phases split lots into "Flagship" vs "External" (e.g., Parkway A1: 4 Flagship + 65 External = 69). Need to validate which count is authoritative.

---

## 5. Aggregation Feasibility

### Can we compute `actual_cost_total` per phase reliably?
**YES.** Sum lot-level `cost_to_date` (4-component sum from 2025Status) grouped by Project + Phase. Cross-validate against Collateral Report phase totals.

### Can we compute `expected_total_cost_per_lot` per phase reliably?
**PARTIALLY.**
- **Lomond Heights + Parkway Fields**: Allocation sheets provide per-phase, per-product-type expected costs. High quality.
- **Other projects**: Collateral Report has `Total Dev Cost per Lot` and `All-in Cost per Lot`. Usable but different fidelity (lender estimates, not underwriting budgets).
- **Payson Larsen**: Underwriting model exists but is project-level only.

### Can we compute variance meaningfully?
**YES, with caveats.** Where expected costs exist (any source), `actual - expected` is computable. `cost_data_completeness` should flag which phases have high-fidelity budget data vs. lender estimates.

---

## 6. Readiness Verdict

### PARTIAL

**LotState: READY** with ingestion rules:
1. Treat `12/30/1899` as null in all date fields
2. Split plat dates: `horiz_prelim_plat_date` + `horiz_final_plat_date`
3. Add 6 horizontal date fields from Lot Data (HorzMDA, HorzFinInv, HorzWEnter, HorzWExit, HorzContract, HorzSale)
4. `cost_to_date` = Permits and Fees + Direct Construction - Lot + Direct Construction + Shared Cost Alloc.
5. Build VF project code → full project name mapping table
6. Infer `lot_type`: Vert Sold = "Yes" → PRESOLD, else SPEC; MODEL is manual

**PhaseState: PARTIALLY READY:**
1. Composition, actuals, phase_state, timing — fully derivable from LotState roll-up
2. Expected costs available for 2 projects (allocation sheets) + Collateral Report fallback for others
3. Variance computable but should flag fidelity per phase via `cost_data_completeness`

### Remaining Blockers (Before Full Readiness)
1. **VF project code mapping table** — required for GL-level data joins
2. **Allocation sheets for remaining ~14 projects** — or acceptance that Collateral Report figures are sufficient for v1
3. **MODEL lot identification** — no source; requires manual input or separate system
4. **Buyer/customer data** — no post-sale buyer name or ID in current data
