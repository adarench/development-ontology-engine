# Terminal B Lane — GL / Financials Worker

**Read this whole file before you do anything.** Then read the inputs, then write the deliverables.

## Role

You are the GL/Financials worker. You inspect every GL and finance source, validate `staged_gl_transactions_v2`, profile cost-attribution fields, and document what GL can and cannot support for BCPD Track A and (with caveats) for org-wide Track B.

You do **not** define the canonical ontology or field map. You do **not** build any operating-state output. You produce findings.

## Hard rules

- Read-only on `output/*`, `ontology/*`, `pipelines/*`, `financials/*`, every existing file under `data/staged/`, every existing file under `data/reports/`, and every existing file under `docs/` except your own scratch.
- Write only to: `scratch/gl_financials_findings.md`, `scratch/bcpd_financial_readiness.md`. You may *append* an addendum section to `data/staged/staged_gl_transactions_v2_validation_report.md` if you find something new — clearly labeled as your addendum, never deleting existing content.
- Do not edit any other terminal's scratch files.

## Inputs (in priority order)

1. `data/staged/staged_gl_transactions_v2.{csv,parquet}` (210,440 rows × 47 canonical cols)
2. `data/staged/staged_gl_transactions_v2_validation_report.md`
3. `data/staged/gl_candidate_inventory.csv` (19 GL candidates with date ranges, amount cols, etc.)
4. `data/staged/gl_coverage_report.md` (per-source date coverage + per-year row counts)
5. `data/reports/staged_gl_v1_vs_v2_comparison.md` (already documents the BCPD-only multi-year coverage point)
6. `data/staged/datarails_raw_file_inventory.{csv,md}` (full 50-file inventory; subset by likely_dataset_type=GL)
7. `data/staged/staged_gl_transactions.{csv,parquet}` (v1, for comparison only — do not modify)
8. `ontology/lot_state_v1.md`, `ontology/phase_state_v1.md`, `CONTEXT_PACK.md` (read for v1 cost-component conventions and `LOT_STATE_TO_COLLATERAL_BUCKET` / `ADVANCE_RATES`)

## Responsibilities

### B1 — Validate `staged_gl_transactions_v2`
- Confirm row count: 210,440.
- Confirm date coverage: min `posting_date` 2016-01-01, max 2025-12-31, gap 2017-03 → 2018-06.
- Confirm the 3 source schemas (`datarails_38col` 124,085 + `vertical_financials_46col` 83,433 + `qb_register_12col` 2,922).
- Confirm `row_hash` is 100% unique.
- Confirm sign convention (positive = debit) holds across schemas.
- Re-run any check from the existing validation report you don't trust.

### B2 — Profile cost-attribution fields
For each of these canonical columns, report fill rate **by source schema and by year**:
- `project`, `project_code`, `project_name`
- `lot`, `phase`, `job_phase_stage`
- `major`, `minor`
- `division_code`, `division_name`
- `operating_unit`
- `subledger_code`, `subledger_name`
- `memo_1`, `memo_2`, `description`

State explicitly which fields are usable as join keys at lot grain, phase grain, project grain, entity grain, and which are unusable.

### B3 — Determine GL capability matrix
For BCPD specifically, answer YES / NO / WITH-CAVEATS for each:
- BCPD project-level actuals (multi-year)
- BCPD phase-level actuals
- BCPD lot-level actuals
- BCPD account / cost-category rollups
- BCPD vendor / subledger analysis
- Org-wide actuals (any non-BCPD entity has post-2017 data?)

### B4 — Sign / balance audit
- `staged_gl_transactions_v2.amount.sum()` was reported as +$346.5M for Vertical Financials and +$17M for DataRails 38-col. Investigate whether each source is balanced (debits = credits) or one-sided.
- For Vertical Financials specifically: is this a normal one-sided "vertical" view, or is data missing? Look at `Account Group` and `Account Type` distributions to reason about what's included.
- For DataRails 38-col: investigate the $17M imbalance. Could be opening/closing balance mismatch, period spanning, inter-company eliminations, or a real data issue. State your conclusion.

### B5 — QB-register-vs-Vertical-Financials overlap
- `qb_register_12col` covers BCPD 2025. `vertical_financials_46col` also covers BCPD 2025 (~55K rows).
- Determine whether they overlap (same transactions, two views) or are disjoint (different scopes, e.g. QB register is a single-account view).
- Recommend: tie-out only / safe to combine / safe to combine with dedup on `(account_code, posting_date, amount)` / something else.
- Default recommendation if ambiguous: **tie-out only; exclude QB register from primary rollups**.

### B6 — Org-wide blocker statement
Write an explicit paragraph documenting why org-wide Operating State v2 cannot be published yet:
- Hillcrest Road at Saratoga LLC: only 2016-01 → 2017-02 GL data; what would be needed to unblock?
- Flagship Belmont Phase two LLC: same; what would be needed to unblock?
- The 2017-03 → 2018-06 gap: would a fresh pull cover it, or is that period genuinely empty?

## Deliverables

1. `scratch/gl_financials_findings.md` — narrative findings covering B1–B5 above. Use the handoff format in `docs/agent_workflow_plan.md` (file paths, row counts, confidence ratings, recommendations).
2. `scratch/bcpd_financial_readiness.md` — the BCPD readiness matrix from B3 plus the org-wide blocker statement from B6. Keep it short and decisive.
3. (Optional) Addendum to `data/staged/staged_gl_transactions_v2_validation_report.md` if you find something the existing report missed. Clearly label as `## Addendum (Terminal B, 2026-05-02)` or similar; never delete or restructure existing sections.

## Definition of done

- B1–B6 each have at least one paragraph in `scratch/gl_financials_findings.md`.
- BCPD readiness matrix in `scratch/bcpd_financial_readiness.md` has a row per question with one of YES / NO / WITH-CAVEATS plus the caveat.
- QB-register-overlap recommendation is explicit and actionable.
- Org-wide blocker statement is one short paragraph, not a list of TODOs.
- Sign / balance investigation has a stated conclusion (not "unclear").

## Handoff to Terminal A

When done, leave the two scratch files in place. Do not summarize them anywhere else. Terminal A will read them in full as part of integration.

## Out of scope (do not do)

- Do not stage any other source (inventory, collateral, allocations) — that's Terminal C.
- Do not propose ontology entities or field-map rows — that's Terminal A.
- Do not write any output under `output/`.
- Do not modify `staged_gl_transactions_v2.{csv,parquet}` itself.
- Do not write any code that modifies state. All work is read + write your two scratch files.
