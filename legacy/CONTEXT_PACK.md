# Development Ontology Engine — Context Pack

Self-contained brief for a thinking partner. Covers what this repo does, every function in the pipeline, the data flow, and current state.

---

## 1. What this is

A data pipeline for a real-estate / land-development portfolio. Ingests raw Excel-exported CSVs and produces two normalized entities:

- **LotState** — one row per lot, point-in-time snapshot of lifecycle + actual horizontal costs.
- **PhaseState** — one row per phase, rolls up LotState actuals and layers on budgeted expected costs + variance.

Plus a curated **phase_cost_query** dataset — the subset of PhaseState safe to use in product queries.

Ontology boundary:
- **LotState = lifecycle + actuals** (what has happened to a lot)
- **PhaseState = budget + comparison** (what should happen, and how actuals compare)

---

## 2. File layout

```
ontology/                               # specs (authoritative)
    lot_state_v1.md
    phase_state_v1.md
    data_readiness_audit.md             # 2026-04-10 source inventory
pipelines/
    config.py                           # all constants, paths, mappings, normalize_phase()
    build_lot_state.py                  # produces output/lot_state.{csv,parquet}
    build_phase_state.py                # consumes lot_state, produces phase_state.{csv,parquet} + phase_cost_query.{csv,parquet}
output/                                 # pipeline outputs (gitignored)
audit.py, audit2.py                     # forensic reconciliation scripts
<project-root>/*.csv                    # raw Excel exports (gitignored)
```

Dependencies: pandas ≥ 2.0, pyarrow ≥ 14.0. No other runtime deps.

---

## 3. Raw inputs (project root, gitignored)

| File | Role |
|---|---|
| `Collateral Dec2025 01 Claude.xlsx - Lot Data.csv` | Lifecycle dates per lot. ~3,627 rows. Primary key (Project, Phase, LotNo.) |
| `Collateral Dec2025 01 Claude.xlsx - 2025Status.csv` | Per-lot costs + status + collateral bucket. Header row = row 3. `as_of_date` stored in cell B1. |
| `Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv` | Phase-level borrowing base + total dev cost. Header row = row 9. Fallback source for expected cost (PARTIAL fidelity). |
| `LH Allocation 2025.10.xlsx - LH.csv` | Lomond Heights expected cost per lot by (phase, prod_type). Total column is blank — reconstructed from land+direct+water+indirect. |
| `Parkway Allocation 2025.10.xlsx - PF.csv` | Parkway Fields expected cost per lot. Full column set available. |
| Dehart underwriting, IA Breakdown, GL Detail, etc. | **Inventoried but not yet wired in.** |

Sentinel: source data encodes nulls as `12/30/1899` (Excel epoch). Filtered on ingest.

---

## 4. `config.py` — constants + normalize_phase

Key exports:

- **Paths** — `LOT_DATA_FILE`, `STATUS_2025_FILE`, `COLLATERAL_REPORT_FILE`, `ALLOCATION_LH_FILE`, `ALLOCATION_PF_FILE`, plus output paths for lot_state / phase_state / phase_cost_query (CSV + Parquet each).
- **`SENTINEL_DATE = "1899-12-30"`** — null placeholder to filter.
- **`COST_TO_DATE_COMPONENTS = ["Permits and Fees", "Direct Construction - Lot", "Shared Cost Alloc."]`** — horizontal-only. `Direct Construction` (mixed vertical+horizontal) and `Vertical Costs` deliberately excluded.
- **`LOT_STATE_WATERFALL`** — ordered list of (date_field, state) pairs, top-down first match wins:
  ```
  vert_close_date   → CLOSED
  vert_sale_date    → SOLD_NOT_CLOSED
  vert_co_date      → VERTICAL_COMPLETE
  vert_start_date   → VERTICAL_IN_PROGRESS
  vert_purchase_date → VERTICAL_PURCHASED
  horiz_record_date → FINISHED_LOT
  horiz_start_date  → HORIZONTAL_IN_PROGRESS
  horiz_purchase_date → LAND_OWNED
  (else)            → PROSPECT
  ```
