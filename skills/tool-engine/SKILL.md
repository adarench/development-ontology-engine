# SKILL.md — Tool Engine

## 1. Skill name

**Tool Engine — Building Steps and Tools**

Internal slug: `tool-engine`
Version: tracks Phase 1 of the Tool Engine plan. See [`docs/tool_engine_plan.md`](../../docs/tool_engine_plan.md).

## 2. One-line description

> Build typed, reviewable Python **steps**, compose them into **tools** (graphs), and run them through the engine.

## 3. Two concepts you'll use

**In short:** A *step* is a function with declared ports and effects. A *tool* is a graph of steps stored in the DB. AI proposes tools; humans review them; the engine runs them.

```
   ┌──────────────┐   composes into   ┌──────────────┐   executed by   ┌─────────┐
   │    STEP      │ ─────────────────►│    TOOL      │ ───────────────►│ engine  │
   │  (code)      │                   │  (graph in   │                 │ runner  │
   │              │                   │   the DB)    │                 │         │
   └──────────────┘                   └──────────────┘                 └─────────┘
   one Python fn,                    nodes + edges,                    durable
   one purpose,                      one immutable                     pause /
   reviewed via PR                   version per save                  resume
```

| Term | What it is | Who owns it |
|---|---|---|
| **Step** | Python function with `@step(...)` | Engineers (PR-reviewed) |
| **Tool** | JSON graph referencing step names | AI proposes + humans approve |
| **Run** | One execution of one tool version | Engine |

---

## 4. Building a step

**In short:** Write a Python function, decorate with `@step`, declare its ports and effects. The decorator records it in the in-process registry at import time.

### Anatomy

```python
from core.engine.registry import step

@step(
    name="cluster_phases",                       # globally unique, stable
    inputs={"lots": list, "gap": int},           # port name → declared type
    outputs={"phases": dict, "confidence": float},
    effects=("probabilistic",),                  # see effect taxonomy below
    description="Gap-based heuristic phase clustering from lot numbers.",
)
def cluster_phases(lots, gap=50):
    # pure Python; return a dict keyed by declared output port names.
    return {"phases": {...}, "confidence": 0.5}
```

### The five fields of `@step`

| Field | Used by | Rule |
|---|---|---|
| `name` | graph definitions reference it | unique, stable, snake_case |
| `inputs` | compiler binds edges + config to kwargs | every kwarg the function uses should be declared |
| `outputs` | compiler validates downstream edges | every key your function returns must be declared |
| `effects` | engine treats step accordingly (dry-run, cost tracking, interrupts) | from the canonical list — see below |
| `description` | AI authoring + dashboards | one sentence, plain language |

### Effect taxonomy

```
   ┌─ pure ──────────────────────────────────────────────┐
   │  (no effects declared)                              │
   │  deterministic, no side effects, safe to re-run     │
   └─────────────────────────────────────────────────────┘
   ┌─ has effects ───────────────────────────────────────┐
   │  read              reads external data              │
   │  write             writes external data             │
   │  cost              costs money (LLM, paid API)      │
   │  external_call     talks to an external service     │
   │  nondeterministic  same input ≠ same output         │
   │  probabilistic     inferred/estimated result        │
   │  needs_approval    pauses; waits for human          │
   └─────────────────────────────────────────────────────┘
```

Effects can stack: `effects=("cost", "nondeterministic")` for an LLM call.

### Step folders (where to put it)

```
core/steps/
├── data/        fetch external data           → effects: read [, external_call]
├── transform/   compute / reshape / estimate  → none, or probabilistic / nondeterministic
├── ai/          LLM calls                     → cost, nondeterministic
└── output/      human-facing artifacts        → write
```

Pick by the step's **primary effect on the world**, not its complexity.

### Sync vs async

Both work. The compiler awaits async steps and calls sync steps directly. Default to sync unless you need to do I/O.

