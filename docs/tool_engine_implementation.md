# Tool Engine — Implementation Big Picture

Companion to [tool_engine_plan.md](tool_engine_plan.md). The plan answers *what* and *why*; this doc answers *how*. Phase 1 scope only — later phases get their own implementation notes when we get there.

Each section opens with a one-line plain-language summary, then digs in.

---

## 1. Stack

**In short:** Python end-to-end, Postgres for state, LangGraph for execution, FastAPI for the HTTP surface, Pydantic for schemas. No frontend in Phase 1.

```
   ┌──────────────────────────────────────────────────┐
   │  HTTP        FastAPI (5 endpoints)               │
   ├──────────────────────────────────────────────────┤
   │  App         Compiler · Runner · Interrupts      │
   ├──────────────────────────────────────────────────┤
   │  Engine      LangGraph + Postgres checkpointer   │
   ├──────────────────────────────────────────────────┤
   │  Schemas     Pydantic models for everything      │
   ├──────────────────────────────────────────────────┤
   │  Storage     Postgres (asyncpg + SQLAlchemy 2)   │
   └──────────────────────────────────────────────────┘
```

| Layer | Library | Why |
|---|---|---|
| HTTP | FastAPI | Pydantic-native, async, minimal ceremony |
| Workflow | LangGraph | Interrupts, checkpointer, replay — out of the box |
| State | Postgres | Concurrent runs, JSONB, mature LG checkpointer |
| Schemas | Pydantic v2 | Validates graph defs, payloads, decisions |
| DB access | SQLAlchemy 2.0 + asyncpg | Async, typed, plays well with FastAPI |
| Migrations | Alembic | One canonical answer |
| Tests | pytest + pytest-asyncio | Already in the repo |

---

## 2. Environments: local vs production

**In short:** Same code runs both. Differences are limited to where the database lives, where secrets come from, and whether API + worker share a process. Durability means there's no "local mode" — runs pause and resume the same way everywhere.

```
   LOCAL                                  PRODUCTION
   ─────                                  ──────────
   ┌──────────────────────────┐           ┌──────────────────────────┐
   │  docker-compose          │           │  container host          │
   │                          │           │                          │
   │  ┌────────────────────┐  │           │  ┌────────┐ ┌─────────┐  │
   │  │ FastAPI            │  │           │  │  API   │ │ Worker  │  │
   │  │  + in-process      │  │           │  │  svc   │ │  svc    │  │
   │  │    runner          │  │           │  └────┬───┘ └────┬────┘  │
   │  └──────────┬─────────┘  │           │       └─────┬────┘       │
   │             │            │           │             ▼            │
   │             ▼            │           │   ┌──────────────────┐   │
   │   ┌──────────────────┐   │           │   │ Managed Postgres │   │
   │   │ Postgres         │   │           │   └──────────────────┘   │
   │   │ container        │   │           │                          │
   │   └──────────────────┘   │           │   Secrets: cloud KMS     │
   │                          │           │   Logs:    structured    │
   │   Secrets: .env file     │           │   Errors:  Sentry-like   │
   └──────────────────────────┘           └──────────────────────────┘
```

| Concern | Local | Production |
|---|---|---|
| Database | Postgres in docker-compose | Managed Postgres (Supabase / Neon / RDS / Fly) |
| Process model | One FastAPI process, in-process runner | API + worker split when steps get slow enough to warrant it |
| Secrets | `.env` file (gitignored) | Cloud secret manager → env vars at runtime |
| External APIs (ClickUp, QB, DR) | Real dev keys, rate-limited | Real prod keys with rotation policy |
| AI model | Cheap model for iteration (e.g. Haiku) | Per-step model config (Sonnet / Opus where needed) |
| Migrations | `alembic upgrade head` against local DB | Same command, gated by deploy pipeline |
| Notifications | Inbox-only (manual poll) | Inbox + email/Slack (Phase 2+) |
| Auth | Single hardcoded test user | Real identity (added when ≥2 humans share the system) |
| Logs | Stdout | Structured JSON, shipped to a backend |
| Errors | Console traceback | Sentry or similar |

### Two principles that keep them similar

