# VF Lot-Code Decoder — GL/Finance Review (Terminal B response to W1)

**Built**: 2026-05-01
**Author**: Terminal B (GL/Financials worker)
**Purpose**: Answer the 5 finance/GL treatment questions raised by W1 in `data/reports/vf_lot_code_decoder_report.md` § "Hand-off questions for source-owner validation".
**Inputs read**:
- `data/reports/vf_lot_code_decoder_report.md`
- `data/staged/vf_lot_code_decoder_v0.csv`
- `data/staged/staged_gl_transactions_v2.parquet` (re-derived all numbers below directly from this)
- `data/staged/staged_inventory_lots.parquet` (used for Q3 inventory cross-check)
- `scratch/gl_financials_findings.md`, `scratch/bcpd_financial_readiness.md` (own prior work)
- `data/staged/staged_gl_transactions_v2_validation_report.md` (incl. Terminal B addendum)

**Hard guardrails honored**:
- Did **not** modify `vf_lot_code_decoder_v0.csv` or the W1 report.
- Did **not** modify any `output/operating_state_v2_*` artifact.
- Did **not** promote any inferred rule to higher confidence — every recommendation below is a finance/GL judgment for A_integrator to consider; promotion still requires source-owner sign-off and stays out of v0.

---

## Q1 — Harm3 phase routing by lot range

### Recommendation
**The W1 rule is the only viable approach with the data we have. Proceed with W2/W3 using lot-range routing, but require human sign-off before promoting the rule above `inferred`. Do NOT attempt to mine phase from any other GL field — there isn't one.**

### Evidence
1. **Harm3 collapses many Lot Data phases under one VF code.** Harm3 has 9,234 VF rows / 114 distinct 4-digit lot codes ranging from `0001` to `1044`. Mapping lot ranges to Lot Data Harmony phases:
   - Lots 0001 (lone outlier, 2 rows) — looks like MF1 territory but more likely a stray entry
   - Lots 0101-0192 → B1
   - Lots 0201-0271 → B2
   - Lots 0301-0347 → B3
   - Lots 0701-0749 → A7
   - Lots 0801-0848 → A8
   - Lots 0901-0950 → A9
   - Lots 1001-1044 → A10
   - Lots 1301-1334 → ADB13
   - Lots 1401-1438 → ADB14
   The Harm3 VF code unambiguously **rolls up at least 9 Lot Data phases** under a single project token.

2. **Phase is not encoded anywhere else in VF.** I enumerated VF's `raw_column_map_json`. Source columns are: `Account`, `Account Group`, `Account Name`, `Account Type`, `Amount`, `Journal Code`, `Company`, `Company Name`, `Credit`, `Debit`, `Division`, `Division Name`, `Posting Date FY`, `Line No`, **`Lot`**, `Major`, `Memo 1`, `Memo 2`, `Minor`, `OUnit`, `Posting Date`, **`Project`**, `Sub-Ledger`, `Sub-Ledger Name`, `Trans No`. **No phase column.** Within Harm3 specifically: `division_name='Corporate'` (1 distinct), `operating_unit='HB'` (1 distinct), `subledger_*` 0% filled, `account_code` ∈ {1535, 1540, 1547} (the cost-accumulation triple), `major` 89 distinct values that look like job-cost component codes, `minor` 5 values (00, 02, 03, 07, 80), and `memo_1` contains payment/invoice references with no phase tokens (only 34 of 9,234 rows match a phase-like regex `\b(A[789]|A10|A4\.1|ADB1[34]|B[123]|MF[123]|Phase\s*\d|Ph\s*\d)\b` and those matches are spurious — text like "Salem Ph 1").

