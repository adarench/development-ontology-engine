# Operating State v2 — Build Plan (post-guardrail playbook for A8–A11)

**Owner**: Terminal A (integrator)
**Status**: built; v2 outputs shipped (guardrail GREEN)
**Last updated**: 2026-05-01
**Companion**: `docs/operating_state_v2_master_plan.md`, `data/reports/guardrail_check_v0.md`

This is the implementation playbook for steps A8 through A11 of the integrator
lane (`docs/agent_lanes/terminal_a_integrator.md`). It documents how the v2
BCPD outputs were assembled and how to rebuild them deterministically.

---

## Build order

```
1. Stage inventory                  → financials/stage_inventory_lots.py        → staged_inventory_lots.{csv,parquet} + validation report
2. Build crosswalks                 → financials/build_crosswalks_v0.py         → staged_*_crosswalk_v0.{csv,parquet}
3. Build canonical tables           → financials/build_canonical_tables_v0.py   → canonical_*.{csv,parquet}
4. Measure join coverage            → financials/measure_join_coverage_v0.py    → join_coverage_v0.md
5. Guardrail check (manual+derived) → data/reports/guardrail_check_v0.md
6. Build operating state            → financials/build_operating_state_v2_bcpd.py → output/operating_state_v2_bcpd.json
7. Write agent context              → output/agent_context_v2_bcpd.md (manual)
8. Write query examples             → output/state_query_examples_v2_bcpd.md (manual)
9. Write quality report             → output/state_quality_report_v2_bcpd.md (manual)
```

Re-run the whole pipeline:

```bash
python3 financials/stage_inventory_lots.py
python3 financials/build_crosswalks_v0.py
python3 financials/build_canonical_tables_v0.py
python3 financials/measure_join_coverage_v0.py
python3 financials/build_operating_state_v2_bcpd.py
```

---

## Inventory staging (step 1)

Source: `data/raw/datarails_unzipped/datarails_raw/Inventory _ Closing Report (2).xlsx`

**Choice rationale** (deviation from lane doc): workbook (2) was selected over
(4) per data evidence. (2) is freshest by ~2 days of save time and carries 1
net-new sale event vs (4). See `staged_inventory_lots_validation_report.md` §
Source-selection note. If the human's intent was "the file marked (4)",
re-run with `PRIMARY_FILE = ALT_FILE` in the stager.

**Sheet selection**: union of `INVENTORY` (header=0, ~978 rows) + `CLOSED ` (header=1, ~2,894 rows).

**Derived columns**:
- `lot_status`: `ACTIVE` (INVENTORY-tab row), `CLOSED` (CLOSED-tab row with `Closing Date <= as_of`), `ACTIVE_PROJECTED` (CLOSED-tab row with `Closing Date > as_of`).
- `subdiv` is forward-filled (Excel uses vertical-merge in the INVENTORY tab).
- `canonical_project` from `SUBDIV_TO_PROJECT` map.
- `canonical_lot_id = blake2s_8(canonical_project|phase|lot_num)`.
- `as_of_date = 2026-04-29` (data-derived; max INVENTORY.SALE DATE in workbook 2).

**Validation**: 3,872 rows; 8 high-confidence + 1 low-confidence (Silver Lake) + ~25 historical low-confidence subdivs + 5 unmapped (`SPEC`, `ML`, `TO BE`, `MIDWAY`, `P2 14`). Confidence distribution: high=1,311; low=2,556; unmapped=5.

---

## Crosswalk build (step 2)

Five tables produced:

1. **`staged_entity_crosswalk_v0`** (13 rows): GL `entity_name` ↔ 2025Status `HorzCustomer` ↔ Lot Data `HorzSeller` ↔ QB filename → `canonical_entity` (BCPD/BCPBL/ASD/BCPI/Hillcrest/Flagship Belmont/Lennar/EXT).

2. **`staged_project_crosswalk_v0`** (142 rows): all source vocabularies → `canonical_project`. Sources: 2025Status, Lot Data, Collateral Report, GL DR 38-col, GL VF 46-col, inventory.subdiv, ClickUp.subdivision.

3. **`staged_phase_crosswalk_v0`** (385 rows): per-source `(canonical_project, raw_phase)` enumeration with `canonical_phase = strip(raw_phase)`. Confidence = high if ≥2 ops sources carry the phase; medium if 1; low if ClickUp-only.

4. **`staged_lot_crosswalk_v0`** (14,537 rows): per-source `(source_subdiv, raw_phase, raw_lot)` → `(canonical_project, canonical_phase, canonical_lot_number, canonical_lot_id)`. Includes inventory + Lot Data + 2025Status + ClickUp + GL VF + GL DR.

5. **`staged_entity_project_crosswalk_v0`** (133 rows): BCPD-scoped projection of project crosswalk; the explicit guardrail-prereq-#2 satisfier.

Each row carries `(source_system, source_value, canonical_*, confidence, evidence_file, notes)`.

---

## Canonical tables (step 3)

| table | rows | grain | confidence column |
|---|---:|---|---|
| `canonical_legal_entity` | 8 | one per entity | n/a (authority list) |
| `canonical_project` | 42 (BCPD scope) | one per `(canonical_entity, canonical_project)` | `source_confidence` (high/medium/low) |
| `canonical_phase` | 215 | one per `(canonical_entity, canonical_project, canonical_phase)` | `source_confidence` |
| `canonical_lot` | 6,908 (6,087 BCPD-scope) | one per `(canonical_project, canonical_phase, canonical_lot_number)` | `source_confidence` (worst-link of project_confidence + source_count) |
| `canonical_account` | 335 | one per `(source_schema, account_code)` | `source_confidence` |
| `canonical_cost_category` | 9 | one per category | `source_confidence` |

