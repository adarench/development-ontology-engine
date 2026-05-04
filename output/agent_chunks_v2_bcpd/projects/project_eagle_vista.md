---
chunk_id: project_eagle_vista
chunk_type: project
title: Project: Eagle Vista
project: Eagle Vista
source_files:
  - output/operating_state_v2_1_bcpd.json
  - output/state_quality_report_v2_1_bcpd.md
  - data/reports/join_coverage_v0.md
  - data/reports/join_coverage_simulation_v1.md
state_version: v2.1
confidence: low
last_generated: 2026-05-04
allowed_uses:
  - RAG retrieval for project-specific Q&A about BCPD scope
  - Grounding facts for an LLM agent answering business questions
  - Refusing cost-estimation queries on this project
caveats:
  - Cost is unknown for this project; do not infer from sibling projects.
---

## Plain-English summary

Eagle Vista is an active BCPD project with inventory rows but **no GL coverage**. There are 5 active 2025Status lots; no Vertical Financials rows, no DataRails 38-col rows after the canonical filter, and no Collateral Report row. This is a structural gap, not a v2.1 defect — the cost is **unknown**, not zero. 5 active 2025Status lots; no GL coverage. Cost unknown.

## Key facts

- Active 2025Status lot count: 5.
- Total canonical lots in body: 5.
- Phase count in body: 5.
- **Cost is unknown, not zero.** No GL row exists for this project; do not estimate.

## Evidence / source files

- `output/operating_state_v2_1_bcpd.json`
- `output/state_quality_report_v2_1_bcpd.md`
- `data/reports/join_coverage_v0.md`
- `data/reports/join_coverage_simulation_v1.md`

## Confidence

Confidence is low because no GL data exists. Inventory facts (lot count, status) are high-confidence; cost is **unknown**. Do not substitute zero for unknown cost.

## Caveats

- Cost is unknown for this project; do not infer from sibling projects.

## Safe questions this chunk grounds

- How many active lots does Eagle Vista have in inventory?
- What is the v2.1 status of Eagle Vista (active / no GL / decoder-derived / etc.)?

## Questions to refuse or caveat

- What is Eagle Vista's actual cost? — REFUSE: no GL data; cost is unknown, not zero.
- What is the cost-per-lot for Eagle Vista? — REFUSE: cannot compute without GL.
- Provide org-wide cost including Eagle Vista? — REFUSE: org-wide v2 is blocked.
