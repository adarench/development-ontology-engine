---
chunk_id: source_allocation_workbooks
chunk_type: source_family
title: Source family: Allocation workbooks
project: n/a
source_files:
  - scratch/ops_inventory_collateral_allocation_findings.md
  - data/staged/ops_inventory_collateral_validation_report.md
state_version: v2.1
confidence: medium
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for source-system questions
  - Anchor for any answer that cites this source family
caveats:
  - Allocation expansion is gated on populating Flagship workbook or wiring OfferMaster fallback.
---

## Plain-English summary

Per-project budget data. Lomond Heights (LH Allocation 2025.10) and Parkway Fields (Parkway Allocation 2025.10) have populated per-phase × prod_type rows. The Flagship Allocation Workbook v3 covers 8 communities but most cells are empty in the current snapshot.

## Key facts

- Lomond Heights LH.csv: 12 phase × prod_type rows (already in v1).
- Parkway Fields PF.csv: 14 phase × prod_type rows (already in v1).
- Flagship Allocation Workbook v3: 67 (community, phase) pairs framework — most cells $0.
- Dehart Underwriting (Summary).csv: not stageable as-is; deferred.

## Evidence / source files

- `scratch/ops_inventory_collateral_allocation_findings.md`
- `data/staged/ops_inventory_collateral_validation_report.md`

## Confidence

Confidence: medium. Counts and field profiles are derived directly from staged data.

## Caveats

- Allocation expansion is gated on populating Flagship workbook or wiring OfferMaster fallback.

## Safe questions this chunk grounds

- Where do BCPD budgets come from?
- Which projects have populated allocation workbooks?
- What's the Flagship Allocation Workbook v3 status?

## Questions to refuse or caveat

- Provide budget for Harmony from allocation? — REFUSE: workbook framework exists but cells are empty.
- Treat Dehart underwriting as a stageable allocation source? — REFUSE: not in scope.
