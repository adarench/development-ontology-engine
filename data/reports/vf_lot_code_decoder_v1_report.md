# VF Lot-Code Decoder v1 — Report

**Built**: 2026-05-01
**Owner**: Terminal A (W1.5 of BCPD State Quality Pass)
**Inputs**: W1 report + reviews from Terminal B (`scratch/vf_decoder_gl_finance_review.md`) and Terminal C (`scratch/vf_decoder_ops_allocation_review.md`)
**Output (lookup)**: `data/staged/vf_lot_code_decoder_v1.csv`

All rules ship `confidence='inferred'` with `validated_by_source_owner=False`.

---

## Changes from v0

### 1. AultF B-suffix correction (Terminal B Q2)

**Before (v0)**: AultF B-suffix lots routed to B2 with overlap caveat; this misclassified 1,499 rows / **$4.0M**.

**After (v1)**: AultF B-suffix → **B1** (entire 101-211 range). PWFS2 B-suffix continues to → B2 (273-323 range). Empirically, AultF and PWFS2 B-suffix lot ranges are disjoint (AultF max=211, PWFS2 min=273), so the routing is unambiguous in the actual GL data even though Lot Data shows overlap.

### 2. Harmony 3-tuple join requirement (Terminal B Q1, Q3)

Phase is not encoded in any GL field other than the lot-number range. Harm3 collapses 9+ Lot Data phases under one VF code; MF1 and B1 share lot numbers 101-116 in inventory. **Any downstream join MUST use `(canonical_project, canonical_phase, canonical_lot)`. A flat `(canonical_project, lot)` join double-counts $6.75M** ($1.4M MF1 + $5.3M B1 colliding on 16 inventory lots). The decoder rule is unchanged; the join-key requirement is now explicit.

### 3. HarmCo split (Terminal C Q2)

HarmCo's 374 rows split into two virtual codes:

- `HarmCo_residential` — 20 lots `0000A01`-`0000B10` → MF2 lots `A01`-`B10`. **Lot-grain mappable**, inferred. (v0's 0% match was a validation-harness artifact: the index dropped alpha lots.)
- `HarmCo_commercial` — 11 parcels `0000A-A` through `0000K-K` → Harmony commercial pad `<X>`. **Non-lot inventory**, no Lot Data row. Should NOT enter the canonical lot crosswalk's match-rate denominator.

### 4. SctLot canonical project change (Terminal B Q4)

**Before (v0)**: `canonical_project = 'Scarlet Ridge'`. This silently inflated Scarlet Ridge's project-grain cost by ~46% (+$6.55M / 1,130 rows).

**After (v1)**: `canonical_project = 'Scattered Lots'` (new inferred project). Evidence: zero lot-number overlap with ScaRdg; "SctLot" appears in invoice IDs (e.g. `Inv.:SctLot-000032-01:Turner Excavating`); vendor mix is custom-build / scattered-construction; multi-year history 2018-2025. SctLot rules feed project-grain rollups only. Confidence remains `inferred-unknown`.

### 5. Range entries — broader scope (Terminal B Q5)

Range-form lots (`NNNN-NN` or `NNNN-NNN`) appear in **8 VF project codes** (W1 only listed 3): HarmTo, LomHT1, PWFT1, ArroT1, plus MCreek, SaleTT, SaleTR, WilCrk that W1 considered out-of-scope. Total range exposure:

- **4,020 range rows** across all 8 codes
- **$45,752,046.63** of capitalized cost — ~13% of total VF cost basis

Treatment in v1: keep at **project+phase grain**, do NOT expand to per-lot synthetic rows, do NOT exclude. Memo evidence (`'shell allocation'`, design/engineering vendors, shared-infra accounts) plus per-row dollar magnitude (~$3-14K) confirms these are real shared-shell / shared-infrastructure costs. Equal-split expansion is a v2 candidate that requires source-owner sign-off on the allocation method.

### 6. Lomond Heights confirmed single-phase (Terminal C Q3)

LomHS1 (SFR, lots 101-171) and LomHT1 (TH, lots 172-215) both route to phase **2A**. The W1 routing was correct; the LomHT1 low match rate was range-entry noise, not a routing error. Product-type split (SFR vs TH) lives at the lot level via `Lot Data.ProdType`, not as a separate phase.

---

## Per-rule v1 results

| virtual code | canonical project | rule | rows total | lot-eligible | range | commercial | SR | project-grain | match% (any) | quality | recommendation |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Harm3 | Harmony | `harmony_lot_range_to_phase` | 9,234 | 9,234 | 0 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| HarmCo_residential | Harmony | `harmony_mf2_residential` | 169 | 169 | 0 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| HarmCo_commercial | Harmony | `harmony_commercial_pad_nonlot` | 205 | 0 | 0 | 205 | 0 | 0 | 0% | non-lot-only | non-lot inventory only; do not feed lot-level cost |
| HarmTo | Harmony | `harmony_townhome_mf1_only` | 2,302 | 1,734 | 568 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| LomHS1 | Lomond Heights | `lomondheights_sfr_phase_2a` | 505 | 505 | 0 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| LomHT1 | Lomond Heights | `lomondheights_th_phase_2a` | 90 | 31 | 59 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| PWFS2 | Parkway Fields | `parkway_sfr_phase2_range_route` | 18,264 | 18,264 | 0 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| PWFT1 | Parkway Fields | `parkway_th_phase1_c1c2_route` | 7,994 | 6,880 | 1,114 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| AultF | Parkway Fields | `aultf_suffix_a_b_phase_route_v1` | 16,996 | 16,595 | 0 | 0 | 401 | 0 | 98.7% | high-evidence | safe for v2.1 simulation as inferred mapping |
| ArroS1 | Arrowhead Springs | `arrowhead_sfr_123_456_route` | 5,142 | 5,142 | 0 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| ArroT1 | Arrowhead Springs | `arrowhead_th_123_456_route` | 11 | 6 | 5 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| ScaRdg | Scarlet Ridge | `scarletridge_lot_range_phase` | 3,916 | 3,916 | 0 | 0 | 0 | 0 | 100.0% | high-evidence | safe for v2.1 simulation as inferred mapping |
| SctLot | Scattered Lots | `sctlot_project_grain_only_v1` | 1,130 | 0 | 0 | 0 | 0 | 1,130 | 0% | non-lot-only | project-grain only; do not feed lot-level cost |
| MCreek | Meadow Creek | `range_entry_passthrough` | 7,418 | 6,002 | 1,416 | 0 | 0 | 0 | None% | non-lot-only | project+phase grain; do not feed lot-level cost; preserve dollars in summary rollup |
| SaleTT | Salem Fields | `range_entry_passthrough` | 2,326 | 1,833 | 493 | 0 | 0 | 0 | None% | non-lot-only | project+phase grain; do not feed lot-level cost; preserve dollars in summary rollup |
| SaleTR | Salem Fields | `range_entry_passthrough` | 938 | 655 | 283 | 0 | 0 | 0 | None% | non-lot-only | project+phase grain; do not feed lot-level cost; preserve dollars in summary rollup |
| WilCrk | Willowcreek | `range_entry_passthrough` | 264 | 182 | 82 | 0 | 0 | 0 | None% | non-lot-only | project+phase grain; do not feed lot-level cost; preserve dollars in summary rollup |

---

## Range and non-lot summary

- **Range rows excluded from lot-level denominator**: 4,020 rows, $45,752,046.63
- **Commercial parcel rows (HarmCo X-X)**: 205 rows, $2,630,218.88
- **SR-suffix rows (AultF 0139SR/0140SR)**: 401 rows (per Terminal C Q1), inferred-unknown
- **SctLot project-grain-only rows**: 1,130 rows / $6.55M routing to canonical_project='Scattered Lots'

Range $ by canonical project (for project+phase grain rollup):

| canonical project | range rows | range $ |
|---|---:|---:|
| Parkway Fields (PWFT1) | 1,114 | $15,194,238.34 |
| Meadow Creek (MCreek) | 1,416 | $14,955,856.16 |
| Harmony (HarmTo) | 568 | $5,507,682.33 |
| Salem Fields (SaleTT) | 493 | $5,257,330.12 |
| Salem Fields (SaleTR) | 283 | $3,408,479.43 |
| Willowcreek (WilCrk) | 82 | $859,502.54 |
| Lomond Heights (LomHT1) | 59 | $565,666.16 |
| Arrowhead Springs (ArroT1) | 5 | $3,291.55 |

---

## Per-rule pattern descriptions

**`Harm3` — harmony_lot_range_to_phase** (`canonical_project = Harmony`)

Harmony Harm3 — phase routed by lot-number range (Lot Data ranges).
    Phase is NOT encoded elsewhere (per Terminal B Q1). Downstream joins MUST use
    the (project, phase, lot) 3-tuple — flat (project, lot) joins double-count $6.75M.

**`HarmCo_residential` — harmony_mf2_residential** (`canonical_project = Harmony`)

HarmCo residential subset — `0000<X><NN>` where X∈A-B, NN∈01-10 → Harmony MF2 lot `<X><NN>`.
    Per Terminal C Q2, MF2 has 20 lots A01-A10 + B01-B10. v0 validation harness dropped them.

**`HarmCo_commercial` — harmony_commercial_pad_nonlot** (`canonical_project = Harmony`)

HarmCo commercial parcels — `0000<X>-<X>` where X∈A-K → Harmony commercial pad `<X>`.
    NOT in Lot Data / inventory / allocation. Treat as non-lot inventory.

**`HarmTo` — harmony_townhome_mf1_only** (`canonical_project = Harmony`)

Harmony Townhomes — single 4-digit lot → MF1; range → keep at phase grain.

**`LomHS1` — lomondheights_sfr_phase_2a** (`canonical_project = Lomond Heights`)

Lomond Heights LomHS1 — phase 2A (SFR product-type subset 101-171).

**`LomHT1` — lomondheights_th_phase_2a** (`canonical_project = Lomond Heights`)

Lomond Heights LomHT1 — phase 2A (TH product-type subset 172-215). Many rows are range entries (shell allocations).

**`PWFS2` — parkway_sfr_phase2_range_route** (`canonical_project = Parkway Fields`)

Parkway PWFS2 — 4-digit numeric → D1/D2/G1/G2 by lot range; 5-digit B-suffix → B2.

**`PWFT1` — parkway_th_phase1_c1c2_route** (`canonical_project = Parkway Fields`)

Parkway PWFT1 — 4-digit 3xxx → C1 or C2; range → keep at phase grain.

**`AultF` — aultf_suffix_a_b_phase_route_v1** (`canonical_project = Parkway Fields`)

AultF (Parkway Fields E-1, Ault Farms) — 5-digit NNNNX with letter suffix.
    REVISED v1: A-suffix → A1/A2.x by range; B-suffix → B1 (was B2 in v0; corrected per Terminal B Q2).
    SR-suffix → inferred-unknown (per Terminal C Q1).

**`ArroS1` — arrowhead_sfr_123_456_route** (`canonical_project = Arrowhead Springs`)

**`ArroT1` — arrowhead_th_123_456_route** (`canonical_project = Arrowhead Springs`)

**`ScaRdg` — scarletridge_lot_range_phase** (`canonical_project = Scarlet Ridge`)

**`SctLot` — sctlot_project_grain_only_v1** (`canonical_project = Scattered Lots`)

SctLot → 'Scattered Lots' canonical project. No phase decoder; project-grain only.

---

## Recommendation matrix (per A_integrator instructions)

| rule | safe for v2.1 simulation? | safe for v2.1 inferred mapping in lot-level cost? | safe for project/phase only? | requires source-owner validation? |
|---|---|---|---|---|
| Harm3 lot-range routing | yes | yes (with 3-tuple join key) | yes | no for v2.1 (inferred ok); yes before high confidence |
| HarmCo_residential MF2 | yes | yes | yes | no for v2.1 inferred |
| HarmCo_commercial X-X | yes (for exclusion) | no — non-lot inventory | yes (commercial-pad summary) | yes — needs ontology decision (CommercialParcel?) |
| HarmTo single-lot MF1 | yes | yes | yes | no |
| HarmTo range entries | yes (project+phase only) | no | yes | yes (allocation method) |
| LomHS1 SFR 2A | yes | yes | yes | no |
| LomHT1 TH 2A | yes (range-aware) | yes (single-lot subset) | yes | no |
| PWFS2 4-digit + 5-digit B → D1/D2/G1/G2/B2 | yes | yes | yes | no |
| PWFT1 C1/C2 split | yes | yes (single-lot subset) | yes | no |
| AultF A-suffix → A1/A2.x | yes | yes | yes | no |
| AultF B-suffix → B1 (CORRECTED) | yes | yes | yes | no |
| AultF SR-suffix | yes (exclude) | no | yes (inferred-unknown) | yes — Terminal C Q1 |
| ArroS1 / ArroT1 123/456 routing | yes | yes | yes | no |
| ScaRdg phase 1/2/3 | yes | yes | yes | no |
| SctLot project-grain only | yes | no (no inventory match possible) | yes (project='Scattered Lots') | yes — needs source-owner attribution decision |
| Range entries (MCreek, SaleTT, SaleTR, WilCrk, HarmTo, LomHT1, PWFT1, ArroT1) | yes (project+phase only) | no (do not expand in v0) | yes | yes — for any expansion to per-lot grain |

## Hard guardrails honored

- ✅ All rules `confidence='inferred'`, `validated_by_source_owner=False`.
- ✅ No modification to `staged_gl_transactions_v2`.
- ✅ No modification to canonical_lot or any v2 output.
- ✅ Org-wide v2 untouched.
- ✅ Did not promote any rule to high confidence.
- ✅ HarmCo split honors Terminal C's non-lot inventory recommendation.
- ✅ SctLot canonical_project changed to 'Scattered Lots' per Terminal B; not merged with ScaRdg.
- ✅ AultF B-suffix corrected to B1 per Terminal B's empirical evidence.
- ✅ Range rows kept at project+phase grain; not expanded.
