# Crosswalk Plan v0

**Owner**: Terminal A (integrator)
**Status**: built (post-worker findings)
**Last updated**: 2026-05-01
**Companion**: `docs/ontology_v0.md`, `docs/field_map_v0.csv`

The four canonical entities (`legal_entity`, `project`, `phase`, `lot`) are
referred to by **different vocabularies in different source systems**. This
document is the single source of truth for how those vocabularies map to the
canonical names used in the v0 outputs.

The actual crosswalk tables are under `data/staged/`:
- `staged_entity_crosswalk_v0.{csv,parquet}`
- `staged_project_crosswalk_v0.{csv,parquet}`
- `staged_phase_crosswalk_v0.{csv,parquet}`
- `staged_lot_crosswalk_v0.{csv,parquet}`
- `staged_entity_project_crosswalk_v0.{csv,parquet}` (BCPD-scoped combined; satisfies guardrail prereq #2)

Each row carries: `source_system`, `source_value`, `canonical_*`, `confidence`,
`evidence_file`, `notes`.

---

## 1. Confidence vocabulary

| value | meaning |
|---|---|
| `high` | Identity mapping or unambiguous resolution corroborated by multiple sources or a clear naming convention. |
| `medium` | Single typo or short abbreviation requiring small inference (e.g. `Aarowhead → Arrowhead Springs`, `WR → White Rail`). |
| `low` | Single-source historical (pre-2018) communities not in the active 16-project BCPD universe. |
| `unmapped` | Cannot resolve. Preserved as raw with empty canonical_value. Examples: `SPEC`, `ML`, `TO BE`, `P2 14`. |

Worst-link rule: a canonical row's `source_confidence` is the **minimum** of
all contributing-field confidences. This prevents one weak link from being
washed out by others.

---

## 2. Legal-entity crosswalk

GL `entity_name` is the authoritative source for entity-level identity. Other
sources (2025Status `HorzCustomer`, Lot Data `HorzSeller`, QB-register
filename) map to canonical entities through this crosswalk.

| canonical_entity | role | in BCPD v2 scope? |
|---|---|---|
| BCPD | Building Construction Partners, LLC — vertical builder + horizontal developer (BCPD subset) | ✅ |
| BCPBL | BCP Ben Lomond — Lomond Heights horizontal developer | ✅ (linked via Lot Data.HorzSeller) |
| ASD | Arrowhead Springs Developer — horizontal | ✅ |
| BCPI | BCP Investor — small horizontal | medium-confidence; included |
| Hillcrest | Hillcrest Road at Saratoga, LLC | ❌ (frozen 2017-02; org-wide blocker) |
| Flagship Belmont | Flagship Belmont Phase two LLC | ❌ (frozen 2017-02; org-wide blocker) |
| Lennar | Third-party vertical-builder customer | ❌ |
| EXT | External / commercial / church (mixed) | ❌ |

---

## 3. Project crosswalk

Each project source uses its own vocabulary. The canonical project name is the
one used in `Collateral Dec2025 - 2025Status.csv` and `Lot Data.csv` — which
already lines up with v1 ontology — supplemented by historical names for
pre-2018 communities.

### Active BCPD projects (16 from 2025Status; +1 from Collateral Report)

`Ammon, Arrowhead Springs, Cedar Glen, Eagle Vista, Eastbridge, Erda, Harmony,
Ironton, Lewis Estates, Lomond Heights, Meadow Creek, Parkway Fields,
Salem Fields, Santaquin Estates, Scarlet Ridge, Westbridge, Willowcreek`

(Meadow Creek appears in Collateral Report but not 2025Status — confidence high.)

### GL DataRails 38-col `project_code` (BCPD-relevant subset)

These are **alphanumeric short codes** (not the 8-digit numeric codes the
planning doc anticipated). Mapping to canonical:

| DR code | canonical project | scope |
|---|---|---|
| `3AHptn` | Hamptons | BCPD historical |
| `Bdgprt` | Bridgeport | BCPD historical |
| `BeckP` | Beck Pines | BCPD historical |
| `Cscade` | Cascade | BCPD historical |
| `CottFH` | Cottages at Fox Hollow | BCPD historical |
| `LeChem` | LeCheminant | BCPD historical |
| `Miller` | Miller Estates | BCPD historical |
| `Prksde` | Parkside | BCPD historical |
| `SilvLk` / `SilvTh` / `SL14C` / `SL14S` / `SL15C` / `SL15S` / `SL15T` | Silver Lake (collapses) | BCPD historical |
| `Spring` / `SprCls` | The Springs / The Springs Cluster | BCPD historical |
| `SprnCk` | Spring Creek Ranch | BCPD historical |
| `Vintar` | Villages at Vintaro | BCPD historical |
| `Westbk` | Westbrook | BCPD historical |
| `WhtRl` | White Rail | BCPD historical |
| `WIllis` | Willis | BCPD historical |
| `Willws` | Willows | BCPD historical |
| `HIllcr` / `HllcrM` / `HllcrN` / `HllcrO` / `HllcrP` / `HllcrQ` / `HllcrR` / `HllcrS` | Hillcrest (collapses) | **Hillcrest entity — not BCPD** |
| `Blmont` | Belmont Plaza | **Flagship Belmont entity — not BCPD** |

### GL Vertical Financials 46-col `project_code` (BCPD only, 2018-2025)

| VF code | canonical project | scope |
|---|---|---|
| `ArroS1` / `ArroT1` | Arrowhead Springs (S1=SFR, T1=townhomes) | BCPD active |
| `AultF` | Parkway Fields (Ault Farms aka Parkway Fields) | BCPD active |
| `Harm3` / `HarmCo` / `HarmTo` | Harmony (Phase 3, Commercial, Townhomes) | BCPD active |
| `LomHS1` / `LomHT1` | Lomond Heights (S1=SFR, T1=townhomes) | BCPD active |
| `MCreek` | Meadow Creek | BCPD active (collateral-only project) |
| `PWFS2` / `PWFT1` | Parkway Fields (S2=SFR Phase 2, T1=townhomes Phase 1) | BCPD active |
| `SalemS` / `SaleTR` / `SaleTT` | Salem Fields (S=SFR, TR=townhome row, TT=townhome) | BCPD active |
| `ScaRdg` / `SctLot` | Scarlet Ridge (`SctLot` confidence=`medium` — ambiguous label) | BCPD active |
| `WilCrk` | Willowcreek | BCPD active |

**Crosswalk caveat**: VF codes encode **project + product type + sub-phase** in
a short string. `ArroS1` collapses to `Arrowhead Springs`; Phase information
must be reconstructed by joining to the inventory or Lot Data phase column on
`(canonical_project, lot)`. v0 collapses VF codes to the project level only.

### Inventory subdiv → canonical project (executed in stage)

See `staged_inventory_lots.{csv,parquet}.canonical_project` and the
`SUBDIV_TO_PROJECT` map in `financials/stage_inventory_lots.py`. Active
mappings are confidence `high` (8 mappings + Silver Lake low). Historical
CLOSED-tab subdivs (`LEC`, `WILLOWS`, `WESTBROOK`, etc.) get `low`-confidence
title-cased canonical names; unmapped subdivs (`SPEC`, `ML`, `TO BE`) preserve
empty canonical with `unmapped` confidence.

### ClickUp `subdivision` → canonical project

| ClickUp value | canonical | confidence |
|---|---|---|
| `Harmony` | Harmony | high |
| `Arrowhead` | Arrowhead Springs | high |
| `Aarowhead` / `Aarrowhead` | Arrowhead Springs | medium (typo) |
| `Park Way` | Parkway Fields | high |
| `Lomond Heights` | Lomond Heights | high |
| `Salem Fields` | Salem Fields | high |
| `Willow Creek` | Willowcreek | high |
| `Lewis Estates` | Lewis Estates | high |
| `Scarlett Ridge` | Scarlet Ridge | medium (typo) |
| `P2 14` | (unmapped) | unmapped |

---

## 4. Phase crosswalk

Phase normalization rule (per v1 `pipelines/config.py:normalize_phase`):

1. Coerce to string, strip leading/trailing whitespace.
2. Collapse internal runs of whitespace to a single space.
3. Apply `PHASE_NAME_OVERRIDES` (currently empty in v1; v0 introduces no new overrides).

`canonical_phase_id = f"{canonical_project}::{normalized_phase}"`

Confidence rules (applied at `canonical_phase` rollup):

| sources providing the phase | confidence |
|---|---|
| 2 or 3 of {inventory, Lot Data, 2025Status} | `high` |
| 1 of those | `medium` |
| ClickUp only (or none of the three) | `low` |

GL **does not** carry phase grain for BCPD scope — `phase` column is 0% filled
across DR-38, VF-46, and QB-12. Phase rollups for cost MUST come from
inventory + allocation + ClickUp, joined via `canonical_lot_id`.

---

## 5. Lot crosswalk

Lot normalization rule (used by `measure_join_coverage_v0._norm_lot`):

```
strip whitespace
strip trailing ".0"   (float-coerced ints)
strip leading zeros from numeric prefix   (preserves alpha suffix)
```

`canonical_lot_id = blake2s_8(f"{canonical_project}|{canonical_phase}|{canonical_lot_number}")`

(Implemented in `financials/stage_inventory_lots.py:make_lot_id`.)

### Known lot-encoding mismatches

GL VF `lot` values for some projects encode phase+lot in a single 4-digit
string (e.g., Harmony VF lot `1034` does **not** correspond to inventory
Harmony lot `1034` — it likely encodes Harmony Phase 1 Lot 34). v0 normalizer
does not decode this; coverage drops as a result.

**Decoded matches (work cleanly with v0 normalizer)**:
- Salem Fields: 100% inventory→GL lot match
- Willowcreek: 100% inventory→GL lot match
- Scarlet Ridge: 90.9%
- Arrowhead Springs: 65%
- Parkway Fields: 61.5%
- Harmony: 53.7% (impacted by Harm3/HarmCo/HarmTo phase encoding)
- Lomond Heights: 43.9% (impacted by LomHS1/LomHT1 phase encoding)

**Zero matches**:
- Lewis Estates: no GL data at all (no Collateral Report row, no allocation workbook entry — confirmed structural gap)

A v1 follow-up should add a phase-aware lot decoder that maps GL VF
4-digit-prefix lots to their inventory equivalents.

---

## 6. Crosswalk → canonical-table flow

```
sources → crosswalks → canonical_*

  staged_gl_transactions_v2 ─┐
  staged_inventory_lots ─────┼── staged_*_crosswalk_v0 ──── canonical_legal_entity
  staged_clickup_tasks ──────┤                              canonical_project
  Collateral / Lot Data ─────┤                              canonical_phase
                             │                              canonical_lot
                             └────                          canonical_account
                                                            canonical_cost_category
```

Every canonical row carries `source_confidence` (worst-link of contributing
field confidences) so consumers can filter by quality.

---

## 7. What this doc deliberately does NOT do

- Does not enumerate every historical lot — that lives in
  `data/staged/staged_lot_crosswalk_v0.{csv,parquet}` (14,537 rows).
- Does not implement the phase-aware lot decoder; v0 collapses VF codes to
  the project level and leaves phase to be derived from inventory.
- Does not define cost-category rules — see `docs/field_map_v0.csv` and
  `data/staged/canonical_cost_category.csv`.