3. **Phase is not encoded anywhere else in DR either.** DR's `Lot/Phase` was already split into `lot` + `phase` in v2 staging; the canonical `phase` column is 0% across the whole feed (see Terminal B's prior `bcpd_financial_readiness.md` § B2). DR's `job_phase_stage` is 7.2% filled with values `01`/`04`/`10`/`03`/`09`/`K`/`08`/`L`/`02` — these don't correspond to Harmony phase names. More importantly, **DR has zero Harmony rows** — `project_name` containing 'Harmony' returns 0 rows. Harmony is a post-2018 project. So even if DR carried richer phase metadata, it wouldn't help Harm3.

### Confidence
**High** that lot-range routing is the only available signal; **medium** that the W1 rule's specific range cutoffs are correct (they match Lot Data exactly, but Lot Data itself is not a source-system attestation of how the GL was tagged).

### Impact on lot-level cost
9,234 rows / ~$30M+ of BCPD cost basis depends on this rule. It's the largest single decoder rule by row count and dollar volume after PWFS2 + AultF.

### Can A_integrator proceed with W2/W3?
**Yes**, with two conditions: (a) downstream join keys must be the 3-tuple `(canonical_project, canonical_phase, canonical_lot)` — see Q3 — not `(canonical_project, lot)`; (b) `confidence='inferred'` must be carried all the way through to v2 quality report so consumers know the rule is unvalidated.

---

## Q2 — AultF B-suffix overlap 201–211

### Recommendation
**The W1 rule mis-routes 1,499 rows / $4.0M from B1 to B2. Revise: assign all AultF B-suffix lots to B1, all PWFS2 B-suffix lots to B2 — they are disjoint by lot range in the actual GL data.**

### Evidence
The Lot Data overlap (B1=101-211, B2=201-323) is theoretical. The empirical GL data does NOT exhibit the overlap:

| VF code | B-suffix lot range observed | distinct lots | rows | $ |
|---|---|---:|---:|---:|
| **AultF** | **0127B–0211B** (range 127-211) | 36 | 4,978 | $13.6M |
| **PWFS2** | **0273B–0323B** (range 273-323) | 51 | 7,110 | (~$22.4M) |
| **AultF ∩ PWFS2 lot strings** | **0** (zero shared lot codes) | 0 | 0 | $0 |

AultF B-suffix lot maximum is exactly 0211 — matching B1's max in Lot Data (211). PWFS2 B-suffix lot minimum is 0273 — well above B1's max. There is a numerical gap (212-272) where neither VF code carries any B-suffix lot. **In other words, the VF source has already segregated B1 (under AultF) from B2 (under PWFS2) at the project-code level**; the lot-range overlap exists only in the Lot Data master, not in actual GL postings.

W1's edge-case note: *"AultF `02xxB` lots in the overlap are routed to B2 (because PWFS2 already enumerates B2 lots)"*. This logic is inverted. If AultF carries lots 0201B-0211B (which it does — 1,499 rows = $4M) and PWFS2 carries no lot in that range, then the AultF rows belong to **B1**, not B2.

Concrete impact: 11 distinct lots (0201B–0211B), 1,499 rows, $4,006,662 of capitalized cost is currently mis-tagged.

### Confidence
**High** that AultF B-suffix and PWFS2 B-suffix are disjoint in this dataset and that AultF is B1 / PWFS2 is B2. **Medium** for promoting the rule above `inferred` without source-owner sign-off — there's a small but non-zero risk that the source system happened to put a B2 lot under an AultF coding by mistake (which the data wouldn't reveal). Still, with 0 overlap and clean 211/273 boundary, the rule revision is much safer than W1's current routing.

### Impact on lot-level cost
1,499 rows / $4M of Parkway B1 cost basis. With current W1 rule these rows join to (Parkway, B2, 0201–0211). Inventory has B1 lots 0201–0211 — those will be missing GL coverage (false negative) — and B2 lots 0201–0211 — those will get spurious $4M attached (false positive). Both errors at once.

