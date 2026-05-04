# Terminal A Lane — Planner / Integrator (post-worker)

**Run this terminal AFTER Terminals B and C have produced their scratch deliverables.** Read this whole file, then read the worker findings, then execute the integration step.

## Role

You are the integrator. You read both worker findings, finalize the v0 ontology and field map, define the entity / project / phase / lot crosswalks, stage the remaining source families, measure join coverage, and (only if the guardrail clears) build the BCPD Operating State v2 outputs.

You own everything under `docs/`. You own the canonical staged tables (`data/staged/canonical_*`, `data/staged/staged_*_crosswalk_v0.*`). You own the BCPD v2 outputs under `output/*_v2_bcpd.*`.

## Hard pre-build guardrail (MANDATORY)

**Do NOT build `output/operating_state_v2_bcpd.json` or any v2 query harness until ALL THREE of these are true:**

1. **Inventory closing report is staged.** `data/staged/staged_inventory_lots.{csv,parquet}` exists, validated, with documented header offset and column mapping.
2. **Entity / project / lot crosswalk v0 exists.** `data/staged/staged_entity_project_crosswalk_v0.{csv,parquet}` (or equivalently named) exists with a `confidence` column on every row.
3. **GL ↔ inventory ↔ ClickUp join coverage has been measured.** A written report (e.g. `data/reports/join_coverage_v0.md`) shows what fraction of BCPD lots in inventory have at least one matching GL row and at least one matching ClickUp lot-tagged task, broken down by year.

If any of the three is red, you must either fix it (your responsibility) or explicitly escalate to the human and pause. **You do not ship v2 with the guardrail red.**

## Hard rules

- Allowed writes: everything under `docs/`, all canonical staged tables under `data/staged/canonical_*`, all crosswalk tables under `data/staged/staged_*_crosswalk_v0.*`, the inventory stage `data/staged/staged_inventory_lots.{csv,parquet}`, validation/coverage reports under `data/reports/`, and the BCPD v2 outputs under `output/*_v2_bcpd.*` (only after guardrail clears).
- Forbidden writes: any existing `output/*` file that is NOT `*_v2_bcpd.*`. Any v1 ontology file under `ontology/`. Any v1 pipeline under `pipelines/` or `financials/`. Worker scratch files under `scratch/` (read only).
- Do not modify `staged_gl_transactions_v2.{csv,parquet}` or any prior v1/v2 staged table.
- Additive only. v1 outputs must remain untouched.

## Inputs (read in this order)

1. **Worker findings** under `scratch/`:
   - `scratch/gl_financials_findings.md`
   - `scratch/bcpd_financial_readiness.md`
   - `scratch/ops_inventory_collateral_allocation_findings.md`
   - `scratch/bcpd_ops_readiness.md`
2. Worker validation reports:
   - `data/staged/ops_inventory_collateral_validation_report.md`
   - Any addendum to `data/staged/staged_gl_transactions_v2_validation_report.md`
3. Existing planning docs (this set):
   - `docs/operating_state_v2_master_plan.md`
   - `docs/ontology_v0_plan.md`
   - `docs/field_map_v0_plan.md`
   - `docs/agent_workflow_plan.md`
   - `docs/3_day_execution_plan.md`
4. Existing staged tables:
   - `data/staged/staged_gl_transactions_v2.{csv,parquet}`
   - `data/staged/staged_clickup_tasks.{csv,parquet}`
5. Existing reports:
   - `data/staged/datarails_raw_file_inventory.{csv,md}`
   - `data/staged/gl_coverage_report.md`
   - `data/reports/staged_gl_v1_vs_v2_comparison.md`
6. v1 references (read-only):
   - `CONTEXT_PACK.md`
   - `ontology/lot_state_v1.md`, `ontology/phase_state_v1.md`, `ontology/data_readiness_audit.md`
   - `output/agent_context_v1.md`, `output/operating_state_meeting_brief_v1.md`, `output/operating_state_v1_validation_memo.md` (for voice/format)

## Responsibilities

