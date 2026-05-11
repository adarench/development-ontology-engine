# PhaseState Ontology v1

## 1. Purpose

A **PhaseState** is a phase-level aggregate that combines budgeted expectations with actual performance rolled up from LotState records. It is a point-in-time snapshot of a development phase.

PhaseState exists to:

- **Answer "how is this phase performing against plan?"** by comparing budgeted costs to actual lot-level spend
- **Enable apples-to-apples comparison across phases** — why does one phase cost 60k/lot and another 90k?
- **Aggregate lot-level truth into phase-level intelligence** without duplicating lifecycle logic
- **Surface cost variance** at the phase level for stakeholder dashboards and capital planning

PhaseState does NOT own lot lifecycle logic, lot-level dates, or individual lot costs. Those belong in LotState.

> **LotState captures what has happened to a lot.**
> **PhaseState captures what should happen and how performance compares.**

---

## 2. Core Design Principles

**Aggregation from LotState.** Actual cost and composition fields are derived by rolling up LotState records linked to the phase. PhaseState never stores lot-level detail — it summarizes it.

**Separation of expected vs. actual.** Expected (budget) fields come from underwriting and allocation spreadsheets. Actual fields come from LotState aggregation. These two streams are kept distinct so variance is always traceable.

**Deterministic derivation where inputs exist.** Variance, per-lot averages, composition counts, and phase state are all computed from formulas — never manually entered. If the inputs change, the outputs change.

**Minimal v1 scope.** Only fields that map to real data sources today. Per-lot-type budgets, historical trending, and detailed GL reconciliation are deferred.

---

## 3. Entity Definition: PhaseState

### A. Identity Fields

| Field | Type | Description |
|---|---|---|
| `canonical_phase_id` | string | Composite key: `{project_name}::{phase_name}` |
| `project_name` | string | Name of the development project |
| `phase_name` | string | Name of the phase within the project |

`canonical_phase_id` is the primary key. It must match the `phase_id` reference in LotState records to enable roll-up.

`canonical_phase_id` must exactly match the `phase_id` field used in LotState records. This is a strict requirement to ensure deterministic aggregation. Any mismatch will result in incomplete or incorrect roll-ups.

### B. Composition Fields (Derived from LotState)

These fields are computed by querying all LotState records where `phase_id` matches this phase.

| Field | Type | Description |
|---|---|---|
| `lot_count_total` | integer | Total number of lots linked to this phase |
| `lot_count_by_state` | map[lot_state → integer] | Count of lots in each `lot_state` (e.g., `{VERTICAL_IN_PROGRESS: 12, FINISHED_LOT: 8}`) |
| `lot_count_by_type` | map[lot_type → integer] | Count of lots by `lot_type` (e.g., `{SPEC: 15, PRESOLD: 5, null: 30}`) |
| `product_mix_pct` | map[lot_type → decimal] | Percentage distribution of lots by type (e.g., `{SPEC: 0.30, PRESOLD: 0.10, null: 0.60}`). Derived from `lot_count_by_type / lot_count_total`. |

### C. Expected / Budget Fields

Source: underwriting model + allocation spreadsheets. These are **input fields** — sourced from budget data, not derived from LotState.

#### Phase-Level Totals

| Field | Type | Source | Description |
|---|---|---|---|
| `expected_direct_cost_total` | decimal | Underwriting / budget | Total budgeted direct costs for the phase (labor, materials, subs) |
| `expected_indirect_cost_total` | decimal | Allocation sheets | Total budgeted indirect/allocated costs for the phase (overhead, shared infrastructure, G&A) |
| `expected_total_cost` | decimal | Derived | `expected_direct_cost_total + expected_indirect_cost_total` |
| `expected_cost_source` | string | Manual / system | Identifier for the source of expected cost data (e.g., underwriting model version, allocation sheet name, or reforecast label). Used for auditability and traceability. |

#### Per-Lot Averages (Derived)

| Field | Type | Description |
|---|---|---|
| `expected_direct_cost_per_lot` | decimal | `expected_direct_cost_total / lot_count_total` |
| `expected_indirect_cost_per_lot` | decimal | `expected_indirect_cost_total / lot_count_total` |
| `expected_total_cost_per_lot` | decimal | `expected_total_cost / lot_count_total` |

**Important note on per-lot figures:** In practice, expected costs vary by lot size and product type within a phase. v1 computes per-lot as a **simple average** (total / count). This is acknowledged as an approximation. Per-lot-type budgets (e.g., different expected costs for 50' vs 60' lots) require structured per-type budget data that may not exist yet — this is a v2 concern.

**Denominator note:** Per-lot averages use `lot_count_total` as the denominator in v1. However, this may include lots not yet active (e.g., PROSPECT). Future iterations may introduce `lot_count_active` or state-based filtering to produce more accurate per-lot comparisons.

### D. Actual Fields (Derived from LotState)

