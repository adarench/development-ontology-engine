# Change Impact — v2.0 → v2.1

## Headline dollar impact

| Correction | Rows | Dollar magnitude | Confidence |
|---|---|---|---|
| AultF B-suffix → B1 (was B2 in v0) | 1,499 | $4,006,662 re-attributed | `inferred (high-evidence)` |
| Harmony 3-tuple join | — | $6,750,000 double-count avoided | `inferred (high-evidence)` |
| SctLot → Scattered Lots (off Scarlet Ridge) | 1,130 | $6,553,893 un-inflated | `inferred-unknown (canonical name not source-owner-validated)` |
| Range / shell rows at project+phase grain | 4,020 | $45,752,047 surfaced explicitly | `inferred (high-evidence on interpretation; allocation method pending)` |
| HarmCo residential / commercial split | 169 res + 205 com | non-residential isolated | `inferred (high-evidence on residential; ontology pending for commercial)` |
| AultF SR-suffix isolated | 401 | $1,183,859 held inferred-unknown | `inferred-unknown` |

## Per-correction notes

### `aultf_b_to_b1_correction`
AultF B-suffix lots (0127B-0211B) now route to B1 (was B2 in v0). Empirically AultF and PWFS2 B-suffix lot ranges are disjoint.

_Evidence:_ internal VF decoder review notes (Q2)

### `harmony_3tuple_join_required`
Harmony joins use (project, phase, lot) 3-tuple. Flat (project, lot) would collapse MF1 lot 101 and B1 lot 101 onto the same inventory row.

_Evidence:_ internal VF decoder review notes (Q1+Q3)

### `harmco_split`
HarmCo split: residential A01-B10 → MF2; X-X commercial parcels (A-A through K-K) → non-lot inventory exception. Commercial pads NOT modeled as residential LotState in v2.1.

_Evidence:_ internal VF decoder review notes (Q2)

### `sctlot_to_scattered_lots`
SctLot is now a separate canonical project 'Scattered Lots'. v0 silently inflated Scarlet Ridge's project-grain cost by ~46%.

_Evidence:_ internal VF decoder review notes (Q4)

### `range_rows_at_project_phase_grain`
Range-form lots ('3001-06', '0009-12', etc.) kept at project+phase grain. Surfaced as `vf_unattributed_shell_dollars` per phase. NOT expanded to per-lot synthetic rows in v2.1.

_Evidence:_ internal VF decoder review notes (Q5)

### `aultf_sr_isolated`
AultF SR-suffix lots (0139SR, 0140SR) isolated as inferred-unknown; not attached to lot-level cost in v2.1.

_Evidence:_ internal VF decoder review notes (Q1)

## What did NOT change

- Org-wide v2 is still not available. Hillcrest and Flagship Belmont GL coverage ends 2017-02.
- Decoder rules remain **inferred** until source-owner sign-off.
- Range/shell allocation method is still **pending** — no per-lot expansion has been authorized.

## Retrieval evidence

- **Safe questions this chunk grounds** — `output/agent_chunks_v2_bcpd/guardrails/guardrail_sctlot_scattered_lots.md`
- **Confidence by question (updated for v2.1)** — `output/agent_context_v2_1_bcpd.md`
- **Safe questions this chunk grounds** — `output/agent_chunks_v2_bcpd/cost_sources/cost_source_range_shell_rows.md`
- **Q4 — What changed from v2.0 to v2.1?** — `output/bcpd_state_qa_examples.md`
- **Hard guardrails honored** — `data/reports/v2_0_to_v2_1_change_log.md`
- **Questions to refuse or caveat** — `output/agent_chunks_v2_bcpd/guardrails/guardrail_commercial_not_residential.md`
