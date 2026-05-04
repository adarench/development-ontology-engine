---
chunk_id: cost_source_qb_register_tieout_only
chunk_type: cost_source
title: Cost source: QB Register (tie-out only)
project: n/a
source_files:
  - scratch/gl_financials_findings.md
  - output/state_quality_report_v2_1_bcpd.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for BCPD vendor / cash / AP queries on 2025
caveats:
  - Different chart of accounts; never aggregate against VF/DR.
---

## Plain-English summary

QB Register 12-col carries 2,922 rows for BCPD 2025. It uses a different chart of accounts (177 codes, e.g. 132-XXX, 510-XXX) with **zero account_code overlap to VF or DR**. It is **tie-out only** — never aggregate against VF or DR; would double-count. Use exclusively for 2025 BCPD vendor / cash / AP queries.

## Key facts

- Rows: 2,922 (BCPD 2025 only).
- Account codes: 177 distinct, e.g. 132-XXX (Inventory Asset), 510-XXX, 210-100 (AP).
- Project / lot fill: 0% (no project_code, no lot field).
- Vendor fill: 95.7% (161 distinct vendors); only place vendor lives.
- Account-code overlap with VF/DR: zero.
- Sum: balanced (debit = credit ≈ $215.25M to ten decimal places).

## Evidence / source files

- `scratch/gl_financials_findings.md`
- `output/state_quality_report_v2_1_bcpd.md`

## Confidence

High confidence on the chart-of-accounts disjointness and the tie-out-only directive.

## Caveats

- No project / lot tagging; cannot join to inventory.
- 2025-only; do not extrapolate.

## Safe questions this chunk grounds

- What is QB Register used for in v2.1?
- Why can't we aggregate QB against VF?
- Where do BCPD vendor names come from?

## Questions to refuse or caveat

- Sum QB + VF for 2025 BCPD? — REFUSE: double-counts; different charts.
- Provide vendor analysis for 2024 BCPD? — REFUSE: QB is 2025-only.
- Provide per-lot cost from QB? — REFUSE: no lot field in QB.