### A1 — Finalize ontology v0
Write `docs/ontology_v0.md` from `docs/ontology_v0_plan.md` using the worker findings to fill in:
- For each entity, list the actual source columns the workers identified (not the planning placeholders).
- For each relationship, the actual cardinality and key evidence.
- A "BCPD instance count" line per entity (e.g. "BCPD has 12 distinct projects, X phases, Y lots").

### A2 — Finalize field map v0
Write `docs/field_map_v0.csv` (canonical CSV) and `docs/source_to_field_map.md` (the human-readable mapping) from `docs/field_map_v0_plan.md`. Each canonical field gets one row in the CSV and one section in the MD. Use the row format defined in the plan.

### A3 — Define crosswalks
Write `docs/crosswalk_plan.md` documenting how source vocabularies map:
- `legal_entity`: GL `CompanyName/CompanyCode` ↔ collateral / inventory entity refs ↔ allocation workbook entity refs.
- `project`: GL `Project*` ↔ ClickUp `subdivision` ↔ inventory community ↔ collateral project ↔ allocation workbook headers.
- `phase`: GL `Lot/Phase` (parsed) ↔ inventory phase ↔ collateral phase ↔ allocation per-phase.
- `lot`: GL `Lot/Phase` / `Lot` ↔ ClickUp `lot_num` ↔ inventory lot rows.

Then build the actual crosswalk tables:
- `data/staged/staged_entity_crosswalk_v0.csv`
- `data/staged/staged_project_crosswalk_v0.csv`
- `data/staged/staged_phase_crosswalk_v0.csv`
- `data/staged/staged_lot_crosswalk_v0.csv`

Each table carries `(source_system, source_value, canonical_value, confidence, evidence_file)`. Mark unresolved rows `confidence=unmapped`.

For BCPD only, a single combined `data/staged/staged_entity_project_crosswalk_v0.{csv,parquet}` is acceptable as the guardrail-satisfier — but only if it covers entity, project, phase, and lot for the BCPD universe.

### A4 — Stage the inventory closing report
Using Terminal C's proposal in `data/staged/ops_inventory_collateral_validation_report.md`, write the inventory stager and produce:
- `data/staged/staged_inventory_lots.{csv,parquet}`
- `data/staged/staged_inventory_lots_validation_report.md`

This satisfies guardrail prerequisite #1.

### A5 — Build canonical entity tables
Using the v0 ontology + field map + crosswalks, build:
- `data/staged/canonical_legal_entity.{csv,parquet}`
- `data/staged/canonical_project.{csv,parquet}`
- `data/staged/canonical_phase.{csv,parquet}`
- `data/staged/canonical_lot.{csv,parquet}` (BCPD-scoped is fine for v0)
- `data/staged/canonical_account.{csv,parquet}`
- `data/staged/canonical_cost_category.{csv,parquet}`

