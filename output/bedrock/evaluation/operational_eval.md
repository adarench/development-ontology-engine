# Operational Correctness Eval

**Pass rate**: 6/12 (50%)

## By category

| Category | Passed | Failed |
|---|---|---|
| `allocation_ambiguity` | 0 | 1 |
| `aultf_b_correction` | 0 | 1 |
| `canonical_promotion` | 1 | 0 |
| `commercial_isolation` | 0 | 1 |
| `crosswalk` | 0 | 1 |
| `inferred_caveat` | 0 | 1 |
| `lineage_integrity` | 1 | 0 |
| `margin_reconstruction` | 0 | 1 |
| `org_wide_refusal` | 1 | 0 |
| `overlapping_names` | 1 | 0 |
| `phase_ambiguity` | 1 | 0 |
| `source_conflict` | 1 | 0 |

## By assertion type

| Assertion | Passed | Failed |
|---|---|---|
| `lineage_hashes_match_disk` | 1 | 0 |
| `must_distinguish_overlapping_names` | 1 | 0 |
| `must_have_lineage_including` | 6 | 2 |
| `must_not_promote_inferred_to_validated` | 1 | 0 |
| `must_not_return_entity_id_matching` | 1 | 0 |
| `must_resolve_crosswalk` | 1 | 0 |
| `must_return_entity` | 4 | 0 |
| `must_return_guardrail_file` | 5 | 3 |
| `must_surface_warning` | 3 | 3 |

## Scenarios

### ✅ PASS — `harmony_lot_101_distinct_in_mf1_vs_b1` _(category: overlapping_names)_

**Narrative**: An accountant asks 'what is the cost picture for Harmony lot 101?'. There are TWO physical assets: lot 101 in MF1 (townhome) and lot 101 in B1 (single-family). v2.0 used a flat (project, lot) join and conflated $443K of spend onto the wrong inventory row. The retrieval system must surface BOTH lots distinctly so the accountant can see they are not the same asset.

**Query**: `What is the cost picture for Harmony lot 101?`

- pack_id: `d9256ac9861aafb3` | tokens: 1584 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 441 ms
- assertions: 3 passed, 0 failed

  - ✅ `must_distinguish_overlapping_names` — must distinguish overlapping names: ['lot:Harmony::MF1::101', 'lot:Harmony::B1::101']
    - all distinguished entities present
  - ✅ `must_return_guardrail_file` — a guardrail chunk whose path contains `guardrail_harmony_3tuple_join` must surface
    - guardrail chunk found
  - ✅ `must_surface_warning` — pack must surface a warning matching `/inferred|do not promote/`
    - matched warnings: ["[from entity] [lot.cost_to_date] Per-lot actual cost is derived via the v1 VF decoder and is NOT source-owner-validated. Cite as 'inferred' confidence. Do not promote to 'validated'."]

### ❌ FAIL — `sctlot_resolves_to_scattered_lots_not_scarlet_ridge` _(category: crosswalk)_

**Narrative**: A finance lead asks about 'SctLot cost'. In the raw VF GL, SctLot is a vendor-system label for the Scattered Lots program. v2.0 mistakenly bucketed $6.55M of SctLot spend into the Scarlet Ridge project, inflating Scarlet by ~46%. The system must resolve SctLot to Scattered Lots and must NOT silently include Scarlet Ridge as the canonical answer.

**Query**: `What is the actual cost on SctLot?`

- pack_id: `f9f02a8906b52494` | tokens: 1400 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 180 ms
- assertions: 3 passed, 1 failed

  - ✅ `must_resolve_crosswalk` — `SctLot` must resolve to `Scattered Lots`
    - canonical `Scattered Lots` present
  - ✅ `must_return_guardrail_file` — a guardrail chunk whose path contains `guardrail_sctlot_scattered_lots` must surface
    - guardrail chunk found
  - ✅ `must_not_return_entity_id_matching` — no hit may have entity_id matching `/^project:Scarlet Ridge$/`
    - no offending hits
  - ❌ `must_surface_warning` — pack must surface a warning matching `/inferred|Scattered Lots|do not promote/`
    - no warning matched /inferred|Scattered Lots|do not promote/; got: []

### ❌ FAIL — `range_row_cost_must_not_allocate_to_lots` _(category: allocation_ambiguity)_

**Narrative**: A land manager asks 'allocate the range row cost to specific HarmCo lots'. $45.75M of GL postings (~4,020 rows, 8 VF codes) span multiple lots and live at project+phase grain only. They cannot be allocated to specific lots without source-owner method selection (equal split, sales-weighted, fixed proportional). The system must surface the range-row guardrail and refuse to fabricate per-lot allocations.

