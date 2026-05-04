# Staged GL Transactions v2 — Validation Report

**Built**: 2026-05-01T19:00:21+00:00
**Outputs**: `data/staged/staged_gl_transactions_v2.csv` and `.parquet`
**Sources** (transactional GL only):
- `data/raw/datarails/gl/GL (1..14).csv` — DataRails 38-col bundle
- `data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv` — 46-col schema
- `data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv` — 12-col QB register

**Excluded** (per `gl_coverage_report.md`):
- `GL.csv` (6-row stub)
- `GL_QBO_*.csv` (opening-balance summaries; no transaction dates)
- All non-GL files (allocation, collateral, ClickUp, balance sheet, AR, underwriting)

## Headline numbers

- **Total v2 rows**: 210,440
- **min posting_date**: 2016-01-01
- **max posting_date**: 2025-12-31
- **null posting_date rate**: 0.00%
- **canonical columns**: 47

## Row counts by source

| source_schema | rows ingested | rows dropped | dropped reason |
|---|---:|---:|---|
| `datarails_38col` | 124,085 | 0 | no rows dropped (only GL.csv stub excluded by name) |
| `vertical_financials_46col` | 83,433 | 0 | Line Type != 'detail' (subtotal rows) |
| `qb_register_12col` | 2,922 | 405 | Type empty (account headers, total rows, blanks) |

## Row counts by source_schema (in v2)

| source_schema | rows | share |
|---|---:|---:|
| `datarails_38col` | 124,085 | 59.0% |
| `vertical_financials_46col` | 83,433 | 39.6% |
| `qb_register_12col` | 2,922 | 1.4% |

## Row counts by Posting Year

| year | rows |
|---:|---:|
| 2016 | 101,005 |
| 2017 | 23,080 |
| 2018 | 137 |
| 2019 | 175 |
| 2020 | 118 |
| 2021 | 66 |
| 2022 | 10 |
| 2023 | 3,773 |
| 2024 | 23,659 |
| 2025 | 58,417 |

## Row counts by entity

| entity_name | rows |
|---|---:|
| Building Construction Partners, LLC | 197,852 |
| Hillcrest Road at Saratoga, LLC | 12,093 |
| Flagship Belmont Phase two LLC | 495 |

## Null rates by source_schema for cost/project fields

| field | `datarails_38col` | `qb_register_12col` | `vertical_financials_46col` |
|---|---:|---:|---:|
| `project` | 50.46% | 100.00% | 0.00% |
| `project_code` | 50.46% | 100.00% | 0.00% |
| `project_name` | 50.46% | 100.00% | 100.00% |
| `phase` | 100.00% | 100.00% | 100.00% |
| `lot` | 50.46% | 100.00% | 0.00% |
| `account_code` | 0.00% | 0.00% | 0.00% |
| `account_name` | 46.23% | 0.00% | 0.00% |
| `subledger_code` | 99.78% | 100.00% | 100.00% |
| `subledger_name` | 99.78% | 100.00% | 100.00% |
| `vendor` | 100.00% | 4.28% | 100.00% |
| `memo` | 100.00% | 63.45% | 100.00% |
| `memo_1` | 0.00% | 100.00% | 0.00% |
| `memo_2` | 96.46% | 100.00% | 95.54% |
| `description` | 84.24% | 63.45% | 100.00% |

## Project / Phase / Lot usability by year and source_schema

Fill rate by canonical column. Usability threshold: ≥50% means 'usable for cost attribution'.

