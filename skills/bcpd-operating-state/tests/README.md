# Tests — BCPD Operating State Skill

_The Skill's regression bar is the existing test suite. **No new tests
are required for the Skill itself** — the runtime tools and routing
rules are already covered._

---

## The existing regression bar

| Test file | Tests | What it guards |
|---|---|---|
| `tests/test_bcpd_workflows.py` | 31 | Workflow content (Parkway brief mentions AultF / B1 / $4.0M / inferred; margin readiness says missing-is-unknown; false precision lists $45.75M; change impact lists $4.0M / $6.75M / $6.55M / $45.75M; meeting prep has finance/land/ops sections; owner update does NOT claim org-wide ready), `Tool.to_api_schema()` shape, `ToolRegistry` registration, **read-only contract on 7 protected v2.1 files**. |
| `tests/test_route_retrieval.py` | 45 | Routing rules — new `aultf_correction` and `harmco_commercial` rules fire correctly, do not false-positive, and all 16 prior rules still match. End-to-end `build_routed_evidence` surfaces expected chunk files. |
| `tests/test_hybrid_orchestration.py` | 24 | Orchestrator + RRF fusion + per-source isolation (the layer the workflow tools sit on top of). |
| `tests/test_context_packing.py` | 30 | Deterministic context packing (used internally by tool retrieval evidence sections). |
| `tests/test_entity_retrieval.py` | 20 | Entity-aware retrieval (not currently used by workflow tools, but part of the runtime surface). |
| `tests/test_ontology_runtime.py` | 18 | Ontology runtime (registry, lineage, content hashing). |
| `tests/test_operational_eval.py` | 29 | Operational correctness scenarios (overlapping names, crosswalk, allocation ambiguity, etc.). |
| Full suite | **424** | Everything above plus the merged-PR infrastructure layers. |

## How to run

### Quick: workflow + routing only

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_bcpd_workflows.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_route_retrieval.py
```

### Full regression bar

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/
```

### Demo regen + drift check

```bash
python3 -m bedrock.workflows.cli all
git diff --exit-code output/runtime_demo/
```

Empty diff = no drift. Non-empty diff = either a tool output changed
intentionally (regenerate + commit) or a regression (investigate before
shipping the Skill).

### Why `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`?

A globally installed `deepeval` pytest plugin in some dev environments
crashes on Python 3.9 union syntax. Project tests themselves have no
such issue. The env var disables plugin auto-loading and is harmless on
clean envs.

## What these tests prove for the Skill

The 31 workflow content tests are the most directly Skill-relevant:

- **Guardrail enforcement**: `test_owner_update_does_not_claim_orgwide_v2_ready`,
  `test_margin_readiness_says_missing_is_unknown_not_zero`,
  `test_false_precision_says_not_lot_level`, etc. — each maps to one of
  the eight v2.1 hard rules.
- **Read-only**: `test_workflow_tools_did_not_modify_protected_files` —
  runs every tool, verifies sha256 of all 7 protected files is unchanged.
- **Capability shape**: `test_tools_register_with_tool_registry`,
  `test_tools_emit_anthropic_api_schemas` — confirms the Anthropic
  `tool_use` API can consume the registered Skill tools as-is.

If any of these break, the Skill is not safe to ship — the Skill inherits
the runtime's correctness, so any regression in the runtime is a Skill
regression.

## Skill-level smoke tests (recommended after packaging)

Beyond the existing 424, add a small smoke pass after bundling the Skill:

1. Boot the Skill on a clean environment with only the bundled state.
2. Issue each of the 18 sample questions from `prompts/sample_questions.md`.
3. Verify each routes to the expected tool.
4. Issue the 8 boundary / refusal questions.
5. Verify each is refused with the appropriate template from `prompts/refusal_patterns.md`.

If any of these regress, do not ship — fix or roll back.

## CI integration

CI is already configured at `.github/workflows/main.yml` and runs:

1. `python -m pytest tests/`
2. `python -m bedrock.workflows.cli all`
3. `git diff --exit-code output/runtime_demo/`

All three must pass on every PR before the Skill bundle changes can land.
No additional Skill-specific CI is needed today.
