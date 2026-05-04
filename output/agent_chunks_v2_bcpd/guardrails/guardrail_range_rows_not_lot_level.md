---
chunk_id: guardrail_range_rows_not_lot_level
chunk_type: guardrail
title: Guardrail: Range / shell rows are not lot-level cost
project: n/a
source_files:
  - data/reports/vf_lot_code_decoder_v1_report.md
  - scratch/vf_decoder_gl_finance_review.md
  - output/operating_state_v2_1_bcpd.json
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for refusal / caveat decisions
  - Anchor for any answer that touches this guardrail's scope
caveats:
  - $45.75M is ~13% of BCPD VF cost basis; surface separately in any total.
---

## Plain-English summary

$45.75M / 4,020 rows of range-form GL postings (e.g. '3001-06') are kept at project+phase grain via vf_unattributed_shell_dollars per phase. They are shared-shell or shared-infrastructure costs that genuinely span multiple lots and have not been allocated. Per-lot expansion is a v2.2 candidate that requires source-owner sign-off on the allocation method.

## Key facts

- Range rows: 4,020 / $45.75M across 8 VF codes.
- Surfaced per-phase as `vf_unattributed_shell_dollars` and `vf_unattributed_shell_rows`.
- Most affected: PWFT1 ($15.19M), MCreek ($14.96M), HarmTo ($5.51M).
- Memo evidence: 'shell allocation' is the most common memo on these rows.
- v2.1 explicitly does NOT allocate to specific lots.

## Evidence / source files

- `data/reports/vf_lot_code_decoder_v1_report.md`
- `scratch/vf_decoder_gl_finance_review.md`
- `output/operating_state_v2_1_bcpd.json`

## Confidence

High confidence on the interpretation; inferred on per-lot allocation method (deferred to v2.2).

## Caveats

- $45.75M is ~13% of BCPD VF cost basis; surface separately in any total.

## Safe questions this chunk grounds

- How are range / shell rows treated in v2.1?
- Why are they not allocated to specific lots?
- What allocation methods are candidates for v2.2?

## Questions to refuse or caveat

- Allocate range dollars to specific lots in v2.1? — REFUSE: pending allocation-method sign-off.
- Add range dollars to per-lot vf_actual_cost_3tuple_usd? — REFUSE: explicitly excluded.
