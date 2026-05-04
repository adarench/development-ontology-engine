---
chunk_id: project_parkway_fields
chunk_type: project
title: Project: Parkway Fields
project: Parkway Fields
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
  - AultF SR-suffix (0139SR / 0140SR; 401 rows) is inferred-unknown.
  - AultF B-suffix routes to B1 (corrected in v2.1; was B2 in v2.0).
---

## Plain-English summary

Parkway Fields carries decoder-derived per-lot VF cost in v2.1. VF codes split: PWFS2 4-digit (D1/D2/G1/G2) + 5-digit B-suffix (B2). PWFT1 4-digit (C1/C2). AultF 5-digit suffix routing — A → A1/A2.x, **B → B1** (corrected in v2.1; v2.0 routed to B2 wrong by $4.0M / 1,499 rows). AultF SR-suffix (0139SR/0140SR; 401 rows / ~$1.2M) inferred-unknown. All decoder rules ship `confidence='inferred'` and `validated_by_source_owner=False`.

## Key facts

- Active 2025Status lot count: 918.
- Total canonical lots in body: 1131.
- Phase count in body: 20.
- VF 2018-2025 cost total: $145,385,255 (lot-grain $129,007,157; range/shell $15,194,238; commercial $0; SR-inferred-unknown $1,183,859).
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
- AultF SR-suffix (0139SR / 0140SR; 401 rows) is inferred-unknown.
- AultF B-suffix routes to B1 (corrected in v2.1; was B2 in v2.0).

## Safe questions this chunk grounds

- How many active lots does Parkway Fields have in inventory?
- What is the v2.1 status of Parkway Fields (active / no GL / decoder-derived / etc.)?
- What is Parkway Fields's VF cost basis 2018-2025?
- What share of Parkway Fields's cost is at lot grain vs project+phase grain?
- What did the AultF B-suffix correction in v2.1 fix?

## Questions to refuse or caveat

- Is Parkway Fields's decoder-derived per-lot cost source-owner-validated? — REFUSE: no, all rules ship `inferred`.
- Provide org-wide cost including Parkway Fields? — REFUSE: org-wide v2 is blocked.
