---
chunk_id: coverage_clickup_inventory
chunk_type: coverage
title: Coverage: ClickUp lot-tagged ↔ inventory
project: n/a
source_files:
  - data/reports/join_coverage_v0.md
  - output/state_quality_report_v2_1_bcpd.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for ClickUp coverage and lot-tagging questions
caveats:
  - Lot-tagging discipline is the upstream gate; only 21% of ClickUp tasks have both subdivision and lot_num.
---

## Plain-English summary

ClickUp coverage is unchanged between v2.0 and v2.1: 1,177 lot-tagged tasks (filtered from 5,509 total), covering 1,091 distinct (project, lot) pairs across 9 BCPD communities. 811 of 1,285 high-confidence inventory lots (63.1%) have ≥1 lot-tagged task.

## Key facts

- Total ClickUp tasks: 5,509. Lot-tagged subset (subdivision + lot_num both populated): 1,177.
- Distinct (project, lot) pairs in lot-tagged subset: 1,091.
- Inventory match: 811 / 1,285 high-confidence inventory lots (63.1%).
- Phase fill within lot-tagged subset: 92.86% (much higher than 19.86% across the full file).
- Subdivision typo crosswalk applied: Aarowhead → Arrowhead Springs, Scarlett Ridge → Scarlet Ridge, Park Way → Parkway Fields, etc.
- Arrowhead-173 outlier (75 tasks on one lot) flagged but not removed.

## Evidence / source files

- `data/reports/join_coverage_v0.md`
- `output/state_quality_report_v2_1_bcpd.md`
- `data/reports/staged_clickup_validation_report.md`

## Confidence

Counts derived directly from staged_clickup_tasks.parquet; high confidence on the totals. The 21% lot-tagging rate is an operational/process gate, not a data defect.

## Caveats

- 79% of ClickUp tasks lack subdivision/lot_num and are excluded from lot matching.
- Arrowhead lot 173 has 75 tasks (likely template parent); flagged.

## Safe questions this chunk grounds

- How many ClickUp tasks are lot-tagged in BCPD scope?
- Which subdivisions are in scope for ClickUp lot-tagged matching?
- What's the ClickUp coverage of inventory lots?

## Questions to refuse or caveat

- What is the ClickUp progress for a lot not in the lot-tagged subset? — REFUSE: 79% of tasks are not lot-tagged; do not extrapolate.
- Does ClickUp coverage equal active-construction coverage? — CAVEAT: no; ClickUp is a per-lot signal where present.
