# Finance / Land / Ops Review — 30-Minute Agenda
**Scope: BCPD only** (entities BCPD/BCPBL/ASD/BCPI). Hillcrest and Flagship Belmont are out of scope; their GL coverage ends 2017-02 — org-wide v2 is NOT available.

## Why this meeting

Promote `inferred` decoder cost to `validated` for v2.2, and decide the allocation method for range/shell rows. The bottleneck is **source-owner sign-off**, not engineering.

## Dollar gates (anchor the meeting around these)

- Range / shell allocation: **$45,752,047** pending method sign-off.
- AultF B-suffix routing: **$4,006,662** decoder rule to validate.
- Harmony 3-tuple discipline: **$6,750,000** double-count avoided.
- SctLot → Scattered Lots: **$6,553,893** un-inflated; canonical name pending.
- AultF SR-suffix: **$1,183,859** held inferred-unknown.

## Finance / GL — asks

- DR 38-col phase recovery — is there a source-system attribute we missed for pre-2018 lots?

## Land / Development — asks

- Harm3 lot-range routing — confirm phase is recoverable only via lot range, no source-system attribute we missed.
- AultF SR-suffix meaning ('0139SR', '0140SR'; 401 rows / 2 lots).
- AultF B-suffix overlap 201-211 — confirm B1 max lot.
- MF1 vs B1 overlap 101-116 — sample 5-10 Harm3 rows in this range to confirm they are SFR/B1, not MF1 leakage.
- SctLot canonical name and program identity (currently 'Scattered Lots').
- Range-entry allocation method (equal split vs sales-weighted vs unit-fixed) before per-lot expansion.
- HarmCo X-X commercial parcels — which allocation source covers Harmony commercial? (Currently outside Flagship Allocation Workbook.)

## Ops / ClickUp — asks

- (Standing item) ClickUp lot tagging is sparse — only ~21% of active lots are tagged. Decide if better tagging is owned by ops or by the data team.

## Decisions needed by end of meeting

1. Range/shell allocation method (equal split, sales-weighted, or fixed proportional) — finance + land.
2. Canonical name for SctLot ('Scattered Lots' or other) — land.
3. AultF B-suffix decoder validation — finance / GL.
4. HarmCo commercial parcels: kept isolated as commercial entity or rolled into a separate commercial state? — land.

## Retrieval evidence

- **Additional documented decisions (per integrator instructions)** — `data/reports/guardrail_check_v0.md`
- **Caveats** — `output/bcpd_state_qa_examples.md`
- **Caveats** — `output/agent_chunks_v2_bcpd/guardrails/guardrail_sctlot_scattered_lots.md`
- **Caveats** — `output/agent_chunks_v2_bcpd/cost_sources/cost_source_range_shell_rows.md`
- **Tier 3 — Defer or block on source-owner validation** — `data/reports/coverage_improvement_opportunities.md`
