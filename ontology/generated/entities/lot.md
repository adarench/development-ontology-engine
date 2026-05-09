<!-- Generated from ontology/entities/lot.yaml by bedrock.ontology.runtime.render_markdown. Do not edit by hand. -->

# LotState
**Entity type**: `lot`  
**Vertical**: `construction`  
**Schema version**: `v1`

## Description

A point-in-time snapshot of a single residential lot — where it sits in its lifecycle and what has actually been spent. The atomic unit of truth that PhaseState and portfolio views aggregate from. LotState captures *what has happened* to a lot. Budget and variance belong in PhaseState.

## Retrieval Tags

`lot`, `lifecycle`, `actuals`, `waterfall`, `bcpd`, `operational_state`

## Source Lineage

- `Collateral Dec2025 01 Claude.xlsx - Lot Data.csv`
- `Collateral Dec2025 01 Claude.xlsx - 2025Status.csv`
- `ontology/lot_state_v1.md`
- `pipelines/build_lot_state.py`
- `financials/build_operating_state_v2_1_bcpd.py`

## Example Queries

- What state is lot 101 in Harmony B1?
- How many days has Parkway Field A1 lot 12 been in VERTICAL_IN_PROGRESS?
- What's the cost-to-date for finished lots in Lomond Heights?

## Field Definitions

| Field | Type | Nullable | Derived | Description |
|---|---|---|---|---|
| `canonical_lot_id` | string | no | no | Composite key: {project_name}::{phase_name}::{lot_number}. Cross-validated against the SHComb column in Lot Data. |
| `project_name` | string | no | no | Name of the development project. |
| `phase_name` | string | no | no | Name of the phase within the project. |
| `lot_number` | string | no | no | Lot identifier within the phase. Column name differs between Lot Data (LotNo.) and 2025Status (Lot). |
| `project_id` | string | no | no | Reference to the parent project entity. |
| `phase_id` | string | no | no | Reference to the parent phase entity. |
| `customer_name` | string | yes | no | Buyer name, populated post-sale. |
| `buyer_id` | string | yes | no | Buyer identifier, populated post-sale. |
| `horiz_purchase_date` | date | yes | no | Date the raw land was purchased. |
| `horiz_mda_date` | date | yes | no | Master development agreement date. |
| `horiz_prelim_plat_date` | date | yes | no | Date the preliminary plat was filed/submitted. |
| `horiz_final_plat_date` | date | yes | no | Date the final plat was approved. |
| `horiz_start_date` | date | yes | no | Date first physical activity began on horizontal work. |
| `horiz_end_date` | date | yes | no | Date horizontal construction was physically completed. |
| `horiz_fin_inv_date` | date | yes | no | Date the lot entered finished inventory status. |
| `horiz_record_date` | date | yes | no | Date the plat was officially recorded. The legal milestone that triggers FINISHED_LOT state. |
| `horiz_w_enter_date` | date | yes | no | Date the lot entered the warranty period. |
| `horiz_w_exit_date` | date | yes | no | Date the lot exited the warranty period. |
| `horiz_contract_date` | date | yes | no | Date the horizontal sale/disposition contract was executed. |
| `horiz_sale_date` | date | yes | no | Date the horizontal lot sale closed. |
| `vert_purchase_date` | date | yes | no | Date the builder/vertical entity purchased the finished lot. |
| `vert_start_date` | date | yes | no | Date first physical construction activity began on the vertical build. |
| `vert_co_date` | date | yes | no | Date certificate of occupancy was issued. |
| `vert_sale_date` | date | yes | no | Date the lot/home was placed under sale contract. |
| `vert_close_date` | date | yes | no | Date the sale closed and title transferred. |
| `lot_state` | enum | no | yes | Lifecycle position computed deterministically from the date waterfall. Never manually set. |
| `lot_type` | enum | yes | no | Sales/build classification. Independent dimension from lot_state. |
| `lot_state_group` | enum | no | yes | Coarser grouping for reporting and filtering. |
| `collateral_bucket` | enum | no | yes | Lender collateral category for borrowing base reporting. Derived from lot_state and lot_type. |
| `days_in_state` | integer | no | yes | Days the lot has been in its current lot_state. Computed as as_of_date minus the date that triggered the current state. |
| `days_since_purchase` | integer | yes | yes | Days since horiz_purchase_date (or vert_purchase_date if no horizontal purchase). Null if PROSPECT. |
| `pct_complete` | decimal | yes | yes | Rough lot-completion fraction (0.0 to 1.0). v1 is state-based per LOT_STATE_TO_PCT_COMPLETE. |
| `cost_to_date` | decimal | no | no | Total actual cost to date. Sum of: Permits and Fees + Direct Construction - Lot + Shared Cost Alloc. (horizontal-only by design). |
| `remaining_cost` | decimal | yes | no | Estimated remaining spend to reach completion. Source TBD. |
| `advance_rate` | decimal | yes | yes | Lender advance rate for this lot's collateral bucket (e.g., 0.60 = 60%). |
| `capital_exposure` | decimal | yes | yes | Total capital at risk. Typically cost_to_date for unsold lots; reduces post-close. |
| `as_of_date` | date | no | no | The date this snapshot represents. All values are as of this date. |
| `source_systems` | list | no | no | Which data sources contributed (e.g., ["lifecycle_sheet", "gl_export", "inventory_sheet"]). |
| `last_computed_at` | datetime | no | no | Timestamp when this LotState was last computed/refreshed. |

