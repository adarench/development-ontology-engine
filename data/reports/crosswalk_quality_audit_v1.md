# Crosswalk Quality Audit v1

**Built**: 2026-05-01
**Author**: Terminal A (W2 of BCPD State Quality Pass)
**Inputs**:
- `data/staged/staged_entity_crosswalk_v0.csv` (13 rows)
- `data/staged/staged_project_crosswalk_v0.csv` (142 rows)
- `data/staged/staged_phase_crosswalk_v0.csv` (385 rows)
- `data/staged/staged_lot_crosswalk_v0.csv` (14,537 rows; aggregated)
- `data/staged/vf_lot_code_decoder_v1.csv` (17 rows; W1.5 output)

**Confidence policy**: `inferred` is preserved as-is. No mapping is promoted to `high` without source-owner evidence. The audit tier reflects how a mapping should be USED, not what its confidence label IS — a mapping can be `inferred` and still safe for simulation.

---

## Audit-tier definitions

| tier | meaning | use in v2.1? |
|---|---|---|
| **high-confidence direct** | Identity mapping or unambiguously corroborated by ≥2 sources. | yes — use for cost rollups and lot-grain joins |
| **inferred but safe for simulation** | Inferred rule with strong evidence (≥90% match rate, no contradicting signal). | yes for v2.1 with `confidence='inferred'`; promote only after source-owner sign-off |
| **project/phase-only** | Mapping is correct at project (or project+phase) grain but not at lot grain. | use for project rollups; exclude from lot-grain denominators |
| **summary/range row** | Source row aggregates multiple lots (range entry, shared shell). | keep dollars at project+phase grain; do not feed lot-level cost |
| **commercial/non-lot** | Source row is a commercial parcel or non-lot inventory item. | exclude from canonical lot crosswalk; track separately |
| **unresolved** | No mapping; source value is preserved raw. | flag for source-owner review |
| **unsafe for lot-level cost** | Mapping is too low-confidence (typically pre-2018 historicals). | use only for historical/diagnostic queries |

---

## Per-crosswalk roll-up

Counts (rows in each crosswalk, by audit tier):

```
audit_tier     commercial/non-lot  high-confidence direct  inferred but safe for simulation  project/phase-only  project/phase-only (Scattered Lots; v1 fix)  summary/range row  unresolved  unsafe for lot-level cost
level                                                                                                                                                                                                                 
entity                          0                       9                                 1                   0                                            0                  0           0                          3
lot                             0                       7                                 2                   0                                            0                  0           1                          1
phase                           0                     280                                29                   0                                            0                  0           0                         76
project                         0                     122                                 6                   0                                            1                  0           4                          9
vf_decoder_v1                   1                       0                                 8                   5                                            0                  3           0                          0
```

---

## Entity crosswalk (13 rows)

All entity mappings are `high` or `medium` confidence. No structural blockers at the entity level. Out-of-scope entities (Hillcrest, Flagship Belmont, Lennar, EXT) carry their own canonical values and are correctly partitioned.

| source_system | source_value | canonical_entity | tier |
|---|---|---|---|
| gl_v2.entity_name | Building Construction Partners, LLC | BCPD | high-confidence direct |
| gl_v2.entity_name | Hillcrest Road at Saratoga, LLC | Hillcrest | high-confidence direct |
| gl_v2.entity_name | Flagship Belmont Phase two LLC | Flagship Belmont | high-confidence direct |
| 2025Status.HorzCustomer | BCP | BCPD | high-confidence direct |
| 2025Status.HorzCustomer | Lennar | Lennar | high-confidence direct |
| 2025Status.HorzCustomer | EXT | EXT | unsafe for lot-level cost |
| 2025Status.HorzCustomer | EXT-Comm | EXT | unsafe for lot-level cost |
| 2025Status.HorzCustomer | Church | EXT | unsafe for lot-level cost |
| LotData.HorzSeller | BCPD | BCPD | high-confidence direct |
| LotData.HorzSeller | BCPBL | BCPBL | high-confidence direct |
| LotData.HorzSeller | ASD | ASD | high-confidence direct |
| LotData.HorzSeller | BCPI | BCPI | inferred but safe for simulation |
| qb_register_12col.source_file | Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv | BCPD | high-confidence direct |

---

## Project crosswalk — high-impact unresolved/medium rows

Rows ordered by GL-rows-touched (only entries with GL exposure shown):

