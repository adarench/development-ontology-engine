# LotState Ontology v1

## 1. Purpose

A **LotState** is a point-in-time snapshot of a single residential lot that captures where it sits in its lifecycle and what has actually been spent.

LotState exists to:

- **Compute lifecycle state deterministically** from source-backed dates, eliminating manual status tracking
- **Track actual lot-level costs** from GL and financial systems
- **Enable capital visibility** by mapping every lot to a collateral bucket with a known advance rate
- **Serve as the atomic unit of truth** that higher-level entities (PhaseState, portfolio views) aggregate from

LotState is the foundational entity for the development ontology engine. It captures **what has happened** to a lot. Budget comparisons, variance analysis, and cross-phase performance metrics belong in PhaseState.

---

## 2. Core Design Principles

**Deterministic over probabilistic.** `lot_state` is computed from lifecycle dates using a strict waterfall. There is no manual override, no "best guess." If the dates are correct, the state is correct.

**Derived state vs. manually entered.** Fields like `lot_state`, `lot_state_group`, and `collateral_bucket` are never entered directly. They are always computed from raw inputs. Only lifecycle dates and financial actuals are source-backed inputs.

**Lot-level truth only.** LotState captures what has happened to a lot. PhaseState will capture what should happen and how performance compares. Budget expectations, variance formulas, and indirect cost allocation logic do not belong here.

**Snapshot-based with time dimension.** Each LotState record is immutable at a given `as_of_date`. To see how a lot changed over time, compare snapshots. v1 focuses on current-state computation; historical replay is a future concern.

**Traceability to source data.** Every field must map to at least one real data source (lifecycle sheet, GL export, inventory sheet). If a field cannot be sourced, it does not belong in v1.

**Minimal but correct.** No speculative fields. No abstractions for hypothetical future needs. Every field earns its place by mapping to real data and serving a concrete use case.

---

## 3. Entity Definition: LotState

### A. Identity Fields

| Field | Type | Source Column | Description |
|---|---|---|---|
| `canonical_lot_id` | string | Derived / `SHComb` | Composite key: `{project_name}::{phase_name}::{lot_number}`. Cross-validate against `SHComb` column in Lot Data. |
| `project_name` | string | `Project` | Name of the development project |
| `phase_name` | string | `Phase` | Name of the phase within the project |
| `lot_number` | string | `LotNo.` / `Lot` | Lot identifier within the phase. Column name differs between Lot Data (`LotNo.`) and 2025Status (`Lot`). |

`canonical_lot_id` is the primary key. It is deterministically constructed from the three component fields and must be unique across the system.

### B. Relationship Fields

| Field | Type | Description |
|---|---|---|
| `project_id` | string | Reference to the parent project entity |
| `phase_id` | string | Reference to the parent phase entity |
| `customer_name` | string, nullable | Buyer name, populated post-sale |
| `buyer_id` | string, nullable | Buyer identifier, populated post-sale |

### C. Lifecycle Event Fields

These fields originate from operational systems and are treated as ground truth inputs for state derivation. They are **source-backed**, never inferred or computed. Each date represents a real-world event that has occurred.

#### Horizontal Lifecycle Dates

| Field | Type | Source Column | Description |
|---|---|---|---|
| `horiz_purchase_date` | date, nullable | `HorzPurchase` | Date the raw land was purchased |
| `horiz_mda_date` | date, nullable | `HorzMDA` | Master development agreement date |
| `horiz_prelim_plat_date` | date, nullable | `HorzPrelimPlat` | Date the preliminary plat was filed/submitted |
| `horiz_final_plat_date` | date, nullable | `HorzFinalPlat` | Date the final plat was approved |
| `horiz_start_date` | date, nullable | `HorzStart` | Date first physical activity began on horizontal work |
| `horiz_end_date` | date, nullable | `HorzEnd` | Date horizontal construction was physically completed |
| `horiz_fin_inv_date` | date, nullable | `HorzFinInv` | Date the lot entered finished inventory status |
| `horiz_record_date` | date, nullable | `HorzRecord` | Date the plat was officially recorded. **This is the legal milestone that triggers FINISHED_LOT state.** |
| `horiz_w_enter_date` | date, nullable | `HorzWEnter` | Date the lot entered the warranty period |
| `horiz_w_exit_date` | date, nullable | `HorzWExit` | Date the lot exited the warranty period |
| `horiz_contract_date` | date, nullable | `HorzContract` | Date the horizontal sale/disposition contract was executed |
| `horiz_sale_date` | date, nullable | `HorzSale` | Date the horizontal lot sale closed |

#### Vertical Lifecycle Dates

