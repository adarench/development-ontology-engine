# BCPD Operating State — Claude Skill Skeleton

This directory is a **skeleton** for packaging the BCPD v2.1 workflow runtime
as a Claude Skill. It is documentation + manifest only. **The runtime code
itself lives elsewhere in this repo and is NOT duplicated here.**

## Why this exists

The BCPD v2.1 operating-state runtime already ships six read-only workflow
tools (project brief, margin readiness, false-precision audit, change
impact, finance/land review prep, owner update). The workflow tools are
deterministic, lineage-aware, and honor eight hard guardrails. The
remaining step before a finance / land / ops user can invoke them through
Claude is a Skill wrapper.

This skeleton is that wrapper, in scope-only form. To finish it, follow
`PACKAGING_CHECKLIST.md`.

## Where the runtime lives (NOT in this directory)

| What | Path |
|---|---|
| Six workflow tools | `core/tools/bcpd_workflows.py` |
| CLI dispatcher | `bedrock/workflows/cli.py` |
| Retrieval infrastructure | `bedrock/retrieval/`, `financials/qa/{rag_eval,llm_eval}/` |
| State files (bundle source) | `output/operating_state_v2_1_bcpd.json`, `output/agent_chunks_v2_bcpd/`, `output/agent_context_v2_1_bcpd.md`, `output/state_quality_report_v2_1_bcpd.md`, `data/reports/v2_0_to_v2_1_change_log.md`, `data/reports/coverage_improvement_opportunities.md` |
| Demo outputs (expected outputs) | `output/runtime_demo/*.md` |
| Tests (regression bar) | `tests/test_bcpd_workflows.py`, `tests/test_route_retrieval.py` |
| Design / packaging plan | `docs/bcpd_claude_skill_packaging_plan.md` |

## What's in this directory

```
skills/bcpd-operating-state/
├── SKILL.md                       # the manifest (capabilities, guardrails, refusal, versioning)
├── README.md                      # you are here
├── PACKAGING_CHECKLIST.md         # bundling + verification steps before Skill ship
├── prompts/
│   ├── system_prompt.md           # strict Skill behavior contract
│   ├── refusal_patterns.md        # refusal templates for the eight guardrail cases
│   └── sample_questions.md        # 18 sample questions grouped by workflow
├── state/
│   └── README.md                  # what state files to bundle + how the v2.1 pin works
├── tools/
│   └── README.md                  # how a Skill wrapper invokes existing tools (no duplication)
└── tests/
    └── README.md                  # how to use the existing test suite as the Skill's regression bar
```

## What's intentionally NOT here

- No copies of `core/tools/bcpd_workflows.py` or any Python module.
- No copies of state JSON / agent chunks / change log. Bundling happens at
  Skill-archive time per `PACKAGING_CHECKLIST.md` — the live source remains
  in the repo's `output/` and `data/reports/` paths.
- No duplicate Tool / Agent classes. The Skill registers the six existing
  Tool subclasses with the existing `ToolRegistry`.
- No new tests. The existing `tests/test_bcpd_workflows.py` (31) and
  `tests/test_route_retrieval.py` (45) are the Skill's regression bar.
- No new retrieval layer. The Skill uses the existing `bedrock` retrieval +
  packing stack as-is.

## Quick start (reading order)

1. `SKILL.md` — capability manifest + guardrails + refusal behavior.
2. `prompts/system_prompt.md` — system-prompt contract for the Skill runtime.
3. `state/README.md` — what to bundle, version pinning rationale.
4. `tools/README.md` — exact wiring between the Skill and `core/tools/bcpd_workflows.py`.
5. `tests/README.md` — regression bar invocation.
6. `PACKAGING_CHECKLIST.md` — step-by-step bundling.

## Status

This skeleton is **ready for review**. Open items before actual Skill build:

- Decide Skill distribution platform (affects bundle size constraints).
- Make a Skill-version-vs-state-refresh policy call (v2.1 is pinned; how
  does v2.2 ship as a new Skill?).
- Decide telemetry boundary (log capability invocations? log queries?).
- Decide refusal-override policy (user pushes back on a caveat — Skill
  stays strict or relaxes?).

All six items are enumerated in `SKILL.md` §10 and `docs/bcpd_claude_skill_packaging_plan.md` §10.
