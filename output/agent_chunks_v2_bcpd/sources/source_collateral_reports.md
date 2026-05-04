---
chunk_id: source_collateral_reports
chunk_type: source_family
title: Source family: Collateral Reports
project: n/a
source_files:
  - scratch/ops_inventory_collateral_allocation_findings.md
  - data/staged/ops_inventory_collateral_validation_report.md
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

`Collateral Dec2025 - Collateral Report.csv` and `PriorCR.csv` — phase-level borrowing-base snapshots. as_of 2025-12-31 (current) and 2025-06-30 (prior). Covers 9 of 16 active BCPD projects (the actively-pledged universe).

## Key facts

- Rows: 41 phase entries per snapshot.
- Coverage: 9 BCPD projects (Arrowhead Springs, Dry Creek, Harmony, Lomond Heights, Meadow Creek, Parkway Fields, Salem Fields, Scarlet Ridge, Willowcreek).
- Missing from collateral: 7 active BCPD projects + Lewis Estates (not pledged).
- Fields: lot count, total lot value, advance %, loan $, total dev cost, remaining dev cost.
- Sibling files: 2025Status (per-lot status), Lot Data (lifecycle dates), IA Breakdown, RBA-TNW.

## Evidence / source files

- `scratch/ops_inventory_collateral_allocation_findings.md`
- `data/staged/ops_inventory_collateral_validation_report.md`

## Confidence

Confidence: high. Counts and field profiles are derived directly from staged data.

## Caveats



## Safe questions this chunk grounds

- What does the Collateral Report cover?
- Which BCPD projects are pledged collateral?
- What's the 6-month delta between current and prior snapshots?

## Questions to refuse or caveat

- Provide collateral data for Lewis Estates? — REFUSE: not in pledged universe.
- Trend collateral over time? — CAVEAT: only 2 snapshots available.
