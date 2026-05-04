# GL Coverage Report — Combined Audit Across All GL Candidates

## ⚠️ Correction to prior claim

My previous statement — **"The DataRails GL is HISTORICAL data; PostingDate runs 2016-01-01 → 2017-02-28"** — was **WRONG as a global claim about the raw DataRails dump**.

That date range is correct for **only one subset**: the 14 numbered files `GL (1..14).csv` inside `DataRails_raw.zip`. I generalised that subset to the entire raw dump without inspecting `phase_cost_starter_data.zip`. That second archive contains **`Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv`** — 83,433 rows of GL with `Posting Date` running **2018-06-26 → 2025-12-31**, plus **`BCPD GL Detail.csv`** — 3,327 rows of QB-register-style GL covering all of 2025.

Combined GL coverage across the full dump is **2016-01-01 → 2025-12-31** (approximately 10 years), with one structural gap **2017-03-01 → 2018-06-25** (~15 months) where no GL data is present.

---

## Headline numbers

- **Total GL candidate files found**: 19
- **Total rows across GL candidates**: 210,905
- **Total transactional GL rows** (excluding QBO opening-balance files and the 6-row stub): **210,845**
- **Combined min Posting Date**: 2016-01-01
- **Combined max Posting Date**: 2025-12-31
- **Coverage gap**: 2017-03-01 → 2018-06-25 (~15 months)

## Three primary GL sources

| source | rows | date range | entities | schema |
|---|---:|---|---|---|
| DataRails 38-col bundle (`GL (1..14).csv`) | 124,085 | 2016-01-01 → 2017-02-28 | 3 | DataRails 38 cols, multi-entity, includes Project/Lot/Phase tags |
| Vertical Financials (`Collateral Dec2025 ... Vertical Financials.csv`) | 83,433 | 2018-06-26 → 2025-12-31 | 1 | Vertical Financials 46 cols, single-entity (BCPD), includes Project/Lot tags |
| BCPD GL Detail (`Collateral Dec2025 ... BCPD GL Detail.csv`) | 3,327 | 2025-01-01 → 2025-12-31 | 1 (BCPD) | QuickBooks register 12 cols, single-entity, no project/lot tagging |

## Row counts by Posting Year (combined transactional GL)

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

Notable: **2017–2018 gap** (only catch-up CreatedDate entries from the DataRails bundle fall here; no Posting Date records). 2024 and 2025 are the heaviest periods.

## Row counts by file (transactional GL only)

| file | rows | min_date | max_date |
|---|---:|---|---|
| `GL (1).csv` (DataRails bundle) | 4,154 | (within 2016-2017) | (monthly partition) |
| `GL (2).csv` (DataRails bundle) | 5,594 | (within 2016-2017) | (monthly partition) |
| `GL (3).csv` (DataRails bundle) | 6,649 | (within 2016-2017) | (monthly partition) |
| `GL (4).csv` (DataRails bundle) | 4,923 | (within 2016-2017) | (monthly partition) |
| `GL (5).csv` (DataRails bundle) | 8,125 | (within 2016-2017) | (monthly partition) |
| `GL (6).csv` (DataRails bundle) | 10,232 | (within 2016-2017) | (monthly partition) |
| `GL (7).csv` (DataRails bundle) | 7,637 | (within 2016-2017) | (monthly partition) |
| `GL (8).csv` (DataRails bundle) | 8,856 | (within 2016-2017) | (monthly partition) |
| `GL (9).csv` (DataRails bundle) | 9,601 | (within 2016-2017) | (monthly partition) |
| `GL (10).csv` (DataRails bundle) | 9,727 | (within 2016-2017) | (monthly partition) |
| `GL (11).csv` (DataRails bundle) | 11,244 | (within 2016-2017) | (monthly partition) |
| `GL (12).csv` (DataRails bundle) | 14,263 | (within 2016-2017) | (monthly partition) |
| `GL (13).csv` (DataRails bundle) | 10,163 | (within 2016-2017) | (monthly partition) |
| `GL (14).csv` (DataRails bundle) | 12,917 | (within 2016-2017) | (monthly partition) |
| `Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv` (Vertical Financials) | 83,433 | 2018-06-26 | 2025-12-31 |
| `Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv` (BCPD GL Detail) | 3,327 | 2025-01-01 | 2025-12-31 |

