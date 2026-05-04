# Operating State v2 — BCPD Agent Context

_Generated: 2026-05-01_
_Schema: `operating_state_v2_bcpd`_
_Guardrail: ✅ GREEN ([data/reports/guardrail_check_v0.md](../data/reports/guardrail_check_v0.md))_

## What this is

A point-in-time, machine-queryable operating state for **Building Construction
Partners, LLC (BCPD)** — the 16 active projects + ~25 historical communities
where BCPD is the vertical builder (or BCPBL/ASD/BCPI is the horizontal
developer). Mirrors the structure of `operating_state_v1.json` but uses the
v2 source data:

- 197,852 BCPD GL rows (DataRails 38-col + Vertical Financials 46-col + QB register), normalized into `staged_gl_transactions_v2`
- 3,872 inventory lots (978 ACTIVE + 1,760 CLOSED + 1,134 ACTIVE_PROJECTED) from `Inventory _ Closing Report (2).xlsx`
- 1,177 ClickUp lot-tagged tasks (filtered from 5,509 total)
- Collateral Report (Dec 2025) + PriorCR (Jun 2025)
- LH and Parkway allocation workbooks

## Entities in scope

| canonical_entity | role | how it joins |
|---|---|---|
| BCPD | Building Construction Partners, LLC — vertical builder + horizontal developer | GL `entity_name`; 2025Status `HorzCustomer=BCP`; QB register filename |
| BCPBL | BCP Ben Lomond (Lomond Heights horizontal) | Lot Data `HorzSeller=BCPBL` |
| ASD | Arrowhead Springs Developer | Lot Data `HorzSeller=ASD` |
| BCPI | BCP Investor (small horizontal) | Lot Data `HorzSeller=BCPI` (12 lots; medium confidence) |

**Out of scope for v0**: Hillcrest Road at Saratoga LLC, Flagship Belmont
Phase two LLC (both have GL data only through 2017-02; org-wide v2 is blocked
on a fresh GL pull). Lennar (third-party builder), EXT/EXT-Comm/Church (mixed
external categories).

## Confidence by question

### High-confidence answers
- BCPD lot inventory at 2026-04-29 (active + closed): 3,872 rows from staged inventory.
- BCPD lot lifecycle stage from Lot Data dates (2025-12-31 vintage) for the 2,797 BCPD-built lots (HorzCustomer=BCP).
- BCPD project-level GL actuals 2018-2025 from Vertical Financials (100% project + lot fill, $346M one-sided cost basis).
- BCPD account-level rollups within the legacy chart (DR 38-col + VF 46-col share it; 155 + 3 codes).
- BCPD CollateralSnapshot at 2025-12-31 for the 9 actively-pledged projects (and prior period 2025-06-30).
- BCPD lot lifecycle dates (HorzPurchase, HorzStart, VertCO, VertSale, VertClose) from Lot Data.

### Medium-confidence answers
- BCPD project-level GL actuals 2016-02 → 2017-02 from DataRails 38-col **after the row-multiplication dedup** (raw is 2.16× multiplied at source; documented in [guardrail_check_v0.md](../data/reports/guardrail_check_v0.md)).
- BCPD lot-level cost rollups using GL VF 46-col where lot codes match inventory (Salem, Willowcreek, Scarlet Ridge: 90-100% match; Harmony, Lomond Heights, Parkway: 44-62% — phase-encoded lots not yet decoded).
- ClickUp-derived task progress for the lot-tagged subset (1,091 distinct lots; phase fill 92.86% within that subset).

### Low-confidence answers
- Per-lot cost for projects without VF coverage (Lewis Estates: 0 GL rows; Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge: structural collateral-pool gaps).
- Pre-2018 historical communities (Silver Lake, Cascade, Westbrook, Hamptons, etc. — present in DR + inventory CLOSED, but project_confidence=`low`).

### Cannot answer (do not invent)
- Org-wide actuals across all entities (Hillcrest, Flagship Belmont blocked).
- BCPD spend in the 2017-03 → 2018-06 gap (zero GL rows for any entity).
- BCPD vendor analysis outside 2025 — vendor lives only in QB register and only for 2025.
- Phase-grain cost from GL — phase column is 0% filled across all 3 GL source schemas.
- Per-lot allocation/budget for projects other than Lomond Heights and Parkway Fields (Flagship Allocation Workbook v3 is mostly empty).

