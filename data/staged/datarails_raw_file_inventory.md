# DataRails Raw File Inventory

**Total files audited**: 50
**Audit root**: `data/raw/datarails_unzipped/`

Both archives extracted side-by-side:
- `datarails_raw/` — from `DataRails_raw.zip` (May 1, 2026 dump, 24 files)
- `phase_cost_starter/` — from `phase_cost_starter_data.zip` (Apr 20, 2026 dump, 26 files)

## Files by likely dataset type

| type | count |
|---|---:|
| GL | 19 |
| allocation | 14 |
| collateral | 8 |
| inventory | 3 |
| ClickUp | 2 |
| balance_sheet | 2 |
| AR | 1 |
| underwriting | 1 |

## AR (1 files)

| file | ext | rows | cols | min_date | max_date | candidate dates | candidate amounts |
|---|---|---:|---:|---|---|---|---|
| `datarails_raw/AR_QBD_Uncle Boggys LLC_May 2026.csv` | csv | 8 | 8 | 2025-08-18 | 2025-12-05 | Date|Due Date | Amount|Open Balance |

## ClickUp (2 files)

| file | ext | rows | cols | min_date | max_date | candidate dates | candidate amounts |
|---|---|---:|---:|---|---|---|---|
| `datarails_raw/api-upload (1).csv` | csv | 5509 | 32 | 2022-05-25 | 2026-12-31 | date_created|date_updated|date_closed|date_done|due_date|start_date|walk_date|walk_agent|projected_close_date|cancelled_date|close_date|closed|actual_c_of_o|C_of_O|sold_date|sold | - |
| `datarails_raw/api-upload.csv` | csv | 5509 | 32 | 2022-05-25 | 2026-12-31 | date_created|date_updated|date_closed|date_done|due_date|start_date|walk_date|walk_agent|projected_close_date|cancelled_date|close_date|closed|actual_c_of_o|C_of_O|sold_date|sold | - |

## GL (19 files)

| file | ext | rows | cols | min_date | max_date | candidate dates | candidate amounts |
|---|---|---:|---:|---|---|---|---|
| `datarails_raw/GL (1).csv` | csv | 4154 | 38 | 1700-01-01 | 2017-07-07 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (10).csv` | csv | 9727 | 38 | 1700-01-01 | 2017-06-06 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (11).csv` | csv | 11244 | 38 | 1704-01-01 | 2018-08-15 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (12).csv` | csv | 14263 | 38 | 1701-01-01 | 2018-11-13 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (13).csv` | csv | 10163 | 38 | 1700-01-01 | 2018-01-15 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (14).csv` | csv | 12917 | 38 | 1700-01-01 | 2018-01-15 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (2).csv` | csv | 5594 | 38 | 1701-01-01 | 2016-10-31 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (3).csv` | csv | 6649 | 38 | 1701-01-01 | 2017-06-06 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (4).csv` | csv | 4923 | 38 | 1701-01-01 | 2017-06-06 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (5).csv` | csv | 8125 | 38 | 1701-01-01 | 2017-08-30 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (6).csv` | csv | 10232 | 38 | 1703-01-01 | 2017-06-09 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (7).csv` | csv | 7637 | 38 | 1704-01-01 | 2017-06-06 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (8).csv` | csv | 8856 | 38 | 1702-01-01 | 2017-07-13 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL (9).csv` | csv | 9601 | 38 | 1701-01-01 | 2017-06-15 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL.csv` | csv | 6 | 38 | 2026-04-20 | 2026-05-01 | PostingDate|CreatedBy|CreatedDate|ApprovedBy|ApprovalDate|ApprovalTime | DebitCredit|FunctionalAmount |
| `datarails_raw/GL_QBO_Anderson Geneva LLC_May 2026.csv` | csv | 42 | 33 | - | - | Date|Create Date|Created By|Vendor|Invoice Date | Qty|Amount|Balance|Debit|Credit|Open Balance|Tax Amount|Taxable Amount |
| `datarails_raw/GL_QBO_Geneva Project Manager LLC_May 2026.csv` | csv | 12 | 34 | - | - | Date|Create Date|Created By|Vendor|Invoice Date | Qty|Amount|Balance|Debit|Credit|Open Balance|Tax Amount|Taxable Amount |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv` | csv | 3327 | 12 | 2025-01-01 | 2025-12-31 | Date | Debit|Credit|Balance |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv` | csv | 83433 | 46 | 1701-01-01 | 2255-01-01 | Manual RE Postings|Fiscal Year|Opening Balance Date|Closing Balance Date|Posting Date|Posting Date FY|Created By|Create Date|Approved By|Approval Date|Approval Time|Refresh Date | Opening Balance Date|Opening Balance|Debit|Credit|Closing Balance|Closing Balance Date|Amount |

## allocation (14 files)

