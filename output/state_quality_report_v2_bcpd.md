# BCPD Operating State v2 — State Quality Report

_Generated: 2026-05-01_
_Schema: `operating_state_v2_bcpd`_
_Guardrail: ✅ GREEN_

Per-canonical-field fill rate, confidence distribution, known gaps, and
safe-to-use flag. Companion to `output/operating_state_v2_bcpd.json`.

---

## Coverage headline

- **Lots in canonical body**: 5,366 across 25 high-confidence BCPD-relevant projects
- **High-confidence lots**: 2,797 (52.1%) — BCPD-built per HorzCustomer=BCP
- **Medium-confidence lots**: 755 (14.1%)
- **Low-confidence lots**: 1,814 (33.8%) — historical CLOSED-tab lots

- **Inventory base for join coverage**: 1,285 distinct (canonical_project, lot_num) at project_confidence=high
- **With ≥1 GL row**: 810 (63.0%)
- **With ≥1 ClickUp lot-tagged task**: 811 (63.1%)
- **Full triangle (GL ∧ ClickUp)**: 476 (37.0%)

---

## Per-field quality

| canonical_field | fill rate (BCPD canonical) | confidence | safe to use? | known gap |
|---|---|---|---|---|
| `canonical_entity` | 100% | high | yes | n/a |
| `canonical_project` | 100% | high (high-conf body) | yes | low-conf historicals (1,814 rows) carry it but are off the active universe |
| `canonical_phase` | ~100% | high if 2+ ops sources; medium if 1 | mostly yes | empty in GL — derived from inventory + Lot Data + 2025Status |
| `canonical_lot_id` | 100% | derived; deterministic | yes | hash collisions are negligible (8-byte digest) |
| `canonical_lot_number` | 100% | high | yes | format varies across sources; v0 normalizer strips zeros + .0 |
| `lot_status` | 100% (inventory rows) | high | yes | only set for lots in inventory; non-inventory lots have null |
| `current_stage` | ~98% (Lot Data BCPD) | high if waterfall converges | yes | requires Lot Data row; lots only in inventory have null |
| `completion_pct` | ~75% (PROSPECT and CLOSED return null in v1 mapping) | inherits current_stage | yes | inherent v1 design |
| `posting_date` | 100% (GL) | high | yes | required for any FinancialTransaction |
| `amount` | 100% (GL) | high (after DR dedup) | yes after dedup | DR raw is 2.16× multiplied — see guardrail |
| `account_code` | 100% (GL) | high (DR/VF), medium (QB) | yes within source_schema | QB chart differs from DR/VF |
| `account_name` | 53.8% (DR) / 100% (VF) / 100% (QB) | high | yes | DR has many blank account_names |
| `cost_category` | rule-derived; 9 categories | high for explicit; medium for derived | yes | v0 starter mapping |
| `actual_cost` (rollup) | varies by project | high (VF), high after dedup (DR) | yes within era | 2017-03 → 2018-06 gap; Lewis Estates 0% |
| `budget_cost` | LH + PF only (~26 phase rows) | high for those | yes for LH + PF | other projects unsourced |
| `remaining_cost` | derived | inherits min(budget, actual) | yes | only meaningful where budget is populated |
| `collateral_value` | 9 of 16 active projects (41 rows) | high | yes | 7 projects + Lewis Estates have no row |
| `collateral_bucket` | derived from current_stage | inherits | yes | requires current_stage |
| `inventory_status` | 100% (inventory rows) | high | yes | alias for lot_status |
| `sale_date` | 8.5% (INVENTORY tab) / mixed (CLOSED tab) | high in INVENTORY | yes | sparse in INVENTORY because most active lots are unsold |
| `closing_date_actual` | 1,760 of 3,872 inventory rows | high | yes | only set where Closing Date ≤ as_of |
| `closing_date_projected` | 1,134 of 3,872 + ESTIMATED CLOSING from CLOSINGS | medium | yes for planning | up to 2027-06-07 in source |
| `permit_pulled_date` | 60.9% (INVENTORY) | high | yes | n/a |
| `sales_price` | 11.6% (INVENTORY) | high | yes | sparse because most active lots are unsold |
| `deposit` | 8.4% (INVENTORY) | high | yes | n/a |
| `margin_pct` | 7.6% (INVENTORY) | high | yes | not on CLOSED tab |
| `buyer` | 65.3% (INVENTORY) | high | yes | SPEC/MODEL placeholders included |
| `clickup_status` | within lot-tagged subset only (1,177) | high | yes (within subset) | 79% of ClickUp tasks not lot-tagged |
| `walk_date` | 1.78% (lot-tagged) | medium (sparse) | yes when present | mostly null |
| `actual_c_of_o` | 22.77% (lot-tagged) | medium | yes | n/a |
| `due_date` | 45.54% (lot-tagged) | medium | yes (operational) | not always reflective of true close target |
| `source_file`, `source_row_id`, `as_of_date` | 100% | provenance | yes | n/a |
| `source_confidence` | 100% | derived (worst-link) | yes | filter on this |