```python
@step(name="fetch_remote", inputs={"url": str}, outputs={"body": str}, effects=("read","external_call"))
async def fetch_remote(url):
    async with httpx.AsyncClient() as c:
        r = await c.get(url)
        return {"body": r.text}
```

### What a step must NOT do

- Read globals — every input comes through a declared port (or config).
- Mutate its arguments — treat them as immutable.
- Return anything other than a `dict[str, value]` (or `None` for void steps).
- Write to disk / DB / external services unless `effects` says so.

---

## 5. Building a tool (graph)

**In short:** A tool is a JSON document with `nodes` and `edges`. Each node points at a registered step by name; each edge maps one node's output port to another node's input port.

### Anatomy

```json
{
  "nodes": [
    {"node_id": "load",     "step_name": "fetch_clickup", "config": {"path": "data/tasks.csv"}},
    {"node_id": "extract",  "step_name": "lot_parse"},
    {"node_id": "cluster",  "step_name": "cluster_phases", "config": {"gap": 50}},
    {"node_id": "report",   "step_name": "render_dashboard"}
  ],
  "edges": [
    {"from": "load.tasks",      "to": "extract.tasks"},
    {"from": "extract.lots",    "to": "cluster.lots"},
    {"from": "cluster.phases",  "to": "report.phases"}
  ]
}
```

### Visualization

```
   load ─ tasks ──► extract ─ lots ──► cluster ─ phases ──► report
   (data)          (transform)        (transform)        (output)
                                       config:
                                         gap=50
```

### The shape

| Field | Type | Rule |
|---|---|---|
| `nodes[].node_id` | string | unique per graph; identifier-safe |
| `nodes[].step_name` | string | must resolve in the registry |
| `nodes[].config` | object | optional; keys matching declared inputs fill in unconnected ports |
| `edges[].from` | `"node_id.port"` | port must exist in source step's outputs |
| `edges[].to` | `"node_id.port"` | port must exist in target step's inputs |
| `edges[].condition` | string \| null | reserved for branching (Phase 2+) |

### Two rules to remember

1. **Edges win over config.** If an input port has both, the edge value is used.
2. **One source per input.** Two edges into the same `node.port` is a compile error.

### Linear / fan-out / fan-in

```
   linear:    A ──► B ──► C

   fan-out:        ┌──► B
              A ───┤
                   └──► C

   fan-in:    A ──┐
                  ├──► C
              B ──┘
```

All three are supported. Pick whichever topology matches the work.

---

## 6. Validating + compiling

**In short:** Pydantic checks the structure. The validator checks the registry. The compiler turns the graph into a runnable LangGraph.

```
   GraphDef        validate()              compile_graph()           run
   ─────────       ──────────              ───────────────           ───
   raw JSON  ──►   structure OK?  ──►      registry resolved?  ──►   .invoke()
                   ports parse?            types compatible?         /
                   no dup IDs?             topology lowers?          .ainvoke()
                                           edges non-conflicting?
```

```python
from core.engine.schemas import GraphDef
from core.engine.compiler import compile_graph

g = GraphDef.model_validate(graph_dict)     # structural check
compiled = compile_graph(g)                 # registry check + lowering
result = await compiled.ainvoke({"ports": {}})
print(result["ports"])
```

Errors are raised, not silent:

| Error | Why |
|---|---|
| `ValidationError` | Bad shape — duplicate node IDs, malformed port refs, etc. |
| `GraphValidationError` | Step missing from registry, port type mismatch, unknown input/output port |
| `CompilationError` | Two edges into one input port, step returned non-dict, etc. |

---

## 7. Saving + running a tool

**In short:** Save creates a new immutable version. The runner pins each run to a version. Editing a tool never affects in-flight runs.

```
   POST /graphs           ─► graphs row created (version 0, no def yet)
   POST /graphs/{id}/save ─► graph_versions row inserted (version 1)
                             graphs.latest_version = 1

                  ┌── new save? ──► version 2 created; v1 unchanged
                  │
   ─ versions ────┼─ run started against v1? ──► always sees v1
                  │
                  └── existing runs against v1 ──► unaffected
```

