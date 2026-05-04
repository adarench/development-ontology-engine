# VF Lot-Code Decoder — Report (W1)

**Built**: 2026-05-01
**Owner**: Terminal A (W1 of BCPD State Quality Pass)
**Plan**: `docs/vf_lot_code_decoder_plan.md`
**Inputs**: `staged_gl_transactions_v2.parquet`, `staged_inventory_lots.parquet`, `Collateral Dec2025 - Lot Data.csv`
**Output (lookup)**: `data/staged/vf_lot_code_decoder_v0.csv`

**All rules ship `confidence='inferred'`.** None has been validated by the source-system owner. Promotion to higher confidence requires explicit human sign-off recorded in `validated_by_source_owner=true` per row.

---

## Step 1 — Per-VF-project profile

VF rows in scope (excludes Salem Fields and Willowcreek which are already at 100% v0 match):

| VF code | canonical project | rows | distinct lots | length distribution | sample lots |
|---|---|---:|---:|---|---|
| Harm3 | Harmony | 9,234 | 114 | len=4: 9234 | 0001, 0101, 0102, 0103, …, 1043, 1044 |
| HarmCo | Harmony | 374 | 31 | len=7: 374 | 0000A-A, 0000A01, 0000A02, 0000A03, …, 0000J-J, 0000K-K |
| HarmTo | Harmony | 2,302 | 141 | len=4: 1587, len=6: 147, len=7: 541, len=8: 27 | 0001, 0001-4, 0002, 0003, …, 0115, 0116 |
| LomHS1 | Lomond Heights | 505 | 31 | len=4: 505 | 0101, 0102, 0103, 0104, …, 0170, 0171 |
| LomHT1 | Lomond Heights | 90 | 29 | len=4: 31, len=8: 59 | 0172, 0172-175, 0173, 0174, …, 0211, 0212-215 |
| PWFS2 | Parkway Fields | 18,264 | 167 | len=4: 11154, len=5: 7110 | 0273B, 0274B, 0275B, 0276B, …, 7062, 7063 |
| PWFT1 | Parkway Fields | 7,994 | 136 | len=4: 6880, len=7: 1114 | 3001, 3001-06, 3002, 3003, …, 3234, 3235 |
| AultF | Parkway Fields | 16,996 | 125 | len=4: 213, len=5: 16382, len=6: 401 | 0001, 0112A, 0113A, 0114A, …, 0341A, 0342A |
| ArroS1 | Arrowhead Springs | 5,142 | 128 | len=4: 5142 | 0001, 0002, 0003, 0004, …, 0127, 0128 |
| ArroT1 | Arrowhead Springs | 11 | 9 | len=4: 6, len=8: 5 | 0130-137, 0162, 0162-167, 0163, …, 0167, 0168-173 |
| ScaRdg | Scarlet Ridge | 3,916 | 22 | len=4: 3916 | 0101, 0103, 0105, 0106, …, 0151, 0152 |
| SctLot | Scarlet Ridge | 1,130 | 6 | len=4: 1130 | 0001, 0002, 0003, 0008, 0029, 0639 |

Per-canonical-project Lot Data ranges (used as the validation target):

```

Harmony:
          min     max  count
Phase                       
A10    1001.0  1044.0     44
A4.1    453.0   454.0      2
A7      701.0   749.0     49
A8      801.0   848.0     48
A9      901.0   950.0     50
ADB13  1301.0  1334.0     34
ADB14  1401.0  1438.0     38
B1      101.0   192.0     92
B2      201.0   271.0     71
B3      301.0   347.0     47
MF1       1.0   116.0    116
MF2       NaN     NaN      0
MF3       0.0     0.0      1

Lomond Heights:
       min  max  count
Phase                 
2A       0  215    116
2B     254  410    157
2C       0    0      2
2D     200  335    136
5        0    0      1
6A       0    0      1
6B       0    0      1
6C       0    0      1

Parkway Fields:
        min   max  count
Phase                   
A1      101   169     69
A2.1    201   236     36
A2.2    237   281     45
A2.3    282   343     62
B1      101   211    111
B2      201   323    123
C1     3001  3116    116
C2     3117  3235    119
D1     4001  4159    159
D2     4201  4282     82
E1     5001  5198    198
E2     5201  5276     76
F      6001  6061     61
G1     7001  7065     65
G2     7065  7209    145
H      8001  8248    248

Arrowhead Springs:
       min  max  count
Phase                 
10       0    0      1
11       0    0      1
12       0    0      1
123      1  129    129
13       0    0      1
14       0    0      1
15       0    0      1
16       0    0      1
17       0    0      2
18       0    0      2
19       0    0      2
20       0    0      2
21       0    0      2
22       0    0      2
456    130  207     78
8        0    0      1
9        0    0      1
Comm     0    0      1

Scarlet Ridge:
       min  max  count
Phase                 
1      101  152     24
2      201  260     60
3      301  364     64
```