## Entities by source

### DataRails bundle entities (3 distinct)
| CompanyName | rows |
|---|---:|
| Building Construction Partners, LLC | 111,497 |
| Hillcrest Road at Saratoga, LLC | 12,093 |
| Flagship Belmont Phase two LLC | 495 |

### Vertical Financials entities (1)
| Company Name | rows |
|---|---:|
| Building Construction Partners, LLC | 83,433 |

### BCPD GL Detail entities (1, implied by filename)
| entity | rows |
|---|---:|
| Building Construction Partners, LLC (implied by filename) | 3,327 |

**Critical observation**: only **Building Construction Partners, LLC (BCPD)** has GL coverage spanning multiple years. The other two DataRails entities — Hillcrest Road at Saratoga LLC and Flagship Belmont Phase two LLC — appear ONLY in the 2016-2017 DataRails bundle. We have no 2018+ GL data for them in this dump.

## Which files are current vs historical

| file | classification | reasoning |
|---|---|---|
| `GL (1..14).csv` | **historical** | PostingDate 2016-01 → 2017-02; ~9 years old |
| `Vertical Financials.csv` | **current (BCPD only)** | Posting Date through 2025-12-31; Refresh Date 2026-02-11 |
| `BCPD GL Detail.csv` | **current (BCPD only, calendar 2025)** | Date 2025-01 → 2025-12 |
| `GL.csv` | **stub/sample** | 6 rows, PostingDate 2026-05-01; not a real export |
| `GL_QBO_Anderson Geneva LLC_May 2026.csv` | **non-transactional** | All Date values are blank or 'Beginning Balance'; opening-balance summary, not GL |
| `GL_QBO_Geneva Project Manager LLC_May 2026.csv` | **non-transactional** | Same as above |

## Best candidates for Operating State v2

**For BCPD (the only entity with multi-year coverage)**:
- Primary: **Vertical Financials.csv** — 83,433 rows, 2018-06 → 2025-12, 100% Project & Lot fill rates, single-entity (clean), 46-col schema with explicit Sub-Ledger, Memo 1/2, Account Group, Account Type. This is the strongest GL feed in the dump.
- Augment: `GL (1..14).csv` filtered to `CompanyCode=1000` (BCPD) for 2016-01 → 2017-02 history.
- Cross-check: BCPD GL Detail.csv as a 2025 tie-out at the QB-register grain.

**For Hillcrest Road at Saratoga LLC and Flagship Belmont Phase two LLC**:
- Only `GL (1..14).csv` (2016-01 → 2017-02). Operating State for these entities will necessarily be historical unless a fresh export covering 2017-present is supplied.

**Files to ignore for v2**:
- `GL.csv` (6-row stub)
- `GL_QBO_*.csv` (no transactions; opening balances only)

## Recommendation for `staged_gl_transactions` rebuild

The current `data/staged/staged_gl_transactions.{csv,parquet}` is incomplete — it was built from `GL (1..14).csv` only and therefore covers 2016-2017 only.

**Proposed rebuild**: a normalized, multi-source staged GL with a unified column schema:

1. **Load** each of the three primary sources (DataRails bundle, Vertical Financials, BCPD GL Detail).
2. **Map** each to a common canonical schema, e.g.:
   ```
   source_file, source_schema, posting_date, fiscal_year,
   entity_code, entity_name,
   account_code, account_name, account_type,
   project_code, project_name, lot, phase,
   debit, credit, amount, currency,
   transaction_id, line_no, memo, source_confidence
   ```
3. **Concatenate** with `source_schema` ∈ {`datarails_38col`, `vertical_financials_46col`, `qb_register_12col`} for traceability.
4. **Filter** out the QBO opening-balance files and the GL.csv stub.
5. **Validate**: per-year row totals match the source files; entity totals sum correctly; the gap 2017-03 → 2018-06 is correctly empty (or sourced from yet-to-arrive data).

Recommended output paths (additive — leave existing v1 staged tables in place until v2 is validated):
- `data/staged/staged_gl_transactions_v2.csv`
- `data/staged/staged_gl_transactions_v2.parquet`
- `data/reports/staged_gl_v2_validation_report.md`
