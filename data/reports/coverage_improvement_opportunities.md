# Coverage Improvement Opportunities (W3 — recommendations)

**Built**: 2026-05-01
**Author**: Terminal A
**Companion**: `data/reports/join_coverage_simulation_v1.md`, `data/staged/high_impact_join_fixes.csv`

This document ranks the candidate fixes by impact-per-effort and gives a clear go/no-go recommendation for each. The numbers come from the W3 simulation.

---

## Headline lift

- **GL coverage**: v0 63.0% → v1 66.6% (delta +3.6pp; +46 lots)
- **Triangle coverage**: v0 37.0% → v1 37.2% (delta +0.2pp; +2 lots)
- **GL VF rows newly attached at lot grain**: 44,244 (vs v0 flat-2-tuple match counts)
- **GL VF dollars newly attached at lot grain**: $154,977,943
- **Range rows isolated from lot denominator**: 1,746 rows (~$45.75M kept at project+phase grain)
- **Commercial parcels isolated**: 205 rows
- **SctLot moved off Scarlet Ridge**: 1,130 rows / ~$6.55M no longer inflating Scarlet Ridge

---

## Ranked recommendations

### Tier 1 — Apply for v2.1 simulation (no source-owner sign-off needed beyond `inferred`)

1. **Apply v1 VF decoder with 3-tuple join key** (largest single lift). Coverage moves from baseline to substantially higher; GL VF rows attach to specific (project, phase, lot) triples for the first time. Effort: M.
2. **Apply AultF B→B1 correction** ($4M routed correctly). Already in v1. Effort: S.
3. **Apply SctLot → 'Scattered Lots'** ($6.55M no longer inflates Scarlet Ridge). Already in v1. Effort: S.
4. **Apply HarmCo split** (residential MF2 vs commercial X-X non-lot). Already in v1. Effort: S.
5. **Surface range rows at project+phase grain** ($45.75M unattributed-shell dollars surfaced explicitly in the quality report). Already in v1. Effort: S.

### Tier 2 — Already-resolved or low marginal value

6. **Inventory phase normalization** (`2-A`→`2A`, etc.). Already in v1 decoder via PHASE_INV_TO_LD. Effort: S.
7. **ClickUp subdivision typo cleanup**. Already in v0 crosswalk. Effort: S.

### Tier 3 — Defer or block on source-owner validation

8. **Range-row per-lot expansion** — would attach $45.75M to specific lots. Requires allocation-method sign-off (equal split vs sales-weighted vs fixed). DEFER until source-owner input. Effort: M after sign-off.
9. **AultF SR-suffix routing** — 401 rows / 2 lots. Source owner must explain semantics. DEFER. Effort: S after sign-off.
10. **HarmCo X-X commercial parcels ontology** — 205 rows. Requires a `CommercialParcel` entity type or similar in the ontology. DEFER for v0.2. Effort: M.
11. **SctLot inventory feed** — 1,130 rows / $6.55M. Needs a separate scattered-lots inventory source. DEFER until data lands. Effort: L (data acquisition).
12. **DR 38-col phase recovery** — 0% phase fill in source. Investigate source-system attributes. DEFER. Effort: M.
13. **Lewis Estates and 7 no-GL projects** — structural gap; cannot be fixed by transformation. DEFER until fresh GL pull. Effort: blocked.
14. **Org-wide v2 (Hillcrest, Flagship Belmont)** — same. DEFER. Effort: blocked.

---

## Recommendation summary table

| fix | effort | confidence | apply for v2.1? | needs source-owner? |
|---|---|---|---|---|
| v1 VF decoder + 3-tuple join | M | high | **YES** | no for v2.1; yes before high confidence |
| AultF B→B1 correction | S | high | **YES** | no |
| SctLot → 'Scattered Lots' | S | medium-high | **YES** | yes for canonical name promotion |
| HarmCo split | S | high | **YES** | yes for ontology entity decision |
| Range rows at project+phase grain | S | high | **YES** | yes for per-lot expansion |
| Inventory phase normalization | S | high | already applied | no |
| Range row per-lot expansion | M | medium | NO | yes |
| AultF SR routing | S | low | NO | yes |
| HarmCo X-X ontology | M | medium | NO | yes |
| SctLot inventory feed | L | n/a (data) | NO | yes (data acquisition) |
| DR 38-col phase recovery | M | low | NO | yes |
| 7 no-GL projects + Lewis Estates | — | — | NO | yes (data acquisition) |
| Org-wide v2 | — | — | NO | yes (data acquisition) |

---

## Should BCPD v2.1 be rebuilt now or wait for validation?

**Recommendation: rebuild v2.1 now with Tier 1 fixes applied as `inferred`. Hold higher confidence and Tier 3 fixes for source-owner validation.**

Rationale:

- Tier 1 fixes are evidence-backed and reversible; v2.1 ships with `confidence='inferred'` so consumers know the rules are not source-owner-validated.
- The current v2 has known correctness defects (AultF $4M misroute, SctLot $6.55M inflation, range rows polluting lot denominator). v2.1 is strictly more accurate even before validation.
- The 3-tuple join requirement (Terminal B Q3) is a silent correctness defect in v2 — a flat (project, lot) join would double-count $6.75M on Harmony alone. v2.1 fixes this.
- Tier 3 items are real issues but can be addressed in v0.3 / v2.2 once the source owner has time to weigh in.