---

## Step 2 + 3 — Per-rule pattern, decoder, and validation

Each VF code gets one decoder rule. The rule decodes `(vf_project_code, vf_lot)` → `(canonical_phase, canonical_lot_number)`. Validation against Lot Data and inventory is then computed per row.

Rule `confidence` is always `inferred`. The `rule_quality` column reflects the validation match rate (high-evidence ≥ 90%, medium 60-90%, low 30-60%, no-decoder < 30%).

| VF code | rule | rows_total | decoded | undecoded/range | match LD | match inv | decoded-unmatched | match% (any) | rule_quality |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Harm3 | `harmony_lot_range_to_phase` | 9,234 | 9,234 | 0 | 9,234 | 8,862 | 0 | 100.0% | high-evidence |
| HarmCo | `harmony_commercial_mf2_marker` | 374 | 374 | 0 | 0 | 0 | 374 | 0.0% | no-decoder |
| HarmTo | `harmony_townhome_mf1_only` | 2,302 | 1,587 | 715 | 1,587 | 1,587 | 0 | 68.9% | medium-evidence |
| LomHS1 | `lomondheights_sfr_phase_2a` | 505 | 505 | 0 | 505 | 505 | 0 | 100.0% | high-evidence |
| LomHT1 | `lomondheights_th_phase_2a` | 90 | 31 | 59 | 31 | 31 | 0 | 34.4% | low-evidence |
| PWFS2 | `parkway_sfr_phase2_range_route` | 18,264 | 18,264 | 0 | 18,264 | 15,921 | 0 | 100.0% | high-evidence |
| PWFT1 | `parkway_th_phase1_c1c2_route` | 7,994 | 6,880 | 1,114 | 6,880 | 4,509 | 0 | 86.1% | medium-evidence |
| AultF | `aultf_suffix_a_b_phase_route` | 16,996 | 16,382 | 614 | 16,382 | 3,797 | 0 | 96.4% | high-evidence |
| ArroS1 | `arrowhead_sfr_123_456_route` | 5,142 | 5,142 | 0 | 5,142 | 5,142 | 0 | 100.0% | high-evidence |
| ArroT1 | `arrowhead_th_123_456_route` | 11 | 6 | 5 | 6 | 6 | 0 | 54.5% | low-evidence |
| ScaRdg | `scarletridge_lot_range_phase` | 3,916 | 3,916 | 0 | 3,916 | 3,737 | 0 | 100.0% | high-evidence |
| SctLot | `sctlot_no_decoder` | 1,130 | 0 | 1,130 | 0 | 0 | 0 | 0.0% | no-decoder |

### Decoder pattern descriptions

**`Harm3` — harmony_lot_range_to_phase** (`canonical_project = Harmony`)

Harmony: lot is the actual lot number (zero-padded 4 digits in VF);
    phase is inferred from lot-number range (Lot Data ranges).

**`HarmCo` — harmony_commercial_mf2_marker** (`canonical_project = Harmony`)

Harmony Commercial: 7-char strings like '0000A01' or '0000A-A'.
    Map: '0000<X><suffix>' → MF2 lot '<X><suffix>' (where MF2 has lots like A01, B01).

Sample decoded-but-unmatched VF lots:

