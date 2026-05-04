# 3-Day Execution Plan — Operating State v2 (BCPD)

**Owner**: Terminal A coordinates; Terminals B and C execute their lanes.
**Last updated**: 2026-05-01

This is the practical day-by-day plan. It enforces the master-plan guardrail: **no v2 output (operating_state_v2_bcpd.json or query harness) until inventory is staged + crosswalk v0 exists + join coverage measured.**

If the guardrail is RED at end of Day 2, Day 3 is spent unblocking it. v2 ships when it ships, not on a fixed date.

---

## Day 1 — Verify GL v2; inventory + profile ops sources; draft ontology + field map

### Tasks
- **Terminal A**: write the 9 scaffolding planning docs (this set). DONE when this doc set lands.
- **Terminal B** (parallel with C): execute lane `docs/agent_lanes/terminal_b_gl_financials.md`. Specifically:
  - B1: Re-verify `staged_gl_transactions_v2` row count, date coverage, schema integrity.
  - B2: Profile cost-attribution fields by year and source schema.
  - B3: Fill the BCPD capability matrix (project / phase / lot / account / vendor: yes/no/with-caveats).
  - B4: Sign / balance audit for Vertical Financials and DataRails 38-col.
  - B5: QB-register-vs-Vertical-Financials overlap recommendation.
  - B6: Org-wide blocker statement.
- **Terminal C** (parallel with B): execute lane `docs/agent_lanes/terminal_c_ops_inventory_collateral_allocations.md`. Specifically (priority order):
  - C1 — Inventory closing report: determine `header=N`, identify columns, compare versions, propose stage plan.
  - C2 — Collateral reports: per-file `header=N`, grain, `as_of_date`, key columns.
  - (C3 — ClickUp lot-tagged subset and C4 — Allocations are next priority but may slip to Day 2 if time-constrained.)

### Outputs (end of Day 1)
- `docs/operating_state_v2_master_plan.md` (✓ in this commit)
- `docs/ontology_v0_plan.md` (✓ in this commit)
- `docs/field_map_v0_plan.md` (✓ in this commit)
- `docs/agent_workflow_plan.md` (✓ in this commit)
- `docs/agent_lanes/terminal_b_gl_financials.md` (✓)
- `docs/agent_lanes/terminal_c_ops_inventory_collateral_allocations.md` (✓)
- `docs/agent_lanes/terminal_a_integrator.md` (✓)
- `docs/3_day_execution_plan.md` (✓ this file)
- `docs/first_prompts_to_run.md` (✓ in this commit)
- `scratch/gl_financials_findings.md` (Terminal B)
- `scratch/bcpd_financial_readiness.md` (Terminal B)
- `scratch/ops_inventory_collateral_allocation_findings.md` (Terminal C — at least C1+C2 sections)
- `scratch/bcpd_ops_readiness.md` (Terminal C)
- `data/staged/ops_inventory_collateral_validation_report.md` (Terminal C — at least inventory + collateral verdicts)

### Validation checks
- All 9 planning docs exist (`find docs scratch -type f -name '*.md' | wc -l` — expect ≥9 in docs).
- Worker scratch files exist and are non-trivial (≥30 lines each).
- Inventory `header=N` is determined with a stated reason in C's validation report.

### Definition of done (Day 1)
- All scaffolding docs written.
- Both worker findings have at least the priority sections filled.
- Inventory header offset is identified (this is the gating finding for Day 2).

---

## Day 2 — Stage inventory; build crosswalk v0; build canonical tables

