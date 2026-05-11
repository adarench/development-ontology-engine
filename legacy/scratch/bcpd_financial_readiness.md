# BCPD Financial Readiness — Terminal B

**Built**: 2026-05-01
**Source**: `data/staged/staged_gl_transactions_v2.parquet` filtered to `entity_name == 'Building Construction Partners, LLC'` (197,852 rows).
**Companion**: `scratch/gl_financials_findings.md` (full findings, including DR row-multiplication artifact in B4 and QB-overlap reasoning in B5).

---

## BCPD GL capability matrix

| question | YES / NO / WITH-CAVEATS | caveat / recommended action |
|---|---|---|
| **BCPD project-level actuals (multi-year)** | **WITH-CAVEATS** | VF gives 100% project fill on 87,032 rows for 2018-2025 ($346.5M one-sided cost basis). DR gives 49.5% project fill on 111,497 rows for 2016-02→2017-02 ($330.9M debit / $331.4M credit AFTER mandatory dedup). **Project codes use two different encodings between eras** (DR numeric `00010030`, VF alphanumeric `PWFS2`) with **no overlap** — Terminal A must build a project-code crosswalk before any cross-era rollup is meaningful. **DR must be deduplicated first** (2.16× multiplication artifact, see findings B4). Within each era, project rollups are reliable. |
| **BCPD phase-level actuals** | **NO** | The canonical `phase` column is 0% filled across all three GL sources. DR has a sparse `job_phase_stage` (7.2% fill, 10 distinct values like `01`, `04`, `10`) but it is not a phase identifier of the kind needed for phase-state rollups. Phase grain must come from ClickUp + phase dictionary work, not from GL. |
| **BCPD lot-level actuals** | **WITH-CAVEATS** | VF gives 100% lot fill on 2018-2025 (892 distinct lots, 1,306 distinct (project, lot) pairs). DR gives 49.5% lot fill on 2016-02→2017-02 (409 distinct lots, 619 distinct (project, lot) pairs). Lot codes are 4-digit numeric in both, but `lot` alone is not unique — must always be paired with `project`. **Same crosswalk caveat as project** for cross-era joins. **Same DR-dedup caveat**. Within VF, BCPD lot-level cost is the cleanest grain available in the entire dump. |
| **BCPD account / cost-category rollups** | **WITH-CAVEATS** | DR (155 codes) and VF (3 codes — capitalized-cost subset) **share the legacy 4-digit chart of accounts**, so DR-era and VF-era account rollups are directly compatible. **QB register uses a different newer chart** (177 codes, e.g. `132-187`, `510-XXX`) with **zero account_code overlap to DR/VF**. For BCPD 2025 specifically, the primary feed (VF) and the supplementary feed (QB) cannot be aggregated against the same account dimension without a separate chart-of-accounts crosswalk. Recommend account-level rollups using DR + VF only, on the legacy chart. |
| **BCPD vendor / subledger analysis** | **NO at lot/project grain; YES at entity grain for 2025-only via QB** | Subledger is effectively absent (DR 0.22% / VF 0% / QB 0%). Vendor lives **only** in QB register: 95.7% fill, 161 distinct values, 2025-only. Vendor names are hierarchical strings like `Ault Farms aka Parkway Fields:Parkway Fields E-1` — usable for 2025 vendor activity at the entity level, **not** as a lot or project grain join key. Promise vendor breakdowns in v2 only for 2025 BCPD entity-level views. |
| **Org-wide actuals (any non-BCPD entity has post-2017 data?)** | **NO** | Hillcrest Road at Saratoga LLC: 12,093 rows total, all in 2016-01→2017-02. Flagship Belmont Phase two LLC: 495 rows total, all in 2016-04→2017-02. Neither entity appears in Vertical Financials (single-entity BCPD) or QB register (BCPD GL Detail). Both are frozen at 2017-02 in the entire dump. See blocker paragraph below. |

---

## Org-wide Operating State v2 — explicit blocker statement

Org-wide Operating State v2 cannot be published from the current dump. **Hillcrest Road at Saratoga LLC** (12,093 GL rows, all from `GL (1..14).csv` between 2016-01-01 and 2017-02-28) and **Flagship Belmont Phase two LLC** (495 rows, same window) appear in **no other GL source in the available zips** — neither `Vertical Financials.csv` (single-entity BCPD by design) nor `BCPD GL Detail.csv` (single-entity BCPD by filename and content) carries them, and `phase_cost_starter_data.zip` has no other entity-tagged GL file. Unblocking either requires a fresh DataRails / Sage / source-system pull covering 2017-03 onward, scoped to those entity codes; nothing in the current data can substitute. Separately, the 2017-03-01 → 2018-06-25 gap (~15 months, zero GL rows for **any** entity, including BCPD) likewise cannot be filled from existing files — a fresh export covering that period is the only path. Until both are addressed, an org-wide v2 release would mix 2024-2025 BCPD activity against 2017-frozen Hillcrest/Flagship Belmont, which is misleading without explicit per-entity period labeling. **Recommended near-term path**: ship Operating State v2 as **BCPD-only** (Track A in `staged_gl_v1_vs_v2_comparison.md`); defer org-wide v2 (Track B) explicitly with a "blocked on fresh GL pulls for Hillcrest + Flagship Belmont and the 2017-03→2018-06 gap" note in `output/state_quality_report_v2_bcpd.md`.

---

## Confidence ratings

- **B3 capability matrix**: **high** for every row. Each YES/NO is supported by a fill-rate count and a distinct-value count derived directly from the parquet, not the prior validation report.
- **Org-wide blocker statement**: **high**. Confirmed zero rows for the gap and confirmed Hillcrest/Flagship Belmont absence in VF and QB by direct inspection.
- **DR-dedup recommendation referenced in the matrix**: **high**. Validated post-dedup balance (debit-credit within 0.15% across 14 files); see `scratch/gl_financials_findings.md` § B4 for full evidence.
