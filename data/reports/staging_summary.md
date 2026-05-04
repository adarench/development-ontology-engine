# Staging Summary — 2026-05-01

**Sources**: `DataRails_raw.zip` → `data/raw/datarails/{gl,clickup}/`
**Outputs**: `data/staged/staged_gl_transactions.{csv,parquet}`, `data/staged/staged_clickup_tasks.{csv,parquet}`
**Validation reports**: `data/reports/staged_{gl,clickup}_validation_report.md`
**`output/` artifacts**: untouched.

---

## What staged successfully

- ✅ **`staged_gl_transactions`** — **124,085 rows × 41 cols** (38 original + 3 staging metadata: `source_file`, `source_row_number`, `staged_loaded_at`). Concatenated from `GL (1..14).csv`. Schema verified identical across all 14 files (column names AND order). Row total reconciles exactly to the inventory expectation. CSV 44 MB; Parquet 2 MB.
- ✅ **`staged_clickup_tasks`** — **5,509 rows × 35 cols** (32 original + 3 staging metadata). From `api-upload.csv` only; the byte-identical `api-upload (1).csv` was excluded. 0 duplicate IDs, 0 empty IDs. CSV 0.9 MB; Parquet 0.16 MB.

## Two findings that change the picture

### Finding 1 — The DataRails GL is HISTORICAL data
- `PostingDate` range: **2016-01-01 → 2017-02-28** (14 months, ~9 years old as of today).
- `CompanyName` distinct count: **3 entities** (not the full org).
- This dump is suitable as a **training / structural** foundation for the staging schema and pipelines, but it is **not** a current operating snapshot. Any "Operating State v2" built directly on this data will describe 2016–2017, not present-day. Before publishing v2 against real-world consumers, we need a fresh GL extract on the same DataRails schema.

### Finding 2 — ClickUp lot tagging is sparse
- `name` 100%, `status` 100%, `date_created/updated` 100% — task-level data is clean.
- BUT lot-identity fields are partial:
  - `subdivision`: **28.86%** filled
  - `lot_num`: **21.37%** filled (1,177 rows, **677 distinct lot numbers**)
  - `projected_close_date`: **1.02%** (56 rows)
  - `actual_c_of_o`: **4.88%** (~270 rows)
  - `sold_date`: **1.02%** (56 rows)
- Implication: ClickUp is not just a lot tracker — most tasks are general project work. Lot-level analysis must filter to the lot-tagged subset (~1,177 tasks across ~677 lots). That is still a large upgrade over the prior pipeline, but the headline fill rates need this caveat.
- `top_level_parent_id` is present at 78.65% (1,302 distinct); **`parent_id` is not in the export** at all — only the root of the task tree comes through. Intermediate parents need a separate ClickUp API pull to reconstruct.

## Ready for operating-state rebuild

- **Cost attribution from GL**: ready in principle. The schema includes `Project` / `ProjectCode` / `ProjectName` (49.54%), `Lot/Phase` (49.54%), `Major` / `Minor` (49.54%), `JobPhaseStage` (7.23% — too sparse to rely on), `AccountCode` (100%), `AccountName` (53.77% — coded entries often unnamed), `FunctionalAmount` (100%), `DebitCredit` flag (100%), `CompanyCode/CompanyName` (100%). Cost-to-phase joins are now a primary-key operation rather than an inference. The unattributed ~50% of rows are presumably overhead/admin entries; that is expected and correctly modeled by leaving them at the entity level.
- **Lot status from ClickUp**: ready for the **lot-tagged subset** (~677 lots / 1,177 tasks). Date fields support projected-vs-actual close variance and sold-date timing. Cannot drive a comprehensive operating state alone, but combined with the inventory closing report (still pending), it should cover.

## Still blocked

1. **Current GL data** — the staged GL ends Feb 2017. Need a fresh DataRails pull on the same 38-col schema to rebuild operating state for present day.
2. **Entity ↔ project crosswalk** — DataRails uses `CompanyCode/CompanyName` (3 entities here) and `ProjectName`; ClickUp uses `subdivision` (lot-tagged subset). No authoritative mapping is in the dump. Must be supplied or reconstructed from distinct-value lists + manual review.
3. **Inventory closing report** — staging deferred. The xlsx has a title row at row 1, so headers parse as `Unnamed: N`; needs `pd.read_excel(header=2)` or `header=3` and a re-profile pass.
4. **Multi-entity Balance Sheet** and **multi-entity AR** — only one entity present each (Anderson Geneva for BS, Uncle Boggy's for AR). Insufficient for org-wide rollup.
5. **QBO/QBD register normalization** — `GL_QBO_*`, `Balance_Sheet_QBO_*`, `AR_QBD_*` are tie-out only; not staged. Normalizing them onto the DataRails schema is a future task.
6. **Intermediate `parent_id` for ClickUp tasks** — only `top_level_parent_id` is exported. If the task hierarchy matters for state derivation, a separate ClickUp API pull is required.

## Does GL improve cost attribution?

**Yes, materially — for the periods covered.** The DataRails GL carries explicit `Project*`, `Lot/Phase`, `Major`, `Minor`, `Division*`, `OUnit`, `Subledger*`, and `Account*` tags directly on each row. The previous pipeline had no equivalent primary-key path from a GL line to a lot/phase. The caveat is the historical period — the *capability* is unblocked, the *data* needs a fresh pull.

## Does ClickUp improve LotState?

**Yes, for the ~677 lots represented in the lot-tagged subset.** The export carries `status`, `walk_date`, `projected_close_date`, `actual_c_of_o`, `sold_date`, `cancelled_date`, plus identity (`subdivision`, `lot_num`). That supports date-based status progression and projected-vs-actual close variance for those lots. It does not give us a list of *all* lots; for that we still need the inventory closing report.

## Recommended next step

**Sequence:**

1. **Confirm whether a fresh GL pull is coming.** Operating State v2 on 2016–2017 data is a structural exercise; on current data it is a business deliverable. Decide which we are building before investing in v2 logic.
2. **Re-profile `Inventory _ Closing Report (4).xlsx`** with `header=2` and `header=3` to find the real header row, then build `staged_inventory_lots`. This gives us the canonical lot universe to join everything against.
3. **Seed `staged_entity_mapping` v0** from the 3 distinct `CompanyName` values in GL and the distinct `subdivision` values in ClickUp; flag every row `confidence=unmapped` until a human approves the joins.
4. **Build Operating State v2** from `staged_gl_transactions` (cost) ⨝ `staged_clickup_tasks` (lot status/dates) ⨝ `staged_inventory_lots` (lot universe) ⨝ `staged_entity_mapping`. Write to a new `output/operating_state_v2.json`. Leave v1 artifacts in place.

## Files left untouched (per instruction)

- `output/lot_state_real.csv`
- `output/project_state_real.csv`
- `output/operating_state_v1.json`
- `output/agent_context_v1.md`
- `output/operating_view_v1.csv`
