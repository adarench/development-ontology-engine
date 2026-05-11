# BCPD Operating State — Claude Skill Packaging Plan

_Plan to wrap the existing BCPD v2.1 workflow runtime into a Claude Skill.
This document is the design + scope brief. **It is not the Skill itself** —
the Skill is built only after this plan is reviewed._

## 1. Skill identity

- **Skill name**: `BCPD Operating State`
- **Internal slug**: `bcpd-operating-state`
- **One-line description**: "Reconstruct, brief, and pressure-test BCPD v2.1 operating state — read-only, lineage-aware, source-owner-honest."
- **Version**: `v0.1` (pre-release; gated on Skill review)

## 2. Intended user

| Role | Why they'd use it |
|---|---|
| **Finance / accounting** | Margin-report readiness, "do not include" lists for closing weeks, AultF B-suffix attribution, false-precision audit. |
| **Land / development** | Project briefs with phase / lot / cost-basis tables; decoder validation queue; commercial-parcel isolation. |
| **Ops / data team** | Finance/land/ops review prep; source-owner validation queue; v2.0 → v2.1 change impact. |
| **Executive / owner** | Honest scope update; what v2.1 fixed (dollar magnitudes); what's still blocked. |

Out of scope (intentionally): generic real-estate Q&A, autonomous agent action, anything that mutates source/staged data.

## 3. Six capabilities (the product surface)

Each capability maps 1:1 to an existing `Tool` subclass in `core/tools/bcpd_workflows.py` and an existing CLI subcommand in `bedrock/workflows/cli.py`. **No new code is required to expose these as Skill capabilities** — the Skill manifest just lists them.

| Capability | Underlying tool | CLI subcommand |
|---|---|---|
| Generate Project Brief | `GenerateProjectBriefTool` | `project-brief --project <name>` |
| Review Margin Report Readiness | `ReviewMarginReportReadinessTool` | `margin-readiness --scope bcpd` |
| Find False Precision Risks | `FindFalsePrecisionRisksTool` | `false-precision --scope bcpd` |
| Summarize Change Impact | `SummarizeChangeImpactTool` | `change-impact` |
| Prepare Finance / Land Review | `PrepareFinanceLandReviewTool` | `meeting-prep --scope bcpd` |
| Draft Owner Update | `DraftOwnerUpdateTool` | `owner-update --scope bcpd` |

Each tool already implements `to_api_schema()` (Anthropic tool_use shape) and registers with `ToolRegistry`. The Skill can either invoke them as direct tools (recommended) or as CLI commands via a sandboxed runner.

## 4. Sample user questions → capability mapping

| User question | Capability triggered | Sample arguments |
|---|---|---|
| "Give me a finance-ready summary of Parkway Fields." | Generate Project Brief | `project="Parkway Fields"` |
| "What about Harmony?" | Generate Project Brief | `project="Harmony"` |
| "Which BCPD projects should I be careful including in a lot-level margin report?" | Review Margin Report Readiness | `scope="bcpd"` |
| "Where might our current reports be giving false precision?" | Find False Precision Risks | `scope="bcpd"` |
| "What changed in v2.1 that affects prior views?" | Summarize Change Impact | `from_version="v2.0", to_version="v2.1"` |
| "Prepare me for a finance and land review." | Prepare Finance / Land Review | `scope="bcpd"` |
| "Draft an owner update for BCPD." | Draft Owner Update | `scope="bcpd"` |

Skill manifest should also list 2–3 "negative" sample questions that the Skill explicitly cannot answer (so users learn the boundary fast):

- "What's our org-wide actuals across BCPD and Hillcrest?" → **refused** (org-wide v2 not available).
- "Allocate range-row cost to specific lots." → **refused** (no allocation method signed off).
- "Is the per-lot decoder cost validated?" → **NO; surfaces the inferred caveat instead.**

## 5. Guardrails (must be enforced by the Skill, not just by the underlying tools)

All eight v2.1 hard rules. The Skill prompt / Skill-runtime layer should re-affirm them in the system prompt so they hold even when the user pushes back:

