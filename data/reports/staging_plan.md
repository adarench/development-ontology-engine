# Staging Plan — DataRails / QBO / ClickUp / Inventory Dump (2026-05-01)

This plan defines the **proposed** staged tables. No staging code has been written yet; this document is the contract the next pipeline iteration should satisfy.

Source dump: `DataRails_raw.zip` (see `data/reports/raw_data_inventory_report.md`).

---

## 1. Merge opportunities & decisions

### 1a. `GL (1).csv` … `GL (14).csv` — same schema, safe to concatenate
- All 14 files share the **identical 38-column DataRails schema** (`PostingDate, JournalCode, BatchNumber, DocumentNumber, TransactionNumber, LineNo, CompanyCode, CompanyName, …, DebitCredit, FunctionalAmount`).
- Combined row count: **124,085**.
- **Confidence: HIGH.** Concatenate into a single staged table; tag each row with `source_file` so the partition origin is traceable.
- The numbering looks like an export-pagination artifact (chunked by row count or by entity slice), not a schema split.

### 1b. `GL.csv` (6 rows) — exclude
- Same 38-column schema, but only 6 rows. Reads as a stub/preview export.
- **Decision: do not include** in the merge. Keep in raw for traceability.

### 1c. `GL_QBO_Anderson Geneva LLC_May 2026.csv` and `GL_QBO_Geneva Project Manager LLC_May 2026.csv` — DIFFERENT schema, do NOT merge with the DataRails GL bundle
- These are 33–34-column QBO register exports (`Account, Date, Transaction Type, Num, Create Date, Created By, Name, Customer, …`).
- **Confidence the schemas overlap: LOW.** They name the same business concept (general ledger lines) but use different column names, different identifier conventions, and probably different sign conventions for debits/credits.
- **Decision:** keep them in `data/raw/datarails/gl/` for now; do not merge with the DataRails bundle. Treat as reconciliation/validation data, not as primary GL.
- Future: write a separate normalizer that maps the QBO register columns onto the same canonical `staged_gl_transactions` schema. Until that exists, route them only to a side table (`staged_gl_qbo_register`) if needed.

### 1d. `api-upload.csv` and `api-upload (1).csv` — exact duplicate
- Byte-identical (same sha256 `d86de508d860…`, same 930,077 bytes, same 5,509 rows × 32 cols).
- **Decision: drop `api-upload (1).csv`** from staging. Use `api-upload.csv` as canonical.

### 1e. `Inventory _ Closing Report (2).xlsx`, `(3).xlsx`, `(4).xlsx` — near-duplicates
- Same shape (84 × 13), distinct sha256 hashes, sizes within 318 bytes.
- **Decision: use `(4).xlsx` as canonical** (latest version implied by suffix). Archive `(2)` and `(3)` to `data/raw/archive/` once we confirm `(4)` parses cleanly.
- Parser caveat: row 1 is a title (`"Flagship Lot Inventory & Development Schedule"`), so `pd.read_excel` will need `header=N` (likely `header=2` or `header=3`); current profile shows `Unnamed: 0..N` headers because the default `header=0` reads the title row.

### 1f. Do entity-specific QBO files overlap with the generic GL files?
- Likely yes for the *same posting period*, but at different grain and through a different system path. **Confidence: MEDIUM.**
- **Decision:** treat the DataRails bundle as primary; use QBO entity files only for tie-out. Do not double-count.

---

## 2. Proposed staged tables

### `staged_gl_transactions`

Built from `GL (1..14).csv`. Field naming chosen to be QBO-compatible so the future QBO normalizer can land into the same table.

