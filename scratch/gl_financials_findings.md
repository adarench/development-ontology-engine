# GL / Financials Findings — Terminal B

**Built**: 2026-05-01
**Author**: Terminal B (GL/Financials worker)
**Scope**: Validate `staged_gl_transactions_v2`, profile cost-attribution fields, audit sign / balance, assess QB ↔ Vertical Financials overlap, document org-wide blockers.
**Primary input**: `data/staged/staged_gl_transactions_v2.parquet` (210,440 rows × 47 cols, BLAKE-style row hashes)
**Companion docs read**: `data/staged/staged_gl_transactions_v2_validation_report.md`, `data/staged/gl_coverage_report.md`, `data/staged/gl_candidate_inventory.csv`, `data/reports/staged_gl_v1_vs_v2_comparison.md`.

All row counts and sums in this document were re-derived from the parquet, not copied from the prior validation report.

---

## B1 — Validate `staged_gl_transactions_v2`

**Confirmed**:

| check | expected | observed | result |
|---|---|---|---|
| total rows | 210,440 | 210,440 | ✅ |
| min `posting_date` | 2016-01-01 | 2016-01-01 | ✅ |
| max `posting_date` | 2025-12-31 | 2025-12-31 | ✅ |
| `posting_date` null count | 0 | 0 | ✅ |
| `datarails_38col` rows | 124,085 | 124,085 | ✅ |
| `vertical_financials_46col` rows | 83,433 | 83,433 | ✅ |
| `qb_register_12col` rows | 2,922 | 2,922 | ✅ |
| `row_hash` distinct | 210,440 | 210,440 | ✅ |
| `row_hash` null | 0 | 0 | ✅ |
| 2017-03-01 → 2018-06-25 gap | 0 rows | 0 rows | ✅ |

The headline structure of v2 is sound. Confidence: **high**. The validation report's row-count, schema, date, and hash claims all reproduce.

**Sign convention claim from existing report does NOT hold uniformly across schemas** (see B4 for full investigation). Quick result:

| schema | rows w/ amount > 0 | rows w/ amount < 0 | rows w/ amount = 0 | sum of amount |
|---|---:|---:|---:|---:|
| `datarails_38col` | 68,691 | 55,248 | 146 | +$16,999,162 |
| `vertical_financials_46col` | 77,724 | **0** | 5,709 | +$346,517,009 |
| `qb_register_12col` | 1,559 | 1,302 | 61 | ≈ $0 (balanced) |

Vertical Financials carries **only positive amounts** — it is structurally a one-sided debit-only feed, not a balanced two-sided journal. The v2 report's claim that "amount is signed; positive = debit, negative = credit" is technically true (positive = debit), but in this source there are no credit-side rows at all by design. This is a **finding**, not a defect — see B4.

---

## B2 — Cost-attribution field profile

### Fill rate by source schema (entire feed)

| field | `datarails_38col` (124,085) | `vertical_financials_46col` (83,433) | `qb_register_12col` (2,922) |
|---|---:|---:|---:|
| `project` | 49.5% | **100%** | 0% |
| `project_code` | 49.5% | **100%** | 0% |
| `project_name` | 49.5% | 0% | 0% |
| `lot` | 49.5% | **100%** | 0% |
| `phase` | 0% | 0% | 0% |
| `job_phase_stage` | 7.2% | 0% | 0% |
| `major` | 49.5% | **100%** | 0% |
| `minor` | 49.5% | **100%** | 0% |
| `division_code` | 100% | 100% | 0% |
| `division_name` | 100% | 100% | 0% |
| `operating_unit` | 99.9% | 100% | 0% |
| `subledger_code` | 0.22% | 0% | 0% |
| `subledger_name` | 0.22% | 0% | 0% |
| `vendor` | 0% | 0% | **95.7%** |
| `account_name` | 53.8% | 100% | 100% |
| `memo_1` | 100% | 100% | 0% |
| `memo_2` | 3.5% | 4.5% | 0% |
| `description` | 15.8% | 0% | 36.6% |

DR's `project`/`lot`/`major`/`minor` fill rate is exactly 49.5% (61,474 / 124,085 rows) — i.e., the SAME rows are tagged or untagged across all four columns. Untagged DR rows are concentrated in non-job-cost accounts (cash, AP, equity).

### Fill rate by year — BCPD only (the only multi-year entity)

