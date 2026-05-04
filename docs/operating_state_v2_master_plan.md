# Operating State v2 — Master Plan

**Owner**: Terminal A (Planner / Integrator)
**Status**: planning, pre-build
**Last updated**: 2026-05-01

## 1. Objective

Turn the raw DataRails / ClickUp / GL / inventory / collateral / allocation dump into a structured, queryable operating-state foundation that AI agents can use to answer business questions with **evidence, caveats, and source traceability**.

This is not a dashboard task. It is not a generic data-cleaning task. The deliverable is a versioned operating-state artifact (`output/operating_state_v2_bcpd.json`) plus an agent-context brief and a thin query harness — everything that lets an agent say "BCPD has X lots in Phase Y at $Z cost as of <date>, sourced from <files>, with these caveats."

### Non-goals
- No dashboard/HTML output in v2 (v1 already has that; out of scope).
- No org-wide rollup until non-BCPD entities have fresh GL data (see Track B below).
- No re-architecture of v1 ontology, pipelines, or output artifacts.

## 2. Hard pre-build guardrail

**Do not build `output/operating_state_v2_bcpd.json` or any v2 query harness until ALL THREE of the following are true:**

1. **Inventory closing report is staged** — `Inventory _ Closing Report (4).xlsx` parsed with the correct header offset, written as `data/staged/staged_inventory_lots.{csv,parquet}`, and validated.
2. **Entity / project / lot crosswalk v0 exists** — `data/staged/staged_entity_project_crosswalk_v0.{csv,parquet}` (or equivalent) covering the BCPD universe with a `confidence` column on every row.
3. **GL ↔ inventory ↔ ClickUp join coverage has been measured** — a written report (e.g. `data/reports/join_coverage_v0.md`) showing what fraction of BCPD lots in inventory have at least one matching GL row and at least one matching ClickUp lot-tagged task, broken down by year.

This guardrail applies to the master plan, the agent workflow plan, the Terminal A lane doc, and the 3-day plan. Any work that produces `output/operating_state_v2_*` or a v2 query harness before all three are met is out of scope.

## 3. Current known data families

| family | primary staged artifact | status |
|---|---|---|
| GL transactions (3 source schemas normalized) | `data/staged/staged_gl_transactions_v2.{csv,parquet}` | **built**, 210,440 rows, `row_hash` PK, max posting_date 2025-12-31 |
| ClickUp tasks (raw) | `data/staged/staged_clickup_tasks.{csv,parquet}` | **built**, 5,509 rows; lot-tagged subset ~1,177 rows |
| Inventory closing report | — | **not staged** (header-offset issue); 3 near-duplicate xlsx versions |
| Collateral reports (Dec 2025) | — | not staged; loose CSVs in `data/raw/datarails_unzipped/phase_cost_starter/` |
| Allocation workbooks (Flagship, LH, Parkway) | — | not staged; loose CSVs in same dir |
| Crosswalks (entity↔project↔lot) | — | not built; needed before v2 |

## 4. Target outputs (Track A — BCPD only)

- `output/operating_state_v2_bcpd.json` — canonical, versioned, machine-queryable state for Building Construction Partners, LLC.
- `output/agent_context_v2_bcpd.md` — short brief an agent can load to ground its answers (mirrors the voice of `output/agent_context_v1.md` and `CONTEXT_PACK.md`).
- `output/state_quality_report_v2_bcpd.md` — explicit data-quality and coverage caveats per field, per year.
- `output/state_query_examples_v2_bcpd.md` — 10–15 example natural-language questions and the queries that answer them.

All v2 outputs are **additive**. v1 artifacts (`output/lot_state_real.csv`, `output/project_state_real.csv`, `output/operating_state_v1.json`, `output/agent_context_v1.md`, `output/operating_view_v1.csv`, `output/operating_state_meeting_brief_v1.md`, `output/operating_state_console_v1.html`, `output/operating_dashboard_v1.html`) remain untouched.

## 5. Why Track A is BCPD-only

- BCPD has GL coverage from 2016-01 through 2025-12 (with a 2017-03 → 2018-06 gap).
- BCPD has 100% project + lot fill on the 83K Vertical Financials rows (2018-2025).
- BCPD also appears in the lot-tagged ClickUp subset and most inventory/collateral artifacts.
- An operating state for one entity, with multi-year support, is genuinely useful and defensible.