---

## Per-project quality

| project | active 2025Status lots | inventory lots | GL VF rows | GL DR rows (dedup) | ClickUp lot-tagged | confidence |
|---|---:|---:|---:|---:|---:|---|
| Ammon | 16 | 0 | 0 | 0 | 0 | high (presence) but **no GL** |
| Arrowhead Springs | 229 | 206 | 5,153 | 0 | 92 | high |
| Cedar Glen | 10 | 0 | 0 | 0 | 0 | high (presence) **no GL** |
| Eagle Vista | 5 | 0 | 0 | 0 | 0 | high (presence) **no GL** |
| Eastbridge | 6 | 0 | 0 | 0 | 0 | high (presence) **no GL** |
| Erda | 14 | 0 | 0 | 0 | 0 | high (presence) **no GL** |
| Harmony | 612 | 391 | 11,910 | 0 | 269 | high |
| Ironton | 12 | 0 | 0 | 0 | 0 | high (presence) **no GL** |
| Lewis Estates | 34 | 34 | 0 | 0 | 34 | high (presence) **no GL no allocation** |
| Lomond Heights | 415 | 114 | 595 | 0 | 113 | high — has LH allocation |
| Meadow Creek | 0 | 0 | 7,418 | 0 | 0 | high (GL only) |
| Parkway Fields | 1,715 | 317 | 43,254 | 0 | 106 | high — has PF allocation |
| Salem Fields | 341 | 139 | 9,793 | 0 | 122 | high |
| Santaquin Estates | 2 | 0 | 0 | 0 | 0 | high (presence) **no GL** |
| Scarlet Ridge | 148 | 22 | 5,046 | 0 | 13 | high |
| Westbridge | 6 | 0 | 0 | 0 | 0 | high (presence) **no GL** |
| Willowcreek | 62 | 62 | 264 | 0 | 62 | high |
| _Historical (Cascade, Silver Lake, etc.)_ | n/a | varies | many | many | 0 | low — pre-2018, not in active universe |

Notes:
- "no GL" projects are 7 of the 16 active 2025Status projects: Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge. They appear in 2025Status (lot inventory + status) but have no GL VF or DR coverage and no Collateral Report row. Treat them as **structural gaps**: lot existence is high-confidence; cost is unknown.
- Lewis Estates: special case — 34 lots in 2025Status + Lot Data + ClickUp lot-tagged, but no GL coverage and no allocation workbook.

---

## Source-coverage matrix (active BCPD projects)