| source_value | canonical | tier | GL rows | $ touched | notes |
|---|---|---|---:|---:|---|
| `SctLot` | Scarlet Ridge | project/phase-only (Scattered Lots; v1 fix) | 1,130 | $6,553,893 | 2018-2025 era code; product-type variants (S1/T1/S2/T2/Co/To) collapse to one project |

Top notes:

- **`SctLot`** appears multiple times across crosswalks. v1 fix moves it to canonical_project='Scattered Lots'; remains `inferred-unknown`.
- **Hillcrest variants** (`HIllcr`, `HllcrM`, `HllcrN`, `HllcrO`, `HllcrP`, `HllcrQ`, `HllcrR`, `HllcrS`) all collapse cleanly to `Hillcrest` with high confidence — out of scope for BCPD v2 but logged for Track B.
- **Pre-2018 inventory subdivs** (`COUNTRY VIEW`, `JAMES BAY`, `SPRING LEAF`, `ANTHEM WEST`, etc.) carry `low` confidence — these are historical CLOSED-tab lots; safe to leave as-is for BCPD v2 (they're outside the active 16-project universe).

---

## Phase crosswalk — top patterns

Counts by tier:

```
audit_tier
high-confidence direct              280
inferred but safe for simulation     29
unsafe for lot-level cost            76
```

Phase mappings are largely identity-or-strip-whitespace; only mismatches across source vocabularies need attention. v1 fix list:

- `Lomond Heights / 2-A` (inventory) ↔ `2A` (Lot Data) — single normalization rule
- `Arrowhead Springs / 1,2,3` (inventory) ↔ `123` (Lot Data) — single normalization rule
- `Arrowhead Springs / 4,5,6` (inventory) ↔ `456` (Lot Data) — single normalization rule
- `Harmony / MF 1` (inventory) ↔ `MF1` (Lot Data) — whitespace strip only
- `Harmony / 14, 10, 9, 8` (inventory) → `ADB14, A10, A9, A8` (Lot Data) — already in v0 normalizer

---

## Lot crosswalk — aggregate quality

Rows by source × tier:

| source_system | tier | rows |
|---|---|---:|
| LotData | high-confidence direct | 3,627 |
| 2025Status | high-confidence direct | 2,806 |
| inventory | unsafe for lot-level cost | 2,556 |
| clickup | high-confidence direct | 1,568 |
| inventory | high-confidence direct | 1,311 |
| gl_v2.vertical_financials_46col | high-confidence direct | 1,300 |
| 2025Status | high-confidence direct | 821 |
| gl_v2.datarails_38col | high-confidence direct | 517 |
| clickup | inferred but safe for simulation | 21 |
| gl_v2.vertical_financials_46col | inferred but safe for simulation | 6 |
| inventory | unresolved | 4 |

---

## VF decoder v1 — recommendation summary

| virtual code | canonical project | tier | rows | recommendation |
|---|---|---|---:|---|
| Harm3 | Harmony | inferred but safe for simulation | 9,234 | safe for v2.1 simulation as inferred mapping |
| HarmCo_residential | Harmony | inferred but safe for simulation | 169 | safe for v2.1 simulation as inferred mapping |
| HarmCo_commercial | Harmony | commercial/non-lot | 205 | non-lot inventory only; do not feed lot-level cost |
| HarmTo | Harmony | summary/range row | 2,302 | safe for v2.1 simulation as inferred mapping |
| LomHS1 | Lomond Heights | inferred but safe for simulation | 505 | safe for v2.1 simulation as inferred mapping |
| LomHT1 | Lomond Heights | summary/range row | 90 | safe for v2.1 simulation as inferred mapping |
| PWFS2 | Parkway Fields | inferred but safe for simulation | 18,264 | safe for v2.1 simulation as inferred mapping |
| PWFT1 | Parkway Fields | summary/range row | 7,994 | safe for v2.1 simulation as inferred mapping |
| AultF | Parkway Fields | inferred but safe for simulation | 16,996 | safe for v2.1 simulation as inferred mapping |
| ArroS1 | Arrowhead Springs | inferred but safe for simulation | 5,142 | safe for v2.1 simulation as inferred mapping |
| ArroT1 | Arrowhead Springs | inferred but safe for simulation | 11 | safe for v2.1 simulation as inferred mapping |
| ScaRdg | Scarlet Ridge | inferred but safe for simulation | 3,916 | safe for v2.1 simulation as inferred mapping |
| SctLot | Scattered Lots | project/phase-only | 1,130 | project-grain only; do not feed lot-level cost |
| MCreek | Meadow Creek | project/phase-only | 7,418 | project+phase grain; do not feed lot-level cost; preserve dollars in summary rollup |
| SaleTT | Salem Fields | project/phase-only | 2,326 | project+phase grain; do not feed lot-level cost; preserve dollars in summary rollup |
| SaleTR | Salem Fields | project/phase-only | 938 | project+phase grain; do not feed lot-level cost; preserve dollars in summary rollup |
| WilCrk | Willowcreek | project/phase-only | 264 | project+phase grain; do not feed lot-level cost; preserve dollars in summary rollup |

---

## High-impact join-fix candidates (forwarded to W3)

Each candidate fix carries a baseline match rate, a simulated post-fix match rate, an effort estimate, and a confidence level. W3 takes this list and runs the dry-run simulation.

Top fixes (full table in `data/staged/high_impact_join_fixes.csv`):

| fix | applies to | effort | confidence |
|---|---|---|---|
| **vf_decoder_v1_apply** — Apply v1 decoder rules to GL VF (3-tuple join) | Harm3, HarmCo_residential, HarmTo, LomHS1/T1, PWFS2, PWFT1, AultF, ArroS1/T1, ScaRdg | M | high (rule data evidence) |
| **aultf_b_to_b1_correction** — Correct AultF B-suffix from B2 → B1 | AultF B-suffix lots 0127B-0211B (1,499 rows / $4.0M) | S | high (Terminal B Q2 empirical) |
| **sctlot_separate_project** — Separate SctLot from Scarlet Ridge | SctLot 1,130 rows / $6.55M | S | medium-high (Terminal B Q4) |
| **harmco_split** — Split HarmCo into residential MF2 + commercial X-X | 169 residential + 205 commercial | S | high (Terminal C Q2) |
| **range_rows_keep_at_phase** — Treat range rows at project+phase grain | 4,020 rows / $45.75M across 8 VF codes | S | high (Terminal B Q5) |
| **clickup_subdivision_typo_cleanup** — Apply ClickUp subdivision typo crosswalk | Aarowhead/Aarrowhead → Arrowhead Springs; Scarlett Ridge → Scarlet Ridge; Park Way → Parkway Fields | S | high |
| **inventory_phase_normalize** — Normalize inventory phase aliases (`2-A` → `2A`, `MF 1` → `MF1`, etc.) | Lomond Heights, Harmony, Arrowhead Springs | S | high |
| **phase_aware_lot_decoder_clickup** — Apply phase-aware decoding to ClickUp lot_num | 1,177 lot-tagged tasks | S | low (no clear gap to fix) |

---

## Recommendations

**Tier-1 fixes (apply in v2.1 simulation; safe)**:

1. `vf_decoder_v1_apply` — apply v1 decoder rules to GL VF using a 3-tuple join. Lifts coverage substantially for Harmony, Lomond Heights, Parkway Fields, Arrowhead Springs.
2. `aultf_b_to_b1_correction` — corrects $4M routing error. Already in v1 decoder.
3. `sctlot_separate_project` — removes $6.55M silent inflation from Scarlet Ridge.
4. `harmco_split` — clean residential vs commercial separation. Already in v1 decoder.
5. `range_rows_keep_at_phase` — surface $45.75M unattributed-shell dollars at project+phase grain.

**Tier-2 fixes (already applied in v0 or low marginal value)**:

6. `inventory_phase_normalize` — small additional lift; mostly handled in v1 decoder via PHASE_INV_TO_LD.
7. `clickup_subdivision_typo_cleanup` — already applied in v0.

**Source-owner validation needed before promoting any rule above `inferred`**:

- Harm3 lot-range routing (Terminal B Q1)
- AultF SR-suffix meaning (Terminal C Q1)
- HarmCo X-X commercial parcels (Terminal C Q2; ontology decision)
- SctLot canonical name and program identity (Terminal B Q4)
- Range-entry allocation method for v2 expansion (Terminal B Q5)

---

## Hard guardrails honored

- ✅ No confidence promoted above `inferred`.
- ✅ No modification to staged_gl_transactions_v2 or any v2 output.
- ✅ Org-wide v2 untouched.
- ✅ Audit tier classifies USAGE; does NOT change the underlying confidence label on any crosswalk row.
