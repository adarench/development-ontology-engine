---
chunk_id: project_arrowhead_springs
chunk_type: project
title: Project: Arrowhead Springs
project: Arrowhead Springs
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
---

## Plain-English summary

Arrowhead Springs carries decoder-derived per-lot VF cost in v2.1. VF codes ArroS1/ArroT1 routed to phases 123 / 456 by lot range. All decoder rules ship `confidence='inferred'` and `validated_by_source_owner=False`.

## Key facts

- Active 2025Status lot count: 224.
- Total canonical lots in body: 422.
- Phase count in body: 20.
- VF 2018-2025 cost total: $24,211,128 (lot-grain $24,207,836; range/shell $3,292; commercial $0; SR-inferred-unknown $0).
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

## Safe questions this chunk grounds

- How many active lots does Arrowhead Springs have in inventory?
- What is the v2.1 status of Arrowhead Springs (active / no GL / decoder-derived / etc.)?
- What is Arrowhead Springs's VF cost basis 2018-2025?
- What share of Arrowhead Springs's cost is at lot grain vs project+phase grain?

## Questions to refuse or caveat

- Is Arrowhead Springs's decoder-derived per-lot cost source-owner-validated? — REFUSE: no, all rules ship `inferred`.
- Provide org-wide cost including Arrowhead Springs? — REFUSE: org-wide v2 is blocked.
