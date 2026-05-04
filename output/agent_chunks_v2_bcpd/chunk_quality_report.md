# Chunk Quality Report — agent_chunks_v2_bcpd

_Generated: 2026-05-04_  |  _State version: v2.1_

Total chunks: **44**

## Counts by type

| chunk_type | count |
|---|---:|
| cost_sources | 6 |
| coverage | 5 |
| guardrails | 8 |
| projects | 18 |
| sources | 7 |

## Projects covered

18 BCPD projects, including the new 'Scattered Lots' canonical project introduced in v2.1.

- Ammon
- Arrowhead Springs
- Cedar Glen
- Eagle Vista
- Eastbridge
- Erda
- Harmony
- Ironton
- Lewis Estates
- Lomond Heights
- Meadow Creek
- Parkway Fields
- Salem Fields
- Santaquin Estates
- Scarlet Ridge
- Scattered Lots
- Westbridge
- Willowcreek

**Not chunked** (deliberate): pre-2018 historical communities (Cascade, Silver Lake, Westbrook, Hamptons, etc.) live in the JSON state but are out of v2.1 active-project scope. They can be referenced via the operating_state JSON when needed; chunking them would inflate the chunk set without analytical value.

## Source families covered

- ✅ Inventory Closing Report
- ✅ Vertical Financials (VF 46-col)
- ✅ DataRails 38-col (DR)
- ✅ QuickBooks Register (QB 12-col)
- ✅ Collateral Reports + PriorCR + 2025Status + Lot Data
- ✅ Allocation Workbooks (LH, Parkway, Flagship v3)
- ✅ ClickUp Tasks

## Guardrails covered (8)

- `guardrail_bcpd_only` — Guardrail: BCPD-only scope
- `guardrail_commercial_not_residential` — Guardrail: Commercial parcels are not residential lots
- `guardrail_harmony_3tuple_join` — Guardrail: Harmony joins require project + phase + lot
- `guardrail_inferred_decoder_rules` — Guardrail: Decoder-derived mappings are inferred
- `guardrail_orgwide_unavailable` — Guardrail: Org-wide v2 is unavailable
- `guardrail_range_rows_not_lot_level` — Guardrail: Range / shell rows are not lot-level cost
- `guardrail_read_only_qa` — Guardrail: Read-only Q&A rules
- `guardrail_sctlot_scattered_lots` — Guardrail: SctLot is Scattered Lots, not Scarlet Ridge

## Cost-source treatments covered (6)

- `cost_source_commercial_parcels` — Cost source: HarmCo commercial parcels (non-lot inventory)
- `cost_source_datarails_38col_dedup` — Cost source: DataRails 38-col (BCPD 2016-17 — dedup mandatory)
- `cost_source_missing_cost_is_not_zero` — Cost source: Missing cost is missing, not zero
- `cost_source_qb_register_tieout_only` — Cost source: QB Register (tie-out only)
- `cost_source_range_shell_rows` — Cost source: Range / shell rows (project+phase grain)
- `cost_source_vertical_financials` — Cost source: Vertical Financials (BCPD 2018-2025 primary)

## Coverage chunks (5)

- `coverage_clickup_inventory` — Coverage: ClickUp lot-tagged ↔ inventory
- `coverage_full_triangle` — Coverage: Full triangle (GL ∧ ClickUp ∧ inventory)
- `coverage_gl_inventory` — Coverage: GL ↔ inventory join
- `coverage_no_gl_projects` — Coverage: BCPD projects with inventory but no GL
- `coverage_source_owner_validation_queue` — Coverage: Source-owner validation queue

## Known omissions

- **Historical pre-2018 projects** — Cascade, Silver Lake, Westbrook, Hamptons, Bridgeport, Beck Pines, etc. Not chunked as individual projects (they are present in the JSON state but out of active v2.1 scope).
- **Per-lot chunks** — too granular for v0; revisit if the agent layer demands lot-level retrieval.
- **Crosswalk-table chunks** — the lot-level crosswalk is 14,537 rows; chunking it would not be useful. Reference the source files instead.
- **Org-wide / non-BCPD entities** — out of scope (Track B). Hillcrest / Flagship Belmont / Lennar / EXT have no chunks.
- **Dehart Underwriting** — single-project underwriting model; not stageable; not chunked.

## Are chunks ready for RAG?

**Yes, with the retrieval strategy below.** Every chunk:

- Has frontmatter parseable by retrieval engines (chunk_id, type, source_files, confidence, allowed_uses, caveats).
- Carries source-file citations on every claim.
- Declares its safe questions explicitly so retrieval can match question-intent to chunk.
- Lists refused/caveated questions explicitly so retrieval can NOT-route those.
- Stays within the W5 plan's 800-word cap (most chunks are 250-500 words).

## Recommended retrieval strategy

For an LLM or RAG layer using these chunks:

**1. Always retrieve a guardrail chunk first** for any question that mentions:
- 'all entities' / 'org-wide' / 'company-wide' → `guardrail_orgwide_unavailable`
- 'cost' or 'dollars' on a project → `guardrail_inferred_decoder_rules` + the relevant cost_source chunk
- 'Harmony' + 'cost' → `guardrail_harmony_3tuple_join`
- 'SctLot' or 'Scarlet Ridge cost' → `guardrail_sctlot_scattered_lots`
- 'shell' / 'range' / 'shared' → `guardrail_range_rows_not_lot_level`
- 'commercial' → `guardrail_commercial_not_residential`

**2. Retrieve project chunk + relevant source/guardrail chunk + quality/caveat chunk.** Never answer from a project chunk alone if the question asks about cost, coverage, org-wide rollup, or source confidence.

**3. For cost questions specifically, retrieve at minimum:**
- The relevant project chunk
- The relevant cost-source chunk (VF / DR-dedup / QB tie-out / range / commercial / missing-not-zero)
- The `guardrail_inferred_decoder_rules` chunk
- The `coverage_no_gl_projects` chunk if the project might be in the no-GL set

**4. For coverage questions, retrieve at minimum:**
- The relevant coverage chunk (`coverage_gl_inventory`, `coverage_clickup_inventory`, `coverage_full_triangle`)
- The relevant project chunk if scoped to one project
- `coverage_source_owner_validation_queue` if the question asks about confidence promotion

**5. Always include guardrail chunks for unsupported/ambiguous questions.** When the question mentions org-wide, missing cost, or anything in scope of a guardrail, the guardrail chunk's 'Questions to refuse or caveat' section drives the answer.

**6. Cite source files in every answer.** Each chunk's `source_files` frontmatter lists the upstream artifacts; an answer that cites those is auditable.

**7. Respect confidence labels.** A chunk labeled `inferred` requires the answer to include the confidence; a chunk labeled `low` (e.g. no-GL projects) should drive a refusal on cost questions.

## Chunk index integrity

All chunks listed in `index.json` exist as files under the directory. The index should be regenerated whenever a chunk is added or modified. Tests (`tests/test_agent_chunks_v2_bcpd.py`) verify:
- Every indexed chunk has a corresponding file.
- Every chunk has the required frontmatter fields.
- Guardrail chunks include `missing_cost_is_not_zero` (in `cost_sources/`) and `org_wide_unavailable` (in `guardrails/`).
- No chunk claims `validated_by_source_owner=True` for inferred decoder rules.
- v2.1 protected files are not modified by chunk regeneration.