## 6. Why Track B (org-wide) is not published yet

- **Hillcrest Road at Saratoga, LLC** has GL data only 2016-01 → 2017-02.
- **Flagship Belmont Phase two LLC** has GL data only 2016-01 → 2017-02.
- Publishing an org-wide v2 today would mix 2024-2025 BCPD against 2017 historical for the other entities — that is misleading regardless of how it is labeled. Track B remains a **roadmap track** with explicit prerequisites.

## 7. Pipeline order

```
Raw files
  → source inventory                                       (DONE: data/staged/datarails_raw_file_inventory.{csv,md})
  → staged source-family tables                            (PARTIAL: GL v2 + ClickUp done; inventory/collateral/allocations pending)
  → canonical entities / ontology                          (Terminal A: docs/ontology_v0.md)
  → field map                                              (Terminal A: docs/field_map_v0.csv)
  → crosswalks (entity / project / phase / lot)            (Terminal A: docs/crosswalk_plan.md → data/staged/staged_*_crosswalk_v0.csv)
  → normalized state tables                                (Terminal A: data/staged/canonical_*)
  → join-coverage measurement                              (Terminal A: data/reports/join_coverage_v0.md) ← guardrail check
  → operating_state_v2_bcpd.json                           (Terminal A, only after guardrail clears)
  → agent context + query harness                          (Terminal A, only after guardrail clears)
```

## 8. Definition of "done" for the next 2–3 days

- Day 1 — both worker findings landed; ontology v0 and field map v0 drafted; inventory closing report stage-plan written; QB-register-overlap decision documented.
- Day 2 — inventory closing report **staged**; crosswalk v0 **built**; canonical normalized tables for BCPD scope ready.
- Day 3 — join-coverage report **written**; if and only if the guardrail clears, `output/operating_state_v2_bcpd.json` + agent context + query examples written.

If the guardrail does not clear by end of Day 2, Day 3 is spent unblocking the guardrail (e.g. crosswalk review, header-offset fix, etc.) and the v2 build slips to Day 4. **Do not ship v2 with the guardrail still red.**

## 9. Sequence of work

1. This planning step (writing the 9 scaffolding docs).
2. Terminals B and C run in parallel against their lane docs.
3. Terminal A integrates worker findings, finalizes ontology + field map + crosswalk plan.
4. Inventory staged. Crosswalk v0 built. Join coverage measured.
5. Guardrail check. If green → Terminal A builds BCPD v2 outputs. If red → unblock first.

## 10. Major risks

- **Entity ↔ project ↔ lot crosswalk** is the highest-friction unknown. GL uses `Project`/`ProjectName`; ClickUp uses `subdivision`; inventory and collateral use community/phase/plat names. Different vocabularies for the same business concepts.
- **Vertical Financials may be one-sided**. Sums to +$346M for BCPD, which is consistent with an asset/expense-only view. Treat with care for any balanced rollup (P&L, BS).
- **QB-register-vs-Vertical-Financials overlap** could cause double counting in 2025 BCPD if naively summed. Default treatment: tie-out only; exclude from primary rollups.
- **ClickUp lot tagging is sparse** (~21% of rows). The lot-tagged subset is rich; the rest is general project work and should be excluded from lot-level state.
- **Inventory xlsx header offset** — title row at row 1; real headers at row 2 or 3. Trivial to fix once isolated, but blocks the staged_inventory_lots build.

## 11. Decisions needed before final build

- **Primary key for staged_gl_transactions_v2**: `row_hash` (already decided; reaffirmed here).
- **Sign convention**: signed `amount`; positive = debit, negative = credit (already decided; reaffirmed).
- **QB-register treatment**: tie-out only; exclude from financial rollups by default. Revisit if Terminal B's findings show non-overlap with Vertical Financials 2025.
- **Project field source-of-truth in v0**: Vertical Financials `Project` for BCPD 2018-2025; DataRails `ProjectCode`/`ProjectName` for BCPD 2016-2017. Do NOT silently coalesce — keep both and let the canonical mapping pick.
- **Crosswalk approval**: Terminal A drafts; explicit human review before any v2 output that depends on it.
