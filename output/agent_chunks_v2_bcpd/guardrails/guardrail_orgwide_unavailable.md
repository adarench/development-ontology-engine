---
chunk_id: guardrail_orgwide_unavailable
chunk_type: guardrail
title: Guardrail: Org-wide v2 is unavailable
project: n/a
source_files:
  - scratch/bcpd_financial_readiness.md
  - data/reports/guardrail_check_v0.md
  - output/agent_context_v2_1_bcpd.md
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for refusal / caveat decisions
  - Anchor for any answer that touches this guardrail's scope
caveats:
  - Track B remains a roadmap track.
---

## Plain-English summary

Hillcrest Road at Saratoga LLC and Flagship Belmont Phase two LLC have GL rows only through 2017-02. Publishing an org-wide rollup today would mix 2024-2025 BCPD activity against 2017-frozen non-BCPD entities — misleading regardless of labeling. The unblocking artifact is a fresh GL pull for those entities covering 2017-03 onward.

## Key facts

- Hillcrest GL rows: 12,093 (all in 2016-01 → 2017-02).
- Flagship Belmont GL rows: 495 (all in 2016-04 → 2017-02).
- Dump-wide gap 2017-03 → 2018-06: zero rows for any entity (~15 months).
- v2.1 refuses org-wide questions explicitly via Q7 in the Q&A harness.

## Evidence / source files

- `scratch/bcpd_financial_readiness.md`
- `data/reports/guardrail_check_v0.md`
- `output/agent_context_v2_1_bcpd.md`

## Confidence

High confidence on the structural gap. Refusal is the right default until fresh data lands.

## Caveats

- Track B remains a roadmap track.

## Safe questions this chunk grounds

- Why is org-wide v2 blocked?
- What would unblock org-wide v2?
- Does Hillcrest have any post-2017-02 GL?

## Questions to refuse or caveat

- Roll up actuals across BCPD + Hillcrest + Flagship Belmont? — REFUSE: blocked.
- Estimate non-BCPD post-2017 cost? — REFUSE: do not infer.