| source_schema | year | rows | project_fill | lot_fill | phase_fill | job_phase_stage_fill | account_code_fill |
|---|---:|---:|---:|---:|---:|---:|---:|
| `datarails_38col` | 2016 | 101,005 | 48.4% | 48.4% | 0.0% | 8.2% | 100.0% |
| `datarails_38col` | 2017 | 23,080 | 54.4% | 54.4% | 0.0% | 3.2% | 100.0% |
| `qb_register_12col` | 2025 | 2,922 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% |
| `vertical_financials_46col` | 2018 | 137 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `vertical_financials_46col` | 2019 | 175 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `vertical_financials_46col` | 2020 | 118 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `vertical_financials_46col` | 2021 | 66 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `vertical_financials_46col` | 2022 | 10 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `vertical_financials_46col` | 2023 | 3,773 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `vertical_financials_46col` | 2024 | 23,659 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `vertical_financials_46col` | 2025 | 55,495 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |

## Duplicate-row check

- **Duplicate rows by `row_hash`: 0** — every row in v2 is unique. All 210,440 rows preserved cleanly.
- Duplicate rows by `(source_schema, transaction_id, line_number)`: 207,132. **This is NOT a data-quality problem.** The source files reuse small integers like `0`, `1`, `-1` as `TransactionNumber` / `Trans No`:
  - `datarails_38col`: only **75 distinct `transaction_number` values** across 124,085 rows (top values: `-1` 47,822 rows, `0` 26,971 rows, `1` 19,677 rows). Looks like a journal sequence, not a row-level transaction id.
  - `vertical_financials_46col`: only **274 distinct values** across 83,433 rows (top: `1` 35,807, `0` 15,600, `2` 12,681). Same pattern.
  - `qb_register_12col`: 1,052 distinct `Num` values across 2,922 rows (close to a PK, but `Num` is the check/wire number — multiple lines per check).
- **Use `row_hash` (or `source_row_id`) as the stable per-row primary key.** The (transaction_id, line_number) composite is informative but is not unique.

## Schema notes — canonical fields not derivable from each source

These are intentionally left null because the source does not carry the field. Documented here so consumers can reason about the gaps.

| canonical field | datarails_38col | vertical_financials_46col | qb_register_12col |
|---|---|---|---|
| `phase` | not separable from `Lot/Phase` | not present | not present |
| `vendor` | not present (use subledger_name as proxy) | not present | from `Name` |
| `project_name` | from `ProjectName` | not present (only `Project`) | not present |
| `project_code` | from `ProjectCode` | from `Project` (no separate code/name) | not present |
| `account_group` | not present | from `Account Group` | not present |
| `account_type` | from `AccountType` | from `Account Type` | not present |
| `currency` | from `Currency` | assumed `USD` | assumed `USD` |
| `functional_currency` | from `FunctionalCurrency` | assumed `USD` | assumed `USD` |
| `memo` | not present (Memo1/Memo2 separate) | not present (Memo 1/Memo 2 separate) | from `Memo` |
| `description` | from `Description` | not present | from `Memo` (same as memo) |
| `subledger_*` | from `SubledgerCode`/`SubledgerDesc` | from `Sub-Ledger`/`Sub-Ledger Name` | not present |
| `lot` | from `Lot/Phase` (combined w/ phase) | from `Lot` | not present |
| `operating_unit` | from `OUnit` | from `OUnit` | not present |
| `major / minor` | from `Major`/`Minor` | from `Major`/`Minor` | not present |
| `line_number` | from `LineNo` | from `Line No` | not present (single-line entries) |

## Sign convention

All three sources are normalized to the same convention: **`amount` is signed; positive = debit, negative = credit**.

- DataRails 38-col: `FunctionalAmount` is already signed. The misleadingly named `DebitCredit` column is also a signed amount (in transaction currency); not a D/C flag.
- Vertical Financials 46-col: detail rows carry signed `Amount`. `Debit`/`Credit` are usually empty on detail rows; populated only on summary rows (which are filtered out).
- QB register 12-col: `Debit` and `Credit` are separate positive columns. `amount = Debit - Credit`.

---

## Addendum (Terminal B, 2026-05-02) — DataRails 38-col row-multiplication artifact

This addendum extends the existing report. **It does not delete or restructure any prior section.** Author: Terminal B (GL/Financials worker).

### Summary