| Field | Type | Source | Description |
|---|---|---|---|
| `actual_cost_total` | decimal | LotState roll-up + allocation sheets | Total realized cost for the phase, defined as the sum of lot-level `cost_to_date` across all lots, plus any phase-level allocated costs not already embedded in lot-level values (e.g., shared infrastructure or overhead allocations from allocation sheets). |
| `actual_cost_per_lot` | decimal | Derived | `actual_cost_total / lot_count_total` |

#### Optional Direct/Indirect Split

| Field | Type | Source | Description |
|---|---|---|---|
| `actual_direct_cost_total` | decimal, nullable | Allocation sheets / GL | Actual direct costs at the phase level. Populated when source data supports it. |
| `actual_indirect_cost_total` | decimal, nullable | Allocation sheets | Actual indirect/allocated costs at the phase level. Populated when source data supports it. |

| `cost_data_completeness` | enum | Derived / manual | Indicates how complete the actual cost data is. Values: `FULL`, `PARTIAL`, `ALLOCATED_ONLY`. Used to interpret variance reliability. |

**Note:** LotState carries only `cost_to_date` with no direct/indirect split. The actual direct vs. indirect breakdown at the phase level may come from allocation sheets directly (not from lot roll-up). These fields are optional in v1 — populated when the source data is available and reliable.

**Denominator note:** Per-lot averages use `lot_count_total` as the denominator in v1. However, this may include lots not yet active (e.g., PROSPECT). Future iterations may introduce `lot_count_active` or state-based filtering to produce more accurate per-lot comparisons.

### E. Variance Fields

All variance fields compare actuals against budget. **Positive = over budget. Negative = under budget.**

| Field | Type | Description |
|---|---|---|
| `variance_total` | decimal | `actual_cost_total - expected_total_cost` |
| `variance_per_lot` | decimal | `actual_cost_per_lot - expected_total_cost_per_lot` |
| `variance_pct` | decimal | `variance_total / expected_total_cost` (e.g., 0.05 = 5% over budget, -0.03 = 3% under) |

**Invariant:** `variance_pct = variance_total / expected_total_cost` when `expected_total_cost > 0`. Null if expected total cost is zero or not yet set.

### F. Phase Lifecycle Fields

#### `phase_state`

An enum representing the operational status of the phase, derived from the **most advanced** lot in the phase using a waterfall. This tells you what stage the phase has reached.

| Value | Condition |
|---|---|
| `CLOSED_OUT` | All lots are CLOSED |
| `SELLING` | Any lot is SOLD_NOT_CLOSED or CLOSED (but not all CLOSED) |
| `VERTICAL_ACTIVE` | Any lot is VERTICAL_PURCHASED, VERTICAL_IN_PROGRESS, or VERTICAL_COMPLETE |
| `HORIZONTAL_ACTIVE` | Any lot is HORIZONTAL_IN_PROGRESS or FINISHED_LOT |
| `LAND_ACQUIRED` | Any lot is LAND_OWNED |
| `PLANNED` | All lots are PROSPECT, or phase has no lots |

Waterfall — evaluate top-down, first match wins:

```
if all lots have lot_state = CLOSED                                    → CLOSED_OUT
if any lot has lot_state in {SOLD_NOT_CLOSED, CLOSED}                  → SELLING
if any lot has lot_state in {VERTICAL_PURCHASED, VERTICAL_IN_PROGRESS,
                             VERTICAL_COMPLETE}                        → VERTICAL_ACTIVE
if any lot has lot_state in {HORIZONTAL_IN_PROGRESS, FINISHED_LOT}     → HORIZONTAL_ACTIVE
if any lot has lot_state = LAND_OWNED                                  → LAND_ACQUIRED
else                                                                   → PLANNED
```

#### `phase_majority_state`

The `lot_state_group` (from LotState) where the **plurality** of lots sit. This shows where the bulk of the phase actually is, which may lag behind the leading edge reflected in `phase_state`.

| Field | Type | Description |
|---|---|---|
| `phase_majority_state` | lot_state_group enum | The `lot_state_group` with the highest lot count. Ties broken by most advanced group. |

Example: A phase with 5 lots in HORIZONTAL, 40 in VERTICAL, and 3 in DISPOSITION has `phase_state = SELLING` but `phase_majority_state = VERTICAL`.

#### `is_transitioning`

| Field | Type | Description |
|---|---|---|
| `is_transitioning` | boolean | True if `phase_state` differs from `phase_majority_state` (comparing the `lot_state_group` of the waterfall-triggering state against the majority group). Indicates the phase is in transition between lifecycle stages — the leading edge has advanced but the bulk has not yet followed. |

### G. Timing Fields

