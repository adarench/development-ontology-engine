# Terminal C Lane — Ops / Inventory / Collateral / Allocation Worker

**Read this whole file before you do anything.** Then read the inputs in priority order, then write the deliverables.

## Role

You are the operational-data worker. You inspect ClickUp tasks, the inventory closing report, collateral reports, and allocation workbooks. You identify grain, join keys, and how each source feeds the canonical entities. You do **not** stage data; you **propose** stage plans (Terminal A executes the actual staging based on your proposals).

You do **not** define the canonical ontology or field map. You do **not** build any operating-state output.

## Hard rules

- Read-only on `output/*`, `ontology/*`, `pipelines/*`, `financials/*`, every existing file under `data/staged/`, every existing file under `data/reports/`, every existing file under `docs/` except your own scratch.
- Write only to: `scratch/ops_inventory_collateral_allocation_findings.md`, `scratch/bcpd_ops_readiness.md`, `data/staged/ops_inventory_collateral_validation_report.md`.
- Do not edit any other terminal's scratch files.

## Priority order — DO IN THIS ORDER

This priority comes from the master plan's hard guardrail. The inventory closing report unblocks the v2 build, so it goes first.

1. **Inventory closing report** (highest priority — unblocks the guardrail).
2. **Collateral reports** (next; needed for CollateralSnapshot entity).
3. **ClickUp lot-tagged subset** (next; needed for TaskState).
4. **Allocations / budgets** (last; needed for Allocation entity but Track A can ship without if necessary).

If you run out of time, finish #1 and #2; the remaining can land in a follow-up.

## Inputs (in priority order)

### Tier 1 — Inventory
- `data/raw/datarails_unzipped/datarails_raw/Inventory _ Closing Report (4).xlsx` (canonical: latest of 3 near-duplicates)
- `data/raw/datarails_unzipped/datarails_raw/Inventory _ Closing Report (2).xlsx` and `(3).xlsx` (for diff if helpful — confirm `(4)` is truly the latest)
- Existing notes: `data/staged/datarails_raw_file_inventory.md` notes that the xlsx has a title row at row 1 ("Flagship Lot Inventory & Development Schedule"), so headers parse as `Unnamed: N`. You must determine the correct `header=N` (likely 2 or 3).

### Tier 2 — Collateral reports
- `data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv`
- `... - Combined BS.csv`
- `... - 2025Status.csv`
- `... - IA Breakdown.csv`
- `... - PriorCR.csv`
- `... - RBA-TNW.csv`
- `... - Cost to Complete Summary.csv`
- `... - Lot Data.csv`
- `... - OfferMaster.csv`
- Existing references: `CONTEXT_PACK.md` documents `LOT_STATE_TO_COLLATERAL_BUCKET`, `ADVANCE_RATES`, and that `Collateral Report.csv` has its header on row 9 and `2025Status.csv` has its header on row 3 (per v1 audit).

### Tier 3 — ClickUp lot-tagged subset
- `data/staged/staged_clickup_tasks.{csv,parquet}` (5,509 rows total)
- `data/reports/staged_clickup_validation_report.md` (lot tagging is sparse: ~21–29% of rows; `top_level_parent_id` 78.65%, `parent_id` not exported)
- `Clickup_Naming_Struct - Sheet1.csv`, `Clickup_Sheet_Structure - Sheet1.csv` (loose at repo root; reference for naming conventions)

### Tier 4 — Allocations / budgets
- `data/raw/datarails_unzipped/phase_cost_starter/Flagship Allocation Workbook v3.xlsx - *.csv` (5 sheets)
- `... LH Allocation 2025.10.xlsx - *.csv` (6 sheets — Loman Heights)
- `... Parkway Allocation 2025.10.xlsx - *.csv` (3 sheets)
- `Dehart Underwriting(Summary).csv` (loose)

### Reference (read-only, do not modify)
- `CONTEXT_PACK.md` — established v1 patterns and source notes.
- `ontology/lot_state_v1.md` — v1 lifecycle waterfall and state→bucket mapping.
- `ontology/phase_state_v1.md` — v1 PhaseState definition.
- `ontology/data_readiness_audit.md` — 2026-04-10 source inventory.
- `data/staged/datarails_raw_file_inventory.{csv,md}` — full audit of the raw dump.

## Responsibilities

### C1 — Inventory closing report
- Determine the correct `header=N` for `Inventory _ Closing Report (4).xlsx`. Try `header=0`, `header=1`, `header=2`, `header=3` and report which one yields meaningful column names.
- Once headers are correct, identify columns for: project / community, phase / plat, lot number, lot type, status, projected close date, actual close date, address, builder.
- Confirm the `as_of_date` (look for it in cell B1 or similar — v1 reports use that pattern).
- Compare `(2)`, `(3)`, `(4)` versions: is `(4)` truly the latest? Are there content differences beyond a refresh date?
- **Propose** a stage plan: target `data/staged/staged_inventory_lots.{csv,parquet}` with columns and parser settings. Terminal A will execute the stage.
- Determine grain: row per lot? per phase? per status?

