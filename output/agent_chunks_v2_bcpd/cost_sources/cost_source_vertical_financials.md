---
chunk_id: cost_source_vertical_financials
chunk_type: cost_source
title: Cost source: Vertical Financials (BCPD 2018-2025 primary)
project: n/a
source_files:
  - scratch/gl_financials_findings.md
  - data/reports/guardrail_check_v0.md
  - output/state_quality_report_v2_1_bcpd.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for any BCPD 2018-2025 cost question
caveats:
  - VF is one-sided; not a balanced trial balance.
---

## Plain-English summary

Vertical Financials 46-col is the **primary** BCPD cost source for 2018-2025. It carries 100% project + lot fill across 83,433 rows and ~$346.5M of one-sided capitalized cost. Each row records the asset-side debit of an entry that capitalized construction cost into the lot/project. The credit-side (cash, AP, accrued) lives in a different feed not included here.

## Key facts

- Rows: 83,433 (BCPD only, 2018-2025).
- Account codes: 1535 (Permits & Fees), 1540 (Direct Construction), 1547 (Direct Construction-Lot).
- Total $346.5M one-sided.
- Project + lot fill: 100% (1,306 distinct (project, lot) pairs).
- Phase fill: 0% — phase is NOT in VF; derive from inventory + Lot Data + decoder.
- Use the 3-tuple (project, phase, lot) join key for any per-lot cost rollup.

## Evidence / source files

- `scratch/gl_financials_findings.md`
- `data/reports/guardrail_check_v0.md`
- `output/state_quality_report_v2_1_bcpd.md`

## Confidence

High confidence on both the row counts and the one-sided structural interpretation. VF is the canonical lot-level cost basis for BCPD 2018-2025.

## Caveats

- One-sided: do not expect debit = credit.
- Phase column is empty — must come from inventory or decoder.

## Safe questions this chunk grounds

- Where does BCPD's 2018-2025 cost basis come from?
- Why is VF described as 'one-sided'?
- What account codes does VF cover?

## Questions to refuse or caveat

- What is the VF debit-credit balance? — REFUSE: VF is one-sided by design; not a trial balance.
- Aggregate VF and QB register together for 2025 BCPD? — REFUSE: zero account-code overlap; would double-count.
