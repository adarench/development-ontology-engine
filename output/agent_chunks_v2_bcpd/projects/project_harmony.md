---
chunk_id: project_harmony
chunk_type: project
title: Project: Harmony
project: Harmony
source_files:
  - output/operating_state_v2_1_bcpd.json
  - output/state_quality_report_v2_1_bcpd.md
  - data/reports/vf_lot_code_decoder_v1_report.md
  - data/staged/vf_lot_code_decoder_v1.csv
  - data/reports/join_coverage_v0.md
  - data/reports/join_coverage_simulation_v1.md
state_version: v2.1
confidence: inferred
last_generated: 2026-05-04
allowed_uses:
  - RAG retrieval for project-specific Q&A about BCPD scope
  - Grounding facts for an LLM agent answering business questions
  - Citing per-project cost with explicit `inferred` confidence label
caveats:
  - Per-lot cost is `inferred` (decoder-derived; not source-owner-validated).
  - Range / shell rows for this project, if any, are kept at project+phase grain via `vf_unattributed_shell_dollars` — not allocated to specific lots.
  - Harmony joins MUST use the 3-tuple (project, phase, lot). Flat (project, lot) doublecounts $6.75M (MF1 lot 101 ≠ B1 lot 101).
  - HarmCo X-X commercial parcels are NOT residential lots; tracked under `commercial_parcels_non_lot`.
---

## Plain-English summary

Harmony carries decoder-derived per-lot VF cost in v2.1. VF code Harm3 (9,234 rows) routes to Harmony phases via lot-range decoding (B1, B2, B3, A4.1, A7-A10, ADB13/14, MF1). HarmCo splits into MF2 residential (169 rows) and X-X commercial parcels (205 rows; non-lot). HarmTo townhomes (1,587 single-lot rows + 568 range rows). Joins MUST use the (project, phase, lot) 3-tuple — flat (project, lot) doublecounts $6.75M because MF1 lot 101 ≠ B1 lot 101. All decoder rules ship `confidence='inferred'` and `validated_by_source_owner=False`.

## Key facts

- Active 2025Status lot count: 612.
- Total canonical lots in body: 773.
- Phase count in body: 18.
- VF 2018-2025 cost total: $53,599,350 (lot-grain $45,461,449; range/shell $5,507,682; commercial $2,630,219; SR-inferred-unknown $0).
- ClickUp lot-tagged tasks present for this project.
- Per-lot VF cost is decoder-derived; cite `confidence='inferred'` when reporting.

## Evidence / source files

- `output/operating_state_v2_1_bcpd.json`
- `output/state_quality_report_v2_1_bcpd.md`
- `data/reports/vf_lot_code_decoder_v1_report.md`
- `data/staged/vf_lot_code_decoder_v1.csv`
- `data/reports/join_coverage_v0.md`
- `data/reports/join_coverage_simulation_v1.md`

## Confidence

Decoder-derived per-lot cost ships with `confidence='inferred'` and `validated_by_source_owner=False`. The mapping rules are evidence-backed but not source-owner-validated. Per-project totals from VF and DR are high-confidence in their source schema; what's inferred is the decomposition into specific (phase, lot) triples.

## Caveats

- Per-lot cost is `inferred` (decoder-derived; not source-owner-validated).
- Range / shell rows for this project, if any, are kept at project+phase grain via `vf_unattributed_shell_dollars` — not allocated to specific lots.
- Harmony joins MUST use the 3-tuple (project, phase, lot). Flat (project, lot) doublecounts $6.75M (MF1 lot 101 ≠ B1 lot 101).
- HarmCo X-X commercial parcels are NOT residential lots; tracked under `commercial_parcels_non_lot`.

## Safe questions this chunk grounds

- How many active lots does Harmony have in inventory?
- What is the v2.1 status of Harmony (active / no GL / decoder-derived / etc.)?
- What is Harmony's VF cost basis 2018-2025?
- What share of Harmony's cost is at lot grain vs project+phase grain?
- Why must Harmony cost queries use the 3-tuple join key?

## Questions to refuse or caveat

- Is Harmony's decoder-derived per-lot cost source-owner-validated? — REFUSE: no, all rules ship `inferred`.
- Provide org-wide cost including Harmony? — REFUSE: org-wide v2 is blocked.