- **`LOT_STATE_TO_GROUP`** — {PRE_DEVELOPMENT, HORIZONTAL, VERTICAL, DISPOSITION} bucket per state.
- **`LOT_STATE_TO_COLLATERAL_BUCKET`** — lender collateral category per state (Raw Land … Sold Inventory).
- **`ADVANCE_RATES`** — per collateral bucket (0.50 … 0.90).
- **`LOT_STATE_TO_PCT_COMPLETE`** — state-based progress approximation (0.05 … 0.95).
- **`PHASE_STATE_TO_GROUP`** — maps phase_state enum back to its lot_state_group (for `is_transitioning`).
- **`ALLOCATION_*_COL`** constants — 0-indexed column positions for allocation sheet parsing (phase=5, prod=6, lots=7, land=13, direct_dev=14, water=15, indirects=16, total=17). Stable across LH and PF.
- **`ALLOCATION_SOURCES`** — maps each allocation file path to (project_name, source_label).
- **`PHASE_NAME_OVERRIDES: dict`** — keyed by `(project, raw_phase)` → canonical phase_name. Currently empty; intentional hook for future renames.
- **`LOT_STATE_OUTPUT_COLUMNS`** / **`PHASE_STATE_OUTPUT_COLUMNS`** — ordered output schemas.

### Functions

**`normalize_phase(project_name, raw_phase_name) -> str`**
Deterministic phase-name normalization. Strips outer whitespace, collapses internal whitespace to single spaces, then looks up `(project, normalized_phase)` in `PHASE_NAME_OVERRIDES` and returns the canonical value. Used in both pipelines to keep LotState and allocation-sheet joins symmetric.

---

## 5. `build_lot_state.py`

Pipeline: load Lot Data + 2025Status → join on (Project, Phase, Lot) → apply waterfall → compute derived fields → write output.

**Module-level helpers:**

- `parse_money(value) -> float` — handles `$`, commas, parens (negative), dashes, em-dashes, `#DIV/0!`, empty. Returns 0.0 on failure.
- `clean_date(series) -> Series` — parses date column, replaces 1899 sentinel with NaT.
- `strip_str(value) -> str` — NaN-safe string strip.

**Load stage:**

- `load_lot_data() -> DataFrame` — reads Lot Data CSV, strips whitespace on (Project, Phase, LotNo.), parses + cleans all lifecycle date columns via `LOT_DATA_DATE_COLUMNS` rename map.
- `load_status_2025() -> (DataFrame, Timestamp)` — extracts `as_of_date` from cell B1, reads table starting row 3, filters to the 16 main columns (excludes the pivot-table sidebar), drops blank rows, parses the 4 horizontal cost components.

**Join:**

- `join_sources(lots, status) -> DataFrame` — merges on (Project, Phase, LotNo./Lot). Dedupes duplicate join keys (Lot="0" aggregate rows appear in both sources). Emits WARN counts for duplicates and unmatched rows.

**Derivations (applied row-wise):**

- `compute_lot_state(row, as_of_date) -> str` — applies `LOT_STATE_WATERFALL`, but **only considers dates ≤ as_of_date**. Future dates (planned starts) are treated as unset. This is the critical gate that distinguishes forecast-state from actual-state.
- `compute_lot_type(row) -> Optional[str]` — null for pre-vertical states. For vertical-or-later states: PRESOLD if `Vert Sold == "yes"`, else SPEC. MODEL is not derivable and isn't set.
- `compute_cost_to_date(row) -> float` — sum of `COST_TO_DATE_COMPONENTS` (3 horizontal-only fields).
- `compute_days_in_state(row, as_of_date)` — days since the date that triggered the current state (via `LOT_STATE_TO_TRIGGERING_DATE` reverse lookup). None for PROSPECT.
- `compute_days_since_purchase(row, as_of_date)` — days since `horiz_purchase_date`, falling back to `vert_purchase_date`.
- `compute_capital_exposure(row)` — `cost_to_date` for non-CLOSED; None for CLOSED (off balance sheet).

**Orchestrator:**

- `build_lot_state() -> DataFrame` — runs all stages. Constructs identity fields (`canonical_lot_id = "{project}::{phase}::{lot}"`, `phase_id = "{project}::{phase}"`). Sets `lot_state_group`, `collateral_bucket`, `advance_rate` via config maps. Writes CSV + Parquet. Prints lot-state distribution.

Outputs: 3,618 rows with 39 columns (schema = `LOT_STATE_OUTPUT_COLUMNS`). `cost_to_date` total = **$69.8M** (horizontal only).

---

## 6. `build_phase_state.py`

Pipeline: load LotState → aggregate to phases → parse allocation sheets (primary) → parse Collateral Report (fallback) → attach expected costs → compute variance → bucket by confidence → write phase_state + phase_cost_query outputs.

**Module-level helpers** (duplicated from build_lot_state for independence): `parse_money`, `strip_str`.

**Load stage:**

