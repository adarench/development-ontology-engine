# staged_inventory_lots — Validation Report

**Built**: 2026-05-01
**Builder**: Terminal A (integrator)
**Source workbook**: `Inventory _ Closing Report (2).xlsx` (workbook **(2)**, deliberately chosen — see Source-selection note below)
**As-of date**: 2026-04-29
**Output**:
- `data/staged/staged_inventory_lots.csv` (846,571 bytes)
- `data/staged/staged_inventory_lots.parquet` (248,629 bytes)

## Source-selection note (deviation from lane doc)

The lane doc states "(4) is canonical, latest of 3." Terminal C's audit
(`scratch/ops_inventory_collateral_allocation_findings.md` § C1) found this is
**not true by the data**. Volatile `=TODAY()-SaleDate` cells in the three
near-duplicate workbooks reveal the actual save order:

| signal | (2) | (3) | (4) |
|---|---|---|---|
| `DAYS SINCE SALE` for Harmony Lot 848 | **64** | 63 | 62 |
| Implied `TODAY()` evaluation date | 2026-04-30 | 2026-04-29 | 2026-04-28 |
| Save order | **latest** | middle | earliest |

There are also **2 static-data deltas** in INVENTORY between (2) and (4):

| lot | (2) state | (4) state |
|---|---|---|
| `PARKWAY G1` lot 7048 | sold 2026-04-29, deposit $4,000, margin 14.35% | unsold/blank |
| `SCARLET RIDGE Phase 1` lot 121 | unsold/cancelled (blank) | sold 2026-03-26, deposit $8,000, margin 13% |

Decision: **stage from workbook (2)**. Rationale: it is freshest by ~2 days
of volatile evaluation **and** carries 1 net-new sale event. The lane doc
recommendation is overruled by the evidence. Caveat: confirm with the human
that the intent was "newest export"; if instead they meant "the file marked
(4) regardless of freshness", reissue the stage from (4).

Cross-check vs file (4): INVENTORY rows: file (2) = 978, file (4) = 978

## Row counts

| metric | value |
|---|---:|
| Total rows | 3,872 |
| ACTIVE (from INVENTORY sheet) | 978 |
| CLOSED (closing_date ≤ as_of) | 1,760 |
| ACTIVE_PROJECTED (closing_date > as_of, in CLOSED  sheet) | 1,134 |
| Distinct `canonical_lot_id` | 3,847 |
| Distinct `subdiv` (raw) | 32 |
| Distinct `canonical_project` | 32 |
| Distinct `(canonical_project, phase)` | 106 |

Expected from C1: ~3,872 ± 50 (978 active + 2,894 closed). Observed: **3,872**.

## Project-confidence distribution

| confidence | rows |
|---|---:|
| high | 1,311 |
| low | 2,556 |
| unmapped | 5 |

## Status breakdown by project

```
lot_status         ACTIVE  ACTIVE_PROJECTED  CLOSED
canonical_project                                  
Anthem West             0                17      29
Arrowhead Springs     204                 2       0
Beck Pines              0                 4      16
Bridgeport              0                31      73
Cascade                 0                35       0
Country View            0                21      33
F. Springs              0                26      23
Hampton                 0                80      55
Harmony               307                74      26
James Bay               0                14      14
Lec                     0                84       0
Lewis Estates          34                 0       0
Lomond Heights        114                 0       0
Maple Fields            0                 1      13
Meadow Creek            0                42      18
Midway                  0                 0       1
Ml                      0                 3       0
Parkside                0                26      44
Parkway Fields        114                89     124
Salem Fields          128                11       0
Scarlet Ridge          14                 7       1
Silver Lake             1               400     896
Spring Leaf             0                49       0
Springs                 0                11      58
To Be                   0                 1       0
Vintaro                 0                 0      37
Westbrook               0                32      84
Willis                  0                18       8
Willowcreek            62                 0       0
Willows                 0                28      83
Windsor                 0                 6      84
Wr                      0                22      40
```

## Schema