```
project              | inventory | LotData | 2025Status | Collateral | GL_VF | GL_DR | LH_Alloc | PF_Alloc | ClickUp_lot
Ammon                |    -      |   ✓     |    ✓       |     -      |   -   |   -   |    -     |    -     |    -
Arrowhead Springs    |    ✓      |   ✓     |    ✓       |     ✓      |   ✓   |   -   |    -     |    -     |    ✓
Cedar Glen           |    -      |   ✓     |    ✓       |     -      |   -   |   -   |    -     |    -     |    -
Eagle Vista          |    -      |   ✓     |    ✓       |     -      |   -   |   -   |    -     |    -     |    -
Eastbridge           |    -      |   ✓     |    ✓       |     -      |   -   |   -   |    -     |    -     |    -
Erda                 |    -      |   ✓     |    ✓       |     -      |   -   |   -   |    -     |    -     |    -
Harmony              |    ✓      |   ✓     |    ✓       |     ✓      |   ✓   |   -   |    -     |    -     |    ✓
Ironton              |    -      |   ✓     |    ✓       |     -      |   -   |   -   |    -     |    -     |    -
Lewis Estates        |    ✓      |   ✓     |    ✓       |     -      |   -   |   -   |    -     |    -     |    ✓
Lomond Heights       |    ✓      |   ✓     |    ✓       |     ✓      |   ✓   |   -   |    ✓     |    -     |    ✓
Meadow Creek         |    -      |   -     |    -       |     ✓      |   ✓   |   -   |    -     |    -     |    -
Parkway Fields       |    ✓      |   ✓     |    ✓       |     ✓      |   ✓   |   -   |    -     |    ✓     |    ✓
Salem Fields         |    ✓      |   ✓     |    ✓       |     ✓      |   ✓   |   -   |    -     |    -     |    ✓
Santaquin Estates    |    -      |   ✓     |    ✓       |     -      |   -   |   -   |    -     |    -     |    -
Scarlet Ridge        |    ✓      |   ✓     |    ✓       |     ✓      |   ✓   |   -   |    -     |    -     |    ✓
Westbridge           |    -      |   ✓     |    ✓       |     -      |   -   |   -   |    -     |    -     |    -
Willowcreek          |    ✓      |   ✓     |    ✓       |     ✓      |   ✓   |   -   |    -     |    -     |    ✓
```

---

## Known caveats (echoed from `data/reports/guardrail_check_v0.md`)

1. **Org-wide v2 is blocked** — Hillcrest, Flagship Belmont have no post-2017-02 GL.
2. **2017-03 → 2018-06 GL gap** — 15 months of zero rows for any entity.
3. **DataRails 38-col is 2.16× multiplied at source** — must dedup before summing.
4. **Vertical Financials 46-col is one-sided** — asset-side debit only by design; not a balanced trial-balance.
5. **QB register uses different chart** — zero account_code overlap to DR/VF; tie-out only.
6. **Phase grain is unsupported in GL** — derive from inventory + Lot Data + 2025Status + ClickUp.
7. **GL VF lot codes encode phase+lot for some projects** — v0 normalizer doesn't decode (Harm3 lot 1034 ≠ Harmony lot 1034).
8. **Allocation populated only for Lomond Heights + Parkway Fields** — Flagship Allocation Workbook v3 framework exists but mostly empty.
9. **ClickUp lot-tagged subset is sparse** — 1,177 of 5,509 tasks; phase fill 92.86% within subset.
10. **Inventory file selected as workbook (2)** — deliberately deviated from lane-doc claim of (4); document in validation report.

---

## What's safe to put in agent answers

- BCPD lot inventory, status, and lifecycle dates (high-confidence; 2,797 BCPD-built lots).
- BCPD VF cost rollups by project for 2018-2025 (with the project-code crosswalk applied).
- BCPD DR cost rollups by project for 2016-02 → 2017-02 (after dedup).
- BCPD CollateralSnapshot for the 9 pledged projects (as_of 2025-12-31).
- BCPD allocation/budget for Lomond Heights and Parkway Fields phases.
- ClickUp task progress for the lot-tagged subset (1,091 distinct lots).

## What's not safe

- BCPD vendor analysis outside 2025 (QB-only, 2025-only).
- Cost basis for the 7 projects without GL coverage (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge) and Lewis Estates — even though they have lot inventory.
- Cross-era project rollups without the project-code crosswalk (DR codes ≠ VF codes).
- Org-wide rollups including Hillcrest or Flagship Belmont.
- 2017-03 → 2018-06 cost — gap.
- Phase-level cost from GL alone — phase column is empty.
- Per-lot cost matching for projects whose VF lot codes encode phase prefixes (Harmony, Parkway Fields portions, Lomond Heights portions) without the phase-aware decoder.
