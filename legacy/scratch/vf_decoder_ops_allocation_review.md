# VF Lot-Code Decoder — Ops/Allocation Review (W1 hand-off)

**Author**: Terminal C
**Date**: 2026-05-01
**Scope**: Answer the three open questions from W1's decoder report by triangulating against ops sources (inventory closing report, Lot Data, 2025Status, IA Breakdown) and allocation workbooks (LH, Parkway PF, Flagship v3).
**Inputs reviewed**: `data/reports/vf_lot_code_decoder_report.md`, `data/staged/vf_lot_code_decoder_v0.csv`, `staged_gl_transactions_v2.parquet`, `Collateral Dec2025 - Lot Data.csv` / `2025Status.csv` / `IA Breakdown.csv`, `Inventory _ Closing Report (4).xlsx`, `LH Allocation 2025.10 - LH.csv`, `Parkway Allocation 2025.10 - PF.csv`, `Flagship Allocation Workbook v3 - Allocation Engine.csv` / `Lot Mix & Pricing.csv`.
**Hard rule honored**: every rule below remains `inferred`. No promotion to higher confidence.

---

## Question 1 — AultF `SR` suffix (`0139SR`, `0140SR`)

### Recommendation

**Likely meaning**: a non-phase 2-character marker on two specific Parkway Fields lots (139, 140) that designates a special construction/sales status — **most plausibly a "Spec / Sales Reserve" or "Show / Specialty" tag** — applied at the GL line level by the source system. **Not** Site Roads (because of the account distribution), **not** South Row (no allocation-workbook phase has that name), **not** Scarlet Ridge (the account, project_code, and entity all stay in Parkway/Ault-Farms scope), **not** an allocation rollup (no IA Breakdown / allocation-workbook entry mentions SR).

This recommendation is **inferred-unknown**; pick the meaning only after source-owner confirmation. For decoder behavior in W2/W3, treat 0139SR / 0140SR as **a 2-character suffix variant of AultF lot 139 and lot 140** and route them to the same canonical phase that AultF's standard A/B suffix would route 0139/0140 to (i.e. Parkway Fields A1, B1, or E-1) — but **flag as `phase_inferred=False`** until the SR semantics are confirmed.

### Evidence