1. **Missing cost is unknown, never $0.** (`cost_source_missing_cost_is_not_zero`)
2. **Inferred decoder rules stay inferred** until source-owner sign-off. (`guardrail_inferred_decoder_rules`)
3. **Range / shell GL rows live at project+phase grain only** — no per-lot allocation without sign-off. (`guardrail_range_rows_not_lot_level`)
4. **Harmony joins require the 3-tuple** `(project, phase, lot)`. (`guardrail_harmony_3tuple_join`)
5. **SctLot → Scattered Lots**, NOT Scarlet Ridge. (`guardrail_sctlot_scattered_lots`)
6. **HarmCo X-X parcels are commercial / non-residential** — exclude from residential lot rollups. (`guardrail_commercial_not_residential`)
7. **Org-wide v2 is unavailable** — Hillcrest / Flagship Belmont GL ends 2017-02. (`guardrail_orgwide_unavailable`)
8. **VF is cost-basis / asset-side**, not a balanced trial balance — never present as TB. (covered in `cost_source_*` chunks; ontology rule.)

Each guardrail is already embedded in the workflow tool outputs. The Skill layer adds:
- A system-prompt refusal pattern when a user asks for an out-of-scope rollup.
- A "see also" pointer for each guardrail to the relevant chunk file (already done in the tools).

## 6. Data / state files required

The Skill is **read-only** — it operates on snapshot artifacts, not live source systems. Bundle vs. reference:

### Bundle (small, deterministic, must travel with the Skill)

| File | Size | Why bundle |
|---|---|---|
| `output/operating_state_v2_1_bcpd.json` | ~4.7 MB | Canonical v2.1 state — every tool reads it. |
| `output/agent_chunks_v2_bcpd/` (46 chunks) | ~250 KB total | Routed + chunk retrieval source. |
| `output/agent_context_v2_1_bcpd.md` | ~10 KB | Hard rules + citation patterns. |
| `output/state_quality_report_v2_1_bcpd.md` | ~12 KB | Per-project coverage + open questions. |
| `data/reports/v2_0_to_v2_1_change_log.md` | ~16 KB | Source of truth for the change-impact tool. |
| `data/reports/coverage_improvement_opportunities.md` | ~20 KB | Source-owner validation queue. |
| `output/bcpd_data_gap_audit_for_streamline_session.md` | ~14 KB | Open-items framing for meeting prep + owner update. |

**Bundle total**: ~5 MB. Fits comfortably in a Skill archive.

### Reference / regenerable (do NOT bundle)

| File | Why exclude |
|---|---|
| `output/bedrock/entity_index.parquet` | Regenerable via `bedrock.embeddings.build`; not used by workflow tools (they use chunk + routed sources only). |
| `output/bedrock/embeddings_cache.parquet` | Pure cache. |
| `data/staged/*.parquet` | Bulk canonical tables — workflow tools don't read these directly. |
| `Collateral Dec2025 01 Claude.xlsx - *.csv` | Raw source extracts — pre-staged and not Skill-readable. |
| `data/raw/`, `data/_unzip_tmp/`, `data/processed/` | Already gitignored. |

The Skill must NOT attempt to read source CSVs directly. If a user asks something that would require a fresh GL load, the Skill refuses and points to the v2.2 source-owner queue.

## 7. Minimal folder structure for the future Skill