1. **Durability is identical in both.** A run started on a laptop checkpoints to Postgres just like prod. You can pause a run locally, kill the FastAPI process, restart your laptop, and resume — the same code path that handles a prod redeploy.
2. **No `if local: ...` branches.** Anything that varies (DB URL, secret values, model name, log format) comes from environment variables. Code reads env at startup; behavior never branches on "am I local."

### The genuinely tricky bit: in-flight runs across deploys

```
   Code @ commit A                       Code @ commit B
   ────────────────                      ────────────────
   cluster_phases v1:                    cluster_phases v2:
     in:  lots                             in:  lots
     out: phases                           out: phases, lots_per_phase  (NEW)

   Run R7 starts. Reaches interrupt.
   Checkpoint written. Process exits.
                                         <deploy commit B>
                                         R7 resumes.
                                         Which version of cluster_phases
                                         runs after the interrupt?
```

**What pin-to-version handles:** graph topology. A run resumes against the same graph *definition* it started under.

**What pin-to-version does NOT handle:** step code. Step implementations live in the codebase that gets redeployed. A run paused under commit A resumes under commit B's code.

**Practical rules:**
- Evolve steps **backward-compatibly**, same way you evolve protobuf or any serialized contract:
  - Add new output ports / new optional input fields freely.
  - Never remove or rename an existing port. Never change a port's type.
  - Behavioral changes should be safe-by-default — if existing graphs pass through, they still get correct results.
- If a step must change in a breaking way, **register it under a new name** (`cluster_phases_v2`). The old name keeps existing for in-flight runs; new graphs use the new name.
- Optional escape hatch (deferred): pin runs to a Git SHA at start. Resuming on a different SHA fails fast. Heavyweight; only worth it once step churn becomes a real source of incidents.

> **Decision needed:** Step code versioning — backward-compat by convention, or Git-SHA pinning from day one? Recommend convention; revisit if step churn hurts.

### Deployment surface for V1

V1 is local-dev only. The contract that makes future lift-and-shift cheap goes in from day one:

- `docker-compose.yml` — Postgres service + API service
- Single `Dockerfile` for the API
- All config via env vars (`DATABASE_URL`, `ANTHROPIC_API_KEY`, `LOG_LEVEL`, etc.)
- Alembic for migrations, run as part of container startup
- `.env.example` in the repo; real `.env` gitignored

When prod arrives, the lift is: provision managed Postgres, push the image to a container host (Fly / Render / Railway / Fargate), set env vars in the host's secret manager, run `alembic upgrade head`. No code changes.

> **Decision needed:** Local stack — docker-compose recommended. Alternative is "install Postgres directly on the laptop" which works but loses repeatability across machines.

> **Decision needed:** AI model in local — recommend Haiku for cheap iteration, configurable per-step in prod. Confirm.

---

## 3. Repository layout — full refactor

**In short:** `core/` is rebuilt from scratch for the engine model. Old folders (`connectors/`, `tools/`, `renderers/`, `agent/`) are folded into a new structure with two top-level concepts: **engine** (orchestration) and **steps** (work). The actual *logic* in the old code (DataRails dedup, phase clustering, etc.) is preserved — it gets rewrapped, not rewritten.

**Before → after:**

```
   BEFORE                          AFTER
   ──────                          ─────
   core/                           core/
   ├── connectors/  ─────────────► ├── steps/data/         (data ingestion steps)
   ├── steps/       ─────────────► ├── steps/transform/    (typed transforms)
   ├── tools/       ─────────────► (gone — tools are now graphs in DB)
   ├── renderers/   ─────────────► ├── steps/output/       (human-facing outputs)
   ├── agent/       ─────────────► (gone — engine handles tool registry & AI)
   └── (no engine)                 ├── engine/             NEW orchestration
                                   └── lib/                NEW shared types

   legacy/   ──────────────────────  legacy/   (unchanged, reference only)
```

**Target tree:**