### Can A_integrator proceed with W2/W3?
**Yes, but with the rule revision applied first.** Concretely: in `vf_lot_code_decoder_v0.csv`, the `aultf_suffix_a_b_phase_route` rule should drop the "with overlap" routing and assign all B-suffix to B1. Update notes column to reference this review. Match-rate-vs-Lot-Data may dip slightly because B1's max in Lot Data is 211 and the rule never reached lots 212+ anyway, so coverage shouldn't change materially. Inventory match rate will improve.

---

## Q3 — Harmony MF1 vs B1 overlap at lots 101–116

### Recommendation
**The W1 rule is sound, but only if W3 uses the 3-tuple `(canonical_project, canonical_phase, canonical_lot)` as the join key. A flat `(canonical_project, lot)` join would silently double-count $1.4M and corrupt 16 inventory lots.**

### Evidence

1. **MF1 lots 101-116 do exist in VF — but under HarmTo, not Harm3:**

   | VF code | rows in lot 0101–0116 | distinct lots | $ |
   |---|---:|---:|---:|
   | Harm3 | 1,733 | 16 (every lot 101-116 present) | $5,349,310 |
   | HarmTo | 53 | 16 (every lot 101-116 present) | $1,401,590 |
   | overlap (both VF codes carry the same 4-digit lot string) | shared 16 lot strings | 16 | n/a |

   Both Harm3 and HarmTo carry rows for the SAME lot strings 0101 through 0116. They are *not* the same physical asset.

2. **Inventory confirms MF1 and B1 are distinct physical lots that share lot numbers:**

   ```
   Harmony inventory phase distribution: MF1=126, B1=92, B2=71, 10=41, 14=38, 9=22, MF 1=10, 8=7
   MF1 lot_num range: 1–116    (126 distinct inventory rows; townhomes / multi-family)
   B1  lot_num range: 101–192  (92 distinct inventory rows; single-family)
   ```

   For every lot number 101–116, **inventory has TWO physical rows** — one with `phase='MF1'` and one with `phase='B1'`. They are different units (e.g. MF1 lot 101 = a townhome; B1 lot 101 = a single-family house).

3. **Concrete double-count risk on a flat `(project, lot)` join:**
   - Naive sum (Harm3 lot 0101 + HarmTo lot 0101) = $443,839
   - Actual breakdown: Harm3 lot 0101 alone (B1) = $344,888; HarmTo lot 0101 alone (MF1) = $98,951
   - On a flat `(canonical_project='Harmony', lot=101)` join, both VF rows attach to the same inventory row → $443K wrongly attributed to a single physical lot, and the other physical lot gets $0.

### Confidence
**High** that the data supports the W1 rule when the 3-tuple is used. **Medium** confidence that the source-system enforces the HarmTo↔MF1 / Harm3↔SFR (B-series) segregation cleanly — we cannot verify from VF alone whether a small fraction of MF1 cost was accidentally posted under Harm3. If there is leakage, those rows would silently mis-route to B1. Source-owner should sample 5-10 Harm3 rows in the 0101-0116 range and confirm they really are SFR/B1 cost.

### Impact on lot-level cost
- Direct: $1.4M of MF1 cost (HarmTo) lives correctly under the MF1 rule.
- Indirect: $5.3M of B1 cost (Harm3 lots 0101-0116) routes to B1 via lot-range — assumes no MF1 leakage.
- **Critical**: if W3 uses a flat `(project, lot)` join key instead of the 3-tuple, the $1.4M (HarmTo MF1) and $5.3M (Harm3 B1) collide on 16 inventory rows, producing a $6.75M attribution error spread across MF1 and B1.

### Can A_integrator proceed with W2/W3?
**Yes, but only with the 3-tuple join key.** Strongly recommend updating `docs/vf_lot_code_decoder_plan.md` and the W3 plan to require `(canonical_project, canonical_phase, canonical_lot)` as the canonical lot key going forward. If the current join coverage harness uses `(canonical_project, lot_int)`, that needs to change before any cost rollup is published. Otherwise this is a silent correctness defect, not a coverage defect — it won't show up in match-rate metrics.

---