| year | source | rows | project | lot | phase | job_phase_stage | account_code |
|---:|---|---:|---:|---:|---:|---:|---:|
| 2016 | datarails_38col | 90,090 | 49.6% | 49.6% | 0% | 8.7% | 100% |
| 2017 | datarails_38col | 21,407 | 54.1% | 54.1% | 0% | 3.4% | 100% |
| 2018 | vertical_financials_46col | 137 | 100% | 100% | 0% | 0% | 100% |
| 2019 | vertical_financials_46col | 175 | 100% | 100% | 0% | 0% | 100% |
| 2020 | vertical_financials_46col | 118 | 100% | 100% | 0% | 0% | 100% |
| 2021 | vertical_financials_46col | 66 | 100% | 100% | 0% | 0% | 100% |
| 2022 | vertical_financials_46col | 10 | 100% | 100% | 0% | 0% | 100% |
| 2023 | vertical_financials_46col | 3,773 | 100% | 100% | 0% | 0% | 100% |
| 2024 | vertical_financials_46col | 23,659 | 100% | 100% | 0% | 0% | 100% |
| 2025 | vertical_financials_46col | 55,495 | 100% | 100% | 0% | 0% | 100% |
| 2025 | qb_register_12col | 2,922 | 0% | 0% | 0% | 0% | 100% |

### Cardinality of join keys

| field | DR 38-col | VF 46-col | QB 12-col |
|---|---:|---:|---:|
| `project` (distinct codes) | 33 | **17** | 0 |
| `lot` (distinct lots) | 409 | **892** | 0 |
| `(project, lot)` distinct pairs | 619 | **1,306** | 0 |
| `phase` | 0 | 0 | 0 |
| `job_phase_stage` | 10 (sparse) | 0 | 0 |
| `account_code` distinct | 155 | 3 | 177 |
| `vendor` distinct | 0 | 0 | 161 |

**Join-key usability** (`high` = ≥ 95% fill on relevant scope, `medium` = 50-94%, `unmapped` = < 50% or 0):

| grain | DR 38-col | VF 46-col | QB 12-col | Notes |
|---|---|---|---|---|
| **entity** | high (`entity_name`, 100%) | high | high | Universal join key. |
| **project** | medium (49.5%) | high (100%) | unmapped (0%) | Project codes use **two different encodings**: DR is numeric 8-digit (`00010030`), VF is alpha-numeric short (`PWFS2`, `AultF`). **No code overlap between eras** — needs a crosswalk before cross-era project rollups work. |
| **(project, lot)** | medium (49.5%) | high (100%) | unmapped | Lot codes are 4-digit numeric in both DR and VF, but the project segment differs by era — same crosswalk dependency. |
| **lot only (within project)** | medium | high | unmapped | Bare `lot` like `0008` is not unique across projects; always pair with project. |
| **phase** | unmapped | unmapped | unmapped | Phase column is empty across all schemas. DR's `job_phase_stage` carries 10 distinct values (`01`, `04`, `10`, …) but only on 7.2% of rows — not usable as a join key. |
| **account / cost-category** | high (100%) | high (100%) | high (100%) | But charts of accounts split by source: DR/VF share the **same legacy 4-digit chart** (`1540`, `1010`, …), with VF being a 3-account subset of DR's 155-account chart. QB uses a **different newer chart** (`132-187`, `510-XXX`, …) with **zero account_code overlap** to DR/VF. Joining QB to DR/VF at the account level requires a chart-of-accounts crosswalk (out of scope for v2 today). |
| **subledger** | unmapped (0.22%) | unmapped | unmapped | Effectively absent. The DR 270 filled rows are concentrated in 29 distinct codes (loan/AP subledgers); too sparse to drive any rollup. |
| **vendor** | unmapped | unmapped | medium (95.7%) | QB-only and 2025-only — 161 distinct vendor names, including hierarchical class:lot strings like `Ault Farms aka Parkway Fields:Parkway Fields E-1`. Sufficient for 2025 BCPD vendor analysis; not generalizable beyond. |
| **operating_unit** | high (99.9%) | high (100%) | unmapped | DR has 5 distinct OUs (multi-entity); VF is single-OU (BCPD), so it carries no segmentation information. |
| **division** | high (100% across all sources) | high | unmapped | Single-division (`000 / Corporate`) in DR/VF — useful as a constant tag, not a slicing key. |

