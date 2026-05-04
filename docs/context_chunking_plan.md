# Context Chunking — Plan

**Owner**: Terminal A
**Status**: planning, pre-implementation
**Parent**: `docs/bcpd_state_quality_pass_plan.md` W5
**Last updated**: 2026-05-01

## Goal

The current BCPD v2 outputs (`operating_state_v2_bcpd.json`, `agent_context_v2_bcpd.md`, `state_quality_report_v2_bcpd.md`, `state_query_examples_v2_bcpd.md`) are large, monolithic documents. An agent that loads them whole spends a lot of context on facts unrelated to the specific question being asked.

This plan defines a chunked context bundle — `output/agent_chunks_v2_bcpd/` — where each chunk is a small, self-contained markdown file an agent can retrieve on demand. Chunks come in four shapes (per project, per coverage type, per caveat, per source family) and every chunk carries the same minimum fields (facts, sources, confidence, caveats, safe questions).

This is **for retrieval**, not for replacing the monolithic docs. Both ship.

## Hard guardrails

1. **Chunks are derived, not original.** Every chunk is generated from the existing v2 artifacts. Nothing in a chunk can be a fact that does not already appear in a source artifact.
2. **Source traceability per chunk.** Every chunk lists its source artifacts in a `sources:` block. No floating claims.
3. **Confidence labeling per chunk.** Every chunk has an explicit `confidence:` for its primary claim and an explicit `caveats:` block.
4. **No double-counting via chunks.** When the same fact appears in two chunks (e.g. a project chunk and a caveat chunk), one is the canonical owner; the other refers to it.
5. **Stable chunk IDs.** Chunk filenames are stable and machine-readable so retrieval indices can rebuild deterministically.

## Chunk schema

Every chunk is a markdown file with frontmatter:

```yaml
---
chunk_id: <stable_identifier>
chunk_type: project | coverage | caveat | source_family | utility
canonical_target: <project_name | coverage_type | caveat_name | source_family_name | n/a>
confidence: high | medium | low | inferred | unmapped
last_built: 2026-05-01
sources:
  - <relative_path_1>
  - <relative_path_2>
related_chunks:
  - <chunk_id>
  - <chunk_id>
---
```

Followed by five required body sections (consistent across chunks):

1. **Facts** — 3–8 short bullet points, every fact with an inline source citation `[1]`, `[2]`, etc. matching the `sources:` list.
2. **Sources** — numbered list expanding the frontmatter `sources:` (path + brief description).
3. **Confidence** — one paragraph explaining why the `confidence:` value applies to this chunk's primary claims.
4. **Caveats** — bulleted list of known limitations specific to this chunk (e.g. "Lot match rate 53.7%", "phase column 0% filled in GL").
5. **Safe questions** — 3–8 example questions this chunk grounds the answer to.

Optional sixth section:

6. **Refused questions** — questions an agent might infer this chunk could answer but should not (e.g. on a Lewis Estates chunk: "What is Lewis Estates' actual cost?" → refused).

**Chunk size**: target ≤500 words per chunk. Hard cap 800. If a chunk grows beyond that, split it.

## Chunk catalog (to generate)

The total chunk set is target ~50 chunks. Estimated counts per type below.

### Type 1 — Per-project chunks (~17 chunks for active BCPD + ~25 historical = ~42, but bundle historical projects)

One chunk per active BCPD project (16 + Meadow Creek = 17). Historical projects bundled into 2 chunks (`historical_pre2018_with_gl_data`, `historical_pre2018_inventory_only`) to avoid 25 thin chunks.

Each project chunk's frontmatter:
```
chunk_id: project_<canonical_name_snake>
chunk_type: project
canonical_target: <project_name>
```

Per-project chunk facts cover (where data exists):
- Project status (active / historical / collateral-only)
- Lot count (active inventory + closed)
- 2018-2025 VF cost basis (if VF data exists)
- 2016-17 DR cost basis (if DR data exists, post-dedup)
- ClickUp lot-tagged coverage
- CollateralSnapshot row count and as_of
- Allocation/budget availability
- VF lot-code decoder applicability (if W1 lands)

Special chunks for the 8 no-GL projects (Ammon, Cedar Glen, …) carry only inventory facts and an explicit refused-questions section: do not estimate cost.

### Type 2 — Per-coverage-type chunks (~5 chunks)

- `coverage_gl_inventory.md` — current 63% GL match, per-project breakdown
- `coverage_clickup_inventory.md` — current 63% ClickUp match
- `coverage_full_triangle.md` — current 37% full-triangle, what limits it
- `coverage_by_year.md` — GL coverage by year (lots-with-GL-data per year, cross-referenced to inventory)
- `coverage_active_subset.md` — same metrics restricted to active inventory (49.2% triangle)

Each coverage chunk's primary source is `data/reports/join_coverage_v0.md`. Confidence is `high` for the metric itself; `medium` for any forward-looking estimate (which should be deferred to the W3 outputs anyway).

### Type 3 — Per-caveat chunks (~9 chunks, one per item in `state_quality_report_v2_bcpd.md` "Known caveats")

