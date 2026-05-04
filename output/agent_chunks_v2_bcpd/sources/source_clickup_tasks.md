---
chunk_id: source_clickup_tasks
chunk_type: source_family
title: Source family: ClickUp Tasks
project: n/a
source_files:
  - data/reports/staged_clickup_validation_report.md
  - scratch/ops_inventory_collateral_allocation_findings.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for source-system questions
  - Anchor for any answer that cites this source family
caveats:
  - See state_quality_report_v2_1_bcpd.md for per-field detail.
---

## Plain-English summary

`staged_clickup_tasks` — 5,509 total tasks; lot-tagged subset of 1,177. Used as a per-lot signal (status, due_date, actual_c_of_o) where present. Phase fill within the lot-tagged subset is 92.86% (vs 19.86% across the full file).

## Key facts

- Total rows: 5,509.
- Lot-tagged subset (subdivision + lot_num both populated): 1,177.
- Distinct (project, lot) in lot-tagged: 1,091.
- Subdivision crosswalk: 11 mappings including typos (Aarowhead, Aarrowhead, Scarlett Ridge).
- Date-field coverage uplift in lot-tagged vs full file: 3-5x (e.g., actual_c_of_o 22.77% vs 4.88%).
- Arrowhead-173 outlier (75 tasks on one lot) flagged.

## Evidence / source files

- `data/reports/staged_clickup_validation_report.md`
- `scratch/ops_inventory_collateral_allocation_findings.md`

## Confidence

Confidence: high. Counts and field profiles are derived directly from staged data.

## Caveats



## Safe questions this chunk grounds

- What ClickUp data is in scope?
- What's the lot-tagging discipline?
- Which subdivision typos are crosswalked?

## Questions to refuse or caveat

- Extrapolate ClickUp signals to non-lot-tagged tasks? — REFUSE: 79% are not lot-tagged.
- Use ClickUp as the canonical source for any cost? — REFUSE: progress only.
