# Operating State v2.1 — BCPD Agent Context

_Generated: 2026-05-01_
_Schema: `operating_state_v2_1_bcpd`_
_Supersedes: v2.0 (additive — `output/operating_state_v2_bcpd.json` not modified)_
_Decoder version: `vf_lot_code_decoder_v1` (inferred; not source-owner-validated)_

## What changed from v2.0

v2.1 fixes five known correctness defects in v2.0 by applying the v1 VF lot-code
decoder (per Terminal B + Terminal C reviews). v2.1 is strictly more accurate
than v2.0 even though confidence labels remain `inferred` — the rules are
evidence-backed, not blessed.

| change | impact | confidence |
|---|---|---|
| AultF B-suffix → B1 (was B2) | $4.0M / 1,499 rows correctly routed | inferred (high-evidence) |
| Harmony 3-tuple join discipline enforced | $6.75M double-count prevented | inferred (high-evidence) |
| HarmCo split (residential MF2 vs commercial X-X) | 169 residential matched; 205 commercial isolated | inferred (high on residential) |
| SctLot → 'Scattered Lots' (was Scarlet Ridge) | $6.55M un-inflated from Scarlet Ridge | inferred-unknown (canonical name pending) |
| Range rows kept at project+phase grain | $45.75M / 4,020 rows surfaced as `vf_unattributed_shell_dollars` | inferred (high on interpretation) |

## Hard rules for agent answers

These rules are **enforced**, not optional. An agent that violates them is producing wrong answers.

### Rule 1 — Inferred decoder mappings carry their label

When citing a number derived from the v1 VF decoder, **always include the confidence**: "per VF (inferred decoder, not source-owner-validated), Harmony Phase B1 lot 112 has $X cost."

Decoder rules ship `confidence='inferred'` and `validated_by_source_owner=False`. Do not promote them to "high" or "validated" until a source owner has signed off. The `vf_actual_cost_confidence` field on every lot in `operating_state_v2_1_bcpd.json` reflects this.

### Rule 2 — Range rows are not lot-level cost

The v2.1 state surfaces range-form GL postings (e.g. `'3001-06'`, `'0009-12'`) at the **project+phase** grain via `vf_unattributed_shell_dollars` and `vf_unattributed_shell_rows` per phase. **Do not** attribute these dollars to specific lots — they represent shared-shell or shared-infrastructure costs that genuinely span multiple lots and have not been allocated.

When asked "what is the total cost for lot X?", the answer is `vf_actual_cost_3tuple_usd` for that lot, optionally qualified with the phase-level `vf_unattributed_shell_dollars` ("plus a $X share of phase shell costs that haven't been allocated to specific lots").

Total range exposure across BCPD: **$45.75M / 4,020 rows / 8 VF codes**. Most affected: PWFT1, MCreek, HarmTo, SaleTT, SaleTR.

### Rule 3 — Commercial parcels are not residential lots

The 11 HarmCo X-X parcels (`0000A-A` through `0000K-K`, 205 rows / ~$2.6M) are **commercial parcels in the Harmony master plan**. They have no row in inventory, Lot Data, 2025Status, or any allocation workbook. They are tracked under `commercial_parcels_non_lot` per project in v2.1, not under `phases.lots`.

**Do not** roll commercial parcel cost into residential LotState. **Do not** answer "show me Harmony residential lot costs" by including HarmCo X-X dollars.

### Rule 4 — Harmony joins require project + phase + lot

MF1 lot 101 and B1 lot 101 are **two different physical lots** in Harmony's inventory (a townhome vs a single-family house). They share the lot number 101–116. A flat `(canonical_project, lot)` join collapses them, producing a $6.75M attribution error.

When querying Harmony cost at the lot grain, **always** use `(canonical_project, canonical_phase, canonical_lot_number)` — the 3-tuple. v2.1's `vf_actual_cost_3tuple_usd` is computed this way; do not re-derive cost using a 2-tuple key.

This rule applies generally for v2.1 (not just Harmony). Other projects don't currently have lot-number collisions, but the discipline avoids future surprises.

### Rule 5 — SctLot dollars belong to 'Scattered Lots', not Scarlet Ridge

v2.0 silently attributed 1,130 SctLot rows / $6.55M to Scarlet Ridge, inflating its project-grain cost by ~46%. v2.1 introduces a new canonical project `Scattered Lots` to hold these rows. **Do not** report these dollars under Scarlet Ridge in v2.1 answers. The `Scattered Lots` project is project-grain only — no lot-level inventory feed exists for these scattered/custom-build lots.

## Confidence by question (updated for v2.1)

### High-confidence (corroborated; not decoder-dependent)
- BCPD lot inventory at 2026-04-29 from staged inventory.
- BCPD lot lifecycle stage from Lot Data dates (v1 waterfall).
- BCPD CollateralSnapshot 2025-12-31 for the 9 pledged projects + PriorCR delta.
- BCPD account-level rollups within the legacy chart (DR + VF share it).
- BCPD lot lifecycle dates (HorzPurchase, HorzStart, VertCO, VertSale, VertClose).

