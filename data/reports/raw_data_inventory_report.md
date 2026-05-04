# Raw Data Inventory Report

**Source dump**: `DataRails_raw.zip` (May 1, 2026, 5.8 MB, 24 data files + macOS metadata)
**Snapshot folder**: `data/raw/datarails/snapshots/2026-05-01/`
**Manifest**: `data/manifests/raw_export_manifest.csv`
**Profiles JSON**: `data/manifests/profiles.json`
**Hashes JSON**: `data/manifests/hashes.json`
**Generated**: 2026-05-01

---

## A. Files found (24)

| # | File | Bytes | Rows | Cols |
|---|------|------:|-----:|-----:|
| F001 | AR_QBD_Uncle Boggys LLC_May 2026.csv | 513 | 8 | 8 |
| F002 | Balance_Sheet_QBO_Anderson Geneva LLC_May 2026.csv | 3,443 | 109 | 2 |
| F003 | GL (1).csv | 1,555,056 | 4,154 | 38 |
| F004 | GL (10).csv | 3,744,298 | 9,727 | 38 |
| F005 | GL (11).csv | 4,374,040 | 11,244 | 38 |
| F006 | GL (12).csv | 5,567,716 | 14,263 | 38 |
| F007 | GL (13).csv | 3,889,157 | 10,163 | 38 |
| F008 | GL (14).csv | 4,949,096 | 12,917 | 38 |
| F009 | GL (2).csv | 2,112,434 | 5,594 | 38 |
| F010 | GL (3).csv | 2,536,009 | 6,649 | 38 |
| F011 | GL (4).csv | 1,871,302 | 4,923 | 38 |
| F012 | GL (5).csv | 3,114,701 | 8,125 | 38 |
| F013 | GL (6).csv | 3,885,373 | 10,232 | 38 |
| F014 | GL (7).csv | 2,880,617 | 7,637 | 38 |
| F015 | GL (8).csv | 3,381,043 | 8,856 | 38 |
| F016 | GL (9).csv | 3,686,093 | 9,601 | 38 |
| F017 | GL.csv | 2,553 | 6 | 38 |
| F018 | GL_QBO_Anderson Geneva LLC_May 2026.csv | 2,993 | 42 | 33 |
| F019 | GL_QBO_Geneva Project Manager LLC_May 2026.csv | 1,052 | 12 | 34 |
| F020 | Inventory _ Closing Report (2).xlsx | 1,734,557 | 84 | 13 |
| F021 | Inventory _ Closing Report (3).xlsx | 1,734,294 | 84 | 13 |
| F022 | Inventory _ Closing Report (4).xlsx | 1,734,239 | 84 | 13 |
| F023 | api-upload (1).csv | 930,077 | 5,509 | 32 |
| F024 | api-upload.csv | 930,077 | 5,509 | 32 |

Row totals: GL (1)–GL (14) = **124,085 rows**; GL.csv adds 6.

---

## B. File classification

| Folder | Count | Files |
|---|---:|---|
| `data/raw/datarails/gl/` | 17 | GL.csv, GL (1).csv … GL (14).csv, GL_QBO_Anderson Geneva LLC_May 2026.csv, GL_QBO_Geneva Project Manager LLC_May 2026.csv |
| `data/raw/datarails/clickup/` | 2 | api-upload.csv, api-upload (1).csv |
| `data/raw/datarails/inventory_closing/` | 3 | Inventory _ Closing Report (2..4).xlsx |
| `data/raw/datarails/balance_sheet/` | 1 | Balance_Sheet_QBO_Anderson Geneva LLC_May 2026.csv |
| `data/raw/datarails/ar/` | 1 | AR_QBD_Uncle Boggys LLC_May 2026.csv |
| `data/raw/datarails/unknown/` | 0 | — |

All 24 files also copied to `data/raw/datarails/snapshots/2026-05-01/`.

Source provenance (inferred from filename + columns):

- **DataRails GL bundle** — `GL (1..14).csv`, `GL.csv`. Identical 38-col schema with `PostingDate, JournalCode, BatchNumber, DocumentNumber, TransactionNumber, LineNo, CompanyCode, CompanyName, …, DebitCredit, FunctionalAmount`. Multi-entity in a single feed (CompanyCode/CompanyName columns).
- **QBO entity exports** — `GL_QBO_*.csv`, `Balance_Sheet_QBO_*.csv`. QuickBooks Online register format (33–34 cols: `Account, Date, Transaction Type, Num, Create Date, Created By, Name, Customer, …`). Different schema from the DataRails bundle — these are raw QBO outputs, not the same source.
- **QBD entity export** — `AR_QBD_Uncle Boggys LLC_May 2026.csv`. QuickBooks Desktop AR aging.
- **ClickUp API export** — `api-upload.csv`. 32 columns including `top_level_parent_id, status, date_created, date_done, subdivision, lot_num, walk_date, projected_close_date, sold_date, C_of_O`.
- **Inventory closing report** — `Inventory _ Closing Report (2..4).xlsx`. Title row "Flagship Lot Inventory & Development Schedule" — real headers live below row 1 (parser will need `header=N`).

---

## C. Likely useful datasets (high signal)