```
core/
├── engine/                  NEW — orchestration substrate
│   ├── registry.py              @step decorator + in-process registry
│   ├── schemas.py               Pydantic models (GraphDef, NodeDef, EdgeDef, ...)
│   ├── compiler.py              GraphDef + registry → compiled LangGraph
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
├── steps/                   REFACTORED — all step implementations
│   ├── data/                    was: connectors/
│   │   ├── clickup.py
│   │   ├── quickbooks.py
│   │   ├── datarails.py             (2.16× dedup preserved here)
│   │   └── files.py
│   ├── transform/               was: steps/ (typed transforms)
│   │   ├── cluster_phases.py
│   │   ├── join_costs.py            (3-tuple Harmony join preserved here)
│   │   └── ...
│   ├── ai/                      new — wrapped LLM calls as @step functions
│   │   ├── classify.py
│   │   └── extract.py
│   └── output/                  was: renderers/
│       ├── html_report.py
│       └── ...
│
└── lib/                     NEW — shared, framework-free
    ├── types.py                 common Pydantic types (LotsTable, PhaseTable, ...)
    └── provenance.py            data-integrity invariants (missing ≠ $0, etc.)

migrations/                  Alembic
tests/engine/                Unit + integration for engine
tests/steps/                 Per-step tests (existing 176 tests migrate here)
legacy/                      Unchanged — historical reference
```

**What's preserved (logic, rewrapped as `@step` functions):**
- DataRails 2.16× row-multiplication dedup
- BCPD-scoping rule (Hillcrest / Flagship Belmont coverage ends 2017-02)
- 3-tuple `(project, phase, lot)` join discipline for Harmony
- Phase clustering heuristic with confidence 0.5
- Missing-cost-as-`unknown` invariant

**What's replaced (mechanism, not logic):**
- `ProvenanceSummary` → engine's `decisions` table + `outputs.decision_refs`
- `DeterministicToolStep` / `ProbabilisticToolStep` base classes → effect tags on `@step`
- `ToolRegistry` (Anthropic tool_use formatter) → engine compiles graphs to LG; AI authoring tier reads `@step` registry directly
- `LLMAgent` tool-call loop → AI steps are just steps with `effects=["cost","nondeterministic"]`

**Migration approach: Phase 0** — happens before any engine code is written. See plan doc section 8.

```
   Phase 0 (refactor)             Phase 1 (engine)
   ──────────────────             ────────────────
   1. Establish new folder        Build engine/ on top of
      structure                   the already-reshaped core/
   2. Rewrap existing logic       Reference @step-decorated
      with @step decorator        functions from compiled graphs
   3. Move tests; keep all
      176 passing
   4. Delete old folders
      once empty
```

The point of Phase 0 is that the old structure goes away *before* the engine arrives — no period where two parallel structures coexist.

---

## 4. Data model

**In short:** Ten tables. Identity (3), graph storage (2), run state (2), human-loop (2), outputs (1).

```
   ┌─────────┐     ┌────────────┐     ┌─────────┐
   │  users  │◄────│ user_roles │────►│  roles  │
   └────┬────┘     └────────────┘     └─────────┘
        │ owns / decides
        ▼
   ┌─────────┐     ┌──────────────────┐
   │ graphs  │────►│  graph_versions  │
   └─────────┘     └────────┬─────────┘
                            │ pinned
                            ▼
                       ┌─────────┐     ┌──────────────┐
                       │  runs   │────►│ checkpoints  │   ◄── LangGraph manages
                       └────┬────┘     └──────────────┘
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
         ┌────────────┐ ┌─────────┐ ┌──────────┐
         │queue_items │ │ outputs │ │decisions │ ◄── append-only
         └─────┬──────┘ └────┬────┘ └────┬─────┘
               │              └──refs────┘
               └──answered by──────────►
```

**Identity (3 tables)**

```
users          id, name, email, created_at
roles          id, name                          -- admin, approver, editor
user_roles     user_id, role_id                  -- many-to-many
```

**Graph storage (2 tables)**

```
graphs              id, name, latest_version, status, created_at
graph_versions      graph_id, version, definition (jsonb), created_by, created_at
                    PRIMARY KEY (graph_id, version)
```

`definition` JSONB shape:
```json
{
  "nodes": [{"node_id": "n1", "step_name": "load_lots", "config": {}}],
  "edges": [{"from": "n1.lots", "to": "n2.lots", "condition": null}]
}
```

**Run state (2 tables)**