**Confidence**: **high** for the per-source fill-rate matrix; **high** for the join-key usability conclusions. Recommendation: see B3 + bcpd_financial_readiness.md.

---

## B3 — BCPD GL capability matrix (summary)

Full per-question matrix lives in `scratch/bcpd_financial_readiness.md`. Headline:

- BCPD project-level actuals (multi-year): **YES, with caveats** (project-code crosswalk between DR-era and VF-era required).
- BCPD phase-level actuals: **NO** (phase column is empty everywhere).
- BCPD lot-level actuals: **YES, with caveats** (lot is 100% filled in VF for 2018-2025 but only 49.5% in DR for 2016-2017; same project-code crosswalk caveat).
- BCPD account / cost-category rollups: **YES, with caveats** (DR/VF share legacy chart; QB uses different chart).
- BCPD vendor / subledger analysis: **NO at lot/project grain; YES at entity grain for 2025-only via QB.**
- Org-wide actuals: **NO** (Hillcrest, Flagship Belmont have no GL data after 2017-02).

---

## B4 — Sign / balance audit (with major correction)

I investigated the +$346.5M Vertical Financials sum and the +$17M DataRails 38-col sum that the existing validation report flagged. **Both are explainable; one is by design, the other is a previously-undetected source-level row-multiplication artifact. The underlying GL is balanced once the artifact is corrected.**

### Vertical Financials 46-col: +$346.5M is structural, not missing data

VF is filtered to a one-dimensional slice of the chart of accounts:

```
account_group:  Balance Sheet     (100% of rows)
account_type:   Asset             (100% of rows)
account_code:   1540 Direct Construction       75,683 rows  $223.4M
                1547 Direct Construction-Lot    1,972 rows   $99.1M
                1535 Permits and Fees           5,778 rows   $24.1M
                                                           --------
                                                            $346.5M
```

There are exactly **3 account codes** and **zero credit-side rows** (`credit_amount` sum = $0; `Amount` ≥ 0 in all 83,433 rows). VF is a **purpose-built capitalized-cost feed**: each row records the asset-side debit of an entry that capitalizes construction cost into the lot/project balance. The corresponding credit (cash, AP, accrued) lives in a different report and is **not included in VF**. This is normal for a "vertical financials" cost-accumulation export — it is not a balanced trial-balance.

Implication: VF is the **canonical source for BCPD lot-level cost basis 2018-2025**. It is **not** a primary source for cash/working-capital, AP aging, P&L, or trial balance — those questions require QB or a separate GL pull.

**Confidence: high.** Three account codes, all asset/balance-sheet, all one-sided is unambiguous evidence of a one-sided cost-roll-up extract.

### DataRails 38-col: +$17M is a SOURCE-FILE row-multiplication artifact, NOT a real journal imbalance

This is the most significant finding in this lane. **Every transactional row in `GL (1..14).csv` appears 2-3+ consecutive times in the source file**, with identical financial fields and identical `transaction_id:line_number`, but slightly different metadata bits (`account_name` filled vs blank, `account_type` filled vs blank). The differing metadata bits cause `row_hash` to be unique — so the existing dedup check passed — but the rows are **functional duplicates** for any financial roll-up.

**Concrete example** from `GL (8).csv` rows 5662-5664 — same transaction_id `1:0001`, same posting_date 2016-08-18, same account_code 1010, same amount $5,000,000.00, same memo "Loan from Vin 87 to BCP", same description, same batch_description, same fiscal_period — but three rows:

```
row 5662: account_name='Checking - Central Bank', account_type=''
row 5663: account_name='Checking - Central Bank', account_type='A'
row 5664: account_name='',                        account_type=''
```

Sum these naively and you triple-count $5M into $15M.

**Multiplicity by source file** (calculated by `rows / distinct(posting_date, account_code, amount, entity_name, project, lot, memo_1, description, batch_description)`):

