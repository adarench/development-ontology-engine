# False Precision Risks — BCPD Reports
**Scope: BCPD only** (entities BCPD/BCPBL/ASD/BCPI). Hillcrest and Flagship Belmont are out of scope; their GL coverage ends 2017-02 — org-wide v2 is NOT available.

## 1. Range / shell GL rows shown at lot grain (highest-dollar risk)

- **4,020 GL rows / $45,752,047** sit in range form (e.g. `'3001-06'`, `'0009-12'`) and are safe **only at project+phase grain**.
- Lot-grain rollups that include these dollars manufacture per-lot precision that does not exist in the source data.
- Allocation method is **pending source-owner sign-off** — no method has been ratified.

## 2. Decoder-derived per-lot cost treated as validated

- Per-lot `vf_actual_cost_3tuple_usd` is computed by the **v1 VF decoder** — heuristic, not source-owner-validated.
- Any margin / variance figure inherits this inferred confidence. Reports that cite per-lot cost without the inferred caveat give false precision.

## 3. Harmony 3-tuple discipline

- Flat `(project, lot)` joins for Harmony double-count by **$6,750,000** (MF1 lot 101 vs B1 lot 101 are different physical assets).
- v2.1 requires `(project, phase, lot)` — any v2.0-era report using flat joins is wrong.

## 4. SctLot vs Scarlet Ridge attribution

- **1,130 rows / $6,553,893** were silently bucketed into Scarlet Ridge in v2.0.
- v2.1: SctLot → **Scattered Lots** (separate canonical project). Reports citing 'Scarlet Ridge total' from v2.0 inflate by ~$6.55M.

## 5. HarmCo X-X commercial parcels in residential rollups

- **205 HarmCo X-X rows** are commercial parcels — non-residential.
- Including them in per-lot residential margin reports overstates residential cost basis.

## 6. AultF B-suffix routing (precision changed in v2.1)

- **1,499 rows / $4,006,662** moved from B2 (v2.0) → B1 (v2.1). Any v2.0-based phase rollup for AultF is stale.

## Confidence boundaries

_Each row maps a fact in this brief to the confidence label it actually carries in v2.1 state. Cite accordingly._

| Grain / Fact | Confidence | Source |
|---|---|---|
| Project-level totals (rows, USD sums) | higher — exact aggregates of (inferred) per-lot rows | `operating_state_v2_1_bcpd.json` → `projects[].actuals.*` |
| Per-lot VF cost (`vf_actual_cost_3tuple_usd`) | **inferred** (v1 decoder; not source-owner-validated) | `vf_lot_code_decoder_v1` rule set; per-lot field `vf_actual_cost_confidence` |
| Phase variance / margin (`expected_total_cost` vs `actual_cost_total`) | **queryable on 3/125 phases only** — the rest lack complete expected_cost | `phase_state.is_queryable` gate (v2.1) |
| Range / shell GL rows (`'3001-06'`, `'0009-12'`, etc.) | **project+phase grain only** — allocation method pending source-owner sign-off | `v2_1_changes_summary.range_rows_at_project_phase_grain` ($45.75M / 4,020 rows) |
| HarmCo X-X commercial parcels | **commercial / non-residential** — exclude from residential lot rollups | `v2_1_changes_summary.harmco_split.commercial_rows` (205 rows) |
| Harmony lot cost (when joined) | valid only at **3-tuple** `(project, phase, lot)` — flat 2-tuple double-counts by $6.75M | `v2_1_changes_summary.harmony_3tuple_join_required` |
| AultF B-suffix routing (B1 in v2.1, was B2 in v2.0) | **inferred (high-evidence)** — empirically derived; awaiting source-owner sign-off | `v2_1_changes_summary.aultf_b_to_b1_correction` (1,499 rows / $4.0M) |
| AultF SR-suffix lots (`0139SR`, `0140SR`) | **inferred-unknown** — canonical phase pending source-owner sign-off | `v2_1_changes_summary.aultf_sr_isolated` (401 rows / $1.18M) |

## Retrieval evidence

- **Safe questions this chunk grounds** — `output/agent_chunks_v2_bcpd/guardrails/guardrail_sctlot_scattered_lots.md`
- **Caveats** — `output/agent_chunks_v2_bcpd/projects/project_arrowhead_springs.md`
- **Caveats** — `output/agent_chunks_v2_bcpd/projects/project_lomond_heights.md`
- **Caveats** — `output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md`
