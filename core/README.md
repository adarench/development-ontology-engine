# `core/` — Tool Engine

The heart of the system. Tools are **graphs of steps**: deterministic Python, AI calls, and human interactions composed into workflows that can pause for hours or days and resume cleanly.

> **Status:** This README documents the **target** structure. The codebase is mid-refactor (Phase 0). Folders marked `←  migrated from X` describe code being moved; folders marked `legacy` will be removed once their contents are gone. See [`docs/tool_engine_plan.md`](../docs/tool_engine_plan.md) for the milestones.

---

## At a glance

**In short:** Two halves. `engine/` runs tools. `steps/` is the library of work the tools can compose.

```
   ┌─────────────────────────────────────────────────────┐
   │                                                     │
   │           ┌──────────────────┐                      │
   │           │     engine/      │   runs tools         │
   │           │ (orchestration)  │                      │
   │           └────────┬─────────┘                      │
   │                    │                                │
   │                    │ composes from ───┐             │
   │                    ▼                  │             │
   │           ┌──────────────────┐        │             │
   │           │      steps/      │ ◄──────┘             │
   │           │ (the work itself)│                      │
   │           └──────────────────┘                      │
   │                                                     │
   │           ┌──────────────────┐                      │
   │           │       lib/       │   shared types       │
   │           │  (no framework)  │   and utilities      │
   │           └──────────────────┘                      │
   │                                                     │
   └─────────────────────────────────────────────────────┘
```

---

## Directory tree

**In short:** Two top-level concepts (`engine/` + `steps/`) plus a small shared `lib/`. Steps are grouped by *what they do to the world* (read data, transform it, call AI, write output).

```
core/
│
├── engine/                  ◄── ORCHESTRATION
│   ├── registry.py              @step decorator + in-process registry
│   ├── schemas.py               Pydantic models (GraphDef, NodeDef, ...)
│   ├── compiler.py              graph definition → LangGraph
│   ├── runner.py                start_run() / resume_run()
│   ├── interrupts.py            request_human() + resolution helpers
│   ├── store/                   DB layer (one module per aggregate)
│   │   ├── graphs.py
│   │   ├── runs.py
│   │   ├── queue.py
│   │   ├── decisions.py
│   │   └── identity.py
│   └── api.py                   FastAPI routes
│
├── steps/                   ◄── THE WORK
│   ├── data/                    fetch/load data        ← migrated from connectors/
│   ├── transform/               compute / reshape      ← migrated from old steps/
│   ├── ai/                      LLM-powered steps
│   └── output/                  human-facing artifacts ← migrated from renderers/
│
└── lib/                     ◄── SHARED, FRAMEWORK-FREE
    ├── types.py                 common Pydantic types (LotsTable, PhaseTable, ...)
    └── provenance.py            data-integrity invariants
```

---

## What goes where

**In short:** A function's *effect on the world* determines its folder. Reading a CSV is `data/`; clustering numbers is `transform/`; calling Claude is `ai/`; writing an HTML report is `output/`.

| Folder | Holds | Typical effects |
|---|---|---|
| `steps/data/` | Fetchers from external sources or files | `read`, `external_call` |
| `steps/transform/` | Pure deterministic transforms | (none — pure) |
| `steps/transform/` (probabilistic) | Estimation, clustering, heuristics | `probabilistic`, `nondeterministic` |
| `steps/ai/` | LLM calls — classification, extraction, summarization | `cost`, `nondeterministic` |
| `steps/output/` | Reports, exports, visualizations | `write` |
| `engine/` | Orchestration only. **Never put business logic here.** | n/a |
| `lib/` | Types and invariants shared across steps. **No framework imports.** | n/a |

---

## How a step works

**In short:** A step is a Python function with a decorator. The decorator records the step's name, ports, and effects so the engine can find it, type-check connections, and surface it to AI authoring.

```
   ┌───────────────────────────────────────────────────┐
   │  @step(name="cluster_phases", ...)                │
   │  def cluster_phases(lots):                        │
   │      ...                                          │
   │      return {"phases": ..., "confidence": ...}    │
   └───────────────────────────────────────────────────┘
                          │
                          │  at import time
                          ▼
              ┌────────────────────────┐
              │   In-process registry  │
              │   (one dict per name)  │
              └────────────────────────┘
                          │
                          │  read by
                          ▼
              ┌────────────────────────┐
              │   Compiler & runner    │
              │   (engine/)            │
              └────────────────────────┘
```

Example:

```python
from core.engine.registry import step
from core.lib.types import LotsTable, PhaseTable

@step(
    name="cluster_phases",
    inputs={"lots": LotsTable},
    outputs={"phases": PhaseTable, "confidence": float},
    effects=["probabilistic"],
    description="Gap-based heuristic phase clustering from lot numbers.",
)
def cluster_phases(lots: LotsTable) -> dict:
    ...
```

---

## How a tool runs

**In short:** A tool is a graph stored in the DB. The runner compiles it to a LangGraph using the step registry, executes it, and checkpoints state at every interrupt. The process can fully exit between interrupts — pauses are durable.

