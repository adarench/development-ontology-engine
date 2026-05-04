---
chunk_id: project_salem_fields
chunk_type: project
title: Project: Salem Fields
project: Salem Fields
source_files:
  - output/operating_state_v2_1_bcpd.json
  - output/state_quality_report_v2_1_bcpd.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG retrieval for project-specific Q&A about BCPD scope
  - Grounding facts for an LLM agent answering business questions
caveats:
  - See state_quality_report_v2_1_bcpd.md for project-specific quality notes.
---

## Plain-English summary

Salem Fields reaches the v2.1 lot grain without needing the v1 decoder. VF codes SalemS / SaleTR / SaleTT — already at 100% inventory match in v0; no decoder needed. Range rows: ~776 across SaleTR + SaleTT.

## Key facts

- Active 2025Status lot count: 338.
- Total canonical lots in body: 349.
- Phase count in body: 4.
- VF 2018-2025 cost total: $45,472,837 (lot-grain $36,807,028; range/shell $8,665,810; commercial $0; SR-inferred-unknown $0).
- ClickUp lot-tagged tasks present for this project.

## Evidence / source files

- `output/operating_state_v2_1_bcpd.json`
- `output/state_quality_report_v2_1_bcpd.md`

## Confidence

Project lot-grain join was already at 100% (or near) in v0 without the decoder; v2.1 changes do not affect this project's matching. Per-project totals are high-confidence.

## Caveats

- No project-specific caveats beyond the BCPD-wide guardrail set.

## Safe questions this chunk grounds

- How many active lots does Salem Fields have in inventory?
- What is the v2.1 status of Salem Fields (active / no GL / decoder-derived / etc.)?
- What is Salem Fields's VF cost basis 2018-2025?
- What share of Salem Fields's cost is at lot grain vs project+phase grain?

## Questions to refuse or caveat

- Provide org-wide cost including Salem Fields? — REFUSE: org-wide v2 is blocked.