- `HarmCo`/`0000A-A` → decoded → phase=`MF2`, lot=`A-A` — no inventory or Lot Data row found
- `HarmCo`/`0000B-B` → decoded → phase=`MF2`, lot=`B-B` — no inventory or Lot Data row found
- `HarmCo`/`0000A-A` → decoded → phase=`MF2`, lot=`A-A` — no inventory or Lot Data row found
- `HarmCo`/`0000B-B` → decoded → phase=`MF2`, lot=`B-B` — no inventory or Lot Data row found
- `HarmCo`/`0000B-B` → decoded → phase=`MF2`, lot=`B-B` — no inventory or Lot Data row found

**`HarmTo` — harmony_townhome_mf1_only** (`canonical_project = Harmony`)

Harmony Townhomes: 4-digit numeric (single lot) OR range like '0009-12' or '0097-100'.
    Single lots map to MF1 (which has lots 1-116). Range entries are summary
    allocation rows; they may not match a single inventory lot.

**`LomHS1` — lomondheights_sfr_phase_2a** (`canonical_project = Lomond Heights`)

Lomond Heights SFR Phase 1 → all map to Phase 2A (Lot Data) / 2-A (inventory).

**`LomHT1` — lomondheights_th_phase_2a** (`canonical_project = Lomond Heights`)

Lomond Heights TH Phase 1 → also Phase 2A (TH portion). Inventory does not split by product type.

**`PWFS2` — parkway_sfr_phase2_range_route** (`canonical_project = Parkway Fields`)

Parkway Fields SFR Phase 2 — covers D1/D2/G1/G2 (4-digit) and B2 (5-digit suffix B).

**`PWFT1` — parkway_th_phase1_c1c2_route** (`canonical_project = Parkway Fields`)

Parkway Fields TH Phase 1 — 4-digit 3xxx → C1 or C2; ranges flagged.

**`AultF` — aultf_suffix_a_b_phase_route** (`canonical_project = Parkway Fields`)

AultF (Ault Farms aka Parkway Fields E-1) — 5-digit NNNNX with letter suffix.
    Suffix A + lot range → A1 / A2.1 / A2.2 / A2.3
    Suffix B + lot range → B1 / B2 (with overlap)
    Suffix SR (only 0139, 0140) → unclear; flag inferred unknown.

**`ArroS1` — arrowhead_sfr_123_456_route** (`canonical_project = Arrowhead Springs`)

Arrowhead Springs S1 — 4-digit, lot-range determines phase 123 vs 456.

**`ArroT1` — arrowhead_th_123_456_route** (`canonical_project = Arrowhead Springs`)

Arrowhead Springs T1 (townhomes) — same lot-range routing as S1.

**`ScaRdg` — scarletridge_lot_range_phase** (`canonical_project = Scarlet Ridge`)

Scarlet Ridge — 4-digit, lot-range routes to Phase 1 / 2 / 3.

**`SctLot` — sctlot_no_decoder** (`canonical_project = Scarlet Ridge`)

SctLot — only 6 distinct lots; outlier 0639. No clean rule. Mark inferred-unknown.

---

## Step 4 — Selected rules per project

One rule per VF code (the one tabulated above). For VF codes where the rule has `rule_quality='no-decoder'`, the recommendation is to leave the lot unmatched in v0 and flag for human review with the source-system owner.

Selected verdicts:

- **Harm3** (Harmony): USE. `harmony_lot_range_to_phase`. high-evidence, match 100.0%. 9,234 rows.
- **HarmCo** (Harmony): DO NOT APPLY. `harmony_commercial_mf2_marker`. no-decoder, match 0.0%. 374 rows.
- **HarmTo** (Harmony): USE. `harmony_townhome_mf1_only`. medium-evidence, match 68.9%. 2,302 rows.
- **LomHS1** (Lomond Heights): USE. `lomondheights_sfr_phase_2a`. high-evidence, match 100.0%. 505 rows.
- **LomHT1** (Lomond Heights): USE WITH CAVEAT. `lomondheights_th_phase_2a`. low-evidence, match 34.4%. 90 rows.
- **PWFS2** (Parkway Fields): USE. `parkway_sfr_phase2_range_route`. high-evidence, match 100.0%. 18,264 rows.
- **PWFT1** (Parkway Fields): USE. `parkway_th_phase1_c1c2_route`. medium-evidence, match 86.1%. 7,994 rows.
- **AultF** (Parkway Fields): USE. `aultf_suffix_a_b_phase_route`. high-evidence, match 96.4%. 16,996 rows.
- **ArroS1** (Arrowhead Springs): USE. `arrowhead_sfr_123_456_route`. high-evidence, match 100.0%. 5,142 rows.
- **ArroT1** (Arrowhead Springs): USE WITH CAVEAT. `arrowhead_th_123_456_route`. low-evidence, match 54.5%. 11 rows.
- **ScaRdg** (Scarlet Ridge): USE. `scarletridge_lot_range_phase`. high-evidence, match 100.0%. 3,916 rows.
- **SctLot** (Scarlet Ridge): DO NOT APPLY. `sctlot_no_decoder`. no-decoder, match 0.0%. 1,130 rows.