```
runs                id, graph_id, graph_version, status, inputs (jsonb),
                    started_by, started_at, completed_at
                    status ∈ {running, awaiting_human, succeeded, failed, cancelled}

checkpoints         (managed by LangGraph's Postgres checkpointer — don't hand-roll)
```

**Human-loop (2 tables)**

```
queue_items     id, run_id, node_id, payload_type, payload (jsonb),
                authorized_roles (text[]), status, created_at
                status ∈ {open, answered, expired, cancelled}

decisions       id, queue_item_id, decided_by, decision (jsonb), decided_at
                APPEND-ONLY
```

**Outputs (1 table)**

```
outputs         id, run_id, key, value (jsonb), decision_refs (int[]),
                created_at
                decision_refs links to decisions.id for provenance
```

---

## 5. Step registry

**In short:** A `@step` decorator records metadata at import time. The registry is a module-level dict. The compiler reads it to validate; the runner dispatches into it at execution time.

```
   IMPORT TIME                 GRAPH COMPILE             RUN TIME
   ───────────                 ─────────────             ────────
   @step decorator             compiler reads            runner dispatches
   writes metadata             registry to validate      by step_name
        │                           │                         │
        ▼                           ▼                         ▼
   ┌──────────┐               ┌──────────┐              ┌──────────┐
   │ Registry │ ◄─────────────│ Compiler │              │  Runner  │
   │  (dict)  │               └──────────┘              └──────────┘
   └──────────┘
```

**The decorator does four things:**
1. Stores the wrapped function in `_REGISTRY[name]`.
2. Stores its declared inputs/outputs (Pydantic types) for compile-time checks.
3. Stores its effects list.
4. Stores its description for AI authoring.

```python
# registry.py — sketch
_REGISTRY: dict[str, StepSpec] = {}

def step(name, inputs, outputs, effects, description):
    def decorate(fn):
        _REGISTRY[name] = StepSpec(name, inputs, outputs, effects, description, fn)
        return fn
    return decorate

def get(name) -> StepSpec: ...
def all_steps() -> list[StepSpec]: ...
```

**Discovery:** at FastAPI startup, import every module under `core/steps/`. The decorators fire as a side effect of import.

---

## 6. Graph compiler

**In short:** Pure function from `(graph_def, registry) → compiled LangGraph`. Catches type and reference errors before any run starts.

```
   ┌────────────┐    parse +     ┌────────────┐   build      ┌──────────────┐
   │ graph_def  │───validate────►│   AST      │──with LG───► │ Compiled     │
   │  (JSON)    │                │ (typed)    │   builder    │ graph object │
   └────────────┘                └────────────┘              └──────────────┘
        │                              │                            │
        │                              │                            │
   "raw row from DB"             "every step_name           "ready to .invoke()
                                  resolved in registry,      or .stream() with
                                  every edge type-checked"   thread_id"
```

**Validation rules the compiler enforces:**
- Every `step_name` resolves in the registry.
- Every edge's `from.port` exists in source node's outputs.
- Every edge's `to.port` exists in target node's inputs.
- Port types are compatible (source output schema ⊆ target input schema).
- No dangling required inputs (every required input has an incoming edge or a config value).
- No cycles (or, if we allow them: explicit loop nodes only).

Validation errors raise structured exceptions with the offending node/edge — surfaced to authoring UI later.

---

## 7. Runner

**In short:** Two entry points. `start_run(graph_id, version, inputs)` and `resume_run(run_id, decision)`. Everything between them is LangGraph + the checkpointer.

**Start flow:**

```
 caller          runner           compiler        langgraph      postgres
   │                │                │               │              │
   ├─start_run()───►│                │               │              │
   │                ├─load graph────────────────────────────────────►│
   │                │◄────────────────────────────────────────graph_def
   │                ├─compile()─────►│               │              │
   │                │◄──compiled─────│               │              │
   │                ├─create run row────────────────────────────────►│
   │                ├─graph.invoke(inputs, thread_id=run_id)────────►│
   │                │                │               │ ckpt write──►│
   │                │                │               │ (every step) │
   │                │                │               │              │
   │                │           [interrupt]                          │
   │                │◄──{interrupt: payload}─────────│              │
   │                ├─write queue_item─────────────────────────────►│
   │                ├─update run.status=awaiting_human──────────────►│
   │◄──{run_id, queue_item_id}                                       │
```