| Field | Type | Source Column | Description |
|---|---|---|---|
| `vert_purchase_date` | date, nullable | `VertPurchase` | Date the builder/vertical entity purchased the finished lot. This is a real transaction — e.g., buying from a land entity or third-party developer. |
| `vert_start_date` | date, nullable | `VertStart` | Date first physical construction activity began on the vertical build |
| `vert_co_date` | date, nullable | `VertCO` | Date certificate of occupancy was issued |
| `vert_sale_date` | date, nullable | `VertSale` | Date the lot/home was placed under sale contract |
| `vert_close_date` | date, nullable | `VertClose` | Date the sale closed and title transferred |

**Note on "start" dates:** Both `horiz_start_date` and `vert_start_date` represent the date of first physical activity on site — not permit issuance, not first spend, not contract execution.

**Ingestion rule — sentinel dates:** Source data uses `12/30/1899` as a null placeholder (Excel epoch artifact). Any date value of `12/30/1899` must be treated as null during ingestion. Failure to filter this will cause the state waterfall to incorrectly classify lots as SOLD_NOT_CLOSED or CLOSED.

**Ingestion rule — state-driving dates only:** Of the 12 horizontal date fields, only `horiz_purchase_date`, `horiz_start_date`, and `horiz_record_date` drive the state waterfall. The remaining horizontal dates are captured for operational visibility and future analysis but do not affect `lot_state` derivation.

### D. Derived State Fields

#### `lot_state`

An enum representing the current lifecycle position of the lot. Computed deterministically via the waterfall in Section 4. **Never manually set.**

| Value | Meaning |
|---|---|
| `CLOSED` | Sale closed, title transferred. Lot is off the balance sheet. |
| `SOLD_NOT_CLOSED` | Under sale contract, awaiting close. |
| `VERTICAL_COMPLETE` | Certificate of occupancy issued. Home is built but not yet sold. |
| `VERTICAL_IN_PROGRESS` | Physical construction activity has begun. |
| `VERTICAL_PURCHASED` | Builder/vertical entity has purchased the finished lot. Construction has not yet started. |
| `FINISHED_LOT` | Plat recorded. Horizontal development is complete. Lot is ready for vertical. |
| `HORIZONTAL_IN_PROGRESS` | Physical horizontal development (grading, utilities, roads) is underway. |
| `LAND_OWNED` | Raw land has been purchased. No development activity yet. |
| `PROSPECT` | Lot is identified but land has not been purchased. Pipeline only. |

#### `lot_type`

An enum representing the sales/build classification of the lot. This is a **separate dimension** from `lot_state` — a lot transitions through lifecycle states independently of its type.

| Value | Meaning | How Set |
|---|---|---|
| `SPEC` | Speculative build — no buyer under contract | Default for any vertical lot without a sale contract |
| `PRESOLD` | Buyer under contract before or during construction | Set when `vert_sale_date` is populated and lot is not yet CLOSED |
| `MODEL` | Model home — not for immediate sale | Business-designated, set manually |

A lot can transition from `SPEC` to `PRESOLD` when a buyer contracts. `MODEL` is a manual designation. `lot_type` is only meaningful for lots in VERTICAL_PURCHASED or later states; for earlier states it is null.

#### `lot_state_group`

A coarser grouping for reporting and filtering.

| Group | States Included |
|---|---|
| `PRE_DEVELOPMENT` | PROSPECT, LAND_OWNED |
| `HORIZONTAL` | HORIZONTAL_IN_PROGRESS, FINISHED_LOT |
| `VERTICAL` | VERTICAL_PURCHASED, VERTICAL_IN_PROGRESS, VERTICAL_COMPLETE |
| `DISPOSITION` | SOLD_NOT_CLOSED, CLOSED |

#### Timing Metrics (Derived)

| Field | Type | Description |
|---|---|---|
| `days_in_state` | integer | Number of days the lot has been in its current `lot_state`. Computed as `as_of_date - date_of_most_recent_state_triggering_event`. |
| `days_since_purchase` | integer, nullable | Number of days since `horiz_purchase_date` (or `vert_purchase_date` if no horizontal purchase). Null if lot is PROSPECT. |

#### Progress Metric (Derived)

| Field | Type | Description |
|---|---|---|
| `pct_complete` | decimal, nullable | Rough measure of lot completion (0.0 to 1.0). Exact formula TBD — may be cost-based (`cost_to_date / expected_total_cost`) or state-based (mapping each `lot_state` to a fixed percentage). Null for PROSPECT and CLOSED lots. |

#### `collateral_bucket`

Maps to lender collateral categories for borrowing base reporting. Derived from `lot_state` and `lot_type`.

