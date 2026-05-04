# Staged GL Transactions — Validation Report

**Staged at**: 2026-05-01T16:57:37+00:00
**Source**: `data/raw/datarails/gl/GL (1..14).csv` (14 files)
**Output**: `data/staged/staged_gl_transactions.csv` and `.parquet`

## Row & column counts

- Total staged rows: **124,085**
- Original columns preserved: **38**
- Staging columns added: **3** (`source_file`, `source_row_number`, `staged_loaded_at`)
- Total columns in staged table: **41**
- Per-source row sum: **124,085** (matches total: True)
- Expected from inventory report: **124,085** (MATCH)

## Source file row counts

| source_file | rows |
|---|---:|
| GL (1).csv | 4,154 |
| GL (2).csv | 5,594 |
| GL (3).csv | 6,649 |
| GL (4).csv | 4,923 |
| GL (5).csv | 8,125 |
| GL (6).csv | 10,232 |
| GL (7).csv | 7,637 |
| GL (8).csv | 8,856 |
| GL (9).csv | 9,601 |
| GL (10).csv | 9,727 |
| GL (11).csv | 11,244 |
| GL (12).csv | 14,263 |
| GL (13).csv | 10,163 |
| GL (14).csv | 12,917 |

## Full column list (staged)

- `source_file`
- `source_row_number`
- `staged_loaded_at`
- `PostingDate`
- `JournalCode`
- `BatchNumber`
- `DocumentNumber`
- `TransactionNumber`
- `LineNo`
- `CompanyCode`
- `CompanyName`
- `AccountCode`
- `AccountName`
- `AccountType`
- `DivisionCode`
- `DivisionName`
- `SubledgerCode`
- `SubledgerDesc`
- `OUnit`
- `Project`
- `ProjectCode`
- `ProjectName`
- `Lot/Phase`
- `JobPhaseStage`
- `Major`
- `Minor`
- `Description`
- `Memo1`
- `Memo2`
- `DebitCredit`
- `Currency`
- `FunctionalAmount`
- `FunctionalCurrency`
- `BatchDescription`
- `CreatedBy`
- `CreatedDate`
- `ApprovedBy`
- `ApprovalDate`
- `ApprovalTime`
- `Status`
- `Source`

## Entity coverage (CompanyName)

- Distinct CompanyName values: **3**
- Distinct CompanyCode values: **3**

### Top 20 entities by row count

| CompanyName | rows |
|---|---:|
| Building Construction Partners, LLC | 111,497 |
| Hillcrest Road at Saratoga, LLC | 12,093 |
| Flagship Belmont Phase two LLC | 495 |

## Posting date range

- min PostingDate: **2016-01-01**
- max PostingDate: **2017-02-28**
- PostingDate null/unparseable rate: **0.00%**

## Amount column

- Detected amount column: **`FunctionalAmount`** (signed, aligns with `DebitCredit` indicator)
- Null/unparseable rate: **0.00%**
- Sum of |FunctionalAmount|: **1,597,394,133.72**
- DebitCredit values seen: ['-0.01', '-0.09', '-0.30', '-0.32', '-0.55', '-1.09', '-1.20', '-1.28', '-1.29', '-1.38']

## Account columns

- `AccountCode` distinct: **155**, fill rate: **100.00%**
- `AccountName` distinct: **160**, fill rate: **53.77%**
- `AccountType` distinct: **6**, fill rate: **47.02%**

### Top 20 accounts by Σ|FunctionalAmount|

| account | abs_amount |
|---|---:|
| 1010 — Checking - Central Bank | 314,323,501.12 |
| 1010 —  | 157,161,750.56 |
| 2010 —  | 89,585,623.87 |
| 2010 — Accounts Payable | 89,585,623.87 |
| 1540 — Direct Construction | 79,914,047.46 |
| 1540 —  | 79,914,047.46 |
| 1547 — Direct Construction - Lot | 58,830,407.32 |
| 2320 —  | 47,878,729.64 |
| 2320 — NP - Bank of UT Revolver | 47,878,729.64 |
| 4005 — Base House | 46,159,250.00 |
| 4005 —  | 46,159,250.00 |
| 1210 —  | 37,580,995.36 |
| 1210 — Accounts Receivable | 37,580,995.36 |
| 5010 — COS - Base House | 37,112,880.45 |
| 5010 —  | 37,112,880.45 |
| 1320 —  | 31,252,690.72 |
| 1547 —  | 29,415,203.66 |
| 2351 — NP - Brighton Bank | 24,005,283.56 |
| 1320 — NR - Flagship Development | 15,626,345.36 |
| 1535 — Permits and Fees | 15,133,560.92 |

## Requested fields (Class / Customer:Job / Transaction ID / Vendor / Memo)

**Note:** the DataRails GL schema does not contain literal `Class`, `Customer:Job`, or `Vendor` columns. Closest analogues are noted; consumers should map them deliberately.

| field | fill rate |
|---|---:|
| _Class (no exact column; closest analogues: DivisionName, OUnit, JobPhaseStage)_ | — |
| `DivisionName` (DivisionName (Class analogue)) | 100.00% |
| `OUnit` (OUnit (Class analogue)) | 99.90% |
| _Customer:Job (no exact column; closest analogue: ProjectName / Lot/Phase)_ | — |
| `ProjectName` (ProjectName (Customer:Job analogue)) | 49.54% |
| `TransactionNumber` (TransactionNumber (Transaction ID part 1)) | 100.00% |
| `LineNo` (LineNo (Transaction ID part 2)) | 100.00% |
| _Vendor (no exact column; closest analogue: SubledgerDesc / SubledgerCode)_ | — |
| `SubledgerCode` (SubledgerCode (Vendor analogue)) | 0.22% |
| `SubledgerDesc` (SubledgerDesc (Vendor analogue)) | 0.22% |
| `Memo1` (Memo1) | 100.00% |
| `Memo2` (Memo2) | 3.54% |
| `Description` (Description) | 15.76% |
| `BatchDescription` (BatchDescription) | 82.85% |

## Project / Phase / Lot fields

### Project

| field | fill rate |
|---|---:|
| `Project` | 49.54% |
| `ProjectCode` | 49.54% |
| `ProjectName` | 49.54% |

### Phase / Lot

| field | fill rate |
|---|---:|
| `Lot/Phase` | 49.54% |
| `JobPhaseStage` | 7.23% |
| `Major` | 49.54% |
| `Minor` | 49.54% |

## Null rates for key fields

| field | null rate |
|---|---:|
| `PostingDate` | 0.00% |
| `JournalCode` | 0.00% |
| `TransactionNumber` | 0.00% |
| `LineNo` | 0.00% |
| `CompanyName` | 0.00% |
| `AccountCode` | 0.00% |
| `AccountName` | 46.23% |
| `FunctionalAmount` | 0.00% |
| `DebitCredit` | 0.00% |
| `Status` | 0.00% |

## Schema validation

- All 14 source files share IDENTICAL 38-column schema (column names AND order). ✅
- No silent column loss. ✅
- BOM on `PostingDate` stripped via `encoding='utf-8-sig'`. ✅
- Row total reconciles: 124,085 = 124,085. ✅
