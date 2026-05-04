---
chunk_id: guardrail_commercial_not_residential
chunk_type: guardrail
title: Guardrail: Commercial parcels are not residential lots
project: n/a
source_files:
  - scratch/vf_decoder_ops_allocation_review.md
  - data/reports/vf_lot_code_decoder_v1_report.md
  - output/operating_state_v2_1_bcpd.json
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for refusal / caveat decisions
  - Anchor for any answer that touches this guardrail's scope
caveats:
  - Tracked separately so they're visible but not double-counted into residential.
---

## Plain-English summary

The 11 HarmCo X-X parcels (`0000A-A` through `0000K-K`, 205 rows / ~$2.6M) are commercial parcels in the Harmony master plan. They have no row in inventory, Lot Data, 2025Status, or any allocation workbook. v2.1 tracks them under `commercial_parcels_non_lot` per project. They are NOT modeled as residential LotState and must NOT be rolled into residential lot totals.

## Key facts

- Commercial parcels: 11 X-X strings (A-A, B-B, …, K-K).
- Total rows: 205 (~55% of HarmCo's 374 rows).
- Pads A-A and B-B dominate (active vertical construction); C-K are placeholder.
- Account distribution: 88.5% Direct Construction.
- Future ontology: needs a `CommercialParcel` entity (deferred to v0.2).

## Evidence / source files

- `scratch/vf_decoder_ops_allocation_review.md`
- `data/reports/vf_lot_code_decoder_v1_report.md`
- `output/operating_state_v2_1_bcpd.json`

## Confidence

High confidence on the non-lot treatment; ontology decision (CommercialParcel?) is deferred.

## Caveats

- Tracked separately so they're visible but not double-counted into residential.

## Safe questions this chunk grounds

- Where do HarmCo X-X commercial parcels live in v2.1?
- Why aren't they in residential LotState?
- What ontology decision is pending?

## Questions to refuse or caveat

- Roll commercial parcel cost into Harmony residential lot totals? — REFUSE.
- Treat HarmCo X-X as Harmony LotState rows? — REFUSE.