| Bucket | Lot States | Notes |
|---|---|---|
| `Raw Land` | PROSPECT, LAND_OWNED | Lowest advance rate |
| `Land Under Development` | HORIZONTAL_IN_PROGRESS | |
| `Finished Lots` | FINISHED_LOT, VERTICAL_PURCHASED | Lot is platted and recorded; vertical entity may or may not have taken title |
| `Vertical WIP` | VERTICAL_IN_PROGRESS | SPEC vs PRESOLD may carry different advance rates |
| `Completed Inventory` | VERTICAL_COMPLETE | CO issued, no buyer |
| `Sold Inventory` | SOLD_NOT_CLOSED | Under contract, highest advance rate |
| `N/A` | CLOSED | Off balance sheet — no longer collateral |

### E. Financial Fields

Source: GL / vertical financials (transaction-level costs tied to lots).

| Field | Type | Description |
|---|---|---|
| `cost_to_date` | decimal | Total actual cost incurred to date. Computed as: `Permits and Fees` + `Direct Construction - Lot` + `Direct Construction` + `Shared Cost Alloc.` from the 2025Status source. |
| `remaining_cost` | decimal, nullable | Estimated remaining spend to reach completion. Source and derivation TBD — may come from underwriting or a separate estimate process. |

Granular cost breakdown by category (permits, direct construction, allocations, etc.) is deferred. If needed, it will be available through the underlying GL data rather than denormalized into LotState.

### F. Capital Fields

Source: inventory / collateral / capital sheets.

| Field | Type | Description |
|---|---|---|
| `advance_rate` | decimal, nullable | Lender advance rate for this lot's collateral bucket (e.g., 0.60 = 60%). Mapped from `collateral_bucket` and `lot_type`. |
| `capital_exposure` | decimal, nullable | Total capital at risk. Typically `cost_to_date` for lots not yet sold; reduces post-close. |

Borrowing base calculations, loan value derivations, and multi-layer capital modeling are deferred to a future CapitalState or PhaseState entity.

### G. Metadata / Audit Fields

| Field | Type | Description |
|---|---|---|
| `as_of_date` | date | The date this snapshot represents. All values are as of this date. |
| `source_systems` | list[string] | Which data sources contributed to this snapshot (e.g., `["lifecycle_sheet", "gl_export", "inventory_sheet"]`) |
| `last_computed_at` | datetime | Timestamp when this LotState was last computed/refreshed |

---

## 4. State Transition Logic

### Waterfall Rule

`lot_state` is computed using a **deterministic waterfall**. Evaluate conditions top-down; the **first match wins**.

```
if vert_close_date is not null     → CLOSED
if vert_sale_date is not null      → SOLD_NOT_CLOSED
if vert_co_date is not null        → VERTICAL_COMPLETE
if vert_start_date is not null     → VERTICAL_IN_PROGRESS
if vert_purchase_date is not null  → VERTICAL_PURCHASED
if horiz_record_date is not null   → FINISHED_LOT
if horiz_start_date is not null    → HORIZONTAL_IN_PROGRESS
if horiz_purchase_date is not null → LAND_OWNED
else                               → PROSPECT
```

### Why This Order Works

The waterfall checks the most advanced lifecycle events first. This handles real-world overlaps correctly:

- **Vertical spend before recording:** If a builder begins vertical work before the plat is officially recorded, `vert_start_date` will be set. Because vertical dates are checked before horizontal dates, the lot correctly shows as `VERTICAL_IN_PROGRESS` — reflecting reality that the more advanced activity has begun.
- **Sale before CO:** A lot can be sold (under contract) before CO is issued. `vert_sale_date` is checked before `vert_co_date`, so the lot shows `SOLD_NOT_CLOSED`. Once the CO is issued but the lot hasn't closed yet, it remains `SOLD_NOT_CLOSED` because sale is checked first.
- **No ambiguity:** Every lot maps to exactly one state. The waterfall is exhaustive (the `else` catches everything) and unambiguous (first match wins).

### `lot_state_group` Derivation

```
PRE_DEVELOPMENT  ← {PROSPECT, LAND_OWNED}
HORIZONTAL       ← {HORIZONTAL_IN_PROGRESS, FINISHED_LOT}
VERTICAL         ← {VERTICAL_PURCHASED, VERTICAL_IN_PROGRESS, VERTICAL_COMPLETE}
DISPOSITION      ← {SOLD_NOT_CLOSED, CLOSED}
```

### `collateral_bucket` Derivation

```
PROSPECT, LAND_OWNED           → Raw Land
HORIZONTAL_IN_PROGRESS         → Land Under Development
FINISHED_LOT, VERTICAL_PURCHASED → Finished Lots
VERTICAL_IN_PROGRESS           → Vertical WIP
VERTICAL_COMPLETE              → Completed Inventory
SOLD_NOT_CLOSED                → Sold Inventory
CLOSED                         → N/A
```