```
bcpd-operating-state/                       # skill root
├── SKILL.md                                # Skill manifest (capabilities, sample qs, guardrails)
├── README.md                               # one-page user-facing intro
├── tools/                                  # 6 thin tool registrations
│   ├── generate_project_brief.py           # imports + registers GenerateProjectBriefTool
│   ├── review_margin_report_readiness.py
│   ├── find_false_precision_risks.py
│   ├── summarize_change_impact.py
│   ├── prepare_finance_land_review.py
│   └── draft_owner_update.py
├── runtime/                                # imports from the merged repo
│   └── (vendored or symlinked: core/, bedrock/, financials/, ontology/)
├── state/                                  # bundled v2.1 artifacts (see §6)
│   ├── operating_state_v2_1_bcpd.json
│   ├── agent_chunks_v2_bcpd/
│   ├── agent_context_v2_1_bcpd.md
│   ├── state_quality_report_v2_1_bcpd.md
│   ├── data/reports/
│   │   ├── v2_0_to_v2_1_change_log.md
│   │   └── coverage_improvement_opportunities.md
│   └── bcpd_data_gap_audit_for_streamline_session.md
├── prompts/
│   ├── system_prompt.md                    # role + guardrail enforcement
│   ├── refusal_patterns.md                 # how to refuse org-wide / allocation / promote-to-validated
│   └── sample_questions.md                 # ~15 worked examples
└── tests/
    ├── test_guardrails_enforced.py         # adapter of tests/test_bcpd_workflows.py guardrail checks
    └── test_capability_smoke.py            # one-question smoke test per capability
```

Total Skill size after bundling: ~5–6 MB.

## 8. What's already done (no Skill work needed)

- **Tool classes**: 6 of 6 implemented and tested (`core/tools/bcpd_workflows.py`).
- **CLI dispatcher**: 6 of 6 subcommands (`bedrock/workflows/cli.py`).
- **Demo outputs**: 6 of 6 generated under `output/runtime_demo/`.
- **Glossary**: published at `output/runtime_demo/_glossary.md` — defines BCPD, VF / DR / QB, inferred / validated, unknown-not-zero, cost grains, 3-tuple join, AultF B-suffix and SR-suffix, SctLot, HarmCo X-X, org-wide v2, and the source-owner validation process.
- **Readability polish (complete)**:
  - VF / DR acronyms expanded on first use in the Parkway brief.
  - SR-suffix glossed inline in the Parkway brief cost-basis table.
  - `is_queryable` jargon replaced with plain English in the owner update ("3 of 125 phases currently have complete enough expected-cost data").
  - "Full triangle" glossed inline in the margin readiness coverage snapshot.
  - Dangling `scratch/vf_decoder_*` evidence citations in change-impact replaced with "internal VF decoder review notes (Q…)" via a deterministic transform in the tool layer.
- **Regression tests**: 31 content-level + 45 routing tests + 31 entity-retrieval + 18 ontology-runtime + 30 context-packing + 29 operational-eval + 24 hybrid-orchestration + bedrock-layer + the merged-PR test suite = **424 tests passing**.
- **Guardrails**: enforced in every tool output; verified by `test_owner_update_does_not_claim_orgwide_v2_ready`, `test_margin_readiness_says_missing_is_unknown_not_zero`, and the per-tool inferred-caveat tests.
- **Read-only**: `test_workflow_tools_did_not_modify_protected_files` proves the seven protected files survive every workflow run byte-for-byte.

## 9. What remains before the Skill is built

Ordered by friction:

### Must-do before packaging
1. **Decide bundle vs runtime-fetch.** This plan assumes bundle (~5 MB). If the Skill platform has a tighter size budget, the agent_chunks_v2_bcpd corpus can be regenerable from the v2.1 JSON, but the change_log + coverage_opportunities markdown must stay bundled.
2. **Pin Python and dependency versions.** Skill containers want reproducible deps. The runtime needs: `pandas>=2.0`, `pyarrow>=14.0`, `pydantic>=2.6`, `PyYAML>=6`. (Optional: `tiktoken` for accurate budgeting; `voyageai` and `sentence-transformers` are NOT required for workflow tools — they're for the bedrock entity-vector index, which the workflow tools don't use.)
3. **Write the SKILL.md manifest.** ~150 lines: name, description, 6 capability blocks (one per tool, with name / description / input_schema / 3 sample questions / link to underlying file), guardrail list, sample-question manifest.