### C2 — Collateral reports
For each Collateral Dec2025 file:
- Identify `header=N`.
- Identify grain (project / phase / lot / category / report-level summary).
- Identify the `as_of_date` (typically in a top cell).
- Identify columns for: collateral_value, borrowing_base, total_dev_cost, lot_count, advance_rate (or implied via bucket).
- Note which file maps to which canonical entity (CollateralSnapshot / cost-to-complete / etc.).

Pay special attention to:
- **Collateral Report**: the v1 fallback for expected cost (PARTIAL fidelity per `CONTEXT_PACK.md`).
- **2025Status**: per-lot costs + status + collateral bucket.
- **Combined BS**: balance sheet (likely thin; may not be useful for Track A).
- **Lot Data**: lifecycle dates per lot (~3,627 rows per `CONTEXT_PACK.md`).

### C3 — ClickUp lot-tagged subset
- Filter `staged_clickup_tasks` to the lot-tagged subset (`subdivision` or `lot_num` populated). Confirm row count (~1,177).
- Identify grain: each row is a task, but tasks aggregate to lots via `(subdivision, lot_num)`. Determine join key reliability.
- Status distribution within the lot-tagged subset (how many distinct statuses, how many tasks per status).
- Date-field coverage within the lot-tagged subset specifically (is `actual_c_of_o` / `sold_date` more populated for lot-tagged rows than for the full file?).
- Recommend filtering rules for TaskState entity ingestion.

### C4 — Allocation workbooks
For each workbook (Flagship, LH, Parkway, Dehart):
- Identify per-sheet grain (per-lot output, per-phase total, indirect/land pool, instructions, etc.).
- Identify columns for: project / community / phase, lot_number (where per-lot), category, budget_amount, allocation_method, prod_type, vintage.
- Note that LH's per-lot output has `Total` blank — must be reconstructed from land+direct+water+indirect (per v1 audit).
- Recommend per-workbook ingestion plan: which sheets feed Allocation entity at which grain.

### C5 — Per-source feeding map
For each source you inspect, write one line stating which canonical entities it feeds:
| source | LotState | PhaseState | ProjectState | AllocationState | CollateralSnapshot | InventorySnapshot |
|---|---|---|---|---|---|---|
| `Inventory _ Closing Report (4).xlsx` | … | … | … | … | … | primary |
| `Collateral Dec2025 ... Collateral Report.csv` | … | partial | … | … | primary | … |
| ... | ... | ... | ... | ... | ... | ... |

### C6 — BCPD-specific readiness
Write a short matrix for BCPD Track A:
- Which inventory/collateral/allocation files have BCPD content?
- Which lots in inventory are BCPD?
- Which collateral snapshots cover BCPD as-of which date?
- Which allocations cover BCPD projects (Flagship Belmont? other? — note that Flagship Belmont Phase two LLC is a separate legal entity, so its allocations may not be BCPD-relevant).

### C7 — Org-wide gaps
List inventory / collateral / allocation files that exist for entities OTHER than BCPD. Note which entities they cover and what's missing for an org-wide rollup.

## Deliverables

1. `scratch/ops_inventory_collateral_allocation_findings.md` — narrative findings covering C1–C5 above. Use the handoff format in `docs/agent_workflow_plan.md` (file paths, row counts, confidence ratings, recommendations).
2. `scratch/bcpd_ops_readiness.md` — the BCPD readiness matrix from C6 plus the org-wide gap list from C7. Keep it short and decisive.
3. `data/staged/ops_inventory_collateral_validation_report.md` — formal validation report covering: file existence, header offsets, parsed row counts per file, identified columns per file, and explicit "ready to stage" / "blocked because X" verdict per file.

## Definition of done

- Inventory closing report `header=N` is determined with a stated reason.
- Each of C2's collateral files has identified `header=N`, grain, and `as_of_date`.
- ClickUp lot-tagged subset row count is reported (sanity check: ~1,177).
- Each allocation workbook has per-sheet grain identified.
- C5's per-source feeding map is filled for at least the inventory + collateral files (allocations may be partial if time-constrained).
- BCPD readiness matrix in `bcpd_ops_readiness.md` answers what files are usable for BCPD Track A.
- The validation report has an explicit "ready to stage" verdict for the inventory closing report (this is the guardrail unblocker).

## Handoff to Terminal A

When done, leave the three deliverable files in place. Do not summarize them anywhere else. Terminal A reads them in full and uses C1's stage proposal to actually stage `staged_inventory_lots.{csv,parquet}`.

## Out of scope (do not do)

- Do not validate or modify GL files — that's Terminal B.
- Do not propose ontology entities or field-map rows — that's Terminal A.
- Do not write any output under `output/`.
- Do not actually stage `staged_inventory_lots.*` — propose; Terminal A executes.
- Do not write any code that modifies state files outside your three deliverables.