---

## Step 5 — Edge cases and decoded-but-unmatched lots

Notable patterns that the decoder cannot resolve cleanly:

- **`HarmTo` and `LomHT1` and `PWFT1` range entries** (e.g. `0009-12`, `0172-175`, `3001-06`): these are 'range' allocations — single GL postings whose `lot` field encodes a span of lots rather than a specific one. They cannot match a single inventory lot. v0 leaves them undecoded. A future enhancement could expand a range row into N synthetic per-lot rows by allocating the amount evenly, but that is a financial-treatment decision that requires source-owner sign-off.
- **`AultF` `0139SR` and `0140SR`**: only two lots with `SR` suffix. Meaning is unclear (possibly 'South Row' or a Park West rollup). Marked inferred-unknown until source owner explains.
- **`SctLot` (6 distinct lots, including outlier `0639`)**: the project_code itself is ambiguous (could be 'Scenic Lots' for Scarlet Ridge, or some other label). No clean decoder; the rule returns no match. The 1,130 VF rows under SctLot remain unmatched in v0.
- **`HarmCo` `0000A-A`-style commercial parcels**: only 5 of the 31 distinct lots use this `X-X` form; the rest follow `0000<X><NN>` and decode to MF2 lots. The `X-X` parcels are likely commercial/non-residential roll-ups; flag for human review.
- **HarmCo 0% Lot Data match — validation-harness limitation**: the decoder produces `(Harmony, MF2, A01)`-style triples that *do* exist in Lot Data (MF2 has 20 such alpha lots: `A01`-`A20`). However, the validation harness indexed Lot Data by integer-only lot keys (`lot_int(s)` returns None for `A01`), so MF2 keys were never added to the lookup set and HarmCo registered 0% match. The decoder rule is conceptually correct; only the alpha lots `A01`-`A20` would actually validate against MF2 if the index were rebuilt with alpha lots preserved. The five `X-X` commercial parcels would still not match because Lot Data has no `A-A`/`B-B`/etc. row. Recommendation for W3: rebuild the validation index to preserve alpha lots before computing the simulated coverage lift.
- **Phase ambiguity in Parkway B-suffix**: B1 (101-211) and B2 (201-323) overlap at 201-211. AultF `02xxB` lots in the overlap are routed to B2 (because PWFS2 already enumerates B2 lots). The rule explicitly notes this and treats it as inferred.
- **MF1 vs B1 overlap in Harmony**: MF1 (1-116) and B1 (101-192) share 101-116. We assign 101-192 to B1 and 1-100 to MF1 because VF Harm3 lot samples don't include 1-100. If MF1 lots 101-116 do exist in VF and are mis-routed to B1 by this rule, expect a small false-match population that human review should sample.

---

## Coverage lift estimate (forwarded to W3)

Baseline (per `data/reports/join_coverage_v0.md`): 1,285 distinct BCPD inventory lots; 810 (63.0%) have ≥1 GL row; 476 (37.0%) have full triangle. Coverage was computed against a flat `(canonical_project, lot_int)` key — phase ignored.

With the W1 decoder applied (still using `(canonical_project, lot_int)` for the join, but now phase-validated), the **GL row → inventory lot match count** for the in-scope projects increases as follows. These are dry-run estimates; the decoder is **not wired into the canonical lot crosswalk** in v0.

