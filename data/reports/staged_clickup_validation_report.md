# Staged ClickUp Tasks — Validation Report

**Staged at**: 2026-05-01T16:57:37+00:00
**Source**: `data/raw/datarails/clickup/api-upload.csv`
**Output**: `data/staged/staged_clickup_tasks.csv` and `.parquet`

## Row & column counts

- Total rows: **5,509** (expected 5,509 — MATCH)
- Total columns: **35** (32 original + 3 staging metadata = 35)

## Required fields presence

| field | present | fill rate |
|---|---|---:|
| `name` | ✅ | 100.00% |
| `status` | ✅ | 100.00% |
| `subdivision` | ✅ | 28.86% |
| `lot_num` | ✅ | 21.37% |
| `projected_close_date` | ✅ | 1.02% |
| `actual_c_of_o` | ✅ | 4.88% |
| `sold_date` | ✅ | 1.02% |
| `cancelled_date` | ✅ | 0.04% |

## Parent / top-level identifiers

| field | present | fill rate | distinct |
|---|---|---:|---:|
| `id` | ✅ | 100.00% | 5,509 |
| `top_level_parent_id` | ✅ | 78.65% | 1,302 |
| `parent_id` | ❌ | — | 0 |

> Note: ClickUp's flat task export carries `top_level_parent_id` (list/space root) but **not** the immediate `parent_id`. The intermediate parent must be reconstructed from a separate ClickUp API pull if needed.

## Date fields and fill rates

| field | fill rate |
|---|---:|
| `date_created` | 100.00% |
| `date_updated` | 100.00% |
| `due_date` | 14.72% |
| `date_done` | 4.96% |
| `projected_close_date` | 1.02% |
| `sold_date` | 1.02% |
| `walk_date` | 0.38% |
| `close_date` | 0.07% |
| `start_date` | 0.05% |
| `cancelled_date` | 0.04% |
| `date_closed` | 0.00% |

## Status distribution (top 20)

| status | count |
|---|---:|
| Open | 4,826 |
| walk stage | 266 |
| under construction | 265 |
| waiting for new starts | 65 |
| pulled | 27 |
| pay fees | 26 |
| collecting data | 19 |
| at city | 8 |
| ready close | 7 |

## Subdivision coverage

- Distinct subdivisions (incl. blank): **12**
- subdivision fill rate: **28.86%**

### Top 20 subdivisions by row count

| subdivision | tasks |
|---|---:|
| (blank) | 3,919 |
| Harmony | 550 |
| Arrowhead | 437 |
| Park Way | 190 |
| Lomond Heights | 147 |
| Salem Fields | 122 |
| Willow Creek | 88 |
| Lewis Estates | 34 |
| Scarlett Ridge | 13 |
| Aarowhead | 5 |
| Aarrowhead | 3 |
| P2 14 | 1 |

## Lot number coverage

- `lot_num` filled rows: **1,177** of 5,509 (21.37%)
- distinct `lot_num` values: **677**

## Task name quality

- `name` empty: **0** rows
- `name` shorter than 3 chars: **2** rows

## Duplicate row check

- Duplicate `id` rows: **0**
- Empty `id` rows: **0**

## Full column list (staged)

- `source_file`
- `source_row_number`
- `staged_loaded_at`
- `id`
- `top_level_parent_id`
- `name`
- `status`
- `date_created`
- `date_updated`
- `date_closed`
- `date_done`
- `archived`
- `creator_username`
- `assignee_username`
- `tag_name`
- `priority`
- `due_date`
- `start_date`
- `points`
- `time_estimate`
- `walk_date`
- `walk_agent`
- `projected_close_date`
- `subdivision`
- `lot_num`
- `cancelled_date`
- `cancelled`
- `close_date`
- `closed`
- `actual_c_of_o`
- `C_of_O`
- `sold_date`
- `sold`
- `phase`
- `lot_type`