| Field | Type | Source | Description |
|---|---|---|---|
| `avg_days_in_state` | decimal, nullable | LotState roll-up | Average of `days_in_state` across active lots (excluding PROSPECT and CLOSED). Null if no active lots. |
| `avg_days_since_purchase` | decimal, nullable | LotState roll-up | Average of `days_since_purchase` across lots with a purchase date. |
| `expected_duration_days` | integer, nullable | Underwriting | Budgeted total phase duration in days. Nullable — may not exist in structured form yet. |
| `phase_start_date` | date, nullable | LotState roll-up | Earliest relevant lifecycle date across all lots in the phase (earliest `horiz_purchase_date` or `horiz_start_date`). Represents when the phase first became active. |

### H. Metadata Fields

| Field | Type | Description |
|---|---|---|
| `as_of_date` | date | The date this snapshot represents. All values are as of this date. |
| `last_computed_at` | datetime | Timestamp when this PhaseState was last computed/refreshed |

---

## 4. Derivation Logic

PhaseState is computed in a deterministic sequence. All steps are reproducible given the same inputs.

### Step 1: Identify Lots

Query all LotState records where `phase_id = canonical_phase_id`. This is the lot set for this phase.

### Step 2: Aggregate Composition

- Count total lots → `lot_count_total`
- Group by `lot_state`, count each → `lot_count_by_state`
- Group by `lot_type`, count each → `lot_count_by_type`

### Step 3: Aggregate Actuals

- Sum `cost_to_date` across all lots → `actual_cost_total`
- Divide by `lot_count_total` → `actual_cost_per_lot`
- If phase-level allocation sheets provide direct/indirect split, populate `actual_direct_cost_total` and `actual_indirect_cost_total`

### Step 4: Attach Expected (Budget)

- Pull `expected_direct_cost_total` from underwriting/budget source
- Pull `expected_indirect_cost_total` from allocation sheets
- Compute `expected_total_cost = expected_direct_cost_total + expected_indirect_cost_total`
- Compute per-lot averages by dividing each total by `lot_count_total`

### Step 5: Compute Variance

- `variance_total = actual_cost_total - expected_total_cost`
- `variance_per_lot = actual_cost_per_lot - expected_total_cost_per_lot`
- `variance_pct = variance_total / expected_total_cost` (null if expected is 0)

### Step 6: Derive Phase State

- Apply waterfall to `lot_count_by_state` → `phase_state`
- Find `lot_state_group` with highest count → `phase_majority_state` (ties broken by most advanced)

### Step 7: Compute Timing

- Average `days_in_state` across lots where `lot_state` is not PROSPECT or CLOSED → `avg_days_in_state`
- Average `days_since_purchase` across lots where `days_since_purchase` is not null → `avg_days_since_purchase`
- Pull `expected_duration_days` from underwriting source (if available)

---

## 5. Assumptions and Known Gaps

### Confirmed Assumptions
- PhaseState is computed from LotState roll-up (actuals) + budget sources (expected). It never stores lot-level detail.
- `phase_id` in LotState reliably maps lots to phases. This linkage is assumed to be complete and correct.
- Variance sign convention: positive = over budget, negative = under budget.

### Known Gaps
- **Per-lot-type budgets:** Expected costs vary by lot size and product type in practice. v1 uses phase-level totals and simple per-lot averages. Structured per-type budget data would improve accuracy.
- **Actual direct/indirect split:** Source data is mixed — some costs are lot-level from GL, some are phase-level from allocation sheets. v1 treats the actual direct/indirect fields as optional.
- **Indirect allocation methodology:** How overhead and shared costs get allocated across phases is not defined in this ontology. The numbers come from allocation sheets; PhaseState consumes them as inputs.
- **`expected_duration_days` source:** May not exist in a structured, machine-readable format yet. Nullable until confirmed.
- **Budget versioning:** Underwriting budgets get re-forecast over time. v1 uses the current budget at `as_of_date`. Historical budget comparisons (variance against original vs. re-forecast) are deferred.
- **Lot count denominator:** Per-lot averages use `lot_count_total`, which includes all lots (PROSPECT through CLOSED). May want to exclude certain states (e.g., PROSPECT) for more meaningful averages — TBD based on stakeholder feedback.

---

## 6. Non-Goals (v1 Scope Control)

The following are explicitly **out of scope** for v1:

- **Per-vendor or per-trade cost modeling.** PhaseState does not break costs down by vendor, trade, or line item.
- **Full lender / facility modeling.** Borrowing base, draw schedules, and facility-level caps are not modeled at the phase level.
- **Detailed GL reconciliation.** PhaseState consumes cost totals. It does not validate or reconcile individual GL transactions.
- **ML-based forecasting or predictions.** No projected completion costs, predicted close dates, or risk scores.
- **Historical phase performance trending.** v1 is a current-state snapshot. Comparing how a phase's variance changed over time requires snapshot history infrastructure.
- **Sub-phase or section-level grouping.** Phases are treated as atomic units. No support for sections, blocks, or sub-phases within a phase.
- **Per-lot-type budget breakdown.** v1 computes per-lot as total / count. Per-type expected costs (e.g., different budgets for 50' vs 60' lots) are deferred.