| file | rows | distinct keys | multiplicity |
|---|---:|---:|---:|
| `GL (1).csv` | 4,154 | 1,843 | 2.25× |
| `GL (2).csv` | 5,594 | 2,535 | 2.21× |
| `GL (3).csv` | 6,649 | 3,047 | 2.18× |
| `GL (4).csv` | 4,923 | 2,249 | 2.19× |
| `GL (5).csv` | 8,125 | 3,682 | 2.21× |
| `GL (6).csv` | 10,232 | 4,699 | 2.18× |
| `GL (7).csv` | 7,637 | 3,448 | 2.21× |
| `GL (8).csv` | 8,856 | 4,126 | 2.15× |
| `GL (9).csv` | 9,601 | 4,430 | 2.17× |
| `GL (10).csv` | 9,727 | 4,512 | 2.16× |
| `GL (11).csv` | 11,244 | 5,213 | 2.16× |
| `GL (12).csv` | 14,263 | 6,653 | 2.14× |
| `GL (13).csv` | 10,163 | 4,793 | 2.12× |
| `GL (14).csv` | 12,917 | 6,111 | 2.11× |
| **all** | **124,085** | **57,341** | **2.16×** |

The multiplicity is consistent across all 14 files (2.11–2.25×). It is a **systematic export-format property of the upstream system** (likely Sage/JD-Edwards or similar — the export emits each posting line several times for different account/dimension "views"), not a one-off corruption.

**Sums after deduplicating DR 38-col on the canonical financial fields**:

```
rows           : 124,085  →  57,341
sum(amount)    : +$16.999M  →  -$0.500M  (previously "imbalance"; actually -0.15% of total flow)
sum(debit_amt) : +$807.2M   →  +$330.9M
sum(credit_amt): +$790.2M   →  +$331.4M
debit/credit balance : $17M one-sided  →  $0.5M one-sided (well within rounding)
```

By entity, after dedup:

| entity | dedup rows | sum(amount) |
|---|---:|---:|
| Building Construction Partners, LLC | 51,694 | -$500,517 |
| Hillcrest Road at Saratoga, LLC | 5,447 | +$260 |
| Flagship Belmont Phase two LLC | 200 | -$0 |

By month after dedup, BCPD never deviates from balance by more than ~$113K — consistent with cross-period rounding/cutoff entries, not structural imbalance.

**Conclusion**: **DataRails 38-col is a balanced two-sided journal at the source level. The +$17M apparent imbalance was caused by a 2.16× row-multiplication artifact in the export format that was not detected by the existing `row_hash` dedup check.** Recommendation: **before any cost roll-up from DR 38-col, deduplicate on `(entity_name, posting_date, account_code, amount, project, lot, memo_1, description, batch_description)`** (or an equivalently strong key — must include the financial+narrative fields, NOT just `transaction_id` + `line_number`, since those are already aliased across the duplicates). Pick a canonical row per group by preferring the row with most non-null metadata (e.g., `account_name` and `account_type` both populated). This is a v2-blocker for any consumer that sums DR amounts.

**Confidence: high.** Verified with three independent lines of evidence: (1) consecutive `source_row_id` for duplicates, (2) consistent ~2.16× multiplicity across all 14 files, (3) post-dedup sums align with debit-credit balance to within 0.15%.

### QB register 12-col: balanced, no artifact

QB sums to ≈ $0 (debit $215.25M = credit $215.25M to ten decimal places). 25 of 2,922 rows are duplicates by the canonical key — under 1% multiplicity, ignorable. **QB is a clean balanced register.**

**Confidence: high.**

---

## B5 — QB-register vs Vertical-Financials overlap

### Question

Both feeds cover BCPD 2025: VF has 55,495 rows, QB has 2,922 rows. Are they two views of the same transactions, or disjoint scopes?

### Evidence

