# Owner Update — BCPD Operating State (v2.1)

## Scope (honest)

- v2.1 covers **BCPD entities only** (BCPD, BCPBL, ASD, BCPI). Hillcrest and Flagship Belmont GL data ends 2017-02 — those entities are NOT in v2.1.
- **Org-wide v2 is NOT ready.** It needs three new GL streams — Hillcrest, Flagship Belmont, and a back-fill of the 2017-03 → 2018-06 data gap — before any consolidated view is possible.
- Within scope: 5366 canonical lots across 26 projects, joined across inventory + GL + ClickUp.

## What v2.1 fixed (dollar magnitudes)

- **$6,750,000** Harmony double-count avoided by enforcing the (project, phase, lot) 3-tuple join.
- **$6,553,893** un-inflated from Scarlet Ridge — SctLot rows now live under a separate canonical project (Scattered Lots).
- **$4,006,662** AultF B-suffix rows re-routed to phase B1 (was B2 in v2.0).
- **$45,752,047** in range/shell GL rows surfaced explicitly at project+phase grain (no silent lot-level allocation).

## The real bottleneck (and why eng can't unblock it)

Per-lot decoder rules ship as **inferred**, not **validated**. Promotion to validated requires source-owner sign-off — not engineering work. Open items live in `output/bcpd_data_gap_audit_for_streamline_session.md`.

## What can be answered today (honestly)

- Per-lot cost basis at the (project, phase, lot) 3-tuple, with inferred caveat.
- Per-phase cost roll-ups, but only **3 of 125 phases currently have complete enough expected-cost data to support reliable variance / margin reporting**. The remaining 122 phases have partial or missing budgets.
- Range/shell totals at project+phase grain (not lot grain).

## What CANNOT be answered today (refuse these)

- Org-wide rollups across Hillcrest / Flagship Belmont.
- Lot-level allocation of range/shell rows (no method sign-off).
- 'Is the per-lot decoder cost validated?' — NO. It is inferred.

## Retrieval evidence

- **Caveats** — `output/bcpd_state_qa_examples.md`
- **Confidence** — `output/agent_chunks_v2_bcpd/guardrails/guardrail_bcpd_only.md`
- **1. Entity catalog (with actual sources and BCPD instance counts)** — `docs/ontology_v0.md`
- **Operating State v2.1 — BCPD Agent Context** — `output/agent_context_v2_1_bcpd.md`
