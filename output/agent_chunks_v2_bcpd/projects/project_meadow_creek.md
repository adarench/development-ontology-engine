---
chunk_id: project_meadow_creek
chunk_type: project
title: Project: Meadow Creek
project: Meadow Creek
source_files:
  - output/operating_state_v2_1_bcpd.json
  - output/state_quality_report_v2_1_bcpd.md
  - data/reports/join_coverage_v0.md
  - data/reports/join_coverage_simulation_v1.md
state_version: v2.1
confidence: medium
last_generated: 2026-05-04
allowed_uses:
  - RAG retrieval for project-specific Q&A about BCPD scope
  - Grounding facts for an LLM agent answering business questions
caveats:
  - See state_quality_report_v2_1_bcpd.md for project-specific quality notes.
---

## Plain-English summary

Meadow Creek is collateral-only in v2.1 — present in Vertical Financials and the Collateral Report but not enumerated in 2025Status. VF code MCreek (7,418 rows / $50.3M) but no row in 2025Status — collateral-only project. Range rows: 1,416 / $14.96M (largest range-row project).

## Key facts

- Active 2025Status lot count: 0.
- Total canonical lots in body: 60.
- Phase count in body: 2.
- VF 2018-2025 cost total: $50,330,176 (lot-grain $35,374,320; range/shell $14,955,856; commercial $0; SR-inferred-unknown $0).

## Evidence / source files

- `output/operating_state_v2_1_bcpd.json`
- `output/state_quality_report_v2_1_bcpd.md`
- `data/reports/join_coverage_v0.md`
- `data/reports/join_coverage_simulation_v1.md`

## Confidence

Mixed confidence: some facts are high (lot counts, presence flags) while cost rollups carry `inferred` or `medium` labels per their source.

## Caveats

- No project-specific caveats beyond the BCPD-wide guardrail set.

## Safe questions this chunk grounds

- How many active lots does Meadow Creek have in inventory?
- What is the v2.1 status of Meadow Creek (active / no GL / decoder-derived / etc.)?
- What is Meadow Creek's VF cost basis 2018-2025?
- What share of Meadow Creek's cost is at lot grain vs project+phase grain?

## Questions to refuse or caveat

- Provide org-wide cost including Meadow Creek? — REFUSE: org-wide v2 is blocked.
