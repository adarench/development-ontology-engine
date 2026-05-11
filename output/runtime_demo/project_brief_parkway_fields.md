# Project Brief — Parkway Fields
**Scope: BCPD only** (entities BCPD/BCPBL/ASD/BCPI). Hillcrest and Flagship Belmont are out of scope; their GL coverage ends 2017-02 — org-wide v2 is NOT available.

## Identity

- Canonical project: `Parkway Fields`
- Canonical entity: `BCPD`
- Phase count: 20
- Lot count: 1131
- Active lots (2025Status): 918

## Cost basis (v2.1, inferred via Vertical Financials decoder v1)

_VF = Vertical Financials (primary 2018–2025 GL); DR = DataRails (legacy 2016–2017 GL, deduped); SR-suffix = special-rate lots (`0139SR`, `0140SR`) held inferred-unknown._

| Bucket | Rows | USD |
|---|---|---|
| Vertical Financials (VF) lot grain (2018–2025) | 41526 | $129,007,157 |
| VF range / shell grain | 1114 | $15,194,238 |
| VF commercial parcels | 0 | $0 |
| VF SR-suffix (inferred-unknown) | 401 | $1,183,859 |
| DataRails (DR) 38-col 2016–2017 (deduped) | 0 | $0 |

## v2.1 corrections affecting this project

- **AultF B-suffix → B1 correction**: 1,499 rows / $4,006,662. Previously misrouted to B2 in v2.0. _AultF B-suffix lots (0127B-0211B) now route to B1 (was B2 in v0). Empirically AultF and PWFS2 B-suffix lot ranges are disjoint._ Confidence: `inferred (high-evidence)`.
- **AultF SR-suffix isolated** (inferred-unknown): 401 rows / $1,183,859. Held separately — canonical phase still pending source-owner sign-off.
- (HarmCo split context, also relevant if Parkway↔HarmCo decoder questions surface): 169 residential + 205 commercial. Commercial parcels are non-residential.

## Caveats (do not promote without source-owner sign-off)

- All per-lot VF cost is **inferred (v1 decoder)** — not source-owner-validated. Do not promote to 'validated' for external reporting or transactions.
- Range/shell rows live at project+phase grain only — do not allocate to specific lots without a sign-off allocation method.
- For Harmony queries (not this project, but worth noting in cross-project work): always use the (project, phase, lot) 3-tuple — flat 2-tuple joins double-count by ~$6.75M.

## Confidence boundaries

_Each row maps a fact in this brief to the confidence label it actually carries in v2.1 state. Cite accordingly._

| Grain / Fact | Confidence | Source |
|---|---|---|
| Project-level totals (rows, USD sums) | higher — exact aggregates of (inferred) per-lot rows | `operating_state_v2_1_bcpd.json` → `projects[].actuals.*` |
| Per-lot VF cost (`vf_actual_cost_3tuple_usd`) | **inferred** (v1 decoder; not source-owner-validated) | `vf_lot_code_decoder_v1` rule set; per-lot field `vf_actual_cost_confidence` |
| Range / shell GL rows (`'3001-06'`, `'0009-12'`, etc.) | **project+phase grain only** — allocation method pending source-owner sign-off | `v2_1_changes_summary.range_rows_at_project_phase_grain` ($45.75M / 4,020 rows) |
| AultF B-suffix routing (B1 in v2.1, was B2 in v2.0) | **inferred (high-evidence)** — empirically derived; awaiting source-owner sign-off | `v2_1_changes_summary.aultf_b_to_b1_correction` (1,499 rows / $4.0M) |
| AultF SR-suffix lots (`0139SR`, `0140SR`) | **inferred-unknown** — canonical phase pending source-owner sign-off | `v2_1_changes_summary.aultf_sr_isolated` (401 rows / $1.18M) |
| Per-phase aggregations | inherits per-phase `phase_confidence` label (high / medium / low) | `projects[].phases[].phase_confidence` |

## Retrieval evidence (auto-surfaced chunks)

- **Safe questions this chunk grounds** — `output/agent_chunks_v2_bcpd/projects/project_parkway_fields.md`
- **Caveats** — `output/agent_chunks_v2_bcpd/guardrails/guardrail_range_rows_not_lot_level.md`
- **Safe questions this chunk grounds** — `output/agent_chunks_v2_bcpd/sources/source_gl_vertical_financials.md`
- **Caveats** — `output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md`

