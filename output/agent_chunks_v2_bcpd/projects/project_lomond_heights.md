---
chunk_id: project_lomond_heights
chunk_type: project
title: Project: Lomond Heights
project: Lomond Heights
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

Lomond Heights carries decoder-derived per-lot VF cost in v2.1. LomHS1 (SFR 101-171) + LomHT1 (TH 172-215). Single phase 2A; product-type split lives at lot grain via Lot Data ProdType. Allocation workbook: LH 2025.10. All decoder rules ship `confidence='inferred'` and `validated_by_source_owner=False`.

## Key facts

- Active 2025Status lot count: 414.
- Total canonical lots in body: 527.
- Phase count in body: 9.
- VF 2018-2025 cost total: $2,445,715 (lot-grain $1,880,049; range/shell $565,666; commercial $0; SR-inferred-unknown $0).
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

- How many active lots does Lomond Heights have in inventory?
- What is the v2.1 status of Lomond Heights (active / no GL / decoder-derived / etc.)?
- What is Lomond Heights's VF cost basis 2018-2025?
- What share of Lomond Heights's cost is at lot grain vs project+phase grain?

## Questions to refuse or caveat

- Is Lomond Heights's decoder-derived per-lot cost source-owner-validated? — REFUSE: no, all rules ship `inferred`.
- Provide org-wide cost including Lomond Heights? — REFUSE: org-wide v2 is blocked.