- `caveat_orgwide_blocked.md`
- `caveat_2017_2018_gl_gap.md`
- `caveat_dr_dedup_required.md`
- `caveat_vf_one_sided.md`
- `caveat_qb_register_chart_disjoint.md`
- `caveat_phase_grain_not_in_gl.md`
- `caveat_vf_lot_code_phase_encoding.md`
- `caveat_allocation_partial.md`
- `caveat_clickup_sparse.md`

Each caveat chunk explains:
- What the caveat is
- Which questions it makes refusable or caveatable
- Which questions it does NOT affect (so the agent doesn't over-disclose)
- Source artifact

### Type 4 — Per-source-family chunks (~5 chunks)

- `source_gl_datarails_38col.md` — schema, date range, dedup rule, fill rates by canonical field
- `source_gl_vertical_financials_46col.md` — same
- `source_gl_qb_register_12col.md` — same + tie-out only directive
- `source_clickup_tasks.md` — schema, lot-tagged subset definition, sparsity
- `source_inventory_lots.md` — workbook (2) selection, header offset, as_of

Each source-family chunk's primary source is the relevant validation report under `data/staged/` or `data/reports/`.

### Type 5 — Utility chunks (~5–10 chunks)

- `entity_definition_bcpd.md` — what BCPD is, who's in/out
- `entity_definition_bcpbl_asd_bcpi.md` — adjacent horizontal-developer entities
- `cost_source_hierarchy.md` — which source wins for which question (mirrors the agent contract table)
- `confidence_vocabulary.md` — `high` / `medium` / `low` / `inferred` / `unmapped` definitions
- `citation_format.md` — how an agent should cite (mirrors agent contract)
- `glossary.md` — short definitions of key terms (lot, phase, plat, subdivision, project, community)

## Chunk generation method

Chunks are generated by a script (post-approval) from the existing v2 artifacts:

1. Read `output/state_quality_report_v2_bcpd.md`, `data/reports/join_coverage_v0.md`, `output/agent_context_v2_bcpd.md`, `data/reports/guardrail_check_v0.md`, `docs/crosswalk_plan.md`.
2. For each chunk type, slice the relevant facts using a per-chunk template.
3. Validate: every chunk frontmatter parses; every claim has an inline citation; every chunk is ≤800 words.
4. Write chunks to `output/agent_chunks_v2_bcpd/<chunk_type>/<chunk_id>.md`.

Chunks are **regeneratable**. If the underlying artifacts change, re-run the generator; chunks rebuild deterministically.

## Index files

The chunk directory has two index files:

- `output/agent_chunks_v2_bcpd/index.json` — machine-readable: list of all chunks with `chunk_id`, `chunk_type`, `canonical_target`, `confidence`, `last_built`. Used by the retrieval layer.
- `output/agent_chunks_v2_bcpd/README.md` — human-readable: catalog of chunk types, count per type, link to a few representative chunks.

## Outputs (post-approval)

```
output/agent_chunks_v2_bcpd/
├── README.md
├── index.json
├── projects/
│   ├── project_arrowhead_springs.md
│   ├── project_harmony.md
│   ├── ... (17 active + 2 bundled historical = ~19 chunks)
├── coverage/
│   ├── coverage_gl_inventory.md
│   ├── ... (5 chunks)
├── caveats/
│   ├── caveat_orgwide_blocked.md
│   ├── ... (9 chunks)
├── sources/
│   ├── source_gl_datarails_38col.md
│   ├── ... (5 chunks)
└── utility/
    ├── confidence_vocabulary.md
    ├── ... (5–10 chunks)
```

Total: ~45–50 chunks.

## Validation requirements

- Every chunk's frontmatter validates against the schema above.
- Every body section is present (Facts / Sources / Confidence / Caveats / Safe questions).
- Every fact has an inline citation matching a `sources:` entry.
- No chunk exceeds 800 words.
- Every `chunk_id` listed in `index.json` corresponds to an actual file under the directory.
- The chunk generator is deterministic: a re-run with no upstream changes produces a byte-identical output (modulo `last_built` date).

## Hard guardrails

- **Do not duplicate canonical state**. Chunks are pointers + summaries. The canonical state is `output/operating_state_v2_bcpd.json`. Chunks must not contradict it.
- **Do not invent facts**. Every chunk fact must be traceable to a source artifact line.
- **Do not silently upgrade confidence in chunks**. A chunk can only carry the confidence that the underlying artifact carries.
- **Refresh discipline**. When the underlying artifacts change, chunks must be regenerated; they cannot drift out of sync.

## Out of scope

- The retrieval / embedding layer that uses these chunks. That's a separate plan and likely a separate consumer codebase.
- Chunking historical (pre-2018) lot-level data into per-lot chunks. Too granular for v0; revisit if the agent layer needs it.
- Chunking the full crosswalk tables. Too large; reference the source files instead.
- Any chunks for org-wide / non-BCPD entities. Out of scope until Track B unblocks.

## Definition of done

- All ~45–50 chunks generated under the directory tree above.
- Both index files (`index.json` + `README.md`) written and consistent with the chunks.
- Validation suite passes (schema, citations, size limit, determinism).
- A short test: pick 5 random chunks, verify each can be loaded standalone and answers at least one of its "Safe questions" without needing other chunks loaded.
