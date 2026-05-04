---
chunk_id: source_gl_vertical_financials
chunk_type: source_family
title: Source family: Vertical Financials (GL VF 46-col)
project: n/a
source_files:
  - scratch/gl_financials_findings.md
  - data/reports/staged_gl_validation_report.md
  - data/staged/staged_gl_transactions_v2_validation_report.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for source-system questions
  - Anchor for any answer that cites this source family
caveats:
  - See state_quality_report_v2_1_bcpd.md for per-field detail.
---

## Plain-English summary

BCPD lot-level cost basis 2018-2025. Filtered to a 3-account-code asset-side slice (1535/1540/1547). One-sided — NOT a balanced trial-balance.

## Key facts

- Rows: 83,433 BCPD-only.
- Cost basis total: $346.5M (one-sided).
- Project + lot fill: 100%; phase fill: 0% (no phase column).
- 1,306 distinct (project, lot) pairs.
- Source schema in v2: source_schema='vertical_financials_46col'.

## Evidence / source files

- `scratch/gl_financials_findings.md`
- `data/reports/staged_gl_validation_report.md`
- `data/staged/staged_gl_transactions_v2_validation_report.md`

## Confidence

Confidence: high. Counts and field profiles are derived directly from staged data.

## Caveats



## Safe questions this chunk grounds

- What does VF cover?
- What account codes are in VF?
- Is VF balanced?

## Questions to refuse or caveat

- Treat VF as a balanced trial balance? — REFUSE.
- Aggregate VF + QB Register? — REFUSE: zero account-code overlap.
