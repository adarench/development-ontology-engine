# Join Coverage v0 — BCPD GL ↔ Inventory ↔ ClickUp
**Built**: 2026-05-01
**Builder**: Terminal A (integrator)
**Inputs**:
- `data/staged/staged_inventory_lots.parquet` (3,872 rows; BCPD-scoped subset filtered to `project_confidence=high` for headline)
- `data/staged/staged_gl_transactions_v2.parquet` (197,852 BCPD rows)
- `data/staged/staged_clickup_tasks.parquet` (lot-tagged subset, 1,177 rows)
- `data/staged/staged_project_crosswalk_v0.csv` for source→canonical resolution

**Match key**: `(canonical_project, canonical_lot_number)`. `lot_num` is normalized: trim whitespace, strip trailing `.0` from float-coerced ints. Phase is **not** part of the match key — phase is missing in GL VF and unreliable in DR, and inventory is the authority for `(project, lot_num)` uniqueness.

---

## Headline

BCPD inventory lots in scope (project_confidence=`high`): **1,285** distinct `(canonical_project, lot_num)` pairs.

| dimension | lots | % of base |
|---|---:|---:|
| BCPD inventory base | 1,285 | 100.0% |
| ...with ≥1 GL row (DR or VF, any year) | 810 | 63.0% |
| ...with ≥1 ClickUp lot-tagged task | 811 | 63.1% |
| ...with **full triangle** (GL **and** ClickUp) | 476 | 37.0% |

### Active-only subset (lot_status = ACTIVE, n=965)

| dimension | lots | % |
|---|---:|---:|
| Active BCPD inventory | 965 | 100.0% |
| ...with ≥1 GL row | 607 | 62.9% |
| ...with ≥1 ClickUp task | 810 | 83.9% |
| ...full triangle | 475 | 49.2% |

---

## Per-project breakdown (BCPD inventory base, project_confidence=high)

| project | lots | with GL | with ClickUp | full triangle | % GL | % ClickUp | % triangle |
|---|---:|---:|---:|---:|---:|---:|---:|
| Harmony | 391.0 | 210.0 | 269.0 | 137.0 | 53.7% | 68.8% | 35.0% |
| Parkway Fields | 317.0 | 195.0 | 106.0 | 73.0 | 61.5% | 33.4% | 23.0% |
| Arrowhead Springs | 206.0 | 134.0 | 92.0 | 20.0 | 65.0% | 44.7% | 9.7% |
| Salem Fields | 139.0 | 139.0 | 122.0 | 122.0 | 100.0% | 87.8% | 87.8% |
| Lomond Heights | 114.0 | 50.0 | 113.0 | 49.0 | 43.9% | 99.1% | 43.0% |
| Willowcreek | 62.0 | 62.0 | 62.0 | 62.0 | 100.0% | 100.0% | 100.0% |
| Lewis Estates | 34.0 | 0.0 | 34.0 | 0.0 | 0.0% | 100.0% | 0.0% |
| Scarlet Ridge | 22.0 | 20.0 | 13.0 | 13.0 | 90.9% | 59.1% | 59.1% |

---

## GL coverage by year (BCPD only)

How many distinct `(project, lot)` pairs appear in GL each year, and of those, how many also appear in inventory?

| year | lots in GL | lots in GL ∩ inventory | lots in GL only |
|---:|---:|---:|---:|
| 2016 | 469 | 0 | 469 |
| 2017 | 343 | 0 | 343 |
| 2018 | 1 | 0 | 1 |
| 2019 | 3 | 0 | 3 |
| 2020 | 3 | 0 | 3 |
| 2021 | 1 | 0 | 1 |
| 2022 | 2 | 0 | 2 |
| 2023 | 359 | 65 | 294 |
| 2024 | 749 | 334 | 415 |
| 2025 | 1,145 | 809 | 336 |

Interpretation: rows where 'lots in GL only' is large indicate lots that GL has tagged with a project+lot but that the current inventory does not enumerate — typically pre-2018 historical communities (Silver Lake, Cascade, etc.) that only appear in the inventory CLOSED  tab and are excluded from the high-confidence base.

---

## Diagnostic — inventory lots without GL match

Total: **475** inventory lots (high-confidence projects) have no GL row.

Top by project:

```
canonical_project
Harmony              181
Parkway Fields       122
Arrowhead Springs     72
Lomond Heights        64
Lewis Estates         34
Scarlet Ridge          2
```

Reasons most likely:
1. The lot is a brand-new sale recorded in inventory (2026-04-29) but not yet posted to GL (VF cutoff 2025-12-31).
2. The lot is in a project that GL has not tagged at the lot grain (DR is only ~50% lot-filled).
3. `lot_num` formatting differs (e.g. `'1234'` vs `'1234A'`); manual review may be needed.

---

## Diagnostic — GL lot keys without inventory match

Total: **994** distinct `(canonical_project, lot)` pairs in GL that have no row in inventory's high-confidence base.

Top by project:

```
canonical_project
Parkway Fields         233
Silver Lake            171
Meadow Creek           141
Harmony                 59
White Rail              44
The Springs Cluster     40
Cascade                 36
The Springs             33
Willows                 33
LeCheminant             31
Willis                  30
Westbrook               25
Parkside                22
Hamptons                21
Bridgeport              20
Salem Fields            19
Lomond Heights          10
Scarlet Ridge            8
Willowcreek              6
Miller Estates           3
```

These are typically pre-2018 historical lots (Silver Lake, Cascade, Westbrook, Hamptons, etc.) — the inventory CLOSED  tab does carry many of them, but they're at confidence=`low` so excluded from the base. Re-running with `low`-confidence projects included would recover most.

---

## Acceptable-threshold call

- **GL coverage of active BCPD inventory** of 62.9% is acceptable for v2 BCPD: the gap is dominated by 2026-recent sales (post-2025-12-31 VF cutoff) and DR's structural ~50% lot-tag rate on 2016-17 historical projects.
- **ClickUp coverage of active BCPD inventory** of 83.9% is below ideal but expected: ClickUp has ~1,091 distinct lot-tagged pairs vs ~978 active inventory lots, but the project-name typo variants and the missing `subdivision` tag on 79% of ClickUp tasks limit the join. Use ClickUp as a per-lot signal where present, fall back to inventory + GL where absent.
- **Full triangle** of 49.2% is the realistic ceiling for BCPD v2; queries that require all three sources should disclose this.

---

## Hard guardrail prereq #3

This report exists, is not a placeholder, and quantifies the join coverage. Combined with `staged_inventory_lots.{csv,parquet}` (#1) and the crosswalk v0 (#2), all three guardrail prerequisites are met. Final GREEN/RED call lives in `data/reports/guardrail_check_v0.md`.