| file | ext | rows | cols | min_date | max_date | candidate dates | candidate amounts |
|---|---|---:|---:|---|---|---|---|
| `phase_cost_starter/Flagship Allocation Workbook v3.xlsx - Allocation Engine.csv` | csv | 80 | 10 | - | - | - | Total Proj Sales |
| `phase_cost_starter/Flagship Allocation Workbook v3.xlsx - Indirect & Land Pools.csv` | csv | 36 | 7 | - | - | - | - |
| `phase_cost_starter/Flagship Allocation Workbook v3.xlsx - Instructions.csv` | csv | 29 | 1 | - | - | - | - |
| `phase_cost_starter/Flagship Allocation Workbook v3.xlsx - Lot Mix & Pricing.csv` | csv | 89 | 9 | - | - | - | Avg Projected Sales Price|Total Projected Sales |
| `phase_cost_starter/Flagship Allocation Workbook v3.xlsx - Per-Lot Output.csv` | csv | 81 | 15 | - | - | - | Total Cost|Total / Lot |
| `phase_cost_starter/LH Allocation 2025.10.xlsx - AAJ.csv` | csv | 10 | 8 | - | - | - | - |
| `phase_cost_starter/LH Allocation 2025.10.xlsx - BCPBL SB.csv` | csv | 44 | 36 | - | - | - | - |
| `phase_cost_starter/LH Allocation 2025.10.xlsx - BSJ.csv` | csv | 27 | 11 | - | - | - | - |
| `phase_cost_starter/LH Allocation 2025.10.xlsx - JCSList.csv` | csv | 54 | 25 | - | - | - | - |
| `phase_cost_starter/LH Allocation 2025.10.xlsx - LH.csv` | csv | 91 | 40 | - | - | - | - |
| `phase_cost_starter/LH Allocation 2025.10.xlsx - PLJ.csv` | csv | 39 | 23 | - | - | - | - |
| `phase_cost_starter/Parkway Allocation 2025.10.xlsx - AAJ.csv` | csv | 49 | 32 | - | - | - | - |
| `phase_cost_starter/Parkway Allocation 2025.10.xlsx - JCSList.csv` | csv | 54 | 25 | - | - | - | - |
| `phase_cost_starter/Parkway Allocation 2025.10.xlsx - PF.csv` | csv | 92 | 40 | - | - | - | - |

## balance_sheet (2 files)

| file | ext | rows | cols | min_date | max_date | candidate dates | candidate amounts |
|---|---|---:|---:|---|---|---|---|
| `datarails_raw/Balance_Sheet_QBO_Anderson Geneva LLC_May 2026.csv` | csv | 109 | 2 | - | - | - | Total |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Combined BS.csv` | csv | 80 | 17 | - | - | - | - |

## collateral (8 files)

| file | ext | rows | cols | min_date | max_date | candidate dates | candidate amounts |
|---|---|---:|---:|---|---|---|---|
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - 2025Status.csv` | csv | 3628 | 26 | 2021-12-07 | 2025-12-31 | Status Date|Vert Sold | Vertical Costs|Shared Cost Alloc.|Lot Cost |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv` | csv | 59 | 64 | - | - | - | - |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Cost to Complete Summary.csv` | csv | 11 | 9 | - | - | - | - |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - IA Breakdown.csv` | csv | 37 | 4 | - | - | - | TOTAL |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Lot Data.csv` | csv | 3627 | 26 | 1899-12-30 | 2055-03-01 | ProdType|HorzStart|HorzEnd|VertStart|VertClose | - |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - OfferMaster.csv` | csv | 15 | 6 | - | - | - | Base Costs|Option Cost|Total |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - PriorCR.csv` | csv | 52 | 64 | - | - | - | - |
| `phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - RBA-TNW.csv` | csv | 21 | 9 | - | - | - | - |

## inventory (3 files)

| file | ext | rows | cols | min_date | max_date | candidate dates | candidate amounts |
|---|---|---:|---:|---|---|---|---|
| `datarails_raw/Inventory _ Closing Report (2).xlsx` | xlsx | 74 | 85 | - | - | - | 2019 Total |
| `datarails_raw/Inventory _ Closing Report (3).xlsx` | xlsx | 74 | 85 | - | - | - | 2019 Total |
| `datarails_raw/Inventory _ Closing Report (4).xlsx` | xlsx | 74 | 85 | - | - | - | 2019 Total |

## underwriting (1 files)

| file | ext | rows | cols | min_date | max_date | candidate dates | candidate amounts |
|---|---|---:|---:|---|---|---|---|
| `phase_cost_starter/Dehart Underwriting(Summary).csv` | csv | 122 | 200 | - | - | - | - |

## Notes on date detection

- For DataRails 38-col GL files, `PostingDate` is the canonical transaction date.
  `CreatedDate` and `ApprovalDate` extend later (catch-up entries). `ApprovalTime` is a time-of-day stored as Excel-epoch fractional days, so its 1700–1948 date range is meaningless — that column is excluded from real-date range conclusions below.
- For Vertical Financials.csv, `Posting Date` is canonical. `Refresh Date` (2026-02-11) tells us when the export ran.
- For QB-style files (`BCPD GL Detail.csv`, QBO/QBD register files), the `Date` column is canonical. The QBO register exports for Anderson Geneva and Geneva Project Manager have NO populated transaction dates — every row is `Beginning Balance` or blank — so they are NOT transactional GL despite the filename prefix `GL_QBO_`.