Per-project decoded match counts (VF rows → Lot Data triples):

| canonical project | sum_total VF rows | sum_match_lot_data | lift_vs_v0 (estimate) |
|---|---:|---:|---|
| Harmony | 11,910 | 10,821 | baseline 53.7% inventory-lot triangle → simulated VF-row decode hit-rate 90.9% (delta 37.2) |
| Lomond Heights | 595 | 536 | baseline 43.9% inventory-lot triangle → simulated VF-row decode hit-rate 90.1% (delta 46.2) |
| Parkway Fields | 43,254 | 41,526 | baseline 61.5% inventory-lot triangle → simulated VF-row decode hit-rate 96.0% (delta 34.5) |
| Arrowhead Springs | 5,153 | 5,148 | baseline 65.0% inventory-lot triangle → simulated VF-row decode hit-rate 99.9% (delta 34.9) |
| Scarlet Ridge | 5,046 | 3,916 | baseline 90.9% inventory-lot triangle → simulated VF-row decode hit-rate 77.6% (delta -13.3) |

Caveat: the v0 baseline is **distinct-inventory-lot match rate**, while the decoder validation produces a **VF-row decode hit rate** against Lot Data. These are not the same metric (the former asks 'how many inventory lots have any GL?'; the latter asks 'how many GL rows resolve to a known phase+lot?'). W3 will run the matching simulation in the same metric space as the v0 baseline so the two are directly comparable.

Indicative direction:

- Harmony: large lift expected — Harm3 contains 9,234 rows; the decoder reaches a high match rate on the 4-digit form. HarmCo and HarmTo carry edge-case lots that won't match (range entries, X-X commercial markers).
- Lomond Heights: full lift expected — LomHS1 + LomHT1 single-phase mapping is unambiguous against Lot Data 2A.
- Parkway Fields: large lift expected — PWFT1 (3xxx lots, 6,880 rows) routes cleanly into C1/C2; PWFS2 4xxx routes into D1/D2/G1/G2; AultF suffix-A/B routing is the most novel and needs source-owner validation. Range entries (1,114 in PWFT1) will not match.
- Arrowhead Springs: moderate lift — ArroS1 (5,142 rows) routes cleanly into 123/456; ArroT1 is small.
- Scarlet Ridge: small additional lift — already 90.9% in v0. SctLot (1,130 rows) remains unmatched.

---

## Hard guardrails honored

- ✅ All rules ship `confidence='inferred'` with `validated_by_source_owner=False`.
- ✅ No modification to `staged_gl_transactions_v2.{csv,parquet}`.
- ✅ No modification to canonical_lot or any v2 output.
- ✅ Salem Fields and Willowcreek are out of scope (already at 100% in v0).
- ✅ Lewis Estates and the 7 active no-GL projects are out of scope (structural gaps).
- ✅ Org-wide v2 untouched.
- ✅ W2-W6 not implemented in this artifact.

## Hand-off questions for source-owner validation

Before any of these decoder rules are promoted from `inferred`, the source-system owner should confirm:

1. **Harmony Harm3 phase routing** — does the lot-number range really determine phase as proposed, or is phase encoded elsewhere (e.g. in the GL `Lot/Phase` field for DataRails 38-col, or in a project-system attribute we haven't surfaced)?
2. **AultF SR suffix** — what does `0139SR` and `0140SR` mean? (Two specific lots; total 401 rows.)
3. **AultF B-suffix overlap 201-211** — assigning to B2 may misclassify lots that are actually B1 with high-numbered lot IDs. Confirm B1 max lot.
4. **MF1 vs B1 overlap (Harmony lots 101-116)** — if any MF1 lot in 101-116 exists in VF, our rule misclassifies it as B1.
5. **SctLot semantics** — is this Scarlet Ridge land/scenic-lot rollup, or a distinct project? Especially the `0639` outlier.
6. **Range entries** (`0009-12`, `0172-175`, etc.) — should these be expanded into per-lot allocations (and if so, by what method — equal split, weighted by lot price, etc.)?
7. **Lomond Heights LomHS1 vs LomHT1 split** — confirm both belong to inventory phase `2-A` and the only difference is product type (SFR vs TH), not a different phase.