- `load_lot_state() -> (DataFrame, Timestamp)` — reads `output/lot_state.csv`, extracts `as_of_date`.

**Phase aggregation:**

- `compute_phase_state(lot_states: List[str]) -> str` — phase-level waterfall over the set of lot states. First match: all CLOSED → CLOSED_OUT; any {SOLD_NOT_CLOSED, CLOSED} → SELLING; any vertical state → VERTICAL_ACTIVE; any horizontal state → HORIZONTAL_ACTIVE; any LAND_OWNED → LAND_ACQUIRED; else PLANNED.
- `compute_phase_majority_state(groups: List[str]) -> str` — plurality `lot_state_group`. Ties broken by most-advanced group via `LOT_STATE_GROUP_ORDER`.
- `aggregate_phase(group: DataFrame) -> Series` — per-phase aggregation: `lot_count_total`, `lot_count_by_state` (JSON), `lot_count_by_type` (JSON with `"null"` key for untyped), `product_mix_pct` (JSON, sums to 1.0), `actual_cost_total` = Σ lot `cost_to_date`, `actual_cost_per_lot`, `phase_state`, `phase_majority_state`, `is_transitioning` (= leading_group ≠ majority_group), `avg_days_in_state` (active lots only; PROSPECT/CLOSED excluded), `avg_days_since_purchase`, `phase_start_date` (min of horiz_purchase / horiz_start across lots).
- `build_phase_aggregates(lot_state) -> DataFrame` — groupby(project, phase, phase_id).apply(aggregate_phase).

**Allocation-sheet parsing:**

- `parse_allocation_sheet(file_path, project_name=None) -> DataFrame` — reads semi-structured CSV. Locates the first "Budgeting" or "Allocation" section header (cols 0–4) and stops parsing there so only the "Summary per lot" section is consumed. Per row extracts phase (normalized via `normalize_phase`), prod_type, lot_count, and five cost-per-lot values (land, direct, water, indirect, total). Negative-signed costs are `abs()`'d. **Fallback: if `total_per_lot == 0`, reconstructs as `land + direct + water + indirect`** (required for LH where the Total column is blank).
- `build_allocation_expected() -> DataFrame` — iterates `ALLOCATION_SOURCES`, parses each, computes row totals (per-lot × lot_count), aggregates per (project, phase, source) to `expected_lot_count`, `expected_direct_cost_total`, `expected_indirect_cost_total`, `expected_total_cost`.

**Collateral Report parsing:**

- `parse_collateral_report() -> DataFrame` — header at row 9. Strips column whitespace. Normalizes project to Title Case, phase through `normalize_phase`. Extracts `Total Dev Cost (Spent + Remaining)` as `expected_total_cost`. No direct/indirect split available — so this source is always PARTIAL.

**Attach + variance:**

- `attach_expected_costs(phases, allocation_expected, collateral_expected) -> DataFrame` — two-pass join. Priority 1: allocation (only if `expected_total_cost > 0`) → sets `cost_data_completeness = "FULL"` and records `expected_lot_count`. Priority 2: Collateral Report fallback → sets PARTIAL. Emits diagnostics: allocation phases with no LotState match, CR phases with no LotState match, count of LotState phases with no expected-cost source. Finally computes `expected_{direct,indirect,total}_cost_per_lot = total / lot_count_total`.
- `compute_variance(phases) -> DataFrame` — computes `variance_total`, `variance_per_lot`, `variance_pct`. Sets `variance_meaningful = (actual > 0 AND expected not null)` and **nulls all three variance fields when not meaningful** (prevents –100% artifacts on pre-start phases). Emits a WARNING log for any meaningful phase where `actual > expected × 3`. Also derives:
  - **`expected_cost_status`** ∈ {FULL, PARTIAL, NONE}: FULL iff source is `"Allocation Sheet..."` AND `expected_lot_count == lot_count_total`. Otherwise PARTIAL if any expected, else NONE. This is stricter than `cost_data_completeness` — it also demotes phases with denominator mismatches.
  - **`is_queryable = (expected_cost_status == "FULL") AND variance_meaningful`** — the gate used for the query dataset.

**Orchestrator:**

- `build_phase_state() -> DataFrame` — runs all stages. Writes `phase_state.csv` + `.parquet`. Then filters `is_queryable` rows, selects the 10 query columns, sorts by `variance_per_lot` desc, writes `phase_cost_query.csv` + `.parquet`. Prints bucket summary (TOTAL / FULL / PARTIAL / NONE / QUERYABLE).