1. **Volume and concentration** (from `staged_gl_transactions_v2.parquet`):
   - AultF has 16,996 rows, 125 distinct lots.
   - Only **2 distinct SR lots**: `0139SR` (no separate count given but most rows) and `0140SR`. Combined: **401 rows** (matches W1's `len=6: 401` bucket exactly).
   - Account distribution on the 401 SR rows: `Direct Construction = 375 (93.5%)`, `Permits and Fees = 22 (5.5%)`, `Direct Construction - Lot = 4 (1.0%)`.
   - Posting-date range: starts 2024-07-28 — recent activity.
   - All `phase` field values are `None` for AultF (no source-system phase tag on AultF rows at all).
2. **Account distribution rules out Site Roads / Offsites / Backbone**: a true infrastructure-rollup category (e.g. "Parkway Fields Backbone" in Parkway AAJ, "BCP Ben Lomond Offsites" in JCSList) would be dominated by land-development accounts, not "Direct Construction" — which is a vertical-build account (per `CONTEXT_PACK.md` definitions). 93.5% Direct Construction means real homes are being built on these two lots.
3. **Lot 139 / 140 in Parkway Fields Lot Data exist as standard residential lots**:
   - Phase A1, lots 139 & 140 (SFR, HorzCustomer=Lennar, HorzSeller=BCPD)
   - Phase B1, lots 139 & 140 (SFR, HorzCustomer=BCP)
   These are real residential lots, not infrastructure parcels.
4. **No "SR" label appears in any allocation workbook**:
   - Parkway PF.csv per-lot output has phases B2, D1, D2, E1, E2, F, G1 (Church, Comm), G2, H — no SR.
   - Parkway AAJ.csv column headers are all "Parkway Fields A 2.2", "Parkway Fields A1", …, "Parkway Fields Clubhouse", "Parkway Fields D" — no SR.
   - Parkway JCSList.csv distinct project-name strings — no SR.
   - LH JCSList.csv distinct project-name strings — no SR.
   - Flagship Allocation Engine — no SR.
5. **No "SR" label appears in IA Breakdown**: AultF entity ("Ault Farms aka Parkway Fields") rolls up to: Parkway Fields E-1 ($12.0M), E-2 ($88K), F ($4.7K), G2 ($183K), H1 ($656), Other ($4.4K). No SR sub-bucket.
6. **No "SR" subdivision/community in inventory closing report**: INVENTORY/CLOSED/CLOSINGS sheets show standard Parkway phases (A1, A2.2, A2.3, B2, C1, C2, D1, D2, G1) and no SR suffix or SR-tagged lots 139/140.
7. **Scarlet Ridge cross-allocation hypothesis fails**: Scarlet Ridge has its own VF codes (`ScaRdg`, `SctLot`); Scarlet Ridge phase 1 happens to include lot numbers 101-152 (so 139, 140 are in-range for Scarlet Ridge phase 1 too), but every other identifier — VF project_code = "AultF", company/entity = Ault Farms, account_name = Direct Construction (Parkway scope) — points away from cross-project leakage.

### Confidence

**low** for any specific meaning of the letters "SR". **medium-high** that SR is *not* Site Roads (account profile rules out infrastructure) and *not* Scarlet Ridge (every other identifier disagrees) and *not* an allocation/development rollup (no allocation workbook reference). The space of remaining candidates is "Spec Reserve / Sales Reserve / Show home / Specialty Reseller / sub-area marker" — none independently verifiable from the data alone.

### Impact on phase/lot mapping

- **Small.** 401 rows, 2 lots — a minor share of AultF's 16,996 rows.
- W1's current rule already flags AultF SR as "inferred-unknown" and leaves the 614 unmatched rows undecoded (which includes the 401 SR rows + ~213 other length-4 lots).
- If W3's coverage goal is high inventory-lot match rate, leaving SR undecoded is fine — these are 2 lots of 1,285 BCPD inventory lots (0.16%).

### W2/W3 readiness

**A_integrator can proceed with W2/W3** with SR as inferred-unknown. The decoder rule for AultF (`aultf_suffix_a_b_phase_route`) at 96.4% match is already strong enough; the SR exclusion is documented as a known caveat. If W2/W3 needs a routing decision before source-owner sign-off, route 0139SR → Parkway Fields A1 lot 139 and 0140SR → Parkway Fields A1 lot 140 (the most likely phase given AultF's per-IA-Breakdown phase coverage, BUT flag the routing as `phase_inferred=True` and exclude from any high-confidence canonical lot crosswalk).

---

## Question 2 — HarmCo commercial parcel codes (`0000A-A` … `0000K-K`)

### Recommendation

**Likely meaning**: the X-X-form lots in HarmCo are **non-residential commercial parcels** in the Harmony master plan (Harmony's commercial district), with letters A-K labeling individual pads. They are **not currently enumerated in Lot Data, 2025Status, the inventory closing report, IA Breakdown, or the Flagship Allocation Workbook** — i.e. they are **non-lot inventory** that exists only at the GL grain in the VF source system.

The W1 decoder's existing rule `harmony_commercial_mf2_marker` (which routes `0000<X>NN` → MF2 lot `<X><NN>`) is correct for the **20 numeric-suffix lots** (A01-A10, B01-B10) that map to MF2 residential. **It is NOT correct for the 11 X-X form parcels.** Recommend splitting the rule:

- `harmony_mf2_residential` — `0000<X><NN>` (X ∈ A-B, NN ∈ 01-10) → Harmony MF2 lot `<X><NN>` (matches Lot Data 100% if the validation harness preserves alpha lots).
- `harmony_commercial_pad` — `0000<X>-<X>` (X ∈ A-K) → Harmony commercial pad `<X>` — **canonical phase unresolved** (no row in Lot Data / inventory / allocation); leave canonical_phase/canonical_lot as `inferred-unknown` and tag with a `non_lot_inventory=True` flag.

### Evidence

1. **Distribution of HarmCo's 31 distinct lots** (from `staged_gl_transactions_v2.parquet`, 374 rows total):

   | form | lots | rows | match Lot Data MF2? |
   |---|---:|---:|---|
   | `0000A01`…`0000A10` | 10 | 116 | ✅ matches MF2 lots A01-A10 |
   | `0000B01`…`0000B10` | 10 | 43 | ✅ matches MF2 lots B01-B10 |
   | `0000A-A` | 1 | **106** | ❌ no Lot Data match |
   | `0000B-B` | 1 | **80** | ❌ no Lot Data match |
   | `0000C-C` | 1 | 8 | ❌ no Lot Data match |
   | `0000D-D` | 1 | 2 | ❌ |
   | `0000E-E` | 1 | 1 | ❌ |
   | `0000F-F` | 1 | 1 | ❌ |
   | `0000G-G` | 1 | 1 | ❌ |
   | `0000H-H` | 1 | 1 | ❌ |
   | `0000I-I` | 1 | 1 | ❌ |
   | `0000J-J` | 1 | 1 | ❌ |
   | `0000K-K` | 1 | 3 | ❌ |
   | **X-X subtotal** | **11** | **205 (55% of HarmCo rows)** | |

2. **Lot Data MF2 actually has 20 lots** (W1's "MF2 NaN/0" line in the per-canonical-project summary was a numeric-aggregation artifact — count was computed over digit-only LotNo., so alpha lots A01-B10 dropped out). Direct query against Lot Data: phase `MF2`, 20 lots: `A01-A10` (10) + `B01-B10` (10), all `ProdType = MF`, all `LotCount = 1`, `SHComb` = `HarmonyMF2A01` etc. The numeric-suffix HarmCo lots map cleanly to these.
3. **Account distribution on HarmCo rows** (374 total): `Direct Construction = 331 (88.5%)`, `Permits and Fees = 22 (5.9%)`, `Direct Construction - Lot = 21 (5.6%)`. Direct Construction dominates on the X-X parcels too — so they are **receiving vertical construction posts**, not just allocation/rollup entries.
4. **No Harmony "Commercial" phase in any source**:
   - Lot Data Harmony phases: A10, A4.1, A7, A8, A9, ADB13, ADB14, B1, B2, B3, MF1, MF2, MF3 — no commercial.
   - Inventory closing report INVENTORY HARMONY phases: 8, 10 (and others) — no commercial.
   - Flagship Allocation Engine Harmony rows: A10, A13, A14, A4.1, A7, A8, A9, ADB13, B1, B2, B3, MF1 (TH), MF2 (MF), MF3 (MF) — no commercial.
   - Lot Mix & Pricing Harmony: same 14 phases — no commercial.
   - IA Breakdown Harmony: ADB13, ADB14, B1, B2, B3, Phase A Plat 13, Phase A Plat 14, Nathan, Waddell — no commercial.
5. **By analogy, commercial parcels ARE tracked separately in other projects' allocation workbooks**:
   - LH allocation has a **`Phase 3 - Comm (1 lot)`** row in `LH.csv` per-lot output.
   - Parkway PF.csv per-lot output has **`G1 Church (1)`** and **`G1 Comm (1)`** rows.
   So when commercial parcels exist in a project, the standard pattern is "1-lot commercial entry per phase". Harmony's commercial pads (if there are 11 of them, A-K) would normally show up in Lot Data as 11 rows in some phase like "Comm" or in MF2/MF3. They don't.
6. **VF code naming**: literally `HarmCo` = "Harmony Commercial" (per W1 report). Strong textual signal that this VF code's primary intent is to bucket commercial activity. The fact that 20 of its 31 lots happen to be residential MF2 lots is unusual — likely an artifact of how the source system bundles commercial-shell + residential-floor activity for mixed-use buildings.
7. **Volume distribution within X-X**: `A-A=106 rows`, `B-B=80 rows` are by far the largest; `C-C=8` falls off; `D-D` through `J-J` are 1-2 rows each; `K-K=3`. This skew is consistent with a sequential master-plan rollout where pads A and B are in active vertical construction while C-K are in pre-construction / placeholder state.

### Confidence

**medium** that these are commercial parcels (multiple converging signals: VF code name = "HarmCo", no residential-Lot-Data match, Direct Construction posts indicate real building activity, A-K letter-labeling is a master-plan-pad pattern). **low** that we can identify the specific allocation source — the Flagship Allocation Workbook v3 explicitly does NOT have a Harmony Commercial entry, so these parcels appear to be entirely outside the current allocation framework.

### Impact on phase/lot mapping

- **Medium-high.** 205 rows (55% of HarmCo's 374 rows) currently fall into "decoded-but-unmatched" via the MF2 routing — this is the entire HarmCo "no-decoder" 0% match rate the W1 report flags.
- These cannot be routed to MF2 lots A-A through K-K because Lot Data has no such lots — the validation will keep failing as long as the rule routes there.
- Splitting the rule (residential A01-B10 → MF2 with 100% match; X-X → unmatched non-lot inventory) keeps the residential portion clean and isolates the X-X parcels for separate handling.
- Down the road, the canonical ontology may need a new entity type (`CommercialParcel`) or a new phase value (`Commercial`) to hold these. That's a Terminal A ontology decision; out of scope for me here.

### W2/W3 readiness

**A_integrator can proceed with W2/W3 with caveats:**

1. Rebuild HarmCo's decoder rule into two: residential (A01-B10 → MF2, full-match) + commercial (X-X → unmatched non-lot inventory). The W1 report's note in Section 5 about "rebuilding the validation index to preserve alpha lots" addresses the validation-harness side; the rule split addresses the data-model side.
2. Add a `non_lot_inventory=True` flag (or equivalent) for the X-X parcels so they don't pollute the canonical lot crosswalk's match rate denominator.
3. Defer the "what allocation source covers Harmony commercial" question to a later workstream — there is no current source.

---

## Question 3 — Lomond Heights `LomHS1` vs `LomHT1` split

### Recommendation

**Single canonical phase, product-type split at the lot level.** The two VF codes (LomHS1, LomHT1) are both Lomond Heights phase 2A, distinguished only by **product type** (SFR vs TH) — and the split is **lot-range-clean**: SFR = lots 101-171, TH = lots 172-215. This matches Lot Data exactly. The VF source system's 2-code layout is a *reporting / accounting* split, not a *physical / allocation* phase split. The W1 decoder's existing routing (both → phase `2A`) is correct.

For the canonical ontology: keep one phase (`Lomond Heights :: 2A`) with `ProdType` as a per-lot attribute. The LH allocation workbook's two-budget-rows-per-phase pattern is a budget-modeling convenience and should be reconciled into a single phase with a `product_mix` breakdown in PhaseState (which is already what v1 does).

### Evidence — multi-source treatment matrix

| source | what's there | grain | notes |
|---|---|---|---|
| **Lot Data** (canonical) | one phase `2A` with **116 lots**: 71 SFR (lots 101-171) + 44 TH (lots 172-215) + 1 Comm | per-lot, with `ProdType` column distinguishing | clean lot-range split: SFR ends at 171, TH starts at 172 |
| **2025Status** | same as Lot Data: phase `2A`, 116 lots, ProdType column distinguishes SFR/TH/Comm | per-lot | matches Lot Data 100% on `(project, phase, lot)` |
| **LH Allocation Workbook (`LH.csv` Summary per lot)** | **two rows for phase 2A**: `2A SFR (71 lots, $150K sales)` + `2A TH (44 lots, $110K sales)` | per (phase, prod_type) | budget split; sales price differs (SFR=$150K, TH=$110K) so the two-row structure is an economic, not phase, split |
| **Inventory Closing Report** (`INVENTORY` sheet) | one phase `2-A` (note hyphen format diff from Lot Data's `2A`) | per-lot, no ProdType column on the sheet itself (PLAN column distinguishes by model name e.g. "Rowan B" vs "Walnut B") | 114 INVENTORY rows for Lomond Heights, all `2-A` — the SFR/TH distinction is implicit in PLAN; phase is one bucket |
| **VF GL data** | **two project codes** for one physical phase: `LomHS1` (SFR, 31 distinct lots, 505 GL rows) + `LomHT1` (TH, 29 distinct lots, 90 GL rows) | per (project_code, lot) | accounting-system split; physical lot universe is the same |
| **W1 decoder** | both VF codes route to canonical phase `2A` | `(canonical_project, canonical_phase, canonical_lot)` | LomHS1 = high-evidence (100% match); LomHT1 = low-evidence (34.4%) but only because 59 of 90 rows are *range entries* (`0172-175`, `0212-215`, etc.), not because of phase mis-routing — the 31 single-lot entries match 100% |

**Phase name normalization**: Lot Data uses `2A`; the inventory closing report uses `2-A`. Existing v1 `normalize_phase()` should already collapse these; if not, a one-line mapping rule is sufficient.

### Confidence

**high** that LomHS1 and LomHT1 are two reporting aliases for the same physical phase 2A, distinguished only by product type. The lot-range alignment between Lot Data's ProdType split (SFR=101-171, TH=172-215) and the VF code partition is mechanical — there's no judgment call. The 100% match rate of LomHS1 against Lot Data corroborates this.

### Impact on phase/lot mapping

- **Low.** The W1 decoder's routing is correct as-is. The 34.4% match rate on LomHT1 is a *range-entry artifact* (W1 already calls it out), not a phase-mapping defect.
- For the canonical ontology, this is a clean case: one phase, two product types, one lot universe. No new entity needed.
- The LH allocation workbook's two-budget-row-per-phase format is incidental — Terminal A's PhaseState aggregation should sum across product types within a phase (consistent with v1's `expected_total_cost` derivation).

### W2/W3 readiness

**A_integrator can proceed with W2/W3 unblocked.** No changes to the decoder rules needed. Document in the canonical lot crosswalk that:

- `vf_project_code IN ('LomHS1', 'LomHT1')` → `canonical_project = 'Lomond Heights'`, `canonical_phase = '2A'`, `canonical_lot = vf_lot` (single-lot rows only; range rows stay undecoded).
- The SFR/TH distinction is recoverable from `Lot Data.ProdType` joined on `(canonical_project, canonical_phase, canonical_lot)`.
- The W1 LomHT1 low-match-rate flag is informational (range entries), not a blocker.

---

## Cross-cutting notes

### Does any of this change W1's decoder verdicts?

| W1 verdict | Q affected | recommended adjustment |
|---|---|---|
| `harmony_commercial_mf2_marker`: no-decoder, do not apply | Q2 | Split into residential (A01-B10 → MF2 high-evidence) + commercial (X-X → non-lot inventory, leave undecoded). Net effect: HarmCo's 374 rows split into 169 high-evidence-residential + 205 unmatched-non-lot, instead of 0 / 374. |
| `aultf_suffix_a_b_phase_route`: high-evidence, USE | Q1 | Keep. The 401 SR rows are already in the W1 "undecoded" bucket; my evidence supports keeping them undecoded until source owner explains. |
| `lomondheights_sfr_phase_2a` + `lomondheights_th_phase_2a` | Q3 | Keep. Routing is correct; the LomHT1 low-match is range-row noise, not a routing error. |

### What the source-system owner still needs to confirm

(Adds to W1's hand-off questions list, doesn't replace it.)

1. **AultF SR meaning** (Q1) — open. Most likely a special construction/sales status; not infrastructure or cross-project. 401 rows / 2 lots.
2. **HarmCo X-X parcels** (Q2) — open. Likely 11 commercial pads in the Harmony master plan, currently outside Lot Data and the allocation framework. 205 rows / 11 parcels. May require a new ontology entity (CommercialParcel) or a new phase value.
3. **Lomond Heights 2A SFR/TH** (Q3) — closed. Single phase, product type at lot grain. No source-owner action needed.

### Guardrails honored

- ✅ No decoder files modified.
- ✅ No `output/operating_state_v2_*` files modified.
- ✅ No `confidence` value promoted above `inferred`.
- ✅ Findings sourced from already-staged data + raw allocation/inventory CSVs only.

---
