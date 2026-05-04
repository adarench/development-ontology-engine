---
chunk_id: guardrail_sctlot_scattered_lots
chunk_type: guardrail
title: Guardrail: SctLot is Scattered Lots, not Scarlet Ridge
project: n/a
source_files:
  - scratch/vf_decoder_gl_finance_review.md
  - data/reports/v2_0_to_v2_1_change_log.md
  - output/operating_state_v2_1_bcpd.json
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for refusal / caveat decisions
  - Anchor for any answer that touches this guardrail's scope
caveats:
  - Canonical name not source-owner-validated.
  - Lot 0639 is an outlier; specifically inferred-unknown.
---

## Plain-English summary

In v2.0, 1,130 SctLot rows / $6.55M were silently attributed to Scarlet Ridge (inflating Scarlet Ridge's project-grain cost by ~46%). v2.1 introduces a separate canonical project 'Scattered Lots' to hold these rows. Confidence stays inferred-unknown (canonical name pending source-owner confirmation).

## Key facts

- SctLot rows: 1,130 across 6 distinct lot strings (0001, 0002, 0003, 0008, 0029, 0639).
- SctLot dollars: $6,553,893 — moved off Scarlet Ridge in v2.1.
- Evidence: zero lot-number overlap with ScaRdg (101-152); 'SctLot' appears as accounting bucket in invoice IDs.
- Vendor mix: custom-build / scattered-construction trades (Bob Craghead Plumbing, etc.).
- v2.1 canonical_project: 'Scattered Lots' (working name).
- Project-grain only — no lot-level inventory feed exists.

## Evidence / source files

- `scratch/vf_decoder_gl_finance_review.md`
- `data/reports/v2_0_to_v2_1_change_log.md`
- `output/operating_state_v2_1_bcpd.json`

## Confidence

Medium-high confidence on disjointness from Scarlet Ridge. Inferred-unknown on the canonical name.

## Caveats

- Canonical name not source-owner-validated.
- Lot 0639 is an outlier; specifically inferred-unknown.

## Safe questions this chunk grounds

- What is SctLot in v2.1?
- Why is SctLot not Scarlet Ridge?
- What was the v2.0 misattribution?

## Questions to refuse or caveat

- Report SctLot dollars under Scarlet Ridge in v2.1? — REFUSE: violates v2.1 separation.
- Provide lot-level cost for Scattered Lots? — REFUSE: project-grain only.