| field | source mapping | notes |
|---|---|---|
| `source_file` | manifest pointer | e.g. `GL (12).csv` |
| `entity` | `CompanyName` | also keep `CompanyCode` if present |
| `account_id` | `AccountCode` (verify exact column name in next inspection pass) | |
| `account_name` | `AccountName` (verify) | |
| `amount` | `FunctionalAmount` | signed; cross-check against `DebitCredit` flag |
| `posting_date` | `PostingDate` | parse to `date` |
| `vendor` | `Vendor` if present | nullable |
| `customer` | `Customer` if present | nullable |
| `memo` | `MemoDescription` | nullable |
| `class` | `Class` | nullable |
| `customer_job` | `CustomerJob` | the most likely phase/lot tagging field — confirm |
| `transaction_id` | `TransactionNumber` + `LineNo` (composite) | needed for line-level idempotency |
| `data_type` | constant: `actual` | will diverge once budget/forecast feeds arrive |
| `scenario` | constant: `base` | placeholder for future budget/forecast scenarios |
| `source_confidence` | constant: `high` for DataRails bundle; `medium` once QBO normalizer lands | |

### `staged_clickup_tasks`

Built from `api-upload.csv` only.

| field | source mapping | notes |
|---|---|---|
| `source_file` | constant: `api-upload.csv` | |
| `task_id` | `id` | primary key |
| `parent_id` | (derive from ClickUp parent if present in raw) | the export carries `top_level_parent_id` only; intermediate parent must be inferred from ClickUp API later |
| `top_level_parent_id` | `top_level_parent_id` | join key into project/list |
| `name` | `name` | |
| `status` | `status` | |
| `assignee` | `assignee_username` | |
| `date_created` | `date_created` | epoch-ms or ISO; verify |
| `date_updated` | `date_updated` | |
| `start_date` | `start_date` | |
| `due_date` | `due_date` | |
| `date_done` | `date_done` | |
| `tags` | `tag_name` | |
| `custom_fields` | JSON-pack the lot-tracking columns: `subdivision, lot_num, walk_date, walk_agent, projected_close_date, cancelled_date, cancelled, close_date, closed, actual_c_of_o, C_of_O, sold_date, sold` | preserves all 32 source cols losslessly without column-explosion in the staged table |

### `staged_inventory_lots`

Built from `Inventory _ Closing Report (4).xlsx` after fixing the header offset.

| field | source mapping | notes |
|---|---|---|
| `source_file` | constant: `Inventory _ Closing Report (4).xlsx` | |
| `project` | (column TBD after header fix) | likely community-level |
| `community` | (column TBD) | |
| `phase` | (column TBD) | |
| `lot_number` | (column TBD) | join key into ClickUp `lot_num` |
| `lot_type` | (column TBD) | |
| `status` | (column TBD) | |
| `closing_date` | (column TBD) | projected |
| `sold_date` | (column TBD) | actual |
| `address` | (column TBD) | |
| `source_confidence` | constant: `medium` | until column mapping verified |

**Action item:** before staging, re-profile the xlsx with `header=2` and `header=3` to determine the real header row, then fill the source-column names above.

### `staged_entity_mapping`

Cannot be authoritatively built from this dump alone (we have `CompanyName` from DataRails GL and `subdivision` from ClickUp; the crosswalk between them is not in the export).

| field | source mapping | notes |
|---|---|---|
| `entity_name` | distinct `CompanyName` from DataRails GL | seed list |
| `entity_code` | distinct `CompanyCode` from DataRails GL | |
| `project_code` | distinct `subdivision` from ClickUp `api-upload.csv` | seed list |
| `source_file` | which input contributed the row | |
| `confidence` | `unmapped` until human review provides the entity↔project link | |

**Action item:** seed v0 of this table with the two distinct-value lists; the entity↔project link is a manual mapping decision, not an inference.

---

## 3. Sequencing recommendation

1. Build `staged_gl_transactions` from the 14 numbered GL files (high confidence, mechanical).
2. Build `staged_clickup_tasks` from `api-upload.csv` (high confidence, mechanical).
3. Re-profile the inventory xlsx to find the real header row, then build `staged_inventory_lots`.
4. Seed `staged_entity_mapping` distinct-value lists; flag for manual review.
5. **Defer**: QBO normalizer (`GL_QBO_*`, `Balance_Sheet_QBO_*`, `AR_QBD_*`) until the canonical staged tables are validated against existing pipeline outputs. These per-entity QBO files are best used as tie-out, not as a primary feed.