### Tasks
- **Terminal A** integrates worker findings. Specifically:
  - A1 — Finalize `docs/ontology_v0.md`.
  - A2 — Finalize `docs/field_map_v0.csv` and `docs/source_to_field_map.md`.
  - A3 — Define crosswalks; produce `docs/crosswalk_plan.md`; build the four `staged_*_crosswalk_v0.*` tables (or a single combined entity-project-lot crosswalk for BCPD).
  - A4 — Stage the inventory closing report → `data/staged/staged_inventory_lots.{csv,parquet}` + validation report. **This satisfies guardrail prerequisite #1.**
  - A5 — Build canonical entity tables (`canonical_legal_entity`, `canonical_project`, `canonical_phase`, `canonical_lot`, `canonical_account`, `canonical_cost_category`).
  - Decide QB-register-overlap treatment (informed by Terminal B's recommendation).
- **Terminal C** (if Day 1 priorities slipped): finish C3 (ClickUp lot-tagged) and C4 (allocations). Otherwise stand down.
- **Terminal B**: stand down unless Terminal A flags a missing finding.

### Outputs (end of Day 2)
- `docs/ontology_v0.md`
- `docs/field_map_v0.csv` and `docs/source_to_field_map.md`
- `docs/crosswalk_plan.md`
- `data/staged/staged_*_crosswalk_v0.{csv,parquet}` (per entity level OR combined for BCPD)
- `data/staged/staged_inventory_lots.{csv,parquet}` + `data/staged/staged_inventory_lots_validation_report.md`
- `data/staged/canonical_*.{csv,parquet}` (entity, project, phase, lot, account, cost_category)

### Validation checks
- Inventory staged: row count matches Terminal C's profile; `header=N` documented; column mapping enumerated.
- Crosswalk v0: every row has a `confidence` value; unmapped rows are explicitly tagged.
- Canonical tables: every row has `source_confidence`; pulling a sample lot through `canonical_lot` → `staged_inventory_lots` → `staged_gl_transactions_v2` should yield consistent identifiers.

### Definition of done (Day 2)
- Guardrail prerequisites #1 (inventory) and #2 (crosswalk) are GREEN.
- Canonical entity tables exist for BCPD.
- The QB-register treatment decision is documented in the master plan or build plan.

---

## Day 3 — Measure join coverage; (if GREEN) build BCPD v2 outputs

### Tasks
- **Terminal A**:
  - A6 — Measure join coverage: write `data/reports/join_coverage_v0.md`. **This satisfies guardrail prerequisite #3.**
  - A7 — Run the explicit guardrail check: write `data/reports/guardrail_check_v0.md` with GREEN/RED per prerequisite.
  - **Decision point**:
    - If guardrail GREEN → proceed to A8/A9/A10/A11.
    - If guardrail RED → fix the failing prereq (typically: re-stage with the right header, build a missing crosswalk row, etc.) and re-check. Do NOT ship v2 with the guardrail red.
  - A8 — Build `output/operating_state_v2_bcpd.json`.
  - A9 — Build `output/agent_context_v2_bcpd.md`.
  - A10 — Build `output/state_query_examples_v2_bcpd.md` (10–15 worked examples) and optionally a v2 query harness in `financials/`.
  - A11 — Build `output/state_quality_report_v2_bcpd.md`.

### Outputs (end of Day 3)
Pre-guardrail:
- `data/reports/join_coverage_v0.md`
- `data/reports/guardrail_check_v0.md`
- `docs/operating_state_v2_build_plan.md`

Post-guardrail (only if GREEN):
- `output/operating_state_v2_bcpd.json`
- `output/agent_context_v2_bcpd.md`
- `output/state_quality_report_v2_bcpd.md`
- `output/state_query_examples_v2_bcpd.md`
- (Optional) `financials/state_query_harness_v2_bcpd.py`
- A meeting-ready summary brief (analogue to `output/operating_state_meeting_brief_v1.md`, but for v2 BCPD).
- A list of remaining gaps and source-owner asks for org-wide v2 (e.g. "we need fresh GL pulls for Hillcrest and Flagship Belmont covering 2017-03 → 2026-04").

### Validation checks
- Join coverage report has actual numbers, not placeholders.
- Guardrail check report is explicit GREEN/RED per prereq.
- If v2 is shipped: `output/operating_state_v2_bcpd.json` is valid JSON; `output/agent_context_v2_bcpd.md` cites source files inline; `output/state_quality_report_v2_bcpd.md` enumerates per-field caveats.
- All v1 outputs untouched: `ls -la output/*.{csv,json,md,html} | grep -v _v2_bcpd` mtimes unchanged.

### Definition of done (Day 3)
- Guardrail check report is written.
- If GREEN: all four BCPD v2 outputs exist.
- If RED: the blocker is documented in `data/reports/guardrail_check_v0.md` and the v2 build is explicitly deferred (with a clear next step).

---

## Slip handling

If Day 2 ends with the guardrail still red:
- Day 3 = unblock the failing prereq. Do NOT ship v2.
- Add a Day 4 to do A8–A11 once the guardrail clears.
- Update `docs/operating_state_v2_master_plan.md` Section 8 to reflect the new schedule.

If a worker's lane runs long on Day 1:
- Terminal A still writes the integrator doc.
- Day 2's integration step starts only when Day 1 worker priorities are done.

If Terminal B flags a serious GL data issue (e.g. the imbalance is real and material):
- Terminal A pauses v2 build planning and escalates.
- Worker findings are still useful as documentation; the v2 build slips.

## Hard reminders

- **No `output/` writes by workers**.
- **No v1 file modifications** by anyone.
- **Additive only**: every v2 artifact is a new file with a `_v2` suffix.
- **Guardrail is mandatory**: do not ship v2 with it red.
- **BCPD-only for now**: do not publish org-wide v2.