**Resume flow:**

```
 caller          runner           langgraph      postgres
   │                │                │              │
   ├─resume_run────►│                │              │
   │  (run_id,      │                │              │
   │   decision)    │                │              │
   │                ├─write decision row───────────►│
   │                ├─load checkpoint──────────────►│
   │                ├─graph.invoke(Command(resume=decision),─────►
   │                │                │   thread_id=run_id)
   │                │                │  resumes from interrupt
   │                │                │  ckpt writes as it goes
   │                │                │
   │                │   [interrupt or completion]
   │                │◄──result───────│
   │                ├─update run.status─────────────►│
   │◄──{status, queue_item_id|outputs}
```

**Process model:** the runner can run in-process (FastAPI handler) or as a separate worker. Phase 1: in-process is fine — short steps, single-user. Add a worker queue when steps get slow.

---

## 8. Interrupts and the queue

**In short:** A step calls `request_human(payload_type, payload, authorized_roles)`. The engine writes a queue item, lets LangGraph's interrupt propagate, and the caller exits. Resumption injects the decision back into the step.

```
  Inside a step:                             Engine handles:
  ──────────────                             ───────────────
                                             ┌──────────────────────┐
   value = request_human(    ◄─────────────► │  write queue_items   │
       payload_type="t1",                    │  call interrupt()    │
       payload={...},                        │  yield control       │
       authorized_roles=["approver"]         └──────────┬───────────┘
   )                                                    │
                                                        ▼
   # `value` is the decision payload         ┌──────────────────────┐
   # returned when the run resumes           │  process exits       │
                                             │  (or returns to API) │
                                             └──────────────────────┘

                            (time passes)

                                             ┌──────────────────────┐
   resume_run(run_id,        ◄─────────────► │  write decisions row │
              decision)                      │  inject into ckpt    │
                                             │  langgraph resumes   │
                                             └──────────────────────┘
   # the step's `value` variable
   # now holds the decision payload
```

**Generic shape covers all four interrupt types.** Phase 1 builds the mechanism with `payload_type="inline_approval"`. Adding types 2, 5, 6 in Phase 2 is just new payload schemas + side-effect hooks at decision time — no engine changes.

**Side-effect hooks** (Phase 2 territory but designed in now): each payload type can register a `on_decided(decision, db) -> None` callback. Type 5's callback writes the crosswalk row; Type 6's stamps the output. Phase 1 doesn't need any callbacks; the hook system is just empty plumbing.

---

## 9. Notifications (pluggable)

**In short:** V1 ships **inbox-only** (queue items in the DB, polled by a human). But the notifier abstraction is in from day one so email / Slack / push channels are a new file each, not a refactor.

```
   ┌─────────────────────────────┐
   │  Engine writes queue_item   │
   └─────────────┬───────────────┘
                 │  fan-out
                 ▼
   ┌─────────────────────────────────────────────────────┐
   │      NotificationDispatcher.notify(queue_item)      │
   └─────┬─────────────┬─────────────┬─────────────┬─────┘
         │             │             │             │
         ▼             ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  Inbox   │  │  Email   │  │  Slack   │  │  (your   │
   │  (V1)    │  │ (Phase2) │  │ (Phase2) │  │  channel)│
   └──────────┘  └──────────┘  └──────────┘  └──────────┘
       ALWAYS         opt-in        opt-in         opt-in
```

**Contract:**

```python
class Notifier(Protocol):
    name: str

    def supports(self, queue_item: QueueItem) -> bool:
        """Should this channel fire for this queue item?"""

    async def notify(self, queue_item: QueueItem, user: User) -> None:
        """Best-effort dispatch. Must not block the runner on failure."""
```

**Phase 1 ships:**
- `Notifier` protocol + `NotificationDispatcher` (fan-out, swallow per-channel errors)
- `InboxNotifier` — no-op channel that just confirms the queue item is readable (the inbox *is* the queue row; this channel exists to keep the abstraction honest)
- Registry: env-var `NOTIFICATION_CHANNELS=inbox` selects which channels are active

**Adding a channel later** is one file in `core/engine/notifiers/`:

