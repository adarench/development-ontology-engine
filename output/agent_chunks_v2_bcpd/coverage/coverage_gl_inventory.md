---
chunk_id: coverage_gl_inventory
chunk_type: coverage
title: Coverage: GL ↔ inventory join
project: n/a
source_files:
  - data/reports/join_coverage_v0.md
  - data/reports/join_coverage_simulation_v1.md
  - output/state_quality_report_v2_1_bcpd.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for coverage / fill-rate questions
caveats:
  - Coverage metric is binary (≥1 GL row per inventory lot); does not imply cost completeness.
---

## Plain-English summary

Of the 1,285 high-confidence BCPD inventory lots in v2.1, **864 (67.2%) have ≥1 GL row** (was 810 / 63.0% in v0). The +54 lift comes from the AultF B→B1 correction reaching 11 previously-missed Parkway B1 lots, plus HarmCo residential MF2 matches once alpha lots were preserved in the validation index.

## Key facts

- v0 baseline: 810 / 1,285 inventory lots had ≥1 GL row (63.0%).
- v2.1 simulated: 864 / 1,285 (67.2%) — delta +54 lots / +4.2pp.
- Per-project: Salem Fields 100%, Willowcreek 100%, Scarlet Ridge 90.9%, Parkway Fields 78.0% (was 61.5%), Arrowhead Springs 65.0%, Harmony 53.7%, Lomond Heights 43.9%, Lewis Estates 0%.
- 8 BCPD projects have 0% GL coverage (Lewis Estates + 7 active no-GL projects).

## Evidence / source files

- `data/reports/join_coverage_v0.md`
- `data/reports/join_coverage_simulation_v1.md`
- `output/state_quality_report_v2_1_bcpd.md`

## Confidence

The coverage numbers are directly counted from staged data; high confidence. Forward-looking projections are deferred to W3 outputs.

## Caveats

- Binary coverage metric; not cost completeness.
- Lewis Estates and 7 active projects are structural 0% gaps.

## Safe questions this chunk grounds

- What fraction of BCPD inventory lots have GL coverage?
- Which projects are at 100% GL match? Which at 0%?
- Did the AultF B→B1 correction change GL coverage?

## Questions to refuse or caveat

- What is the GL coverage for Hillcrest? — REFUSE: org-wide v2 is blocked; Hillcrest not in scope.
- Does GL coverage = cost completeness? — CAVEAT: no, coverage is binary; missing-cost-not-zero rule still applies.