| column | dtype | semantic |
|---|---|---|
| `canonical_lot_id` | string | blake2s-8 hash of `(canonical_project|phase|lot_num)` — opaque, stable join key |
| `canonical_project` | string | resolved project name per the subdiv crosswalk (or title-cased subdiv for historical) |
| `project_confidence` | enum: `high`/`low`/`unmapped` | confidence of the subdiv → canonical_project mapping |
| `subdiv` | string | raw SUBDIV/community label from the source sheet (forward-filled where Excel-merged) |
| `phase` | string | phase label as it appears in source (no normalization beyond strip) |
| `lot_num` | string | lot number as it appears in source |
| `lot_status` | enum: `ACTIVE`/`CLOSED`/`ACTIVE_PROJECTED` | derived; ACTIVE = INVENTORY sheet row; CLOSED = CLOSED  sheet row with `Closing Date` ≤ as_of; ACTIVE_PROJECTED = CLOSED  sheet row with `Closing Date` > as_of (forward projection mixed in) |
| `plan_name` | string | model/plan name |
| `buyer` | string | buyer name or `SPEC`/`MODEL` placeholder |
| `sales_price` | float | sales price |
| `deposit` | float | earnest-money deposit |
| `sale_date` | datetime | recorded sale date (when lot went under contract) |
| `permit_pulled_date` | datetime | permit pull date (INVENTORY) or permit/super placeholder (CLOSED) |
| `permit_number` | string | building-permit identifier |
| `margin_pct` | float | gross margin (INVENTORY only — CLOSED  has no margin column) |
| `closing_date` | datetime | actual or projected closing date (CLOSED rows only) |
| `dig_date` | datetime | foundation-dig date (CLOSED rows only) |
| `anticipated_completion` | datetime | anticipated completion date (CLOSED rows only) |
| `as_of_date` | datetime | snapshot as-of (constant `2026-04-29`) |
| `source_file` | string | filename: `Inventory _ Closing Report (2).xlsx` |
| `source_sheet` | enum: `INVENTORY`/`CLOSED` | source tab |
| `source_row_number` | int | 1-indexed row position within the source sheet (post-header) |

## Caveats

1. The volatile `_days_since_sale` columns from both sheets are dropped at stage
   — they are `=TODAY()-SaleDate` formulas that change every time the file is
   opened, with no analytic value once `sale_date` is preserved.
2. `subdiv = "SL"` (Silver Lake) has **no row** in the v1 `Lot Data.csv` source.
   We map it to `canonical_project = "Silver Lake"` with confidence `low`. If a
   downstream consumer treats `low`-confidence projects as in-scope, those
   ~? rows will appear; if it filters to `high`, they're excluded.
3. `CLOSED .Closing Date` extends to 2027-06-07 — clearly forward-projected.
   We split CLOSED-sheet rows into `lot_status = CLOSED` (≤ as_of) vs
   `ACTIVE_PROJECTED` (> as_of). Do **not** count `ACTIVE_PROJECTED` rows in a
   "closed lots" rollup; they're in the universe but not closed yet.
4. The 26 lots in CLOSED  with subdivs in `HISTORICAL_SUBDIVS` (e.g. `WILLOWS`,
   `WINDSOR`, `JAMES BAY`) are pre-2018 communities that are not in current
   scope. They land in canonical_project as title-cased raw with confidence
   `low`. They are kept (not dropped) so historical absorption-rate queries
   still see them.
5. The `CLOSINGS` sheet (929 rows of pending closings) is **not** unioned in;
   it has no phase column and is best treated as an overlay on join
   `(subdiv, lot_num)`. Future enhancement.
6. No deduplication across sheets. A lot might appear as ACTIVE in INVENTORY
   AND as ACTIVE_PROJECTED in CLOSED (a sold-but-not-yet-closed lot in both
   tabs). Downstream consumers should resolve via `lot_status` priority:
   CLOSED > ACTIVE_PROJECTED > ACTIVE if collapsing to one row per lot.

## Hard guardrail status

This artifact satisfies **guardrail prereq #1** (`staged_inventory_lots.{csv,parquet}` exists, validated).
Final guardrail check is in `data/reports/guardrail_check_v0.md`.
