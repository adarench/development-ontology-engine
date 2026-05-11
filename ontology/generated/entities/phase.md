<!-- Generated from ontology/entities/phase.yaml by bedrock.ontology.runtime.render_markdown. Do not edit by hand. -->

# PhaseState
**Entity type**: `phase`  
**Vertical**: `construction`  
**Schema version**: `v1`

## Description

A phase-level aggregate that combines budgeted expectations with actual performance rolled up from LotState records. Answers "how is this phase performing against plan?" PhaseState never stores lot-level detail — it summarizes it. LotState = lifecycle + actuals; PhaseState = budget + comparison.

## Retrieval Tags

`phase`, `aggregate`, `budget`, `variance`, `composition`, `operational_state`

## Source Lineage

- `ontology/phase_state_v1.md`
- `pipelines/build_phase_state.py`
- `LH Allocation 2025.10.xlsx - LH.csv`
- `Parkway Allocation 2025.10.xlsx - PF.csv`
- `financials/build_operating_state_v2_1_bcpd.py`

## Example Queries

- What's the variance on Parkway Fields A1?
- How many lots are in VERTICAL_IN_PROGRESS in Lomond Heights phase 2?
- Which phases are transitioning between lifecycle stages?

## Field Definitions

| Field | Type | Nullable | Derived | Description |
|---|---|---|---|---|
| `canonical_phase_id` | string | no | no | Composite key: {project_name}::{phase_name}. Must match phase_id used in LotState records. |
| `project_name` | string | no | no | Name of the development project. |
| `phase_name` | string | no | no | Name of the phase within the project. |
| `lot_count_total` | integer | no | yes | Total lots linked to this phase. |
| `lot_count_by_state` | map | no | yes | Count of lots in each lot_state (e.g., {VERTICAL_IN_PROGRESS: 12, FINISHED_LOT: 8}). |
| `lot_count_by_type` | map | no | yes | Count of lots by lot_type (e.g., {SPEC: 15, PRESOLD: 5, null: 30}). |
| `product_mix_pct` | map | no | yes | Percentage distribution by lot_type. Derived from lot_count_by_type / lot_count_total. |
| `expected_direct_cost_total` | decimal | no | no | Total budgeted direct costs (labor, materials, subs). |
| `expected_indirect_cost_total` | decimal | no | no | Total budgeted indirect/allocated costs (overhead, shared infra, G&A). |
| `expected_total_cost` | decimal | no | yes | expected_direct_cost_total + expected_indirect_cost_total. |
| `expected_cost_source` | string | no | no | Identifier for the source of expected cost data (model version, allocation sheet name, reforecast label). |
| `expected_direct_cost_per_lot` | decimal | no | yes | expected_direct_cost_total / lot_count_total. |
| `expected_indirect_cost_per_lot` | decimal | no | yes | expected_indirect_cost_total / lot_count_total. |
| `expected_total_cost_per_lot` | decimal | no | yes | expected_total_cost / lot_count_total. |
| `actual_cost_total` | decimal | no | yes | Sum of lot-level cost_to_date across all lots, plus any phase-level allocated costs not embedded at lot grain. |
| `actual_cost_per_lot` | decimal | no | yes | actual_cost_total / lot_count_total. |
| `actual_direct_cost_total` | decimal | yes | no | Actual direct costs at the phase level (when source data supports it). |
| `actual_indirect_cost_total` | decimal | yes | no | Actual indirect/allocated costs at the phase level (when source data supports it). |
| `cost_data_completeness` | enum | no | no | Indicates how complete the actual cost data is. |
| `variance_total` | decimal | no | yes | actual_cost_total - expected_total_cost. Positive = over budget. |
| `variance_per_lot` | decimal | no | yes | actual_cost_per_lot - expected_total_cost_per_lot. |
| `variance_pct` | decimal | no | yes | variance_total / expected_total_cost. Null if expected is 0. |
| `variance_meaningful` | boolean | no | yes | Whether the variance comparison is statistically/semantically reliable. |
| `expected_cost_status` | enum | no | no | Quality of the expected_cost source for this phase. |
| `is_queryable` | boolean | no | yes | True iff expected_cost_status is FULL AND variance is meaningful. |
| `phase_state` | enum | no | yes | Operational status of the phase. Derived from the most advanced lot via waterfall. |
| `phase_majority_state` | enum | no | yes | lot_state_group where the plurality of lots sit. Ties broken by most advanced. |
| `is_transitioning` | boolean | no | yes | True iff phase_state's group differs from phase_majority_state. Indicates the leading edge has advanced but the bulk hasn't. |
| `avg_days_in_state` | decimal | yes | yes | Average days_in_state across active lots (excludes PROSPECT and CLOSED). |
| `avg_days_since_purchase` | decimal | yes | yes | Average days_since_purchase across lots with a purchase date. |
| `expected_duration_days` | integer | yes | no | Budgeted total phase duration in days. Nullable until structured underwriting data confirms. |
| `phase_start_date` | date | yes | yes | Earliest relevant lifecycle date across all lots in the phase. |
| `as_of_date` | date | no | no | The date this snapshot represents. |
| `last_computed_at` | datetime | no | no | Timestamp when this PhaseState was last computed/refreshed. |