Confidence is a worst-link rollup: a row's confidence is the minimum of all
contributing field confidences.

---

## Join coverage (step 4)

`data/reports/join_coverage_v0.md` quantifies:
- Inventory base: 1,285 distinct (canonical_project, lot_norm) at high project_confidence.
- 63.0% have ≥1 GL row; 63.1% have ≥1 ClickUp lot-tagged task; 37.0% have full triangle.
- Per-project breakdown: Salem and Willowcreek hit 100% GL+ClickUp+triangle; Lewis Estates 0% GL.
- Per-year: 2025 has 809 inventory∩GL matches (best); 2016-17 has 0 (DR-era pre-active inventory).

Lot normalization rule (`_norm_lot`): strip whitespace, strip `.0`, strip leading zeros from numeric prefix (preserves alpha suffix). v0 doesn't decode phase-prefixed VF lot codes (e.g. `Harm3` lot `1034` for Harmony Phase 3 Lot 34) — that's a v1 follow-up.

---

## Guardrail check (step 5)

`data/reports/guardrail_check_v0.md` verifies all three prereqs are GREEN:
1. ✅ `staged_inventory_lots.{csv,parquet}` exists with validation
2. ✅ Crosswalk v0 with confidence column on every row
3. ✅ Join coverage report quantifies GL ↔ inventory ↔ ClickUp

It also documents:
- DataRails 38-col duplicate-treatment decision (dedup before any cost rollup; raw v2 parquet preserved).
- BCPD cost-source hierarchy: VF 2018-2025 (primary), DR-dedup 2016-02→2017-02, gap 2017-03→2018-06, QB tie-out only.

---

## Operating state v2 build (step 6)

`financials/build_operating_state_v2_bcpd.py` produces `output/operating_state_v2_bcpd.json`:

- `metadata` block: as-of dates per source family, entities in scope, source versions, guardrail status.
- `data_quality` summary: lot counts by confidence, join coverage, dedup state.
- `caveats` array: 12 explicit caveats (gap, DR multiplicity, VF one-sidedness, etc.).
- `projects` array: 25 high-confidence BCPD-relevant projects, each with:
  - `phases` array of canonical phases for that project.
  - Per-phase: collateral row (where present) + `lots` array.
  - Per-lot: `canonical_lot_id`, `horz_customer`, `horz_seller`, `lot_status_inventory`, `current_stage` (v1 waterfall), `completion_pct`, in_inventory/in_lot_data/in_2025status/in_clickup_lottagged flags, `clickup_status` (first observed for the lot in lot-tagged subset), `actual_c_of_o` (from ClickUp), `source_confidence`.

DR rows are deduplicated before per-project actuals are summed. QB rows are excluded from primary rollups by design.

---

## Agent context, query examples, quality report (steps 7-9)

Three sibling Markdown documents under `output/`:

- **`agent_context_v2_bcpd.md`**: brief an agent loads to ground its answers. Mirrors voice of `agent_context_v1.md` and `CONTEXT_PACK.md`. Sections: what this is, entities in scope, confidence by question type, source provenance, hard limits, citation pattern, quality artifacts to consult, versioning.

- **`state_query_examples_v2_bcpd.md`**: 12 worked example questions with executable Python. Covers: per-phase actuals, lot status counts, projected close dates, missing-GL diagnostics, by-category 2025 spend, pre-2018 dedup workflow, borrowing base, snapshot delta, stuck-phase detection, full-coverage filtering, triangle stats, top vendors.

- **`state_quality_report_v2_bcpd.md`**: per-canonical-field fill rate / confidence / safe-to-use flag; per-project source-coverage matrix; explicit list of "what's safe" vs "what's not" for agent answers.

---

## Out of scope for v0 build

These are deliberately not built in v0; they are roadmap items:

- **Phase-aware lot decoder** for GL VF codes (`Harm3` lot `1034` → Harmony Phase 3 Lot 34). v0 normalizes by stripping zeros only; coverage is honest about the resulting gap.
- **Chart-of-accounts crosswalk** mapping QB register codes (`132-XXX`, `510-XXX`) to legacy chart codes used by VF/DR. Required for QB ↔ VF tie-out at category level.
- **Cross-era project rollup** combining DR-era and VF-era project codes for a single "all years" view. v0 reports them era-by-era.
- **Org-wide v2** (Hillcrest, Flagship Belmont). Blocked on fresh GL pulls.
- **Allocation expansion beyond LH + PF**. Flagship Allocation Workbook v3 framework is in place but cells are mostly empty; populate before wiring.
- **Dehart Underwriting**. Wide-format underwriting model; not tabular grain. Defer.
- **OfferMaster fallback** for projects without populated allocation workbooks. Could provide community×product-type rough cost estimates; not built in v0.

---

## Re-run / freshness

- The pipeline is **deterministic** for a given set of source files. `canonical_lot_id` is a stable hash of `(canonical_project | canonical_phase | canonical_lot_number)`.
- If a source file is updated, re-run from step 1.
- The DR dedup is applied at query time in step 6; raw `staged_gl_transactions_v2` is unchanged.
- v1 outputs (`output/operating_state_v1.json`, `output/agent_context_v1.md`, etc.) are **never modified** by this pipeline. v0 is additive.