**Query**: `Allocate the range row cost to specific HarmCo lots and show me per-lot totals`

- pack_id: `11789c58d41e78b4` | tokens: 1312 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 281 ms
- assertions: 2 passed, 1 failed

  - ✅ `must_return_guardrail_file` — a guardrail chunk whose path contains `guardrail_range_rows_not_lot_level` must surface
    - guardrail chunk found
  - ✅ `must_have_lineage_including` — pack lineage must cite a file containing `cost_source_range_shell_rows`
    - lineage cites a matching file
  - ❌ `must_surface_warning` — pack must surface a warning matching `/inferred|do not promote/`
    - no warning matched /inferred|do not promote/; got: []

### ❌ FAIL — `per_lot_actual_cost_must_carry_inferred_caveat` _(category: inferred_caveat)_

**Narrative**: A controller asks 'what's the actual cost on Harmony B1 lot 101?'. The vf_actual_cost_3tuple_usd field is computed by the v1 VF decoder, which is heuristic-driven and NOT source-owner-validated. The system must cite the inferred-decoder caveat and lineage the decoder report.

**Query**: `What is the actual cost of Harmony B1 lot 101?`

- pack_id: `2877627bd0303cbc` | tokens: 1586 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 194 ms
- assertions: 3 passed, 1 failed

  - ✅ `must_return_entity` — `lot:Harmony::B1::101` must appear in retrieved hits
    - found lot:Harmony::B1::101 in hits
  - ✅ `must_surface_warning` — pack must surface a warning matching `/inferred|VF decoder|not source-owner/`
    - matched warnings: ["[from entity] [lot.cost_to_date] Per-lot actual cost is derived via the v1 VF decoder and is NOT source-owner-validated. Cite as 'inferred' confidence. Do not promote to 'validated'."]
  - ❌ `must_return_guardrail_file` — a guardrail chunk whose path contains `guardrail_inferred_decoder_rules` must surface
    - no chunk contained 'guardrail_inferred_decoder_rules'; files=['output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_commercial_not_residential.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md', 'output/agent_chunks_v2_bcpd/projects/project_harmony.md', 'data/reports/vf_lot_code_decoder_v1_report.md', 'docs/ontology_v0.md', 'output/bcpd_state_qa_examples.md', 'output/agent_chunks_v2_bcpd/cost_sources/cost_source_commercial_parcels.md', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'data/reports/vf_lot_code_decoder_v1_report.md', 'docs/ontology_v0.md', 'output/agent_chunks_v2_bcpd/cost_sources/cost_source_commercial_parcels.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_commercial_not_residential.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md', 'output/agent_chunks_v2_bcpd/projects/project_harmony.md', 'output/bcpd_state_qa_examples.md', 'output/operating_state_v2_1_bcpd.json']
  - ✅ `must_have_lineage_including` — pack lineage must cite a file containing `vf_lot_code_decoder_v1`
    - lineage cites a matching file

### ✅ PASS — `phase_a_ambiguous_across_projects` _(category: phase_ambiguity)_

**Narrative**: A new analyst asks 'what is phase A?'. There are multiple projects with a phase 'A' (Salem Fields A, Eagle Vista A, etc.). The retrieval system must surface multiple project-scoped phase entities so the analyst sees the ambiguity, not a single arbitrary winner.

**Query**: `What is phase A?`

- pack_id: `e2e6bc1acb59f6f9` | tokens: 1121 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 176 ms
- assertions: 2 passed, 0 failed

  - ✅ `must_return_entity` — `phase:Salem Fields::A` must appear in retrieved hits
    - found phase:Salem Fields::A in hits
  - ✅ `must_return_entity` — `phase:Eagle Vista::A` must appear in retrieved hits
    - found phase:Eagle Vista::A in hits

### ❌ FAIL — `harmco_xx_commercial_isolated_from_residential_lots` _(category: commercial_isolation)_

**Narrative**: A pricing analyst asks 'what's the total cost on HarmCo'. HarmCo X-X parcels (~$2.6M, 205 rows) are commercial parcels — NOT residential lots. The system must surface the commercial-not-residential guardrail so the analyst knows to exclude commercial when reporting per-lot costs.

**Query**: `What is the total cost on HarmCo and per-lot averages?`