```
   Time ──────────────────────────────────────────────────────►

   ┌─────────┐    ┌─────────┐                ┌─────────┐
   │ Start   │───►│ Execute │──interrupt────►│ exit    │
   │ run     │    │ steps   │  (checkpoint)  │ process │
   └─────────┘    └─────────┘                └─────────┘
                                                  ║
                                                  ║   ← NOTHING RUNNING →
                                                  ║   (hours / days)
                                                  ▼
                                            ┌─────────┐    ┌─────────┐    ┌──────────┐
                                            │ Human   │───►│ Resume  │───►│ Complete │
                                            │ decides │    │ from    │    │ or next  │
                                            │         │    │ ckpt    │    │ interrupt│
                                            └─────────┘    └─────────┘    └──────────┘
```

The mechanism is **LangGraph + Postgres checkpointer**. The engine wraps it; steps don't see it.

---

## Vocabulary

| Term | Means |
|---|---|
| **Step** | A registered function with typed ports and effect tags. Lives in code. |
| **Graph** | A composition of steps + edges. Stored in the DB. |
| **Graph version** | An immutable snapshot of a graph. Edits create new versions. |
| **Run** | One execution of one graph version. |
| **Interrupt** | A pause point that needs a human answer before continuing. |
| **Queue item** | A record representing something waiting on a human. |
| **Decision** | Recorded human response. Append-only. |
| **Provenance** | The chain of decisions and configs behind an output. |

---

## Where to put new code

**In short:** Almost everything is a step. If your code touches data, it's a step. If it's pure plumbing for the engine, it goes in `engine/`. Cross-step types go in `lib/`.

```
   ┌───────────────────────────────────────────────┐
   │  Does it do work on data, or call an LLM,     │
   │  or produce an output for humans?             │
   │                                               │
   │     ──► yes ──►  it's a step                  │
   │                  pick folder by primary effect│
   │                                               │
   │     ──► no  ──►  is it pure orchestration?    │
   │                  ──► yes ──► engine/          │
   │                  ──► no  ──► lib/             │
   └───────────────────────────────────────────────┘
```

**Decision tree examples:**

| You're adding... | Goes in |
|---|---|
| A QuickBooks fetcher for a new entity | `steps/data/` |
| A new way to allocate shell costs | `steps/transform/` |
| An LLM call that classifies lot descriptions | `steps/ai/` |
| A new monthly board-deck renderer | `steps/output/` |
| A new validation rule the compiler should enforce | `engine/compiler.py` |
| A Pydantic type used by 3+ steps | `lib/types.py` |

---

## Data integrity rules (preserved through the refactor)

**In short:** These rules predate the engine and remain inviolable. They live as code inside the relevant steps now, not in a separate constraint layer.

| Rule | Where it lives |
|---|---|
| Missing cost ≠ `$0` — surface as `unknown` | `lib/provenance.py` + every cost-rollup transform |
| DataRails 2.16× row dedup | `steps/data/datarails.py` |
| Org-wide rollups are blocked (Hillcrest, Flagship Belmont end 2017-02) | `steps/transform/` rollup steps + refusal interrupt (Type 6) |
| Phase IDs are estimates | `steps/transform/cluster_phases.py` — `effects=["probabilistic"]` |
| 3-tuple `(project, phase, lot)` join discipline for Harmony | `steps/transform/` join steps |

---

## Refactor status (Phase 0)

**In short:** Structure complete. Old locations preserved as **compat shims** that re-export from the new canonical paths — existing imports still work. Shims get removed in a later cleanup pass once `tools/` and `agent/` are refactored too.

| Milestone | What landed | Status |
|---|---|---|
| P0.1 | New empty folders + `__init__.py` files | ✅ done |
| P0.2 | `@step` decorator + registry (`core/engine/registry.py`) | ✅ done |
| P0.3 | `connectors/` → `steps/data/` + shims | ✅ done |
| P0.4 | old `steps/` → `steps/transform/` + shims | ✅ done |
| P0.5 | `renderers/` → `steps/output/` + shims | ✅ done |
| P0.6 | CLAUDE.md updated to document canonical paths | ✅ done |

Test status after P0: **413 passed, 11 skipped** (pre-existing). 5 collection failures due to missing `yaml` / `CONTEXT_PACK.md` are pre-existing environment issues, not introduced by the refactor.

**Deferred to a later cleanup pass:**
- Updating ~30 imports in `core/tools/`, `core/agent/`, and tests to use canonical paths.
- Removing the shim files in `core/connectors/`, `core/renderers/`, and top-level `core/steps/*.py`.
- Full removal of `core/tools/` and `core/agent/` — these contain real code, replaced in Phase 1+ engine work.

---

## Related docs

- [`docs/tool_engine_plan.md`](../docs/tool_engine_plan.md) — what we're building and why; phased milestones.
- [`docs/tool_engine_implementation.md`](../docs/tool_engine_implementation.md) — how each piece is built; data model, compiler, runner, interrupts, environments.
- [`docs/human_involvement_types.md`](../docs/human_involvement_types.md) — the 10 types of human participation the engine supports.
- [`docs/local_development.md`](../docs/local_development.md) — localhost setup, Docker/Postgres workflow, test layout.
- [`skills/tool-engine/SKILL.md`](../skills/tool-engine/SKILL.md) — how to build a step or a tool, and how they fit together.
