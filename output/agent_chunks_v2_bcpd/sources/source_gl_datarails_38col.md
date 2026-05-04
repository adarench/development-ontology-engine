---
chunk_id: source_gl_datarails_38col
chunk_type: source_family
title: Source family: DataRails 38-col (GL DR 38-col)
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

BCPD GL extracts for 2016-02 → 2017-02 across 14 monthly CSV files. **2.16× row-multiplied at source** — every posting line appears 2-3 times consecutively. Build pipeline deduplicates before any cost rollup; raw v2 parquet preserved unchanged.

## Key facts

- Raw rows (BCPD): 111,497.
- Post-dedup: 51,694 (multiplicity 2.16×).
- Lot fill (BCPD): 49.5%; phase fill: 0%.
- Dedup key: 9 financial+narrative fields; canonical row picks max non-null metadata.
- Source schema in v2: source_schema='datarails_38col'.

## Evidence / source files

- `scratch/gl_financials_findings.md`
- `data/staged/staged_gl_transactions_v2_validation_report.md`

## Confidence

Confidence: high. Counts and field profiles are derived directly from staged data.

## Caveats



## Safe questions this chunk grounds

- Why is DR 38-col deduplicated?
- What's DR's coverage window?
- Can we get phase from DR?

## Questions to refuse or caveat

- Sum DR amounts directly from raw parquet? — REFUSE: 2.16× off.
- Get Harmony cost from DR? — REFUSE: Harmony is post-2018; not in DR.