1. **DataRails GL bundle** (`GL (1..14).csv`, ~124 K rows, 38 cols, multi-entity). The richest dataset in the dump and the one most likely to power phase-cost rollups directly: it carries `CompanyCode`, `PostingDate`, `FunctionalAmount`, `DebitCredit`, `TransactionNumber`, plus account dimensions. This is the GL pipeline's preferred upstream.
2. **ClickUp API export** (`api-upload.csv`, 5,509 tasks, 32 cols). Carries every field the LotState pipeline needs: `subdivision`, `lot_num`, `status`, `walk_date`, `projected_close_date`, `actual_c_of_o`, `sold_date`, `cancelled_date`. Should fully replace whatever Clickup_Sheet_Structure CSVs we currently rely on.
3. **Inventory _ Closing Report (latest version)** (84 rows). Cross-references lots by community and gives planned/actual close dates — a useful reconciliation source against ClickUp lot state.

## D. Duplicates / near-duplicates

- **`api-upload.csv` and `api-upload (1).csv` are byte-identical** (same sha256 `d86de508d860…`, same 930,077 bytes, same 5,509 rows). Treat as one file; use `api-upload.csv` as canonical and ignore `(1)`.
- **`Inventory _ Closing Report (2..4).xlsx` are near-duplicates**: same row/column shape (84×13), sizes within 318 bytes of each other, distinct sha256 hashes. Likely successive saves of the same workbook (different "as-of" timestamps or trivial cell tweaks). Pick `(4)` as the latest unless content diff says otherwise; archive (2) and (3).
- **`GL.csv` is a stub** (6 rows, same 38-col schema as the numbered GL files). Probably a sample/preview export; not a real dataset. Safe to ignore for staging.
- The numbered **`GL (1..14).csv`** files appear to partition a larger feed (no schema drift across them); see staging plan for the proposed merge.

## E. Highest-value files to inspect next (top 5)

1. `GL (12).csv` (largest at 14,263 rows) — confirm column semantics across the full 38, especially `CustomerJob`, `Class`, `MemoDescription`, `Project`, and any phase-tagging columns we can use as join keys.
2. `api-upload.csv` — verify whether `subdivision` + `lot_num` are reliably populated for every active lot; that's the join key into GL/inventory.
3. `Inventory _ Closing Report (4).xlsx` — find the real header row and identify the lot-level columns (community, lot, projected close, actual close).
4. `GL_QBO_Anderson Geneva LLC_May 2026.csv` — compare entity-level QBO totals against the same entity sliced from the DataRails bundle. Will tell us whether the DataRails feed is complete or whether per-entity QBO pulls are still required.
5. `Balance_Sheet_QBO_Anderson Geneva LLC_May 2026.csv` — only 109 rows × 2 columns (Account, Total). Useful as a reconciliation tie-out for the entity but minimal as a standalone dataset.

## F. Files that look too small / empty / useless

- `GL.csv` (6 rows) — likely a sample/preview, not real data. Keep in raw for traceability; do **not** stage.
- `AR_QBD_Uncle Boggys LLC_May 2026.csv` (8 rows) — single-entity, possibly only open invoices. Useful per-entity but not a system-wide AR snapshot.
- `Balance_Sheet_QBO_Anderson Geneva LLC_May 2026.csv` (109 rows × 2 cols) — only Account + Total; no period detail. Better than nothing for one entity; we still need a multi-entity BS export.
- `api-upload (1).csv` — exact duplicate of `api-upload.csv`; ignore.

## G. Missing files we still need

- **Multi-entity Balance Sheet export** (DataRails or QBO). We have one entity (Anderson Geneva); we need every operating entity to roll up.
- **AR aging across all entities** (only Uncle Boggy's is present).
- **GL chart of accounts / account dimension table**. The GL files reference `JournalCode`, `CompanyCode`, and presumably `AccountCode`; we need the COA to label them.
- **Entity ↔ project mapping**. The DataRails GL has `CompanyCode/CompanyName`; ClickUp has `subdivision`. We need an authoritative crosswalk (entity → project_code → community → ClickUp list).
- **Phase / cost code dictionary** (if phase tagging lives outside the GL Memo or Class field).
- **Closing pipeline source for inventory** (CSV preferred over the XLSX with the title row, so headers parse cleanly).

## H. Recommended next pipeline inputs

1. Build `staged_gl_transactions` by concatenating `GL (1..14).csv` (drop `GL.csv`). Add `source_file` column for traceability. This becomes the new GL pipeline input replacing whatever ad-hoc CSV the current pipeline reads.
2. Build `staged_clickup_tasks` from `api-upload.csv` only. Drop `api-upload (1).csv`. This replaces the Clickup_Sheet_Structure CSVs as the LotState input.
3. Build `staged_inventory_lots` from `Inventory _ Closing Report (4).xlsx` after locating the real header row. Use it as a reconciliation join against `staged_clickup_tasks`.
4. Hold `staged_entity_mapping` until the entity↔project crosswalk arrives (or derive a v0 from `CompanyName` distinct-values + ClickUp `subdivision` distinct-values).
5. Leave `output/lot_state_real.csv`, `output/project_state_real.csv`, `output/operating_state_v1.json`, `output/agent_context_v1.md` untouched in this round. They get regenerated only after the staging tables exist and pass schema validation.