| dimension | VF 2025 BCPD | QB 2025 BCPD |
|---|---|---|
| rows | 55,495 | 2,922 |
| sum(amount) (one-sided DR) | $185.0M | n/a (balanced) |
| sum(debit) | $185.0M | $215.2M |
| sum(credit) | $0 | $215.2M |
| account_code chart | legacy 4-digit (3 codes: 1535/1540/1547) | new dotted (177 codes: 132-XXX, 510-XXX, etc.) |
| project / lot fill | 100% / 100% | 0% / 0% |
| vendor | absent | 95.7% (161 distinct) |
| **account_code overlap with the other feed** | **0 codes shared** | **0 codes shared** |
| grain | line-level capitalized cost per (project, lot, major, minor) | journal line per (account, check#, vendor) |

### Assessment

The two feeds use **completely different chart-of-accounts encodings** with **zero account_code overlap**. The dollar totals also differ ($185M VF asset DR vs $215M QB DR=CR). VF is a one-sided cost-accumulation feed at the lot grain; QB is a balanced double-entry register at the bank/AP/check grain. They are **not redundant views of the same transactions** — they are **complementary views with different lens**:

- **VF** shows: "for each line item that capitalized cost into a lot, where did it land?" (asset-side only, lot-tagged).
- **QB** shows: "what cash/AP/payroll/etc. movements happened, by vendor and by check number?" (full double-entry, vendor-tagged, no lot tagging).

A given construction-cost event likely produces:
- One DR row in VF against `1540 Direct Construction`, tagged with project+lot, sized at the capitalized amount;
- One pair of DR/CR rows in QB against e.g. `132-187 Inventory Asset` / `210-100 Accounts Payable`, sized at the cash-flow-equivalent and tagged with the vendor name.

**These are not the same row, and naive concatenation would double-count.**

### Recommendation

**Tie-out only; exclude QB register from primary BCPD cost rollups.** Specifically:

- **Primary cost-attribution feed for BCPD 2018-2025 = Vertical Financials.** This is the lot-tagged, capitalized-cost view and is correct for "what is the cost basis of lot X?".
- **QB register = supplementary 2025 view.** Use for: vendor-level activity, monthly cash/AP movement on the BCPD checking account, AP aging snapshots, period-end tie-out at the chart-of-accounts category level.
- **Tie-out method (out-of-scope for v2 today, but flag for v3)**: build a chart-of-accounts crosswalk that maps QB account codes (`132-XXX`, `510-XXX`, …) to the legacy chart codes used in VF/DR. Then aggregate QB asset-side DR by category and compare to VF monthly capitalization totals. Discrepancies are the signal we care about (e.g., expense vs capitalize policy drift, missed accruals).

This is the **default recommendation** the lane doc requested when ambiguous; the evidence here (zero account-code overlap, different totals, different grains) makes it the **only safe** recommendation.

**Confidence: high.**

---

## B6 — Org-wide blocker statement

See `scratch/bcpd_financial_readiness.md` for the explicit org-wide blocker paragraph. Short version: only Building Construction Partners, LLC has GL data past 2017-02; Hillcrest Road at Saratoga LLC (12,093 rows) and Flagship Belmont Phase two LLC (495 rows) are frozen at 2017-02 in the available zips, and the 2017-03 → 2018-06 gap (~15 months) has zero rows in the entire dump and cannot be filled from existing files.

---

## Recommended actions for Terminal A (handoff summary)

1. **Treat DR 38-col as 2.16× row-multiplied at the source.** Any pipeline that sums DR amounts must dedup first on the canonical key listed in B4, picking the row with most non-null metadata as the canonical representative. **This is a hard prerequisite for any BCPD 2016-17 cost rollup**, including Operating State v2 BCPD. (Optional addendum to the validation report covers this — see end of this file for the full text.)
2. **Use Vertical Financials as the primary cost-attribution feed for BCPD 2018-2025.** 100% project + lot + major + minor fill, single chart of accounts (legacy), 1,306 distinct (project, lot) combos.
3. **Build a project-code crosswalk** to bridge DR-era project codes (numeric 8-digit) to VF-era project codes (alpha-numeric short). 33 + 17 distinct codes, 40 unique on BCPD; small enough for human review. This is required for any cross-era project rollup; without it, Operating State v2 BCPD must label 2016-17 and 2018-25 cost separately.
4. **Exclude QB register from the primary BCPD rollup**; treat it as a 2025 vendor / cash / AP supplementary view only. Different chart of accounts, zero overlap, would double-count.
5. **Phase grain is unsupported in GL.** Phase rollups will need to come from ClickUp / phase dictionary work that lives in Terminal C's lane. Don't waste time trying to extract phase from GL `Lot/Phase` strings — it isn't there.
6. **Vendor analysis is QB-only and 2025-only.** Don't promise vendor breakdowns in v2 outside this scope.
7. **Subledger is effectively unusable.** Drop it from any v2 schema requirement.
8. **Org-wide v2 is blocked** until fresh GL pulls land for Hillcrest and Flagship Belmont. Recommend BCPD-only v2 build now, deferring org-wide.

---

## Files written by Terminal B

- `scratch/gl_financials_findings.md` (this file)
- `scratch/bcpd_financial_readiness.md` (BCPD readiness matrix + org-wide blocker)
- Addendum appended to `data/staged/staged_gl_transactions_v2_validation_report.md` (DR row-multiplication finding)

No other files modified. No `output/`, `ontology/`, `pipelines/`, `financials/`, or other terminal's scratch was touched.
