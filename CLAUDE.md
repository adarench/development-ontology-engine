# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run all tests
python3 -m pytest tests/

# Run a single test file
python3 -m pytest tests/test_tools.py

# Run a specific test class or function
python3 -m pytest tests/test_tools.py::TestQueryTool
python3 -m pytest tests/test_new_classes.py::TestToolRegistry::test_dispatch_known_tool

# Tool Engine substrate (M3+): start Postgres + apply migrations
docker-compose up -d postgres
alembic upgrade head

# Engine integration tests (skipped automatically when Postgres is unreachable)
DATABASE_URL='postgresql+asyncpg://engine:engine@localhost:5432/engine' \
  python3 -m pytest tests/test_engine_graph_store.py
```

## Architecture

The project is being refactored from a three-tier pipeline into a **Tool Engine** — a graph-based runtime where AI composes tools from a registry of reviewed Python steps. See [`docs/tool_engine_plan.md`](docs/tool_engine_plan.md) and [`docs/tool_engine_implementation.md`](docs/tool_engine_implementation.md) for the full plan.

**For contributors:**
- Setting up locally → [`docs/local_development.md`](docs/local_development.md)
- Building steps + tools → [`skills/tool-engine/SKILL.md`](skills/tool-engine/SKILL.md)

### `core/` directory layout

```
core/
├── engine/                  orchestration substrate
│   ├── registry.py              @step decorator + in-process step registry
│   ├── db.py                    async SQLAlchemy engine + session_scope()
│   ├── models.py                User/Role/UserRole/Graph/GraphVersion SA models
│   ├── schemas.py               Pydantic GraphDef / NodeDef / EdgeDef / PortRef
│   ├── validator.py             registry-aware graph validation
│   ├── compiler.py              GraphDef → executable LangGraph (+ optional checkpointer)
│   ├── runner.py                start_run / resume_run with Postgres checkpointer
│   ├── store/                   DB layer (one module per aggregate)
│   │   ├── graphs.py                graph + graph_version CRUD
│   │   └── runs.py                  run lifecycle CRUD
│   └── notifiers/               pluggable notification channels
│       ├── base.py                  Notifier Protocol + NotificationContext
│       ├── dispatcher.py            fan-out, swallow per-channel errors
│       ├── inbox.py                 always-on V1 channel (no-op log)
│       └── registry.py              env-driven channel selection
│
├── steps/                   step library (the work itself)
│   ├── data/                    fetch data         ← canonical home for connectors
│   ├── transform/               compute/reshape    ← canonical home for typed transforms
│   ├── ai/                      LLM-powered steps  (empty in Phase 0)
│   └── output/                  human-facing       ← canonical home for renderers
│
├── lib/                     shared types (empty in Phase 0)
│
├── connectors/              ⚠ COMPAT SHIMS — re-export from core.steps.data
├── renderers/               ⚠ COMPAT SHIMS — re-export from core.steps.output
├── steps/*.py (top-level)   ⚠ COMPAT SHIMS — re-export from core.steps.transform
│
├── tools/                   legacy — LLM-facing orchestrators (Phase 1+ refactor)
├── agent/                   legacy — ToolRegistry + LLMAgent (Phase 1+ refactor)
└── ...

tests/                       pytest suite, fixtures in tests/fixtures/
legacy/                      original single-company scripts (reference only)
data/                        staged canonical tables and crosswalks
docs/                        ontology and architecture docs
```

### Canonical vs shim paths

Phase 0 of the Tool Engine refactor moved connectors, transforms, and renderers into a unified `core/steps/` tree organized by effect. The old locations were preserved as **compatibility shims** that re-export from the new canonical paths — existing imports still work unchanged. When writing new code, prefer canonical paths:

| Old path (shim) | Canonical path |
|---|---|
| `core.connectors.X` | `core.steps.data.X` |
| `core.renderers.X` | `core.steps.output.X` |
| `core.steps.X` (flat) | `core.steps.transform.X` |
| `core.steps.base` | `core.steps.transform.base` |
| `core.steps.registry` | `core.steps.transform.registry` |

Shims will be removed in a later cleanup pass once `core/tools/` and `core/agent/` are refactored.

### The `@step` decorator (`core/engine/registry.py`)

The new step registration mechanism. Each step is a Python function decorated with `@step(...)` declaring its name, typed input/output ports, effect tags, and description. The registry is populated at import time; the future engine compiler will use it to type-check graph definitions and dispatch step calls at run time.

Effects in current use:
- `read` — reads external data (safe for dry-run)
- `write` — writes external data (stubbed in dry-run)
- `cost` — costs money (LLM, paid API)
- `nondeterministic` — output varies on identical input
- `probabilistic` — inferred/estimated result with confidence
- `external_call` — talks to an external service
- `needs_approval` — requires human approval (emits interrupt)

### Step library overview

**`core/steps/data/`** — fetchers from external sources:
- `FileConnector` (CSV/Parquet/Excel/JSON local), `QuickBooksConnector`, `ClickUpConnector`, `DataRailsConnector`, `GCSConnector`.
- `DataRailsConnector.fetch()` owns the 2.16× row-multiplication dedup.

**`core/steps/transform/`** — typed transforms:
- Each step extends `DeterministicToolStep` (reproducible) or `ProbabilisticToolStep` (estimation — carries `probabilistic_type`, `confidence_level`, `method_description`, `result_caveats`).
- Key files: `gl_clean`, `gl_normalize`, `gl_aggregate`, `lot_parse`, `lot_state`, `project_state`, `phase_cluster`, `phase_state`, `operating_view`, `entity_resolution`, `coverage_metrics`, `chunk_generation`, `query_execution`.
- `PhaseClusterStep` is the key probabilistic step — gap-based lot_number clustering, confidence 0.5. Phase IDs are estimates until a real plat→lot reference table is available.
- `ProvenanceSummary` (in `transform/base.py`) accumulates which steps ran; JSON tools embed it as a `"provenance"` key in output.

**`core/steps/output/`** — human-facing renderers:
- `Renderer` ABC + `DashboardRenderer` (HTML executive dashboard).

**`core/tools/`** (legacy — not yet refactored):
- LLM-facing orchestrators. Each tool declares `name`, `description`, `input_schema()` for the Anthropic tool_use API. Tools return strings (JSON or markdown). To be replaced by graph definitions stored in the DB in Phase 1+.

**`core/agent/`** (legacy — not yet refactored):
- `ToolRegistry` holds registered tools, formats them for the Anthropic API, and dispatches calls by name. `LLMAgent` wraps the Anthropic Messages API in a tool-call loop. To be replaced by the engine's compiler/runner in Phase 1+.

### Key data integrity rules

- **Missing cost ≠ $0**: Projects absent from the GL must surface as `unknown`, never `$0`.
- **DataRails dedup**: Raw DR 38-col exports have a 2.16× row-multiplication bug — deduplicated in `DataRailsConnector.fetch()` (`core/steps/data/datarails.py`).
- **Org-wide is blocked**: Hillcrest and Flagship Belmont GL coverage ends 2017-02. All v2 rollups are BCPD-scoped only.
- **Phase IDs are estimated** — heuristic gap-based clustering, not a real plat reference.
- **3-tuple join discipline**: Harmony lots share lot numbers across phases (MF1 vs B1). Cost rollups must use `(project, phase, lot)` — never flat `(project, lot)`.