### Field Aliases

- `canonical_lot_id` ← `lot_id`, `primary_key`
- `vert_co_date` ← `c_of_o`, `certificate_of_occupancy`
- `lot_state` ← `current_stage`, `stage`
- `pct_complete` ← `completion_pct`
- `cost_to_date` ← `actual_cost`, `lot_cost`, `vf_actual_cost_3tuple_usd`

## Semantic Aliases

- `lot` → `LotState`
- `lot snapshot` → `LotState`
- `lot status` → `lot_state` — current_stage in v2.1 JSON maps to lot_state.
- `actual cost` → `cost_to_date`
- `c_of_o` → `vert_co_date`
- `completion percentage` → `pct_complete`

## Relationships

- **belongs_to_phase** → `phase` (one) via `phase_id`: Each lot belongs to exactly one phase, identified by phase_id.
- **belongs_to_project** → `project` (one) via `project_id`: Each lot belongs to exactly one project, identified by project_id.

## Approved Join Paths

- **harmony_3tuple** → `phase` (one) on `project_name`, `phase_name`, `lot_number`  
  _Required join shape for Harmony cost queries. v2.1 enforces the 3-tuple to prevent ~$6.75M double-count where lot 101 in Harmony MF1 vs B1 are different physical assets._
- **lot_to_clickup** → `phase` (one) on `project_name`, `phase_name`, `lot_number`  
  _ClickUp lot-tagging is sparse (~21%). Only join when in_clickup_lottagged is true._

## Confidence Rules

- `cost_to_date` → **inferred** — VF decoder v1 is heuristic-driven (canonical project/phase/lot extracted from vertical financials line items). Marked validated_by_source_owner=False until source-owner sign-off. Reference: output/agent_context_v2_1_bcpd.md Rule 1.
- `lot_state` → **high** — Deterministic waterfall over 8 source-backed lifecycle dates. Filtered for the 1899-12-30 sentinel during ingestion.

## Validation Rules

- **sentinel_date_filter** _(severity: error)_: Any source date equal to 1899-12-30 must be treated as null at ingest.
- **state_driving_dates_only** _(severity: info)_: Only horiz_purchase_date, horiz_start_date, and horiz_record_date drive the state waterfall on the horizontal side. The remaining 9 horizontal dates are operational visibility only.
- **cost_to_date_components** _(severity: error)_: cost_to_date = sum(Permits and Fees, Direct Construction - Lot, Shared Cost Alloc.). Excludes Direct Construction (mixes horizontal+vertical) and Vertical Costs.

## Semantic Warnings

- **cost_is_inferred** (applies to `cost_to_date`): Per-lot actual cost is derived via the v1 VF decoder and is NOT source-owner-validated. Cite as 'inferred' confidence. Do not promote to 'validated'.
- **missing_is_not_zero** (applies to `cost_to_date`): A null cost_to_date means data is missing, not that the lot has zero spend. Surface 'unknown' rather than '$0' to the user.

## Embedding Payload Template

```text
LotState — {canonical_name}
{business_description}
Aliases: {aliases}
Tags: {retrieval_tags}
Lifecycle states (waterfall): CLOSED → SOLD_NOT_CLOSED → VERTICAL_COMPLETE → VERTICAL_IN_PROGRESS → VERTICAL_PURCHASED → FINISHED_LOT → HORIZONTAL_IN_PROGRESS → LAND_OWNED → PROSPECT.
Cost-to-date is horizontal-only by design (Permits and Fees + Direct Construction - Lot + Shared Cost Alloc.).
```

**Fields to include**: `canonical_lot_id`, `lot_state`, `cost_to_date`, `lot_type`, `collateral_bucket`

## Historical Behavior

v1 (pipelines/build_lot_state.py) computes lot_state from a flat (project, phase, lot) join. v2.0 carried this forward but caused ~$6.75M Harmony double-count. v2.1 enforces the 3-tuple harmony_3tuple join above.
