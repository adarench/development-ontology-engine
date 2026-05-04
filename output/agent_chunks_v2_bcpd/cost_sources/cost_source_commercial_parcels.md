---
chunk_id: cost_source_commercial_parcels
chunk_type: cost_source
title: Cost source: HarmCo commercial parcels (non-lot inventory)
project: Harmony
source_files:
  - scratch/vf_decoder_ops_allocation_review.md
  - data/reports/vf_lot_code_decoder_v1_report.md
  - output/operating_state_v2_1_bcpd.json
state_version: v2.1
confidence: inferred
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for Harmony commercial-parcel questions
caveats:
  - Commercial parcels are NOT residential lots; not in LotState.
---

## Plain-English summary

HarmCo carries 31 distinct lot strings. v2.1 splits them: 20 residential lots `0000A01`–`0000B10` map to Harmony phase MF2 at the lot grain (169 rows). The remaining 11 commercial parcels `0000A-A` through `0000K-K` are **non-lot inventory** — they have no row in Lot Data, 2025Status, inventory closing report, or any allocation workbook. v2.1 tracks them under `commercial_parcels_non_lot` per project. They are NOT modeled as residential LotState.

## Key facts

- Commercial parcels: 11 X-X strings (A-A through K-K), 205 rows total.
- Dollar volume: ~$2.6M across all commercial parcels in HarmCo.
- Concentration: pads A-A (106 rows) and B-B (80 rows) dominate; pads C-K are 1-3 rows each.
- Account distribution: 88.5% Direct Construction (real building activity, not just allocation).
- Not in any allocation workbook (Flagship Allocation Workbook v3 has no Harmony Commercial entry).
- Future ontology entity (`CommercialParcel`?) deferred to v0.2.

## Evidence / source files

- `scratch/vf_decoder_ops_allocation_review.md`
- `data/reports/vf_lot_code_decoder_v1_report.md`
- `output/operating_state_v2_1_bcpd.json`

## Confidence

Inferred (decoder-derived split). Strong evidence the X-X parcels are commercial: VF code name, no residential Lot Data match, A-K letter sequencing.

## Caveats

- 205 rows kept out of residential LotState by design.
- Ontology decision pending.

## Safe questions this chunk grounds

- What are the HarmCo X-X parcels?
- Why aren't commercial parcels in Harmony's LotState?
- How much commercial parcel cost is in Harmony?

## Questions to refuse or caveat

- Add HarmCo commercial dollars to Harmony's residential lot rollup? — REFUSE: violates non-lot inventory rule.
- Show Harmony residential cost including commercial pads? — REFUSE: commercial pads are not residential.
