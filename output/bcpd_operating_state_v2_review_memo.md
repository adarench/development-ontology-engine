# BCPD Operating State v2 — Review Memo

**Date**: 2026-05-01
**Author**: Terminal A (integrator)
**Audience**: BCPD ops, finance, and the agent layer that will consume this state
**Status**: shipped; guardrail GREEN; v1 outputs unchanged

This memo is a short read-out of what got built, what it can be trusted to
answer, and what would improve coverage next. The full evidence is in the
artifact set listed under [Companion artifacts](#companion-artifacts).

---

## 1. What was built

A point-in-time, machine-queryable operating state for **Building Construction
Partners, LLC (BCPD)** — the 16 active 2025Status projects (+ Meadow Creek
from collateral) and ~25 historical communities — assembled from:

- 197,852 BCPD GL rows (DataRails 38-col + Vertical Financials 46-col + QB register), normalized into `staged_gl_transactions_v2`.
- 3,872 inventory lots (978 ACTIVE + 1,760 CLOSED + 1,134 ACTIVE_PROJECTED) staged from `Inventory _ Closing Report (2).xlsx` at as-of 2026-04-29.
- 1,177 ClickUp lot-tagged tasks (filtered from 5,509 total).
- Collateral Report (2025-12-31) and PriorCR (2025-06-30).
- Lomond Heights and Parkway Fields allocation workbooks.

The state is shipped as a JSON document, an agent context brief, a query
example file, and a per-field quality report (paths under
[Companion artifacts](#companion-artifacts)). v1 outputs were not touched.

The build is deterministic and rerunnable (`docs/operating_state_v2_build_plan.md`).
The guardrail check confirmed all three pre-build prereqs are GREEN before
any v2 file shipped.

---

## 2. Headline numbers

| | |
|---|---:|
| BCPD projects in body | 25 (17 active including Meadow Creek + 8 historical) |
| Lots in canonical body | 5,366 |
| High-confidence lots (BCPD-built per HorzCustomer=BCP) | 2,797 |
| BCPD GL rows (raw) | 197,852 |
| BCPD GL rows post-DataRails dedup | 141,752 (DR 51,694 + VF 83,433 + QB 2,922) |
| 2018–2025 cost basis (Vertical Financials, asset-side) | **$346.5M** across 83,433 rows |
| 2016-02–2017-02 net (DataRails post-dedup) | -$0.99M (debit/credit balanced; $330.9M each side) |

VF 2018–2025 by project (top 8):

| project | $M | rows |
|---|---:|---:|
| Parkway Fields | 147.2 | 43,254 |
| Harmony | 53.6 | 11,910 |
| Meadow Creek | 50.3 | 7,418 |
| Salem Fields | 45.5 | 9,793 |
| Arrowhead Springs | 24.2 | 5,153 |
| Scarlet Ridge | 20.7 | 5,046 |
| Willowcreek | 2.6 | 264 |
| Lomond Heights | 2.4 | 595 |

---

## 3. What it can answer (trustworthy)

These questions are safe to ask of the BCPD v2 state today; the underlying
data corroborates and the source confidences are high:

- **Lot inventory at 2026-04-29**: status (ACTIVE / CLOSED / ACTIVE_PROJECTED), buyer, sale date, projected close, permit status, by project and phase.
- **Lot lifecycle stage** for the 2,797 BCPD-built lots, derived from Lot Data dates via the v1 waterfall.
- **Project-level cost 2018–2025** from Vertical Financials, by project and account/cost-category (legacy 4-digit chart: `1535 Permits & Fees`, `1540 Direct Construction`, `1547 Direct Construction-Lot`).
- **Project-level cost 2016-02–2017-02** from DataRails 38-col **after dedup** (the 2.16× row-multiplication artifact must be removed first; the build does this automatically — never query DR raw for cost rollups).
- **CollateralSnapshot** at 2025-12-31 (and prior 2025-06-30 for delta) for the 9 pledged BCPD projects (41 phase rows): lot value, advance %, loan $, total dev cost.
- **Allocation/budget** for Lomond Heights and Parkway Fields (per-phase × prod-type from LH and PF workbooks).
- **ClickUp task progress** for the 1,091 distinct lot-tagged lots: status, due_date (45.5%), actual_c_of_o (22.8%).

---

## 4. What is caveated (use with care)

- **GL ↔ inventory join is partial**: 63% of high-confidence inventory lots have ≥1 GL row; 37% have a full GL+ClickUp triangle. The gap is mostly mechanical:
  - VF lot codes encode phase+lot together for some projects (e.g., Harmony VF lot `1034` likely = Harmony Phase 3 Lot 34, but inventory has it as Lot `34` in Phase A7). The v0 normalizer strips zeros only — a phase-aware decoder is the obvious next improvement.
  - Salem Fields and Willowcreek hit 100% match; Parkway Fields and Harmony land near 60%; Lewis Estates is 0% by structure.
- **DataRails dedup is mandatory**: any consumer that sums DR `amount` directly will be off by ~2.16×. The build pipeline applies the dedup (key: `entity_name, posting_date, account_code, amount, project_code, lot, memo_1, description, batch_description`, prefer the row with most non-null metadata). Raw `staged_gl_transactions_v2.parquet` is preserved unchanged so anyone re-doing analysis can audit the artifact.
- **VF is one-sided**: only asset-side debits (3 account codes: 1535, 1540, 1547). It is *not* a balanced trial-balance. Treat as authoritative for "how much cost was capitalized into lot X" — not for cash, AP, or P&L questions.
- **QB register is tie-out only**: different chart of accounts (177 codes; `132-XXX`, `510-XXX`, …), zero account_code overlap with VF/DR. Naively summing QB against VF would double-count. Use QB exclusively for 2025 vendor / cash / AP queries on a single entity (BCPD) and don't aggregate across feeds without a chart-of-accounts crosswalk.
- **Phase grain is not in GL**: phase column is 0% filled across all three GL source schemas. Phase rollups derive from inventory + Lot Data + 2025Status + ClickUp.
- **Allocation expansion is gated**: Flagship Allocation Workbook v3 has the framework (8 communities × 67 phase-rows) but most cells are $0. Until the workbook is filled in (or an OfferMaster fallback is wired), only Lomond Heights and Parkway Fields have populated budget data.
- **Inventory file selection**: workbook (2) was used, deviating from the lane-doc claim of (4). Workbook (2) is freshest by ~2 days and carries 1 net-new sale event. Confirm with the human if intent was different.

---

## 5. What it cannot answer (do not invent)

- **Org-wide actuals**. Hillcrest Road at Saratoga, LLC and Flagship Belmont Phase two LLC have GL data only through 2017-02. Org-wide v2 is explicitly blocked until a fresh GL pull lands for 2017-03 onward. v0 ships BCPD-only by design.
- **2017-03 → 2018-06 BCPD spend** (15 months). Zero rows for any entity in this window across the entire dump. The gap cannot be reconstructed from existing files.
- **Per-lot cost for 9 active BCPD projects** with no GL coverage and no Collateral Report row: Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Lewis Estates, Santaquin Estates, Westbridge. Lot inventory exists; cost is unknown and should not be estimated.
- **Vendor analysis outside 2025**. Vendor lives only in QB register, which only covers 2025 BCPD.
- **Phase-level cost from GL alone** (phase column empty across DR/VF/QB).
- **Per-lot cost** for projects whose VF lot codes encode phase prefixes (most of Harmony, parts of Parkway Fields, Lomond Heights) — until the phase-aware decoder lands, lot-level matching for those projects is partial.

---

## 6. What source data would improve coverage next

In rough order of value-per-effort:

1. **Fresh GL pull for Hillcrest + Flagship Belmont covering 2017-03 onward**, scoped to those entity codes. Unblocks org-wide v2 (Track B).
2. **Fresh GL pull covering the 2017-03 → 2018-06 window** for any entity (BCPD especially). Closes the 15-month dump-wide gap.
3. **Populated Flagship Allocation Workbook v3** (or equivalent budget data) for Arrowhead Springs, Ben Lomond, Harmony, Lewis Estates, Salem Fields, Scarlet Ridge, Willowcreek. Today the workbook framework is in place but cells are mostly empty. This unblocks budget-vs-actual variance analysis for ~70% of active phases.
4. **Cost source for the 9 active BCPD projects with no GL coverage** (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Lewis Estates, Santaquin Estates, Westbridge). Either a project-tagged GL extract or a parallel allocation/underwriting workbook.
5. **A formal phase-encoding decoder for VF lot codes** (e.g., `Harm3` lot `1034` → Harmony Phase 3 Lot 34). This is mostly a documentation / parsing exercise once we get a key from the source-system owner; would lift GL ↔ inventory triangle from ~37% to a much higher number.
6. **Chart-of-accounts crosswalk** mapping QB register codes (`132-XXX`, `510-XXX`) to legacy chart codes used by VF/DR. Required for QB ↔ VF tie-out at category level and would unlock cross-feed reconciliation.
7. **Project-code crosswalk between DR-era and VF-era** for cross-era project rollups (e.g., would let "Parkway Fields all-time cost" be a single number rather than two era-by-era numbers). Lower priority because most use cases are post-2018.
8. **Improved ClickUp lot-tagging discipline**. Currently 21% of tasks are lot-tagged; raising that lifts TaskState coverage proportionally. Probably an ops-process change rather than a data fix.
9. **Confirmation of intended inventory workbook**. If the human's intent was the file marked `(4)` regardless of freshness, restage from `(4)` and rerun. Two-lot delta is small but non-zero.

Items 1, 2, 3, 4, and 8 require *new data*. Items 5, 6, 7 are mostly transformation logic on data we already have. Item 9 is a quick clarification.

---

## Companion artifacts

| artifact | purpose |
|---|---|
| `output/operating_state_v2_bcpd.json` | the canonical state document (3.3MB) |
| `output/agent_context_v2_bcpd.md` | brief an agent loads to ground its answers |
| `output/state_query_examples_v2_bcpd.md` | 12 worked queries demonstrating safe usage |
| `output/state_quality_report_v2_bcpd.md` | per-field fill rate + per-project coverage matrix |
| `data/reports/guardrail_check_v0.md` | three-prereq GREEN/RED check + DataRails dedup + cost-source hierarchy |
| `data/reports/join_coverage_v0.md` | GL ↔ inventory ↔ ClickUp coverage by year and project |
| `data/reports/staged_inventory_lots_validation_report.md` | inventory stage validation + workbook (2) deviation rationale |
| `docs/ontology_v0.md`, `docs/source_to_field_map.md`, `docs/crosswalk_plan.md` | ontology, field map, crosswalk rules |
| `docs/operating_state_v2_build_plan.md` | re-runnable build playbook |

v0 is BCPD-scoped and additive. v1 outputs (`output/operating_state_v1.json`, `output/agent_context_v1.md`, `output/lot_state_real.csv`, …) are unchanged.