### Field Aliases

- `canonical_phase_id` ← `phase_id`, `primary_key`

## Semantic Aliases

- `phase` → `PhaseState`
- `phase budget` → `expected_total_cost`
- `phase actuals` → `actual_cost_total`
- `budget vs actual` → `variance_total`
- `over budget` → `variance_total` — Positive variance means over budget.
- `phase status` → `phase_state`

## Relationships

- **aggregates_lots** → `lot` (many) via `canonical_phase_id`: A phase aggregates many lots; lot_count_total is the cardinality.
- **belongs_to_project** → `project` (one): Each phase belongs to exactly one project.

## Approved Join Paths

- **phase_to_lots** → `lot` (many) on `project_name`, `phase_name`
- **phase_to_allocation** → `phase` (one) on `project_name`, `phase_name`  
  _Allocation sheets (LH, PF) are the canonical source for expected cost._

## Confidence Rules

- `actual_cost_total` → **inferred** — Inherits inferred confidence from lot.cost_to_date (VF decoder v1).
- `expected_total_cost` → **high** — Allocation sheets are source-owner-authored.
- `variance_total` → **inferred** — Variance is only as confident as its weakest input — actual_cost_total is inferred.

## Validation Rules

- **queryability_gate** _(severity: info)_: is_queryable = (expected_cost_status == 'FULL') AND variance_meaningful. Only 3/125 phases pass in v2.1.
- **variance_pct_invariant** _(severity: error)_: variance_pct is null when expected_total_cost is 0 or null.
- **phase_id_match** _(severity: error)_: canonical_phase_id must exactly match the phase_id used in LotState records (deterministic aggregation requirement).

## Semantic Warnings

- **per_lot_average_is_simple** (applies to `expected_total_cost_per_lot`): v1 computes per-lot as a simple average (total / count). Real-world expected costs vary by lot size and product type. Per-lot-type budgets are deferred to v2.
- **variance_inherits_inferred** (applies to `variance_total`): Variance is only as confident as actual_cost_total. v2.1 actuals are inferred via VF decoder v1; do not promote variance figures to 'validated'.

## Embedding Payload Template

```text
PhaseState — {canonical_name}
{business_description}
Aliases: {aliases}
Tags: {retrieval_tags}
Phase state waterfall: CLOSED_OUT → SELLING → VERTICAL_ACTIVE → HORIZONTAL_ACTIVE → LAND_ACQUIRED → PLANNED.
Variance sign convention: positive = over budget, negative = under budget.
```

**Fields to include**: `canonical_phase_id`, `phase_state`, `lot_count_total`, `actual_cost_total`, `expected_total_cost`, `variance_total`, `is_queryable`

## Historical Behavior

v1 phases used flat (project, lot) joins. v2.1 enforces the 3-tuple via lot.harmony_3tuple to prevent Harmony double-count. is_queryable was added in v2.1 to gate variance reporting on expected-cost completeness — only 3/125 phases pass today.
