---
chunk_id: cost_source_range_shell_rows
chunk_type: cost_source
title: Cost source: Range / shell rows (project+phase grain)
project: n/a
source_files:
  - data/reports/vf_lot_code_decoder_v1_report.md
  - scratch/vf_decoder_gl_finance_review.md
  - output/operating_state_v2_1_bcpd.json
state_version: v2.1
confidence: inferred
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for shared-shell / shared-infrastructure cost questions
caveats:
  - Range rows are NEVER allocated to specific lots in v2.1.
---

## Plain-English summary

Range-form GL rows (lot strings like '3001-06', '0009-12', '0172-175') are summary postings that span multiple lots — typically shared-shell or shared-infrastructure costs. v2.1 keeps them at the **project+phase grain** via `vf_unattributed_shell_dollars` per phase, totaling **4,020 rows / $45,752,047** across 8 VF codes. They are NOT allocated to specific lots.

## Key facts

- Range rows total: 4,020 across 8 VF codes (HarmTo, LomHT1, PWFT1, ArroT1, MCreek, SaleTT, SaleTR, WilCrk).
- Range dollars total: $45,752,047 (~13% of BCPD VF cost basis).
- Largest contributor: MCreek (1,416 rows / $14.96M) followed by PWFT1 (1,114 / $15.19M).
- Memo evidence: 'shell allocation', design/engineering vendors, shared-infra accounts.
- Per-row dollar magnitude: median $3,304, mean $11,381 — real cost line items.
- v2.2 candidate: per-lot expansion (equal split / sales-weighted / unit-fixed) — needs source-owner sign-off.

## Evidence / source files

- `data/reports/vf_lot_code_decoder_v1_report.md`
- `scratch/vf_decoder_gl_finance_review.md`
- `output/operating_state_v2_1_bcpd.json`

## Confidence

High confidence on the interpretation (memo + magnitude evidence). Inferred on the specific allocation method for any future per-lot expansion.

## Caveats

- $45.75M not at lot grain in v2.1.
- Per-lot expansion deferred until source-owner sign-off.

## Safe questions this chunk grounds

- How are range-form GL rows treated in v2.1?
- What is `vf_unattributed_shell_dollars`?
- Why aren't range rows expanded to per-lot in v2.1?

## Questions to refuse or caveat

- Allocate the $45.75M of range cost to specific lots? — REFUSE: requires allocation-method sign-off.
- Drop range rows entirely? — REFUSE: they are real cost; project+phase rollup needs them.
- Add range dollars to per-lot vf_actual_cost_3tuple_usd? — REFUSE: explicitly excluded by design.