Outputs: 125 rows × 33 columns for phase_state. 3 rows for phase_cost_query.

---

## 7. Audit scripts

- **`audit.py`** — pre-patch forensic reconciliation. Independently reconstructs expected cost from raw allocation sheets, actual cost from 2025Status, variance, composition, lifecycle. Produced the first audit finding (Direct Construction + Vertical Costs misclassified; Collateral Report apples-to-oranges).
- **`audit2.py`** — post-patch reconciliation. Confirms horizontal-only actuals, variance arithmetic, gating correctness. Validates denominator mismatches (LH planned phases).

Both run standalone; they consume the outputs plus raw CSVs and print a structured report.

---

## 8. Current state (as_of 2025-12-31)

**Lots:** 3,618 total. Distribution:
```
HORIZONTAL_IN_PROGRESS 1146
LAND_OWNED              559
CLOSED                  486
VERTICAL_IN_PROGRESS    359
FINISHED_LOT            308
PROSPECT                287
VERTICAL_PURCHASED      273
VERTICAL_COMPLETE       188
SOLD_NOT_CLOSED          12
```

**Phases:** 125 total.
```
phase_state distribution:
    LAND_ACQUIRED      45
    PLANNED            43
    SELLING            15
    VERTICAL_ACTIVE    10
    HORIZONTAL_ACTIVE  10
    CLOSED_OUT          2

expected_cost_status:
    FULL     10   (allocation-sourced + denominator matches)
    PARTIAL  20   (CR fallback, reconstructed total, or denom mismatch)
    NONE     95

QUERYABLE (is_queryable=True): 3
    Parkway Fields::G1  -59%  variance_per_lot = -$60,082
    Parkway Fields::D2  -96%  variance_per_lot = -$100,069
    Lomond Heights::2D  -100% variance_per_lot = -$113,635
```

Σ `cost_to_date` = $69.8M (horizontal only). The excluded columns from 2025Status: `Direct Construction` ($61.7M, mixed), `Vertical Costs` ($121.8M).

---

## 9. Known issues / open questions for discussion

1. **Queryability is ~2% of phases (3/125).** The binding constraint is expected-cost coverage, not pipeline correctness. 9 projects have no expected-cost source at all (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Lewis Estates, Santaquin Estates, Westbridge). Dehart underwriting and related sources are inventoried but not wired in.
2. **LH planned-phase structural mismatch.** Allocation sheet plans lot counts for phases 2C (131), 5 (96), 6A (4), 6B (9), 6C (14) — but Lot Data has only `Lot=0` aggregate placeholder rows. Can't attach per-lot expected without an ontology decision: represent "planned" vs "platted" lot counts distinctly, or use allocation lot count as the denominator when platting hasn't happened.
3. **Collateral Report semantics unclear.** `Total Dev Cost (Spent + Remaining)` shows $0 on many clearly-active phases and produces 3.6–3.9× variance on Salem Fields::A and Willowcreek::1 even after horizontal-only alignment. May be a remaining-budget figure, not a true total. Worth confirming with the source before trusting as `expected_total_cost`.
4. **Direct Construction is currently discarded.** Excluded because for some phases it clearly contains vertical spend. But for other phases it's likely real horizontal direct construction that we're now undercounting. A transaction-level GL view (Vertical Financials CSV, ~83K rows, inventoried but not wired in) could disambiguate.
5. **No budget versioning.** v1 uses current budgets at as_of_date. Re-forecasts overwrite originals. Historical variance comparisons would need snapshotting.
6. **No historical LotState replay.** `as_of_date` is in the schema, but there's no snapshot store — re-running the pipeline produces current state only.
7. **Per-lot-type budgets** are deferred to v2. Current per-lot averages are simple total/count, which masks mix effects (a phase with 50' and 60' lots gets a blended average that matches neither).

---

## 10. Things the pipeline is provably correct about (verified by audit)

- Lot waterfall: 0 mismatches across 3,618 lots.
- Phase waterfall + majority + is_transitioning: spot checks pass.
- Composition (lot_count_total, product_mix_pct summing to 1.0): 0 mismatches.
- Actual cost arithmetic: Σ LotState = Σ PhaseState, 0 drift. `Direct Construction` and `Vertical Costs` fully excluded.
- Expected cost arithmetic: 0 mismatches across all 17 allocation-sourced phases vs independent reconstruction.
- Variance arithmetic + gating: 0 leakage, 0 formula errors.
- ID hygiene: no whitespace in canonical IDs.
