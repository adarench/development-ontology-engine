---
chunk_id: coverage_no_gl_projects
chunk_type: coverage
title: Coverage: BCPD projects with inventory but no GL
project: n/a
source_files:
  - output/state_quality_report_v2_1_bcpd.md
  - output/operating_state_v2_1_bcpd.json
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for missing-cost / structural-gap questions
caveats:
  - Cost is unknown for these projects; do not substitute zero.
---

## Plain-English summary

Eight BCPD-scope projects have inventory rows but **no GL coverage**. They appear in 2025Status (and in some cases inventory + Lot Data) but have zero VF or DR rows after the BCPD canonical filter, and no Collateral Report row. Cost is unknown — not zero — for these projects. This is a structural gap that requires new data, not a v2.1 defect.

## Key facts

- Lewis Estates: 34 lots, no GL, no Collateral row, no allocation workbook.
- Ammon: 16 lots, no GL.
- Erda: 14 lots, no GL.
- Ironton: 12 lots, no GL.
- Cedar Glen: 10 lots, no GL.
- Eastbridge: 6 lots, no GL.
- Westbridge: 6 lots, no GL.
- Eagle Vista: 5 lots, no GL.
- Santaquin Estates: 2 lots, no GL.

## Evidence / source files

- `output/state_quality_report_v2_1_bcpd.md`
- `output/operating_state_v2_1_bcpd.json`
- `data/reports/coverage_improvement_opportunities.md`

## Confidence

High confidence that these projects have zero GL coverage; this is observed directly from staged_gl_transactions_v2.parquet. The fix requires new source data.

## Caveats

- Cost = unknown; never substitute zero.
- Ammon, Erda may also appear in DR-era IA Breakdown but project-grain only.

## Safe questions this chunk grounds

- Which BCPD projects have no GL coverage?
- Why is Lewis Estates' cost unknown?
- What does it take to fix the no-GL gap?

## Questions to refuse or caveat

- What is Ammon's actual cost? — REFUSE: cost is unknown, not zero.
- Estimate Lewis Estates' cost from sibling projects? — REFUSE: do not infer; structural gap.
