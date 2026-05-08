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
```

## Architecture

The project is a three-tier pipeline for building LLM-queryable operating state from real-estate development data (ClickUp tasks + GL financials).

```
core/connectors/   — fetch and validate data from a source
core/steps/        — typed intermediate transforms
core/tools/        — LLM-facing orchestrators (return strings)
core/renderers/    — human-facing output (HTML, etc.)
core/agent/        — ToolRegistry + LLMAgent for Anthropic tool_use
tests/             — pytest suite (176 tests), fixtures in tests/fixtures/
legacy/            — original single-company scripts (reference only)
data/              — staged canonical tables and crosswalks
docs/              — ontology and architecture docs
```

### Connector layer (`core/connectors/`)

Each data source has its own `Connector` subclass. `FileConnector` reads CSV/Parquet/Excel/JSON locally — used for all tests. Real connectors: `QuickBooksConnector`, `ClickUpConnector`, `DataRailsConnector`. `DataRailsConnector` owns the known 2.16× row-multiplication dedup at fetch time.

### Step layer (`core/steps/`)

Individual typed transforms. Each extends either `DeterministicToolStep` (reproducible) or `ProbabilisticToolStep` (estimation — carries `probabilistic_type`, `confidence_level`, `method_description`, `result_caveats`). `ProvenanceSummary` accumulates which steps ran; JSON tools embed it as a `"provenance"` key in output.

`PhaseClusterStep` is the key probabilistic step — gap-based lot_number clustering, confidence 0.5. Phase IDs are estimates until a real plat→lot reference table is available.

### Tool layer (`core/tools/`)

LLM-facing only. Each tool declares `name`, `description`, `input_schema()` for the Anthropic tool_use API. Tools return strings (JSON or markdown). HTML output lives in `core/renderers/`, not here.

### Agent layer (`core/agent/`)

`ToolRegistry` holds registered tools, formats them for the Anthropic API, and dispatches calls by name. `LLMAgent` wraps the Anthropic Messages API in a tool-call loop.

### Key data integrity rules

- **Missing cost ≠ $0**: Projects absent from the GL must surface as `unknown`, never `$0`.
- **DataRails dedup**: Raw DR 38-col exports have a 2.16× row-multiplication bug — deduplicated in `DataRailsConnector.fetch()`.
- **Org-wide is blocked**: Hillcrest and Flagship Belmont GL coverage ends 2017-02. All v2 rollups are BCPD-scoped only.
- **Phase IDs are estimated** — heuristic gap-based clustering, not a real plat reference.
- **3-tuple join discipline**: Harmony lots share lot numbers across phases (MF1 vs B1). Cost rollups must use `(project, phase, lot)` — never flat `(project, lot)`.
