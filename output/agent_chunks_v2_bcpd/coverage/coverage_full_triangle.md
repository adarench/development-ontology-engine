---
chunk_id: coverage_full_triangle
chunk_type: coverage
title: Coverage: Full triangle (GL ∧ ClickUp ∧ inventory)
project: n/a
source_files:
  - data/reports/join_coverage_v0.md
  - data/reports/join_coverage_simulation_v1.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for full-triangle coverage questions
caveats:
  - Triangle requires all three data sources; missing any one drops a lot from the count.
---

## Plain-English summary

Full triangle = inventory lots that have ≥1 GL row AND ≥1 ClickUp lot-tagged task. v0 baseline: 476 / 1,285 (37.0%). v2.1: 478 / 1,285 (37.2%, +2 lots). On the active-only subset (n=965), triangle is 49.2% in v2.1.

## Key facts

- v0 baseline triangle: 476 lots (37.0%).
- v2.1 triangle: 478 lots (37.2%) — modest delta.
- Active-only subset triangle: ~49% (965 active lots).
- Per-project triangle: Willowcreek 100%, Salem Fields 87.8%, Scarlet Ridge 59.1%, Lomond Heights 43.0%, Harmony 35.0%, Parkway Fields 23.7%, Arrowhead Springs 9.7%.

## Evidence / source files

- `data/reports/join_coverage_v0.md`
- `data/reports/join_coverage_simulation_v1.md`

## Confidence

High confidence on the binary count; the modest v2.1 delta is honest — v2.1's correctness wins are on dollars, not on lot-binary coverage.

## Caveats

- Lot-tagging discipline gates ClickUp side; structural no-GL gates the GL side.

## Safe questions this chunk grounds

- What is the BCPD full triangle coverage?
- Which projects have the highest full-triangle coverage?
- Why didn't v2.1's correctness fixes increase the triangle much?

## Questions to refuse or caveat

- Is full triangle coverage the right metric for cost completeness? — CAVEAT: no; binary triangle says nothing about cost amounts.