- pack_id: `0e67e525473433e4` | tokens: 968 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 183 ms
- assertions: 0 passed, 2 failed

  - ❌ `must_return_guardrail_file` — a guardrail chunk whose path contains `guardrail_commercial_not_residential` must surface
    - no chunk contained 'guardrail_commercial_not_residential'; files=['output/agent_chunks_v2_bcpd/guardrails/guardrail_range_rows_not_lot_level.md', 'output/agent_chunks_v2_bcpd/projects/project_ammon.md', 'output/agent_chunks_v2_bcpd/projects/project_cedar_glen.md', 'output/agent_chunks_v2_bcpd/projects/project_eagle_vista.md', 'output/agent_chunks_v2_bcpd/projects/project_eastbridge.md', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'output/agent_chunks_v2_bcpd/projects/project_erda.md', 'output/operating_state_v2_1_bcpd.json', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_range_rows_not_lot_level.md', 'output/agent_chunks_v2_bcpd/projects/project_ammon.md', 'output/agent_chunks_v2_bcpd/projects/project_cedar_glen.md', 'output/agent_chunks_v2_bcpd/projects/project_eagle_vista.md', 'output/agent_chunks_v2_bcpd/projects/project_eastbridge.md', 'output/agent_chunks_v2_bcpd/projects/project_erda.md', 'output/operating_state_v2_1_bcpd.json']
  - ❌ `must_have_lineage_including` — pack lineage must cite a file containing `cost_source_commercial_parcels`
    - no lineage entry contained 'cost_source_commercial_parcels'; lineage=['output/agent_chunks_v2_bcpd/guardrails/guardrail_range_rows_not_lot_level.md', 'output/agent_chunks_v2_bcpd/projects/project_ammon.md', 'output/agent_chunks_v2_bcpd/projects/project_cedar_glen.md', 'output/agent_chunks_v2_bcpd/projects/project_eagle_vista.md', 'output/agent_chunks_v2_bcpd/projects/project_eastbridge.md', 'output/agent_chunks_v2_bcpd/projects/project_erda.md', 'output/operating_state_v2_1_bcpd.json']

### ✅ PASS — `inferred_decoder_must_not_promote_to_validated` _(category: canonical_promotion)_

**Narrative**: A reporting analyst asks 'is Harmony lot cost validated by Finance?'. The honest answer is NO — the v1 decoder is inferred until source-owner sign-off. If the system surfaces an entity with confidence='inferred' inside a section that uses 'validated' loosely, that's a quiet promotion bug. This assertion catches it.

**Query**: `Is Harmony lot 101 cost validated, or inferred?`

- pack_id: `9935e6bef04ca6d5` | tokens: 1597 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 198 ms
- assertions: 3 passed, 0 failed

  - ✅ `must_not_promote_inferred_to_validated` — inferred-confidence hits must not be promoted to 'validated'
    - no promotion observed
  - ✅ `must_return_guardrail_file` — a guardrail chunk whose path contains `guardrail_inferred_decoder_rules` must surface
    - guardrail chunk found
  - ✅ `must_surface_warning` — pack must surface a warning matching `/inferred|do not promote/`
    - matched warnings: ["[from entity] [lot.cost_to_date] Per-lot actual cost is derived via the v1 VF decoder and is NOT source-owner-validated. Cite as 'inferred' confidence. Do not promote to 'validated'."]

### ✅ PASS — `dr_and_vf_have_disjoint_semantics_no_silent_combine` _(category: source_conflict)_

**Narrative**: A controller asks 'reconcile DataRails and Vertical Financials cost on Harmony for 2018-2025'. DataRails is legacy 2016-17 (with 2.16x row duplication), VF is the primary 2018-25 lot-cost source, and QB Register is 2025 vendor/cash on a different chart of accounts. They are NEVER combined raw. The system must surface the cost-source guardrails so the controller sees the semantic boundary.

**Query**: `Reconcile DataRails and Vertical Financials cost on Harmony 2018-2025`

- pack_id: `df82ce77da5221c0` | tokens: 1582 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 266 ms
- assertions: 2 passed, 0 failed

  - ✅ `must_have_lineage_including` — pack lineage must cite a file containing `cost_source`
    - lineage cites a matching file
  - ✅ `must_have_lineage_including` — pack lineage must cite a file containing `change_log`
    - lineage cites a matching file

### ❌ FAIL — `margin_reconstruction_must_inherit_inferred_caveat` _(category: margin_reconstruction)_

**Narrative**: An asset manager asks 'what's the margin on Harmony B1 lot 101?'. To compute margin you need vf_actual_cost_3tuple_usd (inferred) + vert_close_date / sale_price. Even if the system surfaces all the inputs correctly, it must carry the inferred-cost caveat through — variance/margin inherits the weakest input's confidence.

**Query**: `What is the margin on Harmony B1 lot 101?`

- pack_id: `9ca9b21bbfd02f9a` | tokens: 1670 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 181 ms
- assertions: 1 passed, 2 failed

  - ✅ `must_return_entity` — `lot:Harmony::B1::101` must appear in retrieved hits
    - found lot:Harmony::B1::101 in hits
  - ❌ `must_surface_warning` — pack must surface a warning matching `/inferred|do not promote/`
    - no warning matched /inferred|do not promote/; got: []
  - ❌ `must_return_guardrail_file` — a guardrail chunk whose path contains `guardrail_inferred_decoder_rules` must surface
    - no chunk contained 'guardrail_inferred_decoder_rules'; files=['output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_commercial_not_residential.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md', 'output/agent_chunks_v2_bcpd/projects/project_harmony.md', 'data/reports/vf_lot_code_decoder_v1_report.md', 'output/bcpd_state_qa_examples.md', 'output/agent_chunks_v2_bcpd/cost_sources/cost_source_commercial_parcels.md', 'output/bcpd_state_qa_examples.md', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'output/operating_state_v2_1_bcpd.json', 'data/reports/vf_lot_code_decoder_v1_report.md', 'output/agent_chunks_v2_bcpd/cost_sources/cost_source_commercial_parcels.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_commercial_not_residential.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md', 'output/agent_chunks_v2_bcpd/projects/project_harmony.md', 'output/bcpd_state_qa_examples.md', 'output/operating_state_v2_1_bcpd.json']

### ✅ PASS — `org_wide_query_must_surface_refusal_guardrail` _(category: org_wide_refusal)_

**Narrative**: A board member asks 'what are our org-wide actuals across all entities?'. Hillcrest and Flagship Belmont have GL data only through 2017-02 — frozen. Org-wide rollups are explicitly out of scope. The system must surface the org-wide-unavailable guardrail so the board member sees the data limit.

**Query**: `What are our org-wide actuals across BCPD, Hillcrest, and Flagship Belmont?`

- pack_id: `349bf2d02e6c598d` | tokens: 1353 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 194 ms
- assertions: 2 passed, 0 failed

  - ✅ `must_return_guardrail_file` — a guardrail chunk whose path contains `guardrail_orgwide_unavailable` must surface
    - guardrail chunk found
  - ✅ `must_have_lineage_including` — pack lineage must cite a file containing `agent_context_v2_1_bcpd`
    - lineage cites a matching file

### ❌ FAIL — `aultf_b_suffix_correction_visible_in_lineage` _(category: aultf_b_correction)_

**Narrative**: An auditor asks 'what changed for AultF in v2.1?'. v2.1 corrected $4.0M / 1,499 rows from B → B1. The change log carries the correction story. The system must lineage-cite the change_log so the auditor can verify the delta themselves.

**Query**: `What changed for AultF in v2.1?`

- pack_id: `56f50e6f2da496fe` | tokens: 1599 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 177 ms
- assertions: 1 passed, 1 failed

  - ✅ `must_have_lineage_including` — pack lineage must cite a file containing `change_log`
    - lineage cites a matching file
  - ❌ `must_have_lineage_including` — pack lineage must cite a file containing `parkway_fields`
    - no lineage entry contained 'parkway_fields'; lineage=['data/reports/v2_0_to_v2_1_change_log.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_bcpd_only.md', 'output/agent_chunks_v2_bcpd/guardrails/guardrail_sctlot_scattered_lots.md', 'output/agent_context_v2_1_bcpd.md', 'output/bcpd_state_qa_examples.md', 'output/operating_state_v2_1_bcpd.json']

### ✅ PASS — `lineage_content_hashes_verify_against_disk` _(category: lineage_integrity)_

**Narrative**: Any pack the system emits must be self-verifying: a downstream consumer must be able to confirm 'this fact came from a file that's still on disk and unchanged'. If a source file is mutated between pack-time and read-time, the lineage hash mismatch must catch it. This scenario asserts integrity on a normal query — verifying the framework works on current state.

**Query**: `Harmony 3-tuple correction overview`

- pack_id: `e52c63944d66b691` | tokens: 1788 | truncated: False | sources: ['entity', 'chunk', 'routed'] | elapsed: 171 ms
- assertions: 1 passed, 0 failed

  - ✅ `lineage_hashes_match_disk` — every lineage content_hash must match the on-disk file
    - all lineage hashes verify