Each row carries `source_confidence` (per the field map's worst-link rule).

### A6 — Measure join coverage
Write `data/reports/join_coverage_v0.md` answering:
- Of the BCPD lots in `staged_inventory_lots`, what fraction have at least one matching row in `staged_gl_transactions_v2` (filtered to BCPD)?
- Of the same BCPD lots, what fraction have at least one matching row in the lot-tagged ClickUp subset?
- Of the same BCPD lots, what fraction have all three (full triangle)?
- Break down by year (2018, 2019, …, 2025).
- Break down by project (where multiple BCPD projects exist).

This satisfies guardrail prerequisite #3.

### A7 — Guardrail check
Write `data/reports/guardrail_check_v0.md`. For each of the three prerequisites, state GREEN or RED with evidence:
- Prereq 1: `staged_inventory_lots.parquet` exists? rows? validated? → GREEN/RED
- Prereq 2: crosswalk v0 exists? rows? confidence distribution? → GREEN/RED
- Prereq 3: join coverage report written? coverage ≥ acceptable threshold? → GREEN/RED

If any RED: STOP. Document the blocker and escalate. Do not proceed to A8/A9/A10.

### A8 — Build operating_state_v2_bcpd.json (only if guardrail GREEN)
Mirror the structure of `output/operating_state_v1.json` but for BCPD with v2 source data. The doc should carry:
- A `metadata` block: `as_of_date`, `entities_in_scope`, `source_versions`, `guardrail_status`.
- Per-project rollups.
- Per-phase rollups.
- Per-lot detail (lot status, current_stage, completion_pct, actual_cost-by-category, budget_cost-by-category, remaining_cost, source_confidence per field).
- A `caveats` section enumerating known data gaps (e.g. "2017-03 → 2018-06 GL gap; lot X in inventory has no GL match in 2024").

### A9 — Build agent context (only if guardrail GREEN)
Write `output/agent_context_v2_bcpd.md`. Mirror the voice of `output/agent_context_v1.md` and `CONTEXT_PACK.md`. Sections:
- What this is (BCPD Operating State v2).
- What the agent can answer with high confidence vs. medium vs. low.
- Source provenance summary.
- Hard limits (org-wide not in scope, 2017-18 gap, ClickUp lot-tagged sparsity).
- How to cite source files in agent answers.

### A10 — Build query examples + harness (only if guardrail GREEN)
Write `output/state_query_examples_v2_bcpd.md` with 10–15 worked example questions and the queries (or steps) that answer them. Examples to include:
- "What is BCPD's actual cost by phase for project X as of <date>?"
- "How many BCPD lots are in CLOSED state per project?"
- "What is the projected close date for lot Y, and how does it compare to actual?"
- "Which BCPD lots have a budget but no actual cost yet?"
- "Show me 2025 BCPD spend by cost category."
- (etc.)

Optionally extend `financials/state_query_harness.py` patterns into a `financials/state_query_harness_v2_bcpd.py` (or similar). Do NOT modify the existing harness — additive only.

### A11 — Build state quality report (only if guardrail GREEN)
Write `output/state_quality_report_v2_bcpd.md` enumerating, per canonical field:
- Fill rate.
- Confidence distribution.
- Known gaps and caveats.
- Whether the field is safe to use in business answers.

## Deliverables

Pre-guardrail (always produced):
- `docs/ontology_v0.md`
- `docs/field_map_v0.csv`
- `docs/source_to_field_map.md`
- `docs/crosswalk_plan.md`
- `data/staged/staged_*_crosswalk_v0.{csv,parquet}` (one per entity level, OR a combined entity-project-lot crosswalk)
- `data/staged/staged_inventory_lots.{csv,parquet}` and validation report
- `data/staged/canonical_*.{csv,parquet}` (entity, project, phase, lot, account, cost_category)
- `data/reports/join_coverage_v0.md`
- `data/reports/guardrail_check_v0.md`
- `docs/operating_state_v2_build_plan.md` (the implementation playbook for A8–A11)

Post-guardrail (only if GREEN):
- `output/operating_state_v2_bcpd.json`
- `output/agent_context_v2_bcpd.md`
- `output/state_quality_report_v2_bcpd.md`
- `output/state_query_examples_v2_bcpd.md`
- (Optional) `financials/state_query_harness_v2_bcpd.py`

## Definition of done

Pre-guardrail:
- All four `docs/` outputs (ontology_v0, field_map_v0.csv, source_to_field_map, crosswalk_plan) exist.
- All canonical staged tables exist with `source_confidence` populated.
- Inventory closing report is staged and validated.
- Crosswalk v0 exists with `confidence` populated.
- Join coverage report is written and tells the truth (not a placeholder).
- Guardrail check report is written; status is explicit.

Post-guardrail (if GREEN):
- All four BCPD v2 outputs exist.
- Quality report enumerates field-level caveats; query examples doc has 10+ worked examples.
- Validation memo confirms the guardrail was green at build time.

## Out of scope (do not do)

- Do not modify v1 outputs.
- Do not modify v1 ontology files.
- Do not modify v1 pipeline scripts.
- Do not build org-wide v2 (Hillcrest, Flagship Belmont). Track B is a roadmap track; do NOT publish.
- Do not stage non-inventory ops sources unless explicitly required by A5/A8 (collateral and allocation staging is welcome but not on the critical path for guardrail clearance).