```python
from core.engine.db import session_scope
from core.engine.store import graphs

async with session_scope() as s:
    graph = await graphs.create_graph(s, name="phase report", created_by=1)
    version = await graphs.save_version(
        s, graph_id=graph.id, definition=g, created_by=1,
    )
print(graph.id, "v", version.version)
```

> **Coming in M5:** durable runs — start a run, pause at an interrupt, resume hours later via a different process. See [`tool_engine_plan.md`](../../docs/tool_engine_plan.md) §6.

---

## 8. Common patterns

### Static config + dynamic data

```json
{
  "node_id": "scale",
  "step_name": "scale_costs",
  "config": {"factor": 1.05, "currency": "USD"}
}
```

Step declares `factor` and `currency` as inputs; only data ports (`costs`) get incoming edges. Config supplies the rest.

### Sharing one source across many consumers

```json
"edges": [
  {"from": "load.tasks", "to": "extract.tasks"},
  {"from": "load.tasks", "to": "audit.tasks"},
  {"from": "load.tasks", "to": "report.tasks"}
]
```

Fan-out is fine. Each consumer gets a reference to the same upstream value.

### Combining multiple sources

```json
"edges": [
  {"from": "load_costs.costs",  "to": "join.costs"},
  {"from": "load_lots.lots",    "to": "join.lots"},
  {"from": "load_phases.phases","to": "join.phases"}
]
```

Fan-in works as long as each edge targets a **different** input port on the receiver.

---

## 9. Testing your step or tool

```bash
# Unit-test a step like any Python function — it's just a function with a
# decorator. No engine setup needed.
python3 -m pytest tests/test_steps/test_my_step.py

# Compile + run the tool with mocked steps to verify topology.
python3 -m pytest tests/test_engine_compiler.py

# Save to DB + reload — verify JSON round-trips clean.
docker-compose up -d postgres && alembic upgrade head
DATABASE_URL='postgresql+asyncpg://engine:engine@localhost:5432/engine' \
  python3 -m pytest tests/test_engine_graph_store.py
```

See [`docs/local_development.md`](../../docs/local_development.md) for the full local-dev workflow.

---

## 10. What's NOT in this skill yet

| Capability | Status |
|---|---|
| Pause / resume across process restarts | M5 (in flight) |
| Inline human approval interrupts | M6 |
| Provenance log (decisions → outputs) | M7 |
| AI-authored graph proposals | Phase 3 |
| Inbox UI / graph viewer | Phase 2 |
| Branching / conditional edges | Phase 2 |
| Scheduled cycles | Phase 5 |

---

## 11. Quick reference

```
   ┌─ Build a step ─────────────────────────────────┐
   │  1. Pick folder by primary effect              │
   │  2. Write fn(...) returning {port: value}      │
   │  3. Decorate with @step(name, inputs,          │
   │     outputs, effects, description)             │
   │  4. Add a unit test                            │
   └────────────────────────────────────────────────┘

   ┌─ Build a tool ─────────────────────────────────┐
   │  1. Sketch the graph (nodes + edges)           │
   │  2. Build GraphDef.model_validate({...})       │
   │  3. compile_graph(g) — surfaces errors early   │
   │  4. graphs.save_version(...) — stores it       │
   │  5. await compiled.ainvoke({"ports": {}})      │
   └────────────────────────────────────────────────┘
```

---

## 12. Related

- [`core/README.md`](../../core/README.md) — directory layout and target structure
- [`docs/tool_engine_plan.md`](../../docs/tool_engine_plan.md) — what we're building and why
- [`docs/tool_engine_implementation.md`](../../docs/tool_engine_implementation.md) — implementation deep dive
- [`docs/local_development.md`](../../docs/local_development.md) — localhost setup
