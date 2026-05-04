# BCPD v2 State Quality Pass — Master Plan

**Owner**: Terminal A (integrator)
**Status**: planning, pre-implementation
**Last updated**: 2026-05-01
**Companion plans**: `docs/vf_lot_code_decoder_plan.md`, `docs/agent_contract_v2_bcpd_plan.md`, `docs/context_chunking_plan.md`

## Context

BCPD Operating State v2 has shipped (`output/operating_state_v2_bcpd.json` and the four companion artifacts). Guardrail was GREEN. The current baseline is in `output/state_quality_report_v2_bcpd.md`, `data/reports/join_coverage_v0.md`, and `output/bcpd_operating_state_v2_review_memo.md`.

This pass does **not** expand scope to org-wide v2 (still blocked: no fresh GL for Hillcrest / Flagship Belmont). It improves the *quality* of the existing BCPD state — better joinability, safer agent answers, more machine-readable provenance — using the data we already have.

The driving facts from the review memo:

- GL ↔ inventory: **63%** of high-confidence inventory lots have ≥1 GL row.
- ClickUp ↔ inventory: **63%**.
- Full triangle (GL ∧ ClickUp ∧ inventory): **37%** (49.2% on the active-only subset).
- VF lot codes encode phase+lot together for parts of Harmony, Lomond Heights, Parkway Fields. Concrete example: Harmony VF lot `1034` likely = Phase 3 Lot 34, but inventory has it as Lot 34 in Phase A7.
- Phase column is 0% filled across all 3 GL source schemas (DR-38, VF-46, QB-12). Phase rollups derive from inventory + Lot Data + 2025Status + ClickUp.
- 7 active BCPD projects + Lewis Estates have **structural gaps** (no GL coverage at all). No transformation logic can fix these.
- DataRails 38-col is 2.16× row-multiplied at source; build pipeline already deduplicates. Raw v2 parquet is preserved unchanged.
- Vertical Financials is one-sided (asset-side debits, 3 account codes only — 1535/1540/1547). Not a balanced trial-balance.
- QB register uses a different chart of accounts (177 codes; zero overlap with VF/DR). Tie-out only.

## Hard guardrails (apply to every workstream)

1. **Do not overwrite BCPD v2 outputs.** Every new artifact is additive and uses a `_v2_1` or `_quality_pass_v0` suffix.
2. **Do not publish org-wide state.** Track B remains blocked.
3. **Do not silently upgrade confidence.** Any decoder rule, crosswalk fix, or coverage estimate must keep the original confidence visible until validated. New rules ship `inferred` until source-owner-validated.
4. **Missing is not zero.** Lots with no GL data must remain `actual_cost = null` (with a reason), never `0`.
5. **Source traceability per row.** Every new row in any new staged or output table carries `source_file`, `source_row_id` (or `row_hash` for transactions), and a `confidence` value.

## Workstreams (W1–W6)

The user's 6 improvement areas map to 6 workstreams. W1, W4, and W5 each have a dedicated plan doc; W2, W3, and W6 are scoped here.

### W1 — Phase-aware VF lot-code decoder
**Plan doc**: `docs/vf_lot_code_decoder_plan.md`
**Goal**: Lift Harmony, Lomond Heights, Parkway Fields lot-match rates from 44–62% toward 80–90% by decoding VF lot codes that encode phase+lot in a single string.
**Outputs (post-approval)**: `data/staged/vf_lot_code_decoder_v0.csv`, `data/reports/vf_lot_code_decoder_report.md`.

### W2 — Crosswalk quality audit
**Goal**: Produce a written audit of all four crosswalk tables (entity, project, phase, lot) showing high/medium/unresolved counts and ranking the highest-impact unresolved mappings.

**Inputs**:
- `data/staged/staged_entity_crosswalk_v0.{csv,parquet}` (small)
- `data/staged/staged_project_crosswalk_v0.{csv,parquet}` (small; both DR + VF + ClickUp + Inventory + 2025Status sources)
- `data/staged/staged_phase_crosswalk_v0.{csv,parquet}` (medium)
- `data/staged/staged_lot_crosswalk_v0.{csv,parquet}` (~14,537 rows)
- `docs/crosswalk_plan.md` (current rules)

**Method**:
- For each crosswalk: count rows by `confidence` (`high` / `medium` / `low` / `unmapped`).
- For unmapped/low rows: rank by **downstream impact** — how many distinct GL rows / inventory lots / ClickUp tasks does each unresolved mapping touch?
- For medium rows: list the typo or convention rule that gave them medium status; flag any that are likely to be wrong (not just imperfect).