## Q4 — SctLot semantics

### Recommendation
**SctLot is NOT Scarlet Ridge. The W1 mapping `canonical_project='Scarlet Ridge'` is unsafe. Treat SctLot as its own canonical project (working name: `Scattered Lots`, confidence `inferred-unknown`). Keep at project grain only — do not attach SctLot rows to ScaRdg inventory or Scarlet Ridge inventory in W2/W3.**

### Evidence

1. **Zero lot-number overlap with ScaRdg.** ScaRdg covers lots 0101-0152 (sequential phased subdivision lots). SctLot has 6 distinct lots: **0001, 0002, 0003, 0008, 0029, 0639** — sparse, non-sequential, and nowhere in the ScaRdg numbering range. No shared lot strings.

2. **The string "SctLot" appears in source-system invoice IDs**, not as a canonical project token. Examples from `memo_1`:
   - `Inv.:SctLot-000032-01:Turner Excavating & Electric Inc.`
   - `Inv.:SctLot-000031-01:Turner Excavating & Electric Inc.`
   - `Inv.:SctLot-000044-01:Bob Craghead Plumbing & Heating, Inc.`
   These look like "SctLot" is an internal accounting bucket ID embedded in invoice numbering, not a Scarlet Ridge phase.

3. **Vendor / cost mix is custom-build / scattered-construction, not master-planned.** Top vendors include Bob Craghead Plumbing, Five Star Building Products, Turner Excavating, Top Notch Framing, CMC Ready Mix, Carpet Diem, Lassen Inc — single-house construction trades. One memo says `"Crew payoff of house"`. Lot 0008 alone has 501 rows / $4.0M (a single-house cost basis is plausible at that scale). This pattern is consistent with **scattered-lot or custom-spec home construction**, not subdivision lots in a Scarlet Ridge phase.

4. **SctLot has its own multi-year history**: $6.55M, 1,130 rows, 2018-2025, growing year-over-year ($330K in 2018 → $2.4M in 2024 → $1.1M in 2025). It is not a one-off rollup or a transient bucket.

5. **DR has zero rows mentioning Scarlet, Scenic, Sct, or SctLot in `project_name`/`project`/`memo_1`** — SctLot is a post-2018 phenomenon. If it were a phase of Scarlet Ridge that pre-dated 2018, we'd expect at least one DR-era row using the same lot numbers. There are none.

6. **Likely interpretation**: `Sct` = "Scattered" (industry shorthand for non-subdivision lots BCPD acquires individually). The 6 lot codes are then internal IDs for individual scattered properties. Lot 0639 (the outlier) is consistent with a high-numbered scattered-acquisition ID, not a Scarlet Ridge phase lot.

### Confidence
**Medium-high** that SctLot ≠ Scarlet Ridge (the lot-number disjointness, vendor mix, and memo evidence are all consistent). **Low** confidence in the specific name "Scattered Lots" — source-owner should confirm the actual program/category. **Should NOT promote SctLot's canonical_project mapping above `inferred-unknown` in v0.**

