# Agent Workflow Plan — 3-Terminal Setup

**Last updated**: 2026-05-01
**Companion to**: `docs/operating_state_v2_master_plan.md`

This document defines the working model for getting Operating State v2 (BCPD) ready. We use a deliberately simple 3-terminal layout. We are **not** building a multi-agent orchestration framework.

## Terminals

| terminal | role | runs |
|---|---|---|
| **A** | Planner / Integrator | first (writes scaffolding + docs); last (reads worker findings, finalizes ontology + field map + crosswalks + builds BCPD v2) |
| **B** | GL / Financials Worker | parallel with C |
| **C** | Ops / Inventory / Collateral / Allocation Worker | parallel with B |

## Hard pre-build guardrail (mirrored from master plan)

**No terminal — including Terminal A — may build `output/operating_state_v2_bcpd.json` or any v2 query harness until ALL THREE of the following are true:**

1. Inventory closing report is staged (`data/staged/staged_inventory_lots.{csv,parquet}` exists with validation).
2. Entity / project / lot crosswalk v0 exists (`data/staged/staged_entity_project_crosswalk_v0.{csv,parquet}` or equivalent, with `confidence` column).
3. GL ↔ inventory ↔ ClickUp join coverage has been measured (`data/reports/join_coverage_v0.md` or equivalent).

This guardrail is enforced by Terminal A. Workers do not write outputs to `output/`; they cannot violate the guardrail by accident.

## Per-terminal contract

### Terminal A — Planner / Integrator
- **Role**: Owns the master plan, the ontology, the field map, the crosswalks, and the final BCPD v2 build.
- **Inputs**: All worker findings under `scratch/`; all staged tables under `data/staged/`; all reports under `data/reports/`; v1 ontology in `ontology/`; v1 outputs in `output/` (read-only).
- **Allowed writes**: Everything under `docs/`; the final canonical staged tables under `data/staged/canonical_*` and `data/staged/staged_*_crosswalk_v0.*`; the BCPD v2 outputs under `output/*_v2_bcpd.*` (only after the guardrail clears).
- **Forbidden writes**: Any existing `output/*` file that is not `*_v2_bcpd.*`. v1 ontology files under `ontology/`. v1 pipeline scripts under `pipelines/` and `financials/`. Worker scratch files (B and C own those).
- **Expected deliverables**: `docs/ontology_v0.md`, `docs/field_map_v0.csv`, `docs/source_to_field_map.md`, `docs/crosswalk_plan.md`, `docs/operating_state_v2_build_plan.md`, then (post-guardrail) `output/operating_state_v2_bcpd.json`, `output/agent_context_v2_bcpd.md`, `output/state_quality_report_v2_bcpd.md`, `output/state_query_examples_v2_bcpd.md`.
- **Definition of done**: All four BCPD v2 outputs exist, the quality report explicitly enumerates field-level caveats, the query examples doc has 10–15 worked examples, and the validation memo confirms the guardrail was green at build time.
- **Handoff format**: Inline references to source files in every doc (e.g. `staged_gl_transactions_v2.parquet:row_hash=…`); explicit `confidence` columns; a "what changed since v1" section in the agent context.

### Terminal B — GL / Financials Worker
See `docs/agent_lanes/terminal_b_gl_financials.md` for the full lane.

- **Role**: Validates and profiles all GL/financial sources to determine what cost attribution is actually possible.
- **Allowed writes**: `scratch/gl_financials_findings.md`, `scratch/bcpd_financial_readiness.md`. May extend `data/staged/staged_gl_transactions_v2_validation_report.md` with an addendum if needed (do not delete or restructure existing content).
- **Forbidden writes**: `output/*`, `ontology/*`, any `docs/*`, any other `data/staged/*` or `data/reports/*` file, any other terminal's scratch files.
- **Expected deliverables**: the two scratch files above, plus optional validation report addendum.
- **Definition of done**: BCPD readiness matrix is filled (project-level / phase-level / lot-level / account / vendor: yes/no/with-caveats); QB-register-overlap risk has a written treatment recommendation; the org-wide-blocker statement is explicit.
- **Handoff format**: each finding includes file paths, row counts, and a confidence rating; recommendations are actionable (e.g. "exclude QB register from primary rollups; use as tie-out only").