**Specific items to investigate**:
- `SctLot` vs `ScaRdg` ambiguity in VF for Scarlet Ridge — is `SctLot` actually Scarlet Ridge or something else?
- ClickUp `P2 14` and similar short tokens — can any be resolved to a project + phase + lot triple?
- Inventory CLOSED-tab subdivs at `low` confidence (LEC, WILLOWS, WESTBROOK, etc.) — are any actually active and just mis-tagged?
- Hillcrest GL `HIllcr` / `HllcrM` / `HllcrN` / etc. — confirm these collapse cleanly to `Hillcrest` (out of scope for BCPD v2 but logged for Track B).

**Output (post-approval)**: `data/reports/crosswalk_quality_audit_v1.md`. Includes per-crosswalk count tables, top-10 high-impact unresolved rows per level, and a recommendations list (which fixes to pursue, which to leave alone).

**Definition of done**: every unresolved row in the four crosswalk tables either has a recommended resolution rule, an "investigate next dump" tag, or an explicit "known structural gap, no action" verdict.

### W3 — Join coverage improvement analysis
**Goal**: Estimate the coverage lift from each candidate fix (W1 decoder, W2 crosswalk fixes, lot formatting normalization, ClickUp subdivision mapping) and rank them by impact-per-effort.

**Inputs**:
- `data/reports/join_coverage_v0.md` (baseline: 63% GL / 63% ClickUp / 37% triangle)
- W1's `vf_lot_code_decoder_v0.csv` (or, if not yet built, the planned decoder rule set)
- W2's audit
- `data/staged/staged_inventory_lots.parquet` and `staged_gl_transactions_v2.parquet` for impact simulation

**Method**:
- Baseline (already known): 63% / 63% / 37%.
- For each candidate fix, **dry-run** the fix (apply to a copy of the join key normalization) and recompute coverage on the same base.
- Report `delta_coverage` per fix, by project, with confidence on the simulated lift.

**Specific candidates to score**:
1. VF lot-code decoder applied to Harmony, Lomond Heights, Parkway Fields. Expected lift: Harmony 53.7% → ~85%, Lomond 43.9% → ~85%, Parkway 61.5% → ~85% (sketch; W1 produces the actual numbers).
2. SctLot/ScaRdg disambiguation. Expected lift: small — Scarlet Ridge is already at 90.9% match.
3. ClickUp subdivision typo cleanup (Aarowhead, Scarlett Ridge). Likely already mostly fixed in v0; verify.
4. Lot-format normalization beyond `_norm_lot` — preserving alpha suffixes (e.g. `1234A` vs `1234`); handling Roman numerals; trimming `Lot ` prefixes if any source carries them.
5. ClickUp lot-tagging discipline (raise from 21% to higher). Operational fix, not technical; estimate only.

**Output (post-approval)**:
- `data/staged/high_impact_join_fixes.csv` — one row per candidate fix with: `fix_name`, `applies_to_projects`, `baseline_match_rate`, `simulated_match_rate`, `delta_lots`, `delta_full_triangle_lots`, `effort_estimate`, `confidence_in_simulation`.
- `data/reports/coverage_improvement_opportunities.md` — narrative ranking + recommendation of which 2-3 fixes to actually land.

**Definition of done**: every candidate fix has an explicit simulated lift number (not a hand-wave) and an effort estimate (S / M / L). Top 3 are recommended for implementation.

### W4 — Agent contract hardening
**Plan doc**: `docs/agent_contract_v2_bcpd_plan.md`
**Goal**: Convert the prose-style content of `output/agent_context_v2_bcpd.md` into a formal, enforceable contract with question categories, citation rules, and refusal templates.
**Output (post-approval)**: `output/agent_contract_v2_bcpd.md`.

### W5 — Source-backed context chunks
**Plan doc**: `docs/context_chunking_plan.md`
**Goal**: Generate small markdown chunks for retrieval — per project, per coverage type, per caveat, per source family — each carrying facts + sources + confidence + caveats + safe questions.
**Output (post-approval)**: `output/agent_chunks_v2_bcpd/` directory tree.

### W6 — State quality report v2.1
**Goal**: Produce an updated quality report that shows current coverage, projected coverage if W1+W2+W3 fixes land, confidence changes, and unresolved blockers. Replaces nothing — published as `_v2_1`.

