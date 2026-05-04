# Guardrail Check v0 — BCPD Operating State v2

**Built**: 2026-05-01
**Author**: Terminal A (integrator)
**Purpose**: Explicit GREEN/RED check of the three hard pre-build prerequisites
defined in `docs/operating_state_v2_master_plan.md` § 2 and `docs/agent_lanes/terminal_a_integrator.md` § "Hard pre-build guardrail".

If any prereq is **RED**, the BCPD v2 build (A8–A11) does not happen.

---

## Prereq 1 — `staged_inventory_lots.{csv,parquet}` exists and is validated

**Status: ✅ GREEN**

| check | evidence |
|---|---|
| File exists (parquet) | `data/staged/staged_inventory_lots.parquet` (248,629 B) |
| File exists (csv) | `data/staged/staged_inventory_lots.csv` (846,571 B) |
| Validation report | `data/reports/staged_inventory_lots_validation_report.md` |
| Row count | **3,872** (978 ACTIVE + 1,760 CLOSED + 1,134 ACTIVE_PROJECTED) |
| Source workbook chosen deliberately | `Inventory _ Closing Report (2).xlsx` (deviation from lane doc — see validation report's Source-selection note) |
| Header offsets | INVENTORY: header=0; CLOSED : header=1 (verified; documented in validation report) |
| `as_of_date` | 2026-04-29 (data-derived; documented) |
| Project-confidence column | populated (`high`/`low`/`unmapped`) on every row |
| Canonical lot id | populated (`canonical_lot_id` = blake2s-8 of `project|phase|lot_num`) |

---

## Prereq 2 — Crosswalk v0 exists with confidence column

**Status: ✅ GREEN**

| check | evidence |
|---|---|
| Combined crosswalk (BCPD-scope guardrail satisfier) | `data/staged/staged_entity_project_crosswalk_v0.{csv,parquet}` — **133 rows** |
| Per-level entity crosswalk | `data/staged/staged_entity_crosswalk_v0.{csv,parquet}` — 13 rows |
| Per-level project crosswalk | `data/staged/staged_project_crosswalk_v0.{csv,parquet}` — 142 rows |
| Per-level phase crosswalk | `data/staged/staged_phase_crosswalk_v0.{csv,parquet}` — 385 rows |
| Per-level lot crosswalk | `data/staged/staged_lot_crosswalk_v0.{csv,parquet}` — 14,537 rows |
| `confidence` column | populated on every row (values: `high` / `medium` / `low` / `unmapped`) |
| Plan doc | `docs/crosswalk_plan.md` |

Confidence distribution on `staged_project_crosswalk_v0` (142 rows):

| confidence | rows | comment |
|---|---:|---|
| `high` | ~90 | identity mappings (2025Status, Lot Data, Collateral Report) + clear GL code resolutions + clear inventory subdiv mappings |
| `medium` | ~10 | typo variants (`Aarowhead`, `Scarlett Ridge`), historical `LEC`, `WR`, ambiguous `SctLot` |
| `low` | ~30 | historical pre-2018 communities (Country View, James Bay, Spring Leaf, etc.) |
| `unmapped` | ~5 | `SPEC`, `ML`, `TO BE`, `P2 14` — preserved as raw |

---

## Prereq 3 — GL ↔ inventory ↔ ClickUp join coverage measured

**Status: ✅ GREEN**

| check | evidence |
|---|---|
| Report file | `data/reports/join_coverage_v0.md` (5,785 B) |
| Headline metrics quantified | yes (see below) |
| Per-project breakdown | yes (8 high-confidence BCPD projects) |
| Per-year breakdown | yes (2016-2025) |
| Active-only sub-breakdown | yes |

Headline (BCPD inventory base, `project_confidence=high`, n=1,285 distinct `(canonical_project, lot_num)` pairs):

| dimension | lots | % |
|---|---:|---:|
| ≥1 GL row | 810 | 63.0% |
| ≥1 ClickUp lot-tagged task | 811 | 63.1% |
| Full triangle (GL ∧ ClickUp) | 476 | 37.0% |

Active-only (lot_status=ACTIVE, n=965): 62.9% have GL, 83.9% have ClickUp, 49.2% full triangle.

**Acceptable threshold**: yes for v0. The non-100% gap is explainable:
1. Lot-encoding mismatch where GL VF uses phase-prefixed 4-digit codes (`1034` for Harmony Phase 1 Lot 34) while inventory uses sequential per-phase numbering (`107`, `108`). v0 normalizer strips leading zeros + alpha suffixes; v1 follow-up should add a phase-aware decoder.
2. Lewis Estates (34 lots) has 0% GL coverage — consistent with Terminal C's finding that Lewis Estates has no Collateral Report row and no allocation workbook entry.
3. Inventory is current as of 2026-04-29; GL VF cutoff is 2025-12-31. ~336 lots are in GL 2025 but not in current inventory — likely closed in early 2026 and removed from the active list.

These gaps are documented explicitly in `data/reports/join_coverage_v0.md`.

---

## Composite verdict

| prereq | status |
|---|---|
| #1 staged inventory exists + validated | ✅ GREEN |
| #2 crosswalk v0 with confidence column | ✅ GREEN |
| #3 join coverage measured + reported | ✅ GREEN |
| **Composite** | **✅ GREEN — proceed to A8–A11** |

---

## Additional documented decisions (per integrator instructions)

### DataRails 38-col duplicate-treatment decision

**Source-of-truth**: see `scratch/gl_financials_findings.md` § B4 and the
addendum to `data/staged/staged_gl_transactions_v2_validation_report.md`.

**Finding**: DR 38-col rows are systematically multiplied 2.16× at the source.
The same posting line appears 2-3+ times consecutively with identical financial
fields and identical `transaction_id:line_number`, but with slightly different
metadata bits (e.g., `account_name` filled vs blank, `account_type` filled vs
blank). The differing metadata makes `row_hash` unique — passing the existing
dedup check — but the rows are functional duplicates for any roll-up.

**v0 decision**: Treat DR 38-col as **2.16× row-multiplied at the source**.
Any consumer that sums DR amounts MUST first deduplicate on the canonical key:

```
(entity_name, posting_date, account_code, amount, project, lot,
 memo_1, description, batch_description)
```

Pick a canonical row per group by preferring the row with most non-null metadata
(both `account_name` and `account_type` populated). This recovers a balanced
two-sided journal: post-dedup BCPD `sum(amount)` falls from +$17M to -$500K
(0.15% of total flow, within rounding).

For the BCPD v2 outputs, this is implemented in the cost-rollup path. The raw
`staged_gl_transactions_v2` parquet is not modified — dedup is applied at query
time in any pipeline that aggregates DR amounts.

**Rollups that don't sum amounts** (e.g., "what BCPD lots have any DR row?")
are unaffected and can use raw v2.

### BCPD cost-source hierarchy

For BCPD lot/project cost, the v0 hierarchy is:

| era | primary source | rationale | confidence |
|---|---|---|---|
| 2018-2025 | `vertical_financials_46col` (`source_schema='vertical_financials_46col'` in `staged_gl_transactions_v2`) | 100% project + lot fill; 1,306 distinct (project, lot) pairs; legacy chart of accounts; one-sided cost-accumulation feed (asset-side debit only — confirmed structural, not a defect). VF is the **canonical lot-level cost basis** for BCPD 2018-2025. | high |
| 2016-02 → 2017-02 | `datarails_38col` filtered to `entity_name='Building Construction Partners, LLC'`, **after row-multiplication dedup** (key above) | 49.5% project/lot fill on the deduplicated 51,694-row BCPD subset; balanced two-sided journal post-dedup. Pre-dedup totals are wrong by 2.16×. | high after dedup; **medium** confidence on lot-level rollups (49.5% lot tag rate) |
| 2017-03 → 2018-06 (15 months) | **NONE** — the entire dump has zero rows for this window. | export gap; cannot be reconstructed from existing files. | n/a — gap |
| 2025 supplementary | `qb_register_12col` | tie-out / vendor / cash-AP only. **Excluded from primary lot/project rollups** — see B5 finding: zero account_code overlap with VF/DR; different chart of accounts; would double-count if naively summed against VF. | n/a (tie-out only) |

**Implementation rule**: a single canonical "actual_cost" for a BCPD lot is the
sum of VF amounts for posting_dates ≥ 2018-06-26, plus the dedup-adjusted DR
amount for posting_dates ≤ 2017-02-28. For lots that span the 2017-03 → 2018-06
gap, the canonical answer is "cost from 2018-onward $X; pre-2018 $Y; the
2017-03–2018-06 window cannot be filled from this dump and is not estimated."

**Vendor / cash / AP analysis** is QB-only and 2025-only. Don't promise vendor
breakdowns outside this scope.

**Phase-grain cost** is unsupported in GL (phase column 0% filled in all three
sources). Phase rollups must come from inventory + allocation + ClickUp.

---

## Sign-off

The guardrail composite is GREEN. Proceeding to A8–A11 (BCPD v2 outputs):
- `output/operating_state_v2_bcpd.json`
- `output/agent_context_v2_bcpd.md`
- `output/state_query_examples_v2_bcpd.md`
- `output/state_quality_report_v2_bcpd.md`
