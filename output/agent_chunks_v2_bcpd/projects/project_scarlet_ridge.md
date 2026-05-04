---
chunk_id: project_scarlet_ridge
chunk_type: project
title: Project: Scarlet Ridge
project: Scarlet Ridge
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
  - Do NOT report SctLot rows under Scarlet Ridge — they live under 'Scattered Lots' in v2.1.
---

## Plain-English summary

Scarlet Ridge carries decoder-derived per-lot VF cost in v2.1. VF code ScaRdg routed to phases 1/2/3 by lot range. SctLot is **NOT** Scarlet Ridge — moved to canonical project 'Scattered Lots' in v2.1 (was silently inflating Scarlet Ridge by $6.55M in v2.0). All decoder rules ship `confidence='inferred'` and `validated_by_source_owner=False`.

## Key facts

- Active 2025Status lot count: 147.
- Total canonical lots in body: 155.
- Phase count in body: 3.
- VF 2018-2025 cost total: $14,121,562 (lot-grain $14,121,562; range/shell $0; commercial $0; SR-inferred-unknown $0).
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
- Do NOT report SctLot rows under Scarlet Ridge — they live under 'Scattered Lots' in v2.1.

## Safe questions this chunk grounds

- How many active lots does Scarlet Ridge have in inventory?
- What is the v2.1 status of Scarlet Ridge (active / no GL / decoder-derived / etc.)?
- What is Scarlet Ridge's VF cost basis 2018-2025?
- What share of Scarlet Ridge's cost is at lot grain vs project+phase grain?

## Questions to refuse or caveat

- What is Scarlet Ridge's total cost including SctLot? — CAVEAT: SctLot dollars belong to 'Scattered Lots' in v2.1, not Scarlet Ridge.
- Is Scarlet Ridge's decoder-derived per-lot cost source-owner-validated? — REFUSE: no, all rules ship `inferred`.
- Provide org-wide cost including Scarlet Ridge? — REFUSE: org-wide v2 is blocked.
