# Lot-Level Margin Report — Readiness Review
**Scope: BCPD only** (entities BCPD/BCPBL/ASD/BCPI). Hillcrest and Flagship Belmont are out of scope; their GL coverage ends 2017-02 — org-wide v2 is NOT available.

## Hard rule

**Missing cost is *unknown*, not $0.** Reporting $0 for a project without GL coverage misstates margin and inflates apparent performance. Use a null / blank cell or an explicit 'unknown' marker.

## Do NOT include at lot grain

### Projects with no GL coverage (cost = unknown for all lots) — 9 projects

- `Ammon` — unknown lot-level cost; show as **unknown**, never $0.
- `Cedar Glen` — unknown lot-level cost; show as **unknown**, never $0.
- `Eagle Vista` — unknown lot-level cost; show as **unknown**, never $0.
- `Eastbridge` — unknown lot-level cost; show as **unknown**, never $0.
- `Erda` — unknown lot-level cost; show as **unknown**, never $0.
- `Ironton` — unknown lot-level cost; show as **unknown**, never $0.
- `Lewis Estates` — unknown lot-level cost; show as **unknown**, never $0.
- `Santaquin Estates` — unknown lot-level cost; show as **unknown**, never $0.
- `Westbridge` — unknown lot-level cost; show as **unknown**, never $0.

### Range / shell GL rows — project+phase grain only

- 4,020 GL rows / $45,752,047 in range/shell form (e.g. `'3001-06'`, `'0009-12'`). **Not safe at lot grain.**
- Allocation method (equal split, sales-weighted, fixed proportional) is **pending source-owner sign-off** and does not yet exist in v2.1.

## Include WITH caveats (inferred-decoder cost)

- Per-lot VF cost is **inferred via the v1 decoder** — not source-owner-validated. Margin figures inherit that inferred confidence.
- Harmony lots: require the 3-tuple `(project, phase, lot)` to avoid the v2.0 $6.75M double-count. v2.1 enforces `vf_actual_cost_3tuple_usd`.
- SctLot lots roll up under **Scattered Lots**, NOT Scarlet Ridge ($6.55M un-inflated in v2.1).
- HarmCo X-X parcels are commercial / non-residential — exclude from per-lot residential margin reports.

## Coverage snapshot (v2.1)

_'Full triangle' = a lot that appears in all three feeds: inventory + GL (general ledger / Vertical Financials) + ClickUp tasks._

| Metric | Value |
|---|---|
| Lots in canonical | 5366 |
| High-confidence lots | 2797 |
| Full-triangle join coverage (lot in inventory + GL + ClickUp) | 37.2% |
| GL join coverage | 67.2% |

## Confidence boundaries

_Each row maps a fact in this brief to the confidence label it actually carries in v2.1 state. Cite accordingly._

| Grain / Fact | Confidence | Source |
|---|---|---|
| Projects with no GL coverage (lot-level cost) | **unknown** — show as null / 'unknown', NEVER $0 | absence in `vf_2018_2025_sum_usd` AND `dr_2016_2017_sum_usd_dedup` |
| Per-lot VF cost (`vf_actual_cost_3tuple_usd`) | **inferred** (v1 decoder; not source-owner-validated) | `vf_lot_code_decoder_v1` rule set; per-lot field `vf_actual_cost_confidence` |
| Range / shell GL rows (`'3001-06'`, `'0009-12'`, etc.) | **project+phase grain only** — allocation method pending source-owner sign-off | `v2_1_changes_summary.range_rows_at_project_phase_grain` ($45.75M / 4,020 rows) |
| Harmony lot cost (when joined) | valid only at **3-tuple** `(project, phase, lot)` — flat 2-tuple double-counts by $6.75M | `v2_1_changes_summary.harmony_3tuple_join_required` |
| HarmCo X-X commercial parcels | **commercial / non-residential** — exclude from residential lot rollups | `v2_1_changes_summary.harmco_split.commercial_rows` (205 rows) |
| Phase variance / margin (`expected_total_cost` vs `actual_cost_total`) | **queryable on 3/125 phases only** — the rest lack complete expected_cost | `phase_state.is_queryable` gate (v2.1) |

## Retrieval evidence

- **Caveats** — `output/agent_chunks_v2_bcpd/projects/project_ammon.md`
- **Caveats** — `output/agent_chunks_v2_bcpd/projects/project_cedar_glen.md`
- **Caveats** — `output/agent_chunks_v2_bcpd/projects/project_eagle_vista.md`
- **Safe questions this chunk grounds** — `output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md`
