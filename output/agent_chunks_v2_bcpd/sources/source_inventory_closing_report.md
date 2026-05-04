---
chunk_id: source_inventory_closing_report
chunk_type: source_family
title: Source family: Inventory Closing Report
project: n/a
source_files:
  - data/staged/staged_inventory_lots.parquet
  - data/reports/staged_inventory_lots_validation_report.md
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

Excel workbook (`Inventory _ Closing Report (2).xlsx`) carrying per-lot inventory snapshots. Two main sheets: `INVENTORY` (header=0; 978 active lots) and `CLOSED ` (header=1; 2,894 closed/projected lots). v2.1 uses workbook (2) deliberately — freshest static data; lane doc claim that (4) is canonical was contradicted by the data.

## Key facts

- Total staged rows: 3,872 (978 ACTIVE + 1,760 CLOSED + 1,134 ACTIVE_PROJECTED).
- as_of_date: 2026-04-29 (data-derived from max INVENTORY.SALE DATE).
- 9 high-confidence active subdivs + ~25 historical communities (CLOSED tab).
- Forward-fill required for vertically-merged subdiv labels.
- Volatile `=TODAY()-SaleDate` columns dropped at stage time.

## Evidence / source files

- `data/staged/staged_inventory_lots.parquet`
- `data/reports/staged_inventory_lots_validation_report.md`
- `scratch/ops_inventory_collateral_allocation_findings.md`

## Confidence

Confidence: high. Counts and field profiles are derived directly from staged data.

## Caveats



## Safe questions this chunk grounds

- What's the as-of date of v2.1 inventory?
- How many active vs closed lots are in inventory?
- Why was workbook (2) chosen over (4)?

## Questions to refuse or caveat

- Provide inventory state as of a different as_of_date? — REFUSE: stage is fixed at 2026-04-29.
- Treat ACTIVE_PROJECTED as actually CLOSED? — REFUSE: forward-projected dates only.
