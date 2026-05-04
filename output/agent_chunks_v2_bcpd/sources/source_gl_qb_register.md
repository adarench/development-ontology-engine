---
chunk_id: source_gl_qb_register
chunk_type: source_family
title: Source family: QuickBooks Register (GL QB 12-col)
project: n/a
source_files:
  - scratch/gl_financials_findings.md
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

2,922 BCPD 2025 rows from QuickBooks. Different chart of accounts (177 codes) — tie-out only. Vendor field is the only place vendor names live (95.7% fill, 161 distinct vendors).

## Key facts

- Rows: 2,922 BCPD 2025-only.
- Account codes: 177 distinct (e.g. 132-XXX, 510-XXX, 210-100).
- Account-code overlap with VF/DR: zero.
- Vendor fill: 95.7%.
- Project / lot / phase fill: 0%.
- Treatment: tie-out only; never aggregate against VF/DR.

## Evidence / source files

- `scratch/gl_financials_findings.md`
- `data/staged/staged_gl_transactions_v2_validation_report.md`

## Confidence

Confidence: high. Counts and field profiles are derived directly from staged data.

## Caveats



## Safe questions this chunk grounds

- What is QB Register used for?
- Where do BCPD vendor names come from?

## Questions to refuse or caveat

- Per-lot cost from QB? — REFUSE: no lot field.
- Aggregate QB + VF for 2025? — REFUSE: would double-count.
