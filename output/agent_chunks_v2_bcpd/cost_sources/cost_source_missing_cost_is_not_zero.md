---
chunk_id: cost_source_missing_cost_is_not_zero
chunk_type: cost_source
title: Cost source: Missing cost is missing, not zero
project: n/a
source_files:
  - output/agent_context_v2_1_bcpd.md
  - output/state_quality_report_v2_1_bcpd.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for refusal of cost-estimation queries on no-GL projects
caveats:
  - Hard rule; never violated.
---

## Plain-English summary

A project or lot with no GL row has cost = **unknown** (null in the JSON), never $0. Reporting $0 would falsely imply the project incurred no cost when in reality the cost is simply not in the available source. v2.1 enforces this rule across all rollups: 8 BCPD projects (Lewis Estates + 7 active no-GL projects) carry inventory but have null cost fields, not zero.

## Key facts

- Affected projects: Lewis Estates, Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge.
- Total unknown-cost lots: ~105 across these 9 projects.
- DR 38-col gap (2017-03 → 2018-06): 15 months of zero rows for any entity — also 'unknown', not zero.
- Hillcrest + Flagship Belmont post-2017-02: blocked org-wide; cost unknown for v2.1 scope.

## Evidence / source files

- `output/agent_context_v2_1_bcpd.md`
- `output/state_quality_report_v2_1_bcpd.md`

## Confidence

High confidence; hard rule enforced at the agent layer.

## Caveats

- Never substitute zero; never infer from siblings.

## Safe questions this chunk grounds

- What does 'missing cost' mean in v2.1?
- How does v2.1 distinguish unknown from zero?
- Which BCPD projects have unknown cost?

## Questions to refuse or caveat

- Substitute $0 for missing cost? — REFUSE: violates the missing-cost-is-not-zero rule.
- Estimate Lewis Estates' cost from sibling projects? — REFUSE: structural gap; do not infer.