### Impact on lot-level cost
$6.55M / 1,130 rows. If W1's mapping (canonical_project = Scarlet Ridge) is preserved into v2, those $6.55M attach to Scarlet Ridge as project-level cost — inflating Scarlet Ridge's cost basis by ~46% (Scarlet Ridge's main project ScaRdg sums to $14.1M). At lot grain, the SctLot rows can never match Scarlet Ridge inventory (no shared lot numbers), so they'd remain unmatched in v0 — the project-grain inflation is the silent error.

### Can A_integrator proceed with W2/W3?
**Yes, after one fix.** In `vf_lot_code_decoder_v0.csv`, change the `SctLot` row's `canonical_project` from `Scarlet Ridge` to `Scattered Lots` (or another inferred-unknown holder), and keep `decoder_pattern='no-decoder'`, `confidence='inferred'`, `validated_by_source_owner=False`. W2/W3 can then proceed treating SctLot as a project-grain-only feed with no inventory lot attachment until source-owner confirms.

---

## Q5 — Range entries (`0009-12`, `0172-175`, `3001-06`, …)

### Recommendation
**For v0 / current pass: keep range entries at project + phase grain, do NOT expand. For v1: expand into N synthetic per-lot rows with equal split, marked with a provenance flag. NEVER exclude — these are real shared-shell costs and excluding would understate lot cost basis by ~$45.7M.**

### Evidence

The range pattern is broader than W1's narrative suggested. I scanned the entire VF feed for lot strings matching `^\d{4}-\d{2,3}$`:

| VF project | range rows | range $ | top lot range | typical range size |
|---|---:|---:|---|---:|
| MCreek | 1,416 | $14.96M | `0606-11` (76 rows) | 4-6 lots |
| PWFT1 | 1,114 | $15.19M | `3230-35` (63 rows) | 4-6 lots |
| HarmTo | 568 | $5.51M | `0009-12` (70 rows) | 4-6 lots |
| SaleTT | 493 | $5.26M | `0111-114` (73 rows) | 4 lots |
| SaleTR | 283 | $3.41M | `0053-56` (46 rows) | 4 lots |
| WilCrk | 82 | $0.86M | `0001-06` (31 rows) | 6 lots |
| LomHT1 | 59 | $0.57M | `0208-211` (21 rows) | 4 lots |
| ArroT1 | 5 | $0.003M | `0162-167` (3 rows) | 6 lots |
| **Total** | **4,020** | **$45.75M** | — | mean 5.0, max 8 |

(W1 reported 1,893 range rows across HarmTo + LomHT1 + PWFT1 + ArroT1; the other ~2,127 rows are in MCreek / SaleTT / SaleTR / WilCrk — projects W1 considered out-of-scope for the decoder pass but which still carry range entries in the GL.)

**Range size distribution**: 4 lots (1,654 rows), 5 lots (564), 6 lots (1,801), 8 lots (1). Mean 5.0. Always more than 1, never a typo of a single lot.

**Memo-1 strongly supports "shell allocation" interpretation**: the most frequent memos are literally `"shell"` (34 rows), `"shell allocation"` (31), `"Shell allocation"` (10). The rest are dominated by:
- design / engineering vendors (`150 Architecture Inc.`, `MB Design Group, LLC`, `LEI Consulting Engineers`, `Trane Engineering, P.C.`)
- shared-infrastructure / commercial-line construction (`Cooper Con, LLC` for `COMM-LINES`, `Boss Holdings, Inc.`, `Lassen, Inc.`, `Westroc, Inc.`)
- utility infra (`Rocky Mountain Power`, `Fields Brothers Drywall`, `Palafox Framing` — services that span multiple units)

This is the standard pattern for **shell-of-house cost spread across the units in a townhome building**, plus **shared infrastructure cost** that genuinely cannot be attributed to a single physical lot.

**Per-row dollar magnitude**: median $3,304, mean $11,381, max $164K. These are real cost line items — not summary buckets. Each line item is one shared invoice that legitimately spans 4-8 lots.

**Per-range total**: top entries like `PWFT1 / 3159-64` total $858K across 60 rows (~$14K avg per row, ~$143K per implied lot) — exactly the magnitude of one townhome-shell allocation per unit.

### Treatment-option analysis

| option | impact | recommendation |
|---|---|---|
| **Leave as summary-level** | Project + phase rollups stay correct; lot rollups miss $45.75M (~13% of total VF capitalized cost) | **YES for v0** (this pass) |
| **Expand into N synthetic per-lot rows, equal split** | Preserves $45.75M at lot grain; consumers can flag synthetic rows via provenance column | **YES for v1** (next pass) — but requires source-owner sign-off on equal-split vs other allocation methods |
| **Equal split across lots** (same as expansion) | — | (same as above) |
| **Exclude from lot-level cost** | Loses $45.75M permanently. Bad. | **NO** |
| **Keep for project/phase rollup only** | Same as "leave as summary-level" | **YES for v0** |

### Confidence
**High** that range entries represent shared-shell / shared-infra costs (memo evidence + range size + per-unit dollar magnitude all align). **Medium** that equal split is the right allocation method — source-owner may instead want square-foot-weighted, sales-price-weighted, or per-unit-fixed split. The choice of allocation is a **finance policy decision**, not a data decision.

### Impact on lot-level cost

| scope | $ at risk | notes |
|---|---:|---|
| All VF range rows | $45.75M | Cumulative shell + shared-infra cost across all multi-lot allocations 2018-2025 |
| Most-affected project: PWFT1 (Parkway Townhomes Phase 1) | $15.19M | Townhome project — large shell-allocation footprint |
| Most-affected project: MCreek (Mill Creek) | $14.96M | Out of W1 scope; should be folded into v1 |
| HarmTo | $5.51M | Harmony townhomes |
| Other townhome / multifamily projects | $9.69M | SaleTT, SaleTR, WilCrk, LomHT1, ArroT1 |

For BCPD Operating State v2:
- **v0 (this pass)**: report lot-level cost basis as VF rows that decode AND have a numeric (single) lot. Range entries are reported at project + phase grain only, with an explicit `n_unattributed_shell_rows` and `unattributed_shell_dollars` field per project in the quality report.
- **v1 (next pass)**: after source-owner confirms allocation method, expand range entries into per-lot synthetic rows. Mark with `cost_attribution_method='range_equal_split'` (or whatever is signed off) so consumers can include / exclude / re-allocate.

### Can A_integrator proceed with W2/W3?
**Yes for v0** — keep range entries at project/phase grain, do not attempt expansion. **Required**: the v2 quality report must surface unattributed shell-cost dollars per project, otherwise the lot-level rollup will silently look ~13% lighter than it should.

---

## Cross-cutting summary table for A_integrator

| question | proceed with W2/W3? | rule change required? | confidence | $ at risk |
|---|---|---|---|---:|
| Q1 Harm3 phase routing | YES | None to the rule itself; require 3-tuple join key downstream | high (no-other-signal) / medium (cutoffs) | ~$30M+ |
| Q2 AultF B-suffix overlap | YES, with rule revision | YES — revise: AultF B-suffix → all B1, PWFS2 B-suffix → all B2 (already disjoint in data) | high | $4.0M |
| Q3 Harmony MF1 vs B1 | YES, with 3-tuple join key | None to the rule; require 3-tuple downstream | high (data) / medium (source-tagging discipline) | $6.75M (silent if 2-tuple) |
| Q4 SctLot | YES, with mapping fix | YES — change `canonical_project` from `Scarlet Ridge` to `Scattered Lots` (inferred-unknown); keep `no-decoder` | medium-high | $6.55M (project-grain inflation) |
| Q5 range entries | YES for v0 | None for v0; defer expansion to v1 with source-owner sign-off | high (interpretation) / medium (allocation method) | $45.75M (lot-grain undercoverage) |

---

## Hard guardrails honored

- ✅ Did not modify `data/staged/vf_lot_code_decoder_v0.csv`.
- ✅ Did not modify `data/reports/vf_lot_code_decoder_report.md`.
- ✅ Did not modify any `output/operating_state_v2_*` artifact.
- ✅ Did not modify `staged_gl_transactions_v2.{csv,parquet}`.
- ✅ Did not modify `staged_inventory_lots.parquet`.
- ✅ Did not promote any inferred rule to high confidence — every rule change recommendation is contingent on source-owner sign-off (which is W1's responsibility, not Terminal B's).
- ✅ Did not edit any other terminal's scratch files.
- ✅ All numbers above were re-derived directly from `staged_gl_transactions_v2.parquet` and (for Q3) `staged_inventory_lots.parquet`. Did not copy any number from W1's report without re-verification.