### Should-do before announcing
4. ~~Polish the four "light polish" outputs~~ — **DONE**. All four readability fixes landed in the tools; demos regenerated; readability review updated.
5. ~~Add a glossary file~~ — **DONE**. `output/runtime_demo/_glossary.md` defines 19 terms.
6. **Per-project briefs**: today only `project_brief_parkway_fields.md` is generated. A loop over all 26 projects would produce a landing-page set the Skill can serve directly. Estimated effort: ~1 hour (single loop in the CLI's `all` mode, plus 25 expected-content tests).

### Nice-to-have (post-launch)
7. **Wire a lightweight UI**: a Streamlit / static-site front-end that renders the 6 demo outputs as cards. The workflow_value_demo_cards.md already used "demo cards" terminology — the UI shape is implied. No retrieval changes needed.
8. **Tool-use loop verification**: run the existing `LLMAgent` against a real Claude session with these tools registered, to verify the Anthropic tool_use round-trip works end-to-end.
9. **Persist retrieval traces**: every workflow tool already builds an `OrchestrationTrace` internally (via `HybridOrchestrator`). Persisting one JSON per run under `output/runtime_demo/traces/` would unlock replay + audit.
10. **CI workflow** for the Skill repo: regenerate the demo set on every PR and assert no content drift via `git diff --exit-code output/runtime_demo/`.

## 10. Open questions to answer before building the Skill

1. **Skill distribution platform.** Anthropic Claude Skill registry, Claude Desktop, or a custom deployment? Different platforms have different bundle constraints.
2. **Refresh cadence.** v2.1 is current. If/when v2.2 ships, does the Skill auto-load the new state file, or version-pin? **Recommendation: version-pin** — a Skill named "BCPD Operating State v2.1" should always answer from v2.1 state. v2.2 ships as a new Skill version.
3. **Identity / auth.** Workflow tools are read-only against bundled state — no auth required. But if the Skill ever calls `core.connectors.QuickBooksConnector` or similar to refresh, an auth pattern is needed.
4. **Telemetry boundary.** Should the Skill log which capabilities are invoked? If yes, where do the logs land? (Don't log query text — it may contain operational details.)
5. **Override behavior.** What happens if a user says "ignore the inferred caveat for my purposes"? **Recommendation: refuse** — the Skill should be honest, not compliant.
6. **Multi-project briefs.** Should `Generate Project Brief` accept a comma-separated list, or one project per invocation? **Recommendation: one per invocation** — keeps each brief focused and avoids context bloat.

## 11. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Skill bundles stale v2.1 state by accident (e.g., a fork takes copies an old JSON) | Medium | Pin the Skill version to a specific v2.1 build; include a hash check at startup. |
| User asks for org-wide and the Skill "tries to help" by approximating | High | Hard refusal pattern in system prompt; tested via `test_owner_update_does_not_claim_orgwide_v2_ready`. |
| User asks for per-lot allocation of range/shell | High | Hard refusal — also tested via `find_false_precision_risks` output. |
| Skill claims decoder is validated | High | Static text scan in `MustNotPromoteInferredToValidated` (operational eval) catches this; bring that into the Skill's smoke tests. |
| Outdated demo outputs in the Skill bundle | Low | CI regeneration step before bundling. |
| Routing rules miss a common phrasing | Low | 45 routing tests; add cases as new phrasings emerge. |

## 12. TL;DR for the next person

The runtime is **ready to package**. All polish work is done. What remains:

1. Write `SKILL.md` (capability manifest pointing at 6 existing tools + glossary + sample questions).
2. Bundle the ~5 MB of v2.1 state.
3. Decide on Skill distribution platform (open question §10).
4. Run the existing 424 tests as the Skill's regression bar.

**Already-done as of this hardening pass**:
- ~~Polish the four light-polish outputs~~
- ~~Add a glossary file~~
- ~~Add HarmCo / AultF routing improvements~~
- ~~Add field-level confidence boundaries~~
- ~~Verify read-only contract (7 protected files unchanged)~~

Estimated remaining effort: **1 day of SKILL.md manifest work + Skill-runtime bundling**. No infrastructure work, no architecture work, no test changes.