The duplicate-row check above ("`Duplicate rows by row_hash: 0` … the (transaction_id, line_number) composite is informative but is not unique") is technically correct but the rationale ("source files reuse small integers like `0`, `1`, `-1`") is **incomplete and obscures a more material issue**. Re-investigating the same data shows that DataRails 38-col carries a **systematic 2.16× row-multiplication artifact at the source**: every transactional posting appears 2-3+ consecutive times in the source CSV with identical financial fields and identical `transaction_id:line_number`, but slightly different metadata bits (`account_name` filled vs blank; `account_type` filled vs blank). The metadata variance keeps `row_hash` unique, so the existing dedup check passed — but downstream consumers that sum `amount` will inflate cost rollups by ~2.16× unless they apply a stronger dedup.

### Evidence

Reproducible example (from `GL (8).csv` rows 5662-5664) — same transaction_id `1:0001`, line_number `0001`, posting_date 2016-08-18, account_code 1010, amount $5,000,000.00, memo "Loan from Vin 87 to BCP", description "Loan from Vin 87", company_code 1000:

```
row 5662: account_name='Checking - Central Bank', account_type=''
row 5663: account_name='Checking - Central Bank', account_type='A'
row 5664: account_name='',                        account_type=''
```

All three rows are present in the staged parquet with three distinct `row_hash` values.

Multiplicity is consistent across **all 14 source files**, in the range 2.11×-2.25×, computed as
`rows / distinct(posting_date, account_code, amount, entity_name, project, lot, memo_1, description, batch_description)`:

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
| **all 14** | **124,085** | **57,341** | **2.16×** |

### Resolves the +$17M apparent imbalance

The +$16,999,162 `amount` sum reported above for `datarails_38col` is an artifact of this multiplication, **not a real journal imbalance**. After deduplicating on the canonical key
`(entity_name, posting_date, account_code, amount, project, lot, memo_1, description, batch_description)`:

| metric | before dedup | after dedup |
|---|---:|---:|
| rows | 124,085 | 57,341 |
| sum(`amount`) | +$16,999,162 | **-$500,257** |
| sum(`debit_amount`) | +$807,196,648 | $330,911,984 |
| sum(`credit_amount`) | $790,197,486 | $331,412,241 |
| imbalance | +$17.0M (+2.1%) | -$0.50M (-0.15%) |

By entity after dedup: BCPD -$500K, Hillcrest +$260, Flagship Belmont ~$0. By month after dedup, BCPD never deviates from balance by more than ~$113K — consistent with cross-period cutoff entries, not structural imbalance. **DR 38-col is a balanced two-sided journal at the source level** once the multiplication is removed.

VF and QB do not exhibit this artifact (under 1% multiplicity by the same key — ignorable).

### Recommendation for downstream consumers

Any pipeline that aggregates DR 38-col `amount`, `debit_amount`, `credit_amount`, or `functional_amount` **must dedup first** on the canonical key above. The (`transaction_id`, `line_number`) composite is **not** sufficient because the duplicate rows share both. Pick one canonical row per group — preferring the row with the most non-null metadata (e.g. `account_name` AND `account_type` both populated) — before summing.

This is a hard prerequisite for Operating State v2 BCPD's 2016-2017 cost rollup. Vertical Financials and QB register can be summed directly without this step.

### Why the original dedup check missed it

The original check used `row_hash`, which incorporates every column including the metadata-bits (`account_name`, `account_type`) that vary across the duplicates — so the duplicates hash differently. The (`transaction_id`, `line_number`) check correctly flagged 207,132 dupes but the rationale attributed them to small-integer reuse alone. Both are partially right: small-integer reuse explains some of it, but for the rows where (`transaction_id`, `line_number`) are reused **and** all financial+narrative fields match, those are the multiplication artifact described here. Suggested fix to the original dedup logic: switch the dedup key from `row_hash` to the canonical financial-and-narrative key listed above.

