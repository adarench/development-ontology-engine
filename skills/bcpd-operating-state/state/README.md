# State Bundle — BCPD Operating State Skill

_What state files the Skill needs at runtime, what to bundle into the
Skill archive, and how the v2.1 version pin works._

---

## What the Skill reads

Every workflow tool in `core/tools/bcpd_workflows.py` loads from the same
seven artifacts via `BcpdContext`. These are the **required** files at
runtime:

| Path | Purpose | Approx size |
|---|---|---|
| `output/operating_state_v2_1_bcpd.json` | Canonical v2.1 state — projects, phases, lots, decoder rules, change summary, data quality, open questions. **Every tool reads this.** | ~4.7 MB |
| `output/agent_chunks_v2_bcpd/` | 46 markdown chunks under `{projects,coverage,cost_sources,guardrails,sources}/`. Retrieval source for the chunk + routed retrievers. | ~250 KB total |
| `output/agent_context_v2_1_bcpd.md` | Hard rules + citation patterns; the agent's read-only contract. | ~10 KB |
| `output/state_quality_report_v2_1_bcpd.md` | Per-project coverage + 8 open source-owner questions. | ~12 KB |
| `data/reports/v2_0_to_v2_1_change_log.md` | Per-correction details (AultF B-suffix, Harmony 3-tuple, SctLot, range/shell, HarmCo split, AultF SR-suffix). Read by `summarize_change_impact`. | ~16 KB |
| `data/reports/coverage_improvement_opportunities.md` | Source-owner validation queue; tier 1/2/3 ranking. Read by `prepare_finance_land_review`. | ~20 KB |
| `output/bcpd_data_gap_audit_for_streamline_session.md` | Meeting-prep brief; framing for the source-owner validation conversation. Read by `prepare_finance_land_review` and `draft_owner_update`. | ~14 KB |

**Bundle total: ~5 MB.** Fits comfortably as a Skill archive payload.

These files are **read-only** by contract. `tests/test_bcpd_workflows.py::test_workflow_tools_did_not_modify_protected_files` snapshots all seven before and after every workflow run and asserts byte-identity.

## What NOT to bundle

| Path | Why excluded |
|---|---|
| Raw source CSVs (`Collateral Dec2025 01 Claude.xlsx - *.csv`, `LH Allocation 2025.10.xlsx - *.csv`, `DataRails_raw.zip`, etc.) | Bulk; raw; the v2.1 state was already built from them. Re-bundling them adds tens of MB of payload that the Skill never reads. |
| `output/bedrock/entity_index.parquet`, `embeddings_cache.parquet` | Regenerable; the workflow tools do NOT use the bedrock entity-vector index. They use chunk + routed retrieval only. |
| `data/staged/*.parquet`, `data/staged/*.csv` | Pre-staged canonical tables; workflow tools read directly from `operating_state_v2_1_bcpd.json` instead. |
| `data/raw/`, `data/_unzip_tmp/`, `data/processed/` | Already gitignored. |
| `.env`, `*.key`, `*.pem` | Secrets. Never bundle. |
| `output/llm_eval/`, `output/rag_eval/` | Eval artifacts from prior dev runs; not part of the Skill's product surface. |
| `output/bedrock/` (other than `evaluation/`) | Bedrock retrieval cache + index; regenerable. |

If a packaging script accidentally globs `output/` or `data/`, an explicit
allow-list keeps the bundle clean. See `PACKAGING_CHECKLIST.md`.

## Version pinning — how it works

This Skill is **pinned to BCPD v2.1**. Two mechanical enforcement points:

1. **Schema version check at load.** The bundled JSON carries
   `schema_version: "operating_state_v2_1_bcpd"`. The `BcpdContext` loader
   does not validate this today, but a Skill-side wrapper should assert
   it before instantiating any tool — fast-fail on a v2.2 state file being
   dropped into a v2.1 Skill bundle.

2. **Sha256 manifest.** At packaging time, record the sha256 of every
   bundled file in a `state/MANIFEST.sha256` sidecar. A pre-flight check
   at Skill startup verifies the bundle hasn't been edited post-packaging.
   See `PACKAGING_CHECKLIST.md` for the recommended `find … sha256sum`
   incantation.

## When BCPD v2.2 ships

- Ship a **new Skill version** — `BCPD Operating State v2.2`.
- Do not silently upgrade the v2.1 Skill — prior audits / reports must
  remain reproducible from the v2.1 Skill.
- The v2.1 Skill stays published.
- The Skill manifest (`SKILL.md`) bumps `Version:` only.
- The six tool capabilities stay the same. Only the bundled state and the
  schema-version assertion change.

If v2.2 introduces new tools (unlikely in the near term), those are also a
new Skill version, not an in-place patch.

## Refresh policy (snapshot, not live)

The Skill does NOT call connectors to refresh data. The bundled state's
as-of dates are visible in the v2.1 JSON's `metadata` block:

- `as_of_date_inventory`
- `as_of_date_collateral`
- `as_of_date_gl_max`
- `as_of_date_collateral_prior`

If a user asks "is this current?", the Skill's honest answer is "this is
the v2.1 snapshot as of [those dates]; for newer data, wait for v2.2."
