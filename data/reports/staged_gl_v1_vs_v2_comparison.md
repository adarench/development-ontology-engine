# Staged GL — v1 vs v2 Comparison & Operating-State-v2 Recommendation

**Built**: 2026-05-01

This document compares `staged_gl_transactions` (v1, built earlier) with the new
`staged_gl_transactions_v2` (built from the full audit), and recommends whether
Operating State v2 should consume v2 immediately or wait for the remaining
prerequisites.

---

## At-a-glance comparison

| dimension | v1 (`staged_gl_transactions`) | v2 (`staged_gl_transactions_v2`) |
|---|---|---|
| **rows** | 124,085 | **210,440** |
| **sources** | 1 — DataRails 38-col bundle (`GL (1..14).csv`) | **3** — DataRails 38-col + Vertical Financials 46-col + QB register 12-col |
| **schema** | raw 38 source cols + 3 staging metadata cols (41 total) | **47 canonical cols**, including `source_schema`, `raw_column_map_json`, `row_hash` for traceability |
| **min posting_date** | 2016-01-01 | 2016-01-01 |
| **max posting_date** | 2017-02-28 | **2025-12-31** (~9 years more coverage) |
| **coverage gap** | n/a (single source) | 2017-03-01 → 2018-06-25 (~15 months) |
| **entities** | 3 (BCPD, Hillcrest, Flagship Belmont) | 3 (same) |
| **BCPD recent (2024–2025) data** | ❌ none | ✅ **79,154 rows** (Vertical Financials 2024+2025 + QB register 2025) |
| **Hillcrest / Flagship Belmont recent data** | ❌ (2017+ missing) | ❌ still missing (no fresh source for these entities) |
| **CSV size** | 44 MB | 296 MB |
| **Parquet size** | 2.0 MB | **13.6 MB** (still small thanks to columnar compression) |
| **row hash uniqueness** | n/a (no row_hash field) | **100%** — 210,440 distinct row_hash values |

## Per-source contribution to v2

| source_schema | rows | share | date range | entities |
|---|---:|---:|---|---|
| `datarails_38col` (`GL (1..14).csv`) | 124,085 | 59.0% | 2016-01-01 → 2017-02-28 | 3 |
| `vertical_financials_46col` (`Collateral … Vertical Financials.csv`) | 83,433 | 39.6% | 2018-06-26 → 2025-12-31 | 1 (BCPD) |
| `qb_register_12col` (`Collateral … BCPD GL Detail.csv`) | 2,922 | 1.4% | 2025-01-01 → 2025-12-31 | 1 (BCPD) |

Rows dropped during normalization:
- `datarails_38col`: 0
- `vertical_financials_46col`: 0 (all rows are `Line Type = "  -- detail"`)
- `qb_register_12col`: 405 non-transaction rows (account headers, total rows, blank lines)

## Per-year row counts (v2)

| year | rows | source(s) |
|---:|---:|---|
| 2016 | 101,005 | datarails_38col |
| 2017 | 23,080 | datarails_38col |
| 2018 | 137 | vertical_financials_46col |
| 2019 | 175 | vertical_financials_46col |
| 2020 | 118 | vertical_financials_46col |
| 2021 | 66 | vertical_financials_46col |
| 2022 | 10 | vertical_financials_46col |
| 2023 | 3,773 | vertical_financials_46col |
| 2024 | 23,659 | vertical_financials_46col |
| 2025 | 58,417 | vertical_financials_46col + qb_register_12col |

The 2018–2022 row counts are extremely thin — these years cover BCPD ramp-up activity. Real volume kicks in 2023 and grows to ~58K rows in 2025.

## Per-entity row counts (v2)

| entity_name | total rows | year coverage |
|---|---:|---|
| Building Construction Partners, LLC | **197,852** | 2016-01 → 2017-02, then 2018-06 → 2025-12 |
| Hillcrest Road at Saratoga, LLC | 12,093 | 2016-01 → 2017-02 only |
| Flagship Belmont Phase two LLC | 495 | 2016-01 → 2017-02 only |

## Cost-attribution capability — v1 vs v2

Project / lot fill rates by year and source schema:

| year | source | rows | project_fill | lot_fill | account_code_fill |
|---:|---|---:|---:|---:|---:|
| 2016 | datarails_38col | 101,005 | 48.4% | 48.4% | 100% |
| 2017 | datarails_38col | 23,080 | 54.4% | 54.4% | 100% |
| 2018 | vertical_financials_46col | 137 | **100%** | **100%** | 100% |
| 2019 | vertical_financials_46col | 175 | **100%** | **100%** | 100% |
| 2020 | vertical_financials_46col | 118 | **100%** | **100%** | 100% |
| 2021 | vertical_financials_46col | 66 | **100%** | **100%** | 100% |
| 2022 | vertical_financials_46col | 10 | **100%** | **100%** | 100% |
| 2023 | vertical_financials_46col | 3,773 | **100%** | **100%** | 100% |
| 2024 | vertical_financials_46col | 23,659 | **100%** | **100%** | 100% |
| 2025 | vertical_financials_46col | 55,495 | **100%** | **100%** | 100% |
| 2025 | qb_register_12col | 2,922 | 0% | 0% | 100% |