```python
# core/engine/notifiers/email.py  (Phase 2 example)
class EmailNotifier:
    name = "email"
    def supports(self, qi): return qi.payload_type in {...}
    async def notify(self, qi, user): await send_email(user.email, ...)
```

**Failure policy:** notifier errors never block run progress. A queue item is created regardless of whether the email send succeeds. Notifications are best-effort; the queue is the source of truth.

---

## 10. HTTP surface

**In short:** Five endpoints in Phase 1. All take and return Pydantic models; OpenAPI is generated automatically by FastAPI.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/graphs` | Create or update a graph (new version on each save) |
| `GET`  | `/graphs/{id}/versions/{v}` | Fetch a graph version |
| `POST` | `/runs` | Start a new run: `{graph_id, version, inputs}` |
| `GET`  | `/runs/{id}` | Read run status, current queue items, outputs |
| `POST` | `/queue_items/{id}/decide` | Submit a decision; triggers `resume_run` |

That's it for Phase 1. Authoring, inbox UI, and graph viewer come in Phase 2.

---

## 11. End-to-end trace

**In short:** A real walk through the foundation — start a graph with one approval node, the process exits at the interrupt, a decision arrives later, the run completes.

The graph:

```
   ┌──────────┐         ┌───────────────────┐         ┌────────────┐
   │load_lots │──lots──►│ cluster_phases    │──ok?──► │write_report│
   └──────────┘         │  (needs_approval) │         └────────────┘
                        └───────────────────┘
```

**T+0.000s — Start**
```
POST /runs  { graph_id: "G1", version: 3, inputs: { source: "..." } }
→ runs row inserted (status=running)
→ runner: compile graph, invoke with thread_id=run_id
→ load_lots executes, output stored in checkpoint
→ cluster_phases starts, calls request_human(...)
→ queue_items row inserted (status=open, authorized_roles=["approver"])
→ runs.status = awaiting_human
→ HTTP response: 202 { run_id: "R7", queue_item_id: "Q12" }
→ process exits
```

**T+0.030s — process is gone. Nothing running.**

**T+5h 22min — A human decides**
```
POST /queue_items/Q12/decide  { decision: { approved: true } }
→ check authorized_roles match decided_by user ✓
→ decisions row inserted (decided_by=U3, decided_at=now)
→ queue_items.status = answered
→ runner.resume_run(R7, decision)
   → load checkpoint at thread_id=R7
   → invoke(Command(resume={approved: true}))
   → cluster_phases continues — its request_human() returns the decision
   → produces phases
   → write_report executes
   → outputs rows inserted with decision_refs=[D8]
   → runs.status = succeeded, completed_at = now
→ HTTP response: 200 { status: "succeeded" }
```

**End state:** decisions table has D8 with the user + timestamp; outputs reference D8; queue item answered. Anyone reading the report later can trace it to the human approval.

---

## 12. Tests to write

**In short:** Three layers — unit (registry, compiler, schemas), integration (real DB, full lifecycle), end-to-end (process restart between pause and resume).

```
   Unit             Integration          End-to-end
   ────             ───────────          ──────────
   fast             real DB              real DB + process boundary
   no DB            one process          two processes
   sub-second       seconds              seconds
```

| Layer | Cover |
|---|---|
| Unit | `@step` decorator, registry lookup, compiler validation (every rule), pydantic schemas |
| Integration | start_run happy path · interrupt + queue write · resume + decision write · pin-to-version (edit graph mid-run, run keeps old version) · authorization (wrong role rejected) |
| End-to-end | Start a run in process A; tear down process A; bring up process B; submit decision; assert completion |

The end-to-end test is the **single most important test in the codebase** — it's the one that proves the durability claim.

---

## 13. What's deliberately not here

**In short:** Phase 1 only. Things that belong in later implementation docs.

- Inbox UI, graph viewer (Phase 2 doc)
- AI authoring loop, validator surfacing (Phase 3 doc)
- Lineage graph and stale propagation (Phase 4 doc)
- Policy registry, scheduled cycles (Phase 5 doc)
- Cost tracking, budget caps (cross-cutting, scheduled when budget pain shows up)
- Multi-tenant identity, SSO (deferred indefinitely)