### Terminal C — Ops / Inventory / Collateral / Allocation Worker
See `docs/agent_lanes/terminal_c_ops_inventory_collateral_allocations.md` for the full lane.

- **Role**: Inspects ClickUp, inventory closing report, collateral reports, allocation workbooks; identifies grain, join keys, and how each source feeds the canonical entities.
- **Priority order** (do these in this order):
  1. Inventory closing report (highest priority — unblocks the guardrail).
  2. Collateral reports.
  3. ClickUp lot-tagged subset.
  4. Allocations / budgets.
- **Allowed writes**: `scratch/ops_inventory_collateral_allocation_findings.md`, `scratch/bcpd_ops_readiness.md`, `data/staged/ops_inventory_collateral_validation_report.md`.
- **Forbidden writes**: `output/*`, `ontology/*`, any `docs/*`, any other `data/staged/*` file, any other terminal's scratch files.
- **Expected deliverables**: the three files above. May propose a stage-plan for the inventory closing report (header offset, column mapping) but does not stage it — that's Terminal A's call after reviewing the proposal.
- **Definition of done**: each ops source has identified grain + join keys; the inventory closing report header offset is determined; the BCPD ops readiness matrix is filled.
- **Handoff format**: same as B — file paths, row counts, confidence; recommendations actionable.

## Hard guardrails (apply to all terminals)

- Workers do **not** define the canonical ontology. Workers report findings; Terminal A decides.
- Workers do **not** modify Operating State v1 outputs. The entire `output/*` directory is read-only for workers.
- Workers do **not** modify v1 ontology, v1 pipelines, or the existing data/staged GL v2 parquet/csv. They may *read* anything.
- Workers do **not** edit each other's scratch files. B owns `scratch/gl_*` and `scratch/bcpd_financial_*`; C owns `scratch/ops_*` and `scratch/bcpd_ops_*`.
- Workers write **findings and validation reports only**.
- Integrator (Terminal A) reads worker findings and decides the final canonical schema.
- Workers do **not** build any v2 output (`output/operating_state_v2_*` is not their concern).

## Sequence

1. Terminal A writes the 9 scaffolding docs (this step). **DONE when this doc set lands.**
2. Terminals B and C run in parallel against their lane docs.
3. Both workers produce findings under `scratch/` (and C produces its validation report under `data/staged/`).
4. Terminal A reads both worker outputs, finalizes ontology v0 + field map v0 + crosswalk plan, then stages the inventory closing report and builds the crosswalk.
5. Terminal A measures join coverage (writes `data/reports/join_coverage_v0.md`).
6. **Guardrail check**: all three prerequisites green?
   - **YES** → Terminal A builds the four BCPD v2 outputs.
   - **NO** → Terminal A documents the blocker, fixes it (or escalates to the human), and re-checks. **Does not ship v2 with the guardrail red.**

## Handoff format (uniform across all terminals)

Every finding / recommendation includes:

- **File path** (relative to repo root) and the specific table or sheet.
- **Row count / shape** evidence (`N rows × M cols`).
- **Confidence rating** (`high`, `medium`, `low`, `unmapped`).
- **Caveat** if confidence is below `high`.
- **Recommended action** if any.

Example:
> `data/staged/staged_gl_transactions_v2.parquet` filtered to `entity_name == 'Building Construction Partners, LLC'` yields 197,852 rows. `Project` fill 100% on the 86,355 post-2018 rows (Vertical Financials), 49.5% on the 111,497 pre-2018 rows (DataRails 38-col). **Confidence: high** for post-2018 lot-level rollup; **medium** for pre-2018 (half the rows are project-untagged). **Recommendation**: scope BCPD v2 lot-level rollup to 2018-onward; report 2016-17 at entity-level only, with explicit caveat in the quality report.

## What this doc does not do

- It does not specify the implementation steps for any individual deliverable; lane docs do that.
- It does not allocate clock-time per terminal; the 3-day plan does.
- It does not define the prompts to paste into each terminal; `docs/first_prompts_to_run.md` does.