For BCPD's recent activity (2018+ via Vertical Financials), **every row carries a project and lot tag**. That is a major upgrade over v1, where ~50% of 2016-17 BCPD rows were untagged.

## What v2 unlocks that v1 did not

1. **Multi-year BCPD operating state.** v2 supports 2018–2025 BCPD analysis directly from primary GL — not possible in v1 at all.
2. **Per-lot cost rollups for BCPD on recent data.** Vertical Financials provides 100% project + lot fill on 83,433 rows. v1 had only the 2016-17 DataRails bundle, which was 49.5% tagged.
3. **A canonical schema future sources can land into.** Adding a new GL source (e.g. fresh DataRails pull for Hillcrest 2024) is now a mapping exercise, not a re-architecture.
4. **Row-level provenance + dedup.** `source_file`, `source_schema`, `source_row_id`, `row_hash`, and `raw_column_map_json` make every canonical value traceable to its origin and let consumers audit per-source contribution.
5. **Stable row identity.** `row_hash` is 100% unique (210,440 distinct values). v1 had no comparable field — staging metadata was source-file + row-number only.

## What v2 still does NOT fix

1. **Hillcrest Road at Saratoga LLC and Flagship Belmont Phase two LLC stay frozen at Feb 2017.** No newer GL source for these two entities exists in either zip. Their operating state is necessarily historical until fresh exports arrive.
2. **The 2017-03 → 2018-06 gap (~15 months) remains for all entities.** Nothing in the dump fills it. If activity truly happened during this window, it's missing from any operating state we build.
3. **`qb_register_12col` is dimensionally thin.** No project / lot / phase / division / sub-ledger fields. Useful as 2025 BCPD tie-out at the bank-account grain, but not as a primary feed for cost attribution.
4. **Entity ↔ project crosswalk is still missing.** v2 carries `Project` codes from both DataRails (`SctLot`, `BCP-...`, etc.) and Vertical Financials (`SctLot`, ...) — they overlap because both describe BCPD — but the join from GL `Project` to ClickUp `subdivision` to inventory `community` is still not authoritative.
5. **No `phase` field.** DataRails combines lot+phase in `Lot/Phase`; Vertical Financials only has `Lot`; QB register has neither. Phase-level rollups need either a parsing rule applied to `Lot/Phase` strings or a separate phase dictionary.
6. **Inventory closing report still not staged** (xlsx header offset issue not yet fixed).
7. **Currency assumed USD** for Vertical Financials and QB register (not in source). Fine for now since BCPD is USD-only, but flag if multi-currency entities arrive.

## Recommendation: Operating State v2 timing

**Build it now, but bound the scope explicitly.**

The strongest path is a **two-track release**:

### Track A — BCPD Operating State (ready to build today)

`staged_gl_transactions_v2` filtered to `entity_name == 'Building Construction Partners, LLC'` is the richest dataset in the repo: 197,852 rows spanning 2016–2025 with 100% project+lot fill on the 83K post-2018 rows. Combined with `staged_clickup_tasks` (filtered to BCPD subdivisions) and a v0 `staged_inventory_lots`, you can produce:

- BCPD lot-level cost rollup (Vertical Financials → project, lot)
- BCPD phase progression (ClickUp → status, dates) for the lot-tagged subset
- BCPD multi-year P&L summary (Vertical Financials)
- BCPD year-over-year activity comparison (2024 vs 2025)

This is a real business deliverable. Recommend writing to `output/operating_state_v2_bcpd.json` (entity-scoped name) so it's not confused with an org-wide v2.

**Soft prerequisites** (would improve quality but not block):
- v0 entity↔project crosswalk seeded from distinct values (machine-derivable from the data; needs ~30 min of human review for the BCPD-only universe).
- Inventory closing report staged for the BCPD lot universe.

### Track B — Org-wide Operating State (blocked)

For Hillcrest and Flagship Belmont, no GL data exists past Feb 2017. An org-wide v2 would mix 2024-2025 BCPD against 2017 historical for the other two entities — that's misleading without explicit period labeling. Recommend **not** building org-wide v2 until either:
- fresh GL pulls land for Hillcrest and Flagship Belmont, OR
- an explicit "Active Entities" filter is agreed and we publish v2 as a BCPD-only product.

### Hard prerequisites for either track

- **Pick a primary key strategy.** `row_hash` is the only PK that works across all three sources. Make this explicit in the v2 docs and in any downstream join/dedup logic.
- **Decide the sign convention.** v2 uses signed `amount` (positive=debit, negative=credit). Confirm before consumer code reads it.
- **Decide what to do with `qb_register_12col` rows.** They overlap with the Vertical Financials 2025 BCPD rows and could double-count if naively summed. Either: (a) exclude them from financial rollups and use them only as a tie-out, or (b) reconcile by `(account_code, posting_date, amount)` and flag overlaps. Recommend (a) for v2.

## Files written

- `data/staged/staged_gl_transactions_v2.csv` (296 MB)
- `data/staged/staged_gl_transactions_v2.parquet` (13.6 MB)
- `data/staged/staged_gl_transactions_v2_validation_report.md`
- `data/reports/staged_gl_v1_vs_v2_comparison.md` (this file)

`staged_gl_transactions.{csv,parquet}` (v1) is **untouched**. `output/*` is **untouched**.