**Inputs**:
- `output/state_quality_report_v2_bcpd.md` (baseline)
- W2's audit
- W3's coverage simulation
- W1's decoder report (if landed) or expected lift (if not)

**Method**:
- Per-field table from baseline; new column `projected_fill_rate_post_quality_pass`.
- Per-project table from baseline; new columns for projected GL / ClickUp / triangle coverage if fixes land.
- New "What changed" section explicitly listing every confidence promotion (and the evidence that justifies it).
- New "Still blocked" section calling out structural gaps (the 7 active projects with no GL, the 2017-03 → 2018-06 dump-wide window, org-wide).

**Output (post-approval)**: `output/state_quality_report_v2_1_bcpd.md`.

**Definition of done**: every confidence promotion has a citable evidence source. Every "Still blocked" item names the unblocking artifact (e.g. "fresh GL pull for entity_code=2000 from 2017-03-01 onward").

## Dependencies and order

```
W2 (crosswalk audit)  ──┐
                        ├──> W3 (coverage simulation) ──> W6 (quality report v2.1)
W1 (VF decoder) ────────┘                                ↑
                                                          │
W4 (agent contract) ─────────────────────────────────────┤
W5 (context chunks)  ────────────────────────────────────┘
```

W1 and W2 are independent and can run in parallel. W3 needs both. W4 and W5 are independent of W1/W2/W3 (they use the existing v2 outputs as their input) and can land in parallel with the others. W6 needs W2, W3, and ideally W1.

## Sequence of work (planned, post-approval)

| step | workstream | deliverable | effort | depends on |
|---|---|---|---|---|
| 1 | W1 (decoder investigation) | `data/reports/vf_lot_code_decoder_report.md` (decoder rules `inferred`) | M | — |
| 2 | W2 (crosswalk audit) | `data/reports/crosswalk_quality_audit_v1.md` | S | — |
| 3 | W4 (agent contract) | `output/agent_contract_v2_bcpd.md` | S | — |
| 4 | W5 (context chunks) | `output/agent_chunks_v2_bcpd/` | M | — |
| 5 | W3 (coverage sim) | `data/staged/high_impact_join_fixes.csv` + `data/reports/coverage_improvement_opportunities.md` | S | W1, W2 |
| 6 | W1 (decoder rule landing, if validated) | `data/staged/vf_lot_code_decoder_v0.csv` | S | W1 step 1 |
| 7 | W6 (quality report v2.1) | `output/state_quality_report_v2_1_bcpd.md` | S | W2, W3 |

Steps 1–4 can run in parallel. Step 5 blocks on 1+2. Step 7 blocks on 2+5.

## Validation requirements

For each delivered artifact:
- **Citations**: every claim references a source file path or upstream artifact path.
- **Confidence labeling**: every new derived value carries an explicit `confidence` (no silent promotions).
- **Reproducibility**: every numerical claim can be regenerated from the staged tables under `data/staged/` plus the documented rule set.
- **Diff against baseline**: every report that updates a baseline (W6 vs `state_quality_report_v2_bcpd.md`) names the specific deltas.

## Decisions needed before implementation begins

1. **Decoder rule provenance**: are the inferred VF lot-code decoder rules acceptable as `confidence='inferred'` for v2.1, or must they be source-owner-validated before they ship? Recommendation: ship `inferred`, gate any confidence promotion on source-owner sign-off.
2. **W2 vs W3 ordering**: can W3 start with a stale crosswalk if W2 hasn't finished? Recommendation: yes, with a note that W3 numbers will be refined when W2 finishes.
3. **Agent chunk count target**: what's the desired upper bound on the chunk set for W5? Recommendation: ~50 chunks (16 active projects + 9 caveats + 5 source-families + ~20 utility/coverage), each ≤500 words.
4. **Inventory workbook (2) vs (4) re-stage**: deferred decision from the v2 review memo. Confirm the human's intent before W6 ships, since the answer changes 2 lot events.

## What this pass deliberately does NOT do

- Does not run org-wide v2.
- Does not modify `staged_gl_transactions_v2.{csv,parquet}` or any existing v2 output under `output/`.
- Does not modify v1 ontology, v1 pipelines, or v1 outputs.
- Does not change confidence values on existing canonical_* rows without explicit evidence.
- Does not solve structural gaps (the 7 BCPD projects with no GL coverage; Lewis Estates; the 2017-03 → 2018-06 window). These require new source data.