### `lot_type` Determination

`lot_type` is not part of the state waterfall. It is determined by separate logic:

- If the lot is in a pre-vertical state (PROSPECT through FINISHED_LOT): `lot_type` is **null**
- If the lot is designated as a model home (business decision): `lot_type` = **MODEL**
- If `vert_sale_date` exists and lot is not CLOSED: `lot_type` = **PRESOLD**
- Otherwise (vertical lot, no sale contract): `lot_type` = **SPEC**

---

## 5. Assumptions and Known Gaps

### Confirmed Assumptions
- **"Finished lot" is triggered by `horiz_record_date`** (plat recorded), not `horiz_end_date`. The record date is the legal milestone. `horiz_end_date` is tracked for operational visibility but does not drive state.
- **`vert_purchase_date` is a real, distinct event.** It represents the builder or vertical entity purchasing the finished lot from a land entity or third-party developer. Not all lots have this — but when it exists, it is a meaningful lifecycle milestone.
- **Start dates represent first physical activity on site.** Not permit issuance, not first financial transaction.
- **SPEC / PRESOLD / MODEL distinctions matter** for collateral bucketing and capital treatment (different advance rates).
- **Column mappings validated against real data** (data readiness audit, 2026-04-10). All lifecycle date fields map directly to Lot Data CSV columns. Source column names are documented in field tables above.
- **`cost_to_date` = component sum** of Permits and Fees + Direct Construction - Lot + Direct Construction + Shared Cost Alloc. from 2025Status.
- **`12/30/1899` is a null sentinel** in source data. Must be filtered during ingestion.

### Known Gaps
- **Advance rate source:** Collateral Report provides per-bucket rates (Entitled 50%, Dev WIP 55%, Finished 60%, Vert WIP 70%, Models 75%, Complete 80%, Sold 90%). `lot_type` (SPEC vs PRESOLD) may affect rate within Vertical WIP, but exact lookup logic is TBD.
- **Customer/buyer linkage:** `HorzCustomer` exists (e.g., "BCP") but no post-sale buyer name or buyer_id. Source for buyer data is unknown.
- **MODEL lot source:** MODEL designation has no flag in any source file. Must be manually provided or derived from another system.
- **`lot_type` transition signal:** `Vert Sold` = "Yes" in 2025Status maps to PRESOLD. But does `vert_sale_date` always mean a binding contract, or could it be a reservation?
- **`pct_complete` formula:** No expected total per lot available in LotState for cost-based calculation. State-based fallback (fixed percentages per `lot_state`) is the only v1 option. Needs business input on percentage assignments.
- **`remaining_cost` source:** Collateral Report has `Remaining Dev Costs` per phase. Per-lot remaining requires allocation or a separate estimate process.
- **Vertical Financials project code mapping:** GL data uses abbreviated codes (SctLot, HB, Hmny, PkF). A mapping table to full project names is required before GL transactions can be joined to lots.

---

## 6. Non-Goals (v1 Scope Control)

The following are explicitly **out of scope** for v1:

- **Phase-level budgets and variance.** Expected costs, budget comparisons, cost/timeline variance, and margin analysis belong in PhaseState.
- **Granular cost breakdown.** Lot-level cost categories (permits, direct construction, allocations) are available in source GL data but not denormalized into LotState v1.
- **Full lender facility modeling.** Multiple tranches, draw schedules, facility-level caps, cross-collateralization, borrowing base calculations.
- **GL reconciliation.** v1 consumes a single `cost_to_date` total. It does not reconcile individual journal entries or validate GL accuracy.
- **Portfolio optimization.** No capital allocation engine, no "which lots should we start next" logic. v1 is descriptive, not prescriptive.
- **Multi-entity / JV structures.** v1 assumes a single entity perspective. Joint ventures, co-developer arrangements, and multi-entity ownership splits are deferred.
- **Automated data ingestion.** v1 defines the target schema. How data flows from spreadsheets into LotState records is a separate concern.
- **Historical state replay.** v1 computes current state. The `as_of_date` field supports future snapshotting, but the replay mechanism is not built.

---

## 7. Scope Clarification

LotState is the **atomic lot-level entity**. It answers: "What state is this lot in, and what has been spent?"

**LotState does NOT contain:**

- Phase-level budgets or expected cost per lot
- Indirect cost allocation logic
- Cross-phase or cross-project comparisons
- Underwriting expectations, variance calculations, or margin analysis
- Budget-to-actual comparisons

**These will be handled in PhaseState**, which aggregates LotState records and layers on budget context, performance metrics, and underwriting feedback loops.

The boundary is clear:

> **LotState = lifecycle + actuals**
> **PhaseState = budget + comparison**
