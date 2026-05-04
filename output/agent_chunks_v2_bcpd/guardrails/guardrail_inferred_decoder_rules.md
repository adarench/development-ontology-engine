---
chunk_id: guardrail_inferred_decoder_rules
chunk_type: guardrail
title: Guardrail: Decoder-derived mappings are inferred
project: n/a
source_files:
  - data/reports/vf_lot_code_decoder_v1_report.md
  - data/staged/vf_lot_code_decoder_v1.csv
  - output/agent_context_v2_1_bcpd.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for refusal / caveat decisions
  - Anchor for any answer that touches this guardrail's scope
caveats:
  - Inferred ≠ low quality; just unvalidated.
---

## Plain-English summary

Every rule in the v1 VF lot-code decoder ships `confidence='inferred'` and `validated_by_source_owner=False`. v2.1 is strictly more accurate than v2.0 even at inferred confidence — the rules are evidence-backed, not blessed. Promotion requires explicit source-owner sign-off.

## Key facts

- Decoder rules cover: Harm3, HarmCo (split), HarmTo, LomHS1, LomHT1, PWFS2, PWFT1, AultF, ArroS1, ArroT1, ScaRdg, SctLot.
- Match rate against Lot Data: 93.9% across 65,958 in-scope VF rows.
- Confidence label: 'inferred' for all 12 rules.
- Source-owner questions open: 8 (see source_owner_validation_queue chunk).

## Evidence / source files

- `data/reports/vf_lot_code_decoder_v1_report.md`
- `data/staged/vf_lot_code_decoder_v1.csv`
- `output/agent_context_v2_1_bcpd.md`

## Confidence

High confidence on the rule itself; inferred on the mapping outputs.

## Caveats

- Inferred ≠ low quality; just unvalidated.

## Safe questions this chunk grounds

- Are v2.1's decoder rules source-owner-validated?
- What confidence level do decoder-derived per-lot costs carry?
- Why is per-lot cost labeled inferred?

## Questions to refuse or caveat

- Promote a decoder rule from inferred without sign-off? — REFUSE.
- Cite per-lot cost without the inferred label? — CAVEAT: always include the confidence.
