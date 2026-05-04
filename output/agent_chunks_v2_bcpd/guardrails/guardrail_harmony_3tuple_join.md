---
chunk_id: guardrail_harmony_3tuple_join
chunk_type: guardrail
title: Guardrail: Harmony joins require project + phase + lot
project: n/a
source_files:
  - scratch/vf_decoder_gl_finance_review.md
  - data/reports/v2_0_to_v2_1_change_log.md
  - docs/bcpd_operating_state_architecture.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for refusal / caveat decisions
  - Anchor for any answer that touches this guardrail's scope
caveats:
  - Rule applies project-wide; Harmony is the visible case.
---

## Plain-English summary

In Harmony, lot numbers 101–116 exist in two distinct phases — MF1 (multi-family) and B1 (single-family). They are different physical assets. A flat (project, lot) join collapses them onto one inventory row, producing a $6.75M attribution error. v2.1 enforces the 3-tuple (canonical_project, canonical_phase, canonical_lot_number).

## Key facts

- Harmony MF1 lots 101-116 are townhomes; B1 lots 101-116 are single-family.
- VF Harm3 (rows for 0101-0116): 1,733 rows / $5.35M (correctly B1 via lot-range routing).
- VF HarmTo (rows for 0001-0116): 53 rows / $1.40M for lots 101-116 (correctly MF1).
- Flat-join error: $443K wrongly attributed to one inventory row, $99K dropped.
- Project-wide error if flat-join: ~$6.75M.
- v2.1 implementation: every lot's vf_actual_cost_3tuple_usd is computed at the 3-tuple.

## Evidence / source files

- `scratch/vf_decoder_gl_finance_review.md`
- `data/reports/v2_0_to_v2_1_change_log.md`
- `docs/bcpd_operating_state_architecture.md`

## Confidence

High confidence on the data evidence; both Harm3 and HarmTo carry rows for the same lot strings.

## Caveats

- Rule applies project-wide; Harmony is the visible case.

## Safe questions this chunk grounds

- Why does Harmony need the 3-tuple join?
- What's the double-count risk on a flat (project, lot) join?
- Does the 3-tuple rule apply only to Harmony?

## Questions to refuse or caveat

- Use a flat (project, lot) join for Harmony cost? — REFUSE: $6.75M error risk.
- Roll Harmony cost without phase? — REFUSE: phase is part of the canonical key.
