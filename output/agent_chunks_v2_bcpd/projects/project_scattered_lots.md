---
chunk_id: project_scattered_lots
chunk_type: project
title: Project: Scattered Lots
project: Scattered Lots
source_files:
  - output/operating_state_v2_1_bcpd.json
  - output/state_quality_report_v2_1_bcpd.md
  - scratch/vf_decoder_gl_finance_review.md
  - data/reports/v2_0_to_v2_1_change_log.md
state_version: v2.1
confidence: inferred
last_generated: 2026-05-04
allowed_uses:
  - RAG retrieval for project-specific Q&A about BCPD scope
  - Grounding facts for an LLM agent answering business questions
  - Citing per-project cost with explicit `inferred` confidence label
caveats:
  - Project-grain only; no lot-level inventory feed exists.
  - Canonical name not source-owner-validated.
---

## Plain-English summary

Scattered Lots is a v2.1-introduced canonical project. v2.1 NEW canonical project. Carries SctLot rows previously misattributed to Scarlet Ridge in v2.0. Project-grain only — no lot-level inventory feed exists for these scattered/custom lots. Confidence: inferred-unknown (canonical name 'Scattered Lots' is a working name pending source-owner confirmation). In v2.0 these rows silently inflated Scarlet Ridge.

## Key facts

- Active 2025Status lot count: 0.
- Total canonical lots in body: 0.
- Phase count in body: 0.
- VF 2018-2025 cost total: $6,553,893 (lot-grain $0; range/shell $0; commercial $0; SR-inferred-unknown unknown (not zero)).

## Evidence / source files

- `output/operating_state_v2_1_bcpd.json`
- `output/state_quality_report_v2_1_bcpd.md`
- `scratch/vf_decoder_gl_finance_review.md`
- `data/reports/v2_0_to_v2_1_change_log.md`

## Confidence

Decoder-derived per-lot cost ships with `confidence='inferred'` and `validated_by_source_owner=False`. The mapping rules are evidence-backed but not source-owner-validated. Per-project totals from VF and DR are high-confidence in their source schema; what's inferred is the decomposition into specific (phase, lot) triples.

## Caveats

- Project-grain only; no lot-level inventory feed exists.
- Canonical name not source-owner-validated.

## Safe questions this chunk grounds

- How many active lots does Scattered Lots have in inventory?
- What is the v2.1 status of Scattered Lots (active / no GL / decoder-derived / etc.)?
- What is Scattered Lots's VF cost basis 2018-2025?
- What share of Scattered Lots's cost is at lot grain vs project+phase grain?

## Questions to refuse or caveat

- What is the per-lot cost for a Scattered Lots lot? — REFUSE: project-grain only; no lot-level inventory feed.
- Provide org-wide cost including Scattered Lots? — REFUSE: org-wide v2 is blocked.