## Source provenance

Every canonical row carries `source_confidence` (worst-link of contributing
field confidences) and provenance metadata (`source_file`, `source_row_id`).
When citing a number, reference the source:

| number type | cite as |
|---|---|
| BCPD 2018-2025 cost | `Vertical Financials 46-col (staged_gl_transactions_v2.parquet, source_schema='vertical_financials_46col')` |
| BCPD 2016-17 cost | `DataRails 38-col post-dedup (staged_gl_transactions_v2.parquet, source_schema='datarails_38col')` — note dedup |
| BCPD lot inventory at 2026-04-29 | `Inventory _ Closing Report (2).xlsx` (workbook 2, deliberately chosen — see staged_inventory_lots_validation_report.md) |
| BCPD collateral position | `Collateral Dec2025 - Collateral Report.csv` |
| BCPD task progress | `staged_clickup_tasks.parquet` (lot-tagged subset filter applied) |
| BCPD lifecycle dates | `Collateral Dec2025 - Lot Data.csv` |

## Hard limits

1. **Org-wide is not in scope.** Do not aggregate Hillcrest or Flagship Belmont with BCPD; they're frozen at 2017-02.
2. **2017-03 → 2018-06 GL gap**: no rows for any entity. State the gap in any time-series answer that crosses it.
3. **DR 38-col dedup**: any cost rollup from DR rows MUST first deduplicate on `(entity_name, posting_date, account_code, amount, project, lot, memo_1, description, batch_description)`, preferring the row with most non-null metadata. The raw v2 parquet is preserved unchanged; dedup is applied at query time.
4. **QB register tie-out only**: zero account_code overlap with VF; would double-count if naively summed against VF. Use only for vendor / cash / AP queries on 2025 BCPD.
5. **Phase grain**: not from GL. Use inventory + Lot Data + 2025Status + ClickUp.
6. **Lot-tagged ClickUp** is sparse (~21% of tasks). Do not extrapolate ClickUp signals to lots not in the lot-tagged subset.
7. **Inventory file selection**: workbook (2) was used, deviating from the lane-doc claim that (4) is canonical. The two files differ by ~2 days of save time and 2 lot events. If the human's intent was "the file marked (4)", reissue.
8. **Allocation coverage**: only Lomond Heights and Parkway Fields have populated workbooks. For other projects, expected cost is unknown; do not estimate.

## How an agent should cite

1. Refer to BCPD lots by `canonical_lot_id` or `(canonical_project, canonical_phase, canonical_lot_number)`. Don't make up phase IDs.
2. When citing cost, name the source schema and confidence: "Per Vertical Financials 46-col (high), Parkway Fields 2018-2025 cost basis is $97.95M across 26,258 rows."
3. When asked about 2016-17, mention dedup: "Per DataRails 38-col post-dedup (high), Cascade had $X cost in 2016."
4. When asked about something unanswerable, say so with the gap reference: "BCPD 2017-03 → 2018-06 cost is in a documented GL gap (zero rows) — cannot be derived from current data."
5. When asked about gross margin or cash flow, surface QB register limits: "QB register covers BCPD 2025 only and uses a different chart of accounts; do not double-count against VF."

## Quality artifacts to consult

- `data/reports/guardrail_check_v0.md` — guardrail GREEN/RED status + DataRails dedup decision + BCPD cost-source hierarchy
- `data/reports/join_coverage_v0.md` — GL ↔ inventory ↔ ClickUp coverage by year and project
- `data/reports/staged_inventory_lots_validation_report.md` — inventory stage validation + workbook (2) deviation rationale
- `output/state_quality_report_v2_bcpd.md` — per-field fill rate / confidence distribution / safe-to-use flag
- `output/state_query_examples_v2_bcpd.md` — 12 worked example queries
- `docs/ontology_v0.md` — entity definitions + BCPD instance counts
- `docs/source_to_field_map.md` — human-readable field map
- `docs/crosswalk_plan.md` — vocabulary mapping rules

## Versioning

This is v0 of the v2 stack. v1 still exists alongside (`output/operating_state_v1.json`)
and is unchanged. v0 is BCPD-only; org-wide remains a Track B roadmap item.
