---
chunk_id: guardrail_bcpd_only
chunk_type: guardrail
title: Guardrail: BCPD-only scope
project: n/a
source_files:
  - output/agent_context_v2_1_bcpd.md
  - output/operating_state_v2_1_bcpd.json
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for refusal / caveat decisions
  - Anchor for any answer that touches this guardrail's scope
caveats:
  - Track B (org-wide) is a roadmap item; not v2.1.
---

## Plain-English summary

v2.1 covers BCPD (Building Construction Partners) and its horizontal-developer affiliates BCPBL, ASD, BCPI. It does NOT cover Hillcrest, Flagship Belmont, Lennar, or external customers. Org-wide is explicitly out of scope.

## Key facts

- In scope: BCPD, BCPBL (Ben Lomond), ASD (Arrowhead Springs Developer), BCPI (BCP Investor).
- Out of scope: Hillcrest Road at Saratoga LLC, Flagship Belmont Phase two LLC, Lennar, EXT/EXT-Comm/Church.
- GL filter: entity_name = 'Building Construction Partners, LLC'.
- 2025Status / Lot Data filter: HorzCustomer = 'BCP'.

## Evidence / source files

- `output/agent_context_v2_1_bcpd.md`
- `output/operating_state_v2_1_bcpd.json`

## Confidence

High confidence; BCPD-only is the canonical scope of v2.1.

## Caveats

- Track B (org-wide) is a roadmap item; not v2.1.

## Safe questions this chunk grounds

- What does BCPD include in v2.1?
- Are the horizontal developers in scope?
- Is Lennar in BCPD's scope?

## Questions to refuse or caveat

- Provide cost for Hillcrest? — REFUSE: out of v2.1 scope.
- Aggregate across all entities? — REFUSE: not org-wide.