### Inferred-but-high-evidence (decoder-derived; not source-owner-validated)
- Per-lot VF cost for **Salem Fields, Willowcreek, Scarlet Ridge** (already 100% / 100% / 90.9% in v0; routing unchanged).
- Per-lot VF cost for **Parkway Fields** lots reachable via PWFS2 4-digit (D1/D2/G1/G2), PWFT1 4-digit (C1/C2), AultF A-suffix (A1/A2.x), and **AultF B-suffix → B1** (corrected in v2.1).
- Per-lot VF cost for **Harmony** lots reachable via Harm3 4-digit lot-range routing, using the **3-tuple join key**.
- Per-lot VF cost for **Lomond Heights** lots in Phase 2A (LomHS1 SFR + LomHT1 TH).
- Per-lot VF cost for **Arrowhead Springs** lots reachable via ArroS1/ArroT1 123/456 routing.
- ClickUp-derived task progress for the 1,091 distinct lot-tagged lots.

### Inferred-unknown (use only with explicit caveats)
- **SctLot rows** under canonical project 'Scattered Lots'. Project-grain only; no inventory match. Canonical name not source-owner-validated.
- **AultF SR-suffix rows** (0139SR, 0140SR; 401 rows / ~$1.2M). Excluded from lot-level cost; meaning unknown.

### Cannot answer (do not invent)
- Org-wide cost (Hillcrest, Flagship Belmont — frozen at 2017-02).
- BCPD spend in 2017-03 → 2018-06 (zero rows).
- Vendor analysis outside 2025 (QB-only / 2025-only).
- Phase-level cost from GL alone (phase column 0% filled across all 3 schemas).
- Per-lot allocation/budget for projects other than Lomond Heights and Parkway Fields.
- Per-lot cost for the 7 active BCPD projects with no GL coverage (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge) and Lewis Estates.
- HarmCo X-X commercial parcel cost at the residential-lot grain.
- Per-lot allocation of range-row dollars (kept at project+phase grain only).

## Citation pattern

When citing a v2.1 number, name **what kind** of number it is:

| number type | cite as |
|---|---|
| Per-lot VF cost (decoder-derived) | "per VF v1 decoder (inferred), Parkway Fields Phase B1 Lot 112: $X across N rows" |
| Per-lot VF cost (no decoder needed; project pre-100%) | "per VF, Salem Fields Phase 2 Lot 218: $X" |
| Per-lot DR cost (2016-17 only) | "per DR 38-col post-dedup (2016-17), Cascade Lot 8: $X (no phase available)" |
| Project-level total | "per VF v2.1 totals, Parkway Fields 2018-2025 cost basis: $X. Includes $Y of unattributed shell costs at project+phase grain." |
| Range/shell cost | "Phase B2 has $X of unattributed shell-allocation cost (range-form GL rows) not yet expanded to specific lots." |
| Commercial parcel | "Harmony has 11 commercial parcels (A-A through K-K) totaling $X. These are non-lot inventory; not residential lot cost." |
| Scattered Lots | "Scattered Lots (formerly attributed to Scarlet Ridge in v2.0) carries $6.55M across 1,130 rows, project-grain only." |

## Hard limits (unchanged from v2.0; restated for clarity)

1. Org-wide is not in scope. Do not aggregate Hillcrest or Flagship Belmont with BCPD.
2. 2017-03 → 2018-06 GL gap. State the gap in any time-series answer that crosses it.
3. DR 38-col dedup is mandatory before summing DR amounts (build pipeline does this).
4. QB register tie-out only; never aggregate against VF without a chart-of-accounts crosswalk.
5. Phase grain is not in GL; derive from inventory + Lot Data + 2025Status + ClickUp.
6. Lot-tagged ClickUp is sparse (~21% of tasks).
7. Inventory file selection is workbook (2); confirm if intent was workbook (4).
8. Allocation coverage is LH + PF only; other projects have no populated workbook.

## Quality artifacts to consult

- **`output/operating_state_v2_1_bcpd.json`** — the v2.1 canonical state document (5MB)
- **`output/state_quality_report_v2_1_bcpd.md`** — per-field fill rate, v2.0→v2.1 deltas, source-owner questions
- **`output/state_query_examples_v2_1_bcpd.md`** — worked queries that respect the v2.1 rules above
- **`data/reports/v2_0_to_v2_1_change_log.md`** — explicit change log
- **`data/reports/vf_lot_code_decoder_v1_report.md`** — decoder rules with evidence
- **`data/reports/crosswalk_quality_audit_v1.md`** — crosswalk audit
- **`data/reports/coverage_improvement_opportunities.md`** — the W3 recommendations that informed v2.1
- **`data/reports/join_coverage_simulation_v1.md`** — coverage simulation v0 vs v1
- **`scratch/vf_decoder_gl_finance_review.md`** — Terminal B's review (5 questions answered)
- **`scratch/vf_decoder_ops_allocation_review.md`** — Terminal C's review (3 questions answered)

## Versioning

- v2.1 is BCPD-only. Org-wide remains a Track B roadmap item.
- v1 outputs (`output/operating_state_v1.json` etc.) and v2.0 outputs (`output/operating_state_v2_bcpd.json` etc.) are unchanged.
- v2.1 sits alongside v2.0. Once consumers migrate, v2.0 can be archived; until then, both coexist.
- v2.2 candidates: range-row per-lot expansion (after allocation-method sign-off), `CommercialParcel` ontology entity (for HarmCo X-X), Scattered Lots inventory feed, DR 38-col phase recovery.
