---
chunk_id: coverage_source_owner_validation_queue
chunk_type: coverage
title: Coverage: Source-owner validation queue
project: n/a
source_files:
  - output/operating_state_v2_1_bcpd.json
  - scratch/vf_decoder_gl_finance_review.md
  - scratch/vf_decoder_ops_allocation_review.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for 'what's still inferred' questions
caveats:
  - Items here gate confidence promotion from `inferred` to higher.
---

## Plain-English summary

v2.1 ships with 8 open source-owner questions. Each gates promotion of a corresponding decoder/mapping rule from `confidence='inferred'` to higher. v2.1 is internally consistent without any of them being resolved; promotion to 'high' / 'validated' requires sign-off.

## Key facts

- Q1 — Harm3 lot-range routing: confirm phase is recoverable only via lot range.
- Q2 — AultF SR-suffix meaning (0139SR, 0140SR; 401 rows / 2 lots).
- Q3 — AultF B-suffix range: confirm B1 max lot = 211.
- Q4 — MF1 vs B1 overlap 101-116: sample audit for SFR/B1 leakage.
- Q5 — SctLot canonical name and program identity ('Scattered Lots' is working name).
- Q6 — Range-entry allocation method (equal split / sales-weighted / unit-fixed).
- Q7 — HarmCo X-X commercial parcels: ontology entity and allocation source.
- Q8 — DR 38-col phase recovery: any source-system attribute we missed?

## Evidence / source files

- `output/operating_state_v2_1_bcpd.json`
- `scratch/vf_decoder_gl_finance_review.md`
- `scratch/vf_decoder_ops_allocation_review.md`

## Confidence

High confidence that these are the open items; the JSON's `source_owner_questions_open` array is the canonical list.

## Caveats

- Until each is resolved, the corresponding rule stays `inferred`.

## Safe questions this chunk grounds

- What still needs source-owner validation in v2.1?
- When can the v1 VF decoder rules be promoted from inferred?
- What's blocking v2.2's range-row per-lot expansion?

## Questions to refuse or caveat

- Promote a rule to source-owner-validated without sign-off? — REFUSE: explicit human sign-off required.
