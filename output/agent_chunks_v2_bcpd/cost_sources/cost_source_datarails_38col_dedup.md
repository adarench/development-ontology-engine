---
chunk_id: cost_source_datarails_38col_dedup
chunk_type: cost_source
title: Cost source: DataRails 38-col (BCPD 2016-17 — dedup mandatory)
project: n/a
source_files:
  - scratch/gl_financials_findings.md
  - data/staged/staged_gl_transactions_v2_validation_report.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for BCPD 2016-17 cost questions
caveats:
  - Raw DR sums are wrong by ~2x without dedup.
---

## Plain-English summary

DataRails 38-col is the BCPD cost source for 2016-02 through 2017-02. **DR is 2.16× row-multiplied at the source** — every posting line appears 2-3 times consecutively with identical financial fields and slightly different metadata bits. Any naive sum is wrong by ~2×. The build pipeline deduplicates on a 9-field canonical key before any cost rollup.

## Key facts

- Raw rows (BCPD): 111,497 across 14 monthly extracts.
- Post-dedup rows: 51,694 (multiplicity 2.16×).
- Dedup key: (entity_name, posting_date, account_code, amount, project_code, lot, memo_1, description, batch_description).
- Pick canonical row preferring most non-null metadata (account_name + account_type both populated).
- Post-dedup balance: debit ≈ credit ≈ $330.9M (within 0.15%).
- Lot fill in DR (BCPD): 49.5% (vs 100% in VF).
- Phase fill in DR: 0% (project-grain only for cost rollups).

## Evidence / source files

- `scratch/gl_financials_findings.md`
- `data/staged/staged_gl_transactions_v2_validation_report.md`

## Confidence

High confidence that dedup is required and that the 9-field key recovers a balanced two-sided journal. The build pipeline applies this automatically.

## Caveats

- Raw v2 parquet is preserved unchanged; dedup happens at query time.
- DR has no Harmony, Parkway Fields, or other post-2018 projects.

## Safe questions this chunk grounds

- Why does DataRails 38-col need deduplication?
- What's the dedup key for DR 38-col?
- What's BCPD's 2016-17 cost from DR after dedup?

## Questions to refuse or caveat

- Sum DR amounts directly from raw v2.parquet? — REFUSE: 2.16× off without dedup.
- Roll DR cost up to phase grain? — REFUSE: phase is 0% filled in DR.
