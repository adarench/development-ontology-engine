# Tool Engine — Build Plan

A working planning doc. Each section opens with a one-line plain-language summary, then the details. Open decisions are marked `> **Decision needed:**`.

---

## 1. What we're building

**In short:** A system where AI proposes multi-step tools, humans review them, and they run with durable pause/resume so a human can answer a question days later without keeping anything alive.

```
   ┌──────────┐  proposes  ┌──────────┐  approves  ┌──────────┐
   │   AI     │ ─────────► │  Human   │ ─────────► │  Tool    │
   │ author   │            │ reviewer │            │  runs    │
   └──────────┘            └──────────┘            └────┬─────┘
                                                        │ pause
                                                        ▼
                                                  ┌──────────┐
                                                  │  Human   │
                                                  │  decides │
                                                  └────┬─────┘
                                                       │ resume (hours/days later)
                                                       ▼
                                                  ┌──────────┐
                                                  │ Outputs  │
                                                  │ + prov.  │
                                                  └──────────┘
```

**Goals**
- AI composes tools from a registry of reviewed step implementations.
- Humans review, approve, edit, or hand-author tools.
- Tools pause for human input; the process exits; a later trigger resumes the run.
- Every human decision is recorded as provenance, attached to the outputs it influenced.
- Tool definitions are **data in the DB**; step implementations are **code in the repo**.

**Non-goals (for now)**
- AI authoring of new step *implementations* (only compositions of existing steps).
- Visual editor as the primary authoring surface (visualization yes, authoring via JSON/DB).
- Scheduled monthly cycles (Type 7) — deferred.
- Sandboxed user-provided code — deferred.

---

## 2. Architecture overview

**In short:** Three layers. Authoring on top, orchestration in the middle, durable substrate underneath.

```
╔══════════════════════════════════════════════════════════════╗
║  AUTHORING & REVIEW                                          ║
║    ┌──────────────┐    ┌──────────────┐                      ║
║    │ AI proposer  │ ─► │  Review UI   │ ─► approved graphs   ║
║    └──────────────┘    └──────────────┘                      ║
╠══════════════════════════════════════════════════════════════╣
║  ORCHESTRATION                                               ║
║    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  ║
║    │  Compiler    │ ─► │   Runner     │ ◄─►│ Checkpointer │  ║
║    │ (DB→graph)   │    │ (LangGraph)  │    │  (Postgres)  │  ║
║    └──────┬───────┘    └──────────────┘    └──────────────┘  ║
║           │                                                  ║
║           └─► reads ─► ┌──────────────┐                      ║
║                        │ Step registry│ (code, in repo)      ║
║                        └──────────────┘                      ║
╠══════════════════════════════════════════════════════════════╣
║  SUBSTRATE                                                   ║
║    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   ║
║    │ Identity │ │  Queue   │ │Provenance│ │ Graph & Run  │   ║
║    │ + Roles  │ │ subsystem│ │   log    │ │    store     │   ║
║    └──────────┘ └──────────┘ └──────────┘ └──────────────┘   ║
╚══════════════════════════════════════════════════════════════╝
```

The **Step registry lives in code** (deliberate, reviewed via PR). Everything else is data in the DB.

---

## 3. Vocabulary

**In short:** A handful of terms, used precisely. A *step* is a piece of code; a *graph* composes steps; a *run* executes a graph; an *interrupt* pauses a run.

```
   Step    ──┐
   Step    ──┼──► Graph ──► Run ──► Interrupt ──► Decision ──► (resume)
   Step    ──┘                                       │
   (code)    (data)  (data)   (event)              (data, provenance)
```

| Term | Plain meaning |
|---|---|
| **Step** | A function with declared inputs, outputs, and effects. Lives in code. |
| **Step registry** | Index of available steps, populated from code at startup. |
| **Graph** | A composition of steps + edges. Stored in DB. |
| **Graph version** | An immutable snapshot of a graph. Edits create new versions. |
| **Run** | One execution of one graph version. |
| **Interrupt** | A pause point that needs a human answer before continuing. |
| **Queue item** | A typed record representing something waiting on a human. |
| **Decision** | Recorded human response to a queue item. Append-only. |
| **Provenance** | The chain of decisions, policies, validations behind an output. |

---

## 4. Step contract

**In short:** A step is a function with a name, typed input ports, typed output ports, and effect tags. The registry knows about it; graphs reference it by name.

```
       ┌─────────────────────────────────────────┐
       │  step: cluster_phases                   │
       │  effects: [probabilistic]               │
       ├─────────────┬───────────────────────────┤
INPUTS │             │            OUTPUTS        │
       │  lots ──►   │   ──► phases              │
       │             │   ──► confidence          │
       └─────────────┴───────────────────────────┘
```

Sketch in code:

```python
@step(
    name="cluster_phases",
    inputs={"lots": LotsTable},
    outputs={"phases": PhaseTable, "confidence": float},
    effects=["probabilistic"],
    description="Gap-based heuristic phase clustering from lot numbers.",
)
def cluster_phases(lots): ...
```

**Effect taxonomy (draft):**

| Effect | Meaning | Drives |
|---|---|---|
| `read` | Reads external data | dry-run safe |
| `write` | Writes external data | dry-run stubs it |
| `cost` | Costs money (LLM, paid API) | budget tracking |
| `nondeterministic` | Result varies on identical input | replay caveats |
| `needs_approval` | Requires human approval before/after | emits interrupt |
| `external_call` | Talks to external service | retry policy |
| `probabilistic` | Inferred / estimated result | confidence labels |

> **Decision needed:** Lock the effect taxonomy. Above is a starting draft.

---

## 5. Graph definition

**In short:** A graph is a JSON document with nodes (each pointing at a step name) and edges (connecting output ports to input ports). Stored as one immutable row per version.

```
Example graph (conceptual):

   ┌─────────────┐         ┌─────────────────┐
   │ load_lots   │──lots──►│ cluster_phases  │──phases─┐
   └─────────────┘         └─────────────────┘         │
                                                       ▼
                                              ┌─────────────────┐
   ┌─────────────┐                            │ compute_costs   │
   │ load_costs  │────────costs──────────────►│                 │──► report
   └─────────────┘                            └─────────────────┘
```

**Storage shape:**

```
graphs
├── id              (uuid)
├── name            (string)
├── latest_version  (int)
└── status          (draft | active | archived)

graph_versions
├── graph_id        (fk → graphs.id)
├── version         (int)
├── created_at      (timestamp)
├── created_by      (fk → users.id)
└── definition      (jsonb)     ◄── { nodes: [...], edges: [...] }
```

**Why one JSONB blob per version, not split tables?** A graph version is read all-at-once and is immutable. Splitting nodes/edges into rows tempts partial updates and complicates versioning. Schema is enforced at write time.

> **Decision needed:** Confirm JSONB blob vs normalized tables. Recommendation: blob.

---

## 6. Run lifecycle

**In short:** A run starts in a process, runs until it hits an interrupt, writes a checkpoint, and the process exits. Later, a new process picks up the checkpoint and continues.

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

**Steps in order:**
1. `POST /runs` → run row created, pinned to a graph version.
2. Runner loads graph, compiles to LangGraph, executes with Postgres checkpointer.
3. Step hits an interrupt → queue item written → state checkpointed → process exits.
4. (No process running. Notifications fire — email / Slack / inbox poll.)
5. Human submits decision via API → handler loads checkpoint → injects input → runs to next interrupt or completion.
6. On completion, outputs are stored with full provenance trail.

**Critical invariant:** runs are pinned to a graph version. Editing creates a new version; in-flight runs keep using the old.

---

## 7. Human involvement mapping

**In short:** Some human touches happen *during* a run (interrupts that pause it). Others happen *outside* any run (queue items that affect future runs). A third group is cross-cutting (identity, access).

**Phase 1 cut of [human_involvement_types.md](human_involvement_types.md):** Only a slice of the 10 types is built in V1; the rest informs the schema or is fully deferred.

| From the doc | Phase 1 status | Notes |
|---|---|---|
| Type 1 (inline approval) | **Built — M6** | This is the V1 exit criterion |
| Type 9 (named owners) | **Built — M1** | Owners registry, even with one user |
| Type 10 (access control) | **Built (minimal) — M1** | Role shape; everyone may be admin |
| Type 2, 5, 6 | **Read-only — design awareness** | Keep interrupt schema generic enough: `payload_type`, `payload_jsonb`, `authorized_roles`, `decision_jsonb` covers all four |
| Type 3, 8 | **Deferred — Phase 2** | Out-of-run queue items |
| Type 4, 7 | **Deferred — Phase 5** | Policies and scheduled cycles |

```
                ┌─────────────────────────────────────────────┐
                │             A SINGLE RUN                    │
   ┌────────┐   │   ┌────┐   ┌────┐   ┌────┐                  │
   │ Type 1 │──►│──►│step│──►│int.│──►│step│──► ...           │
   │ Type 2 │──►│   └────┘   └────┘   └────┘                  │  IN-RUN
   │ Type 5 │──►│                                             │  INTERRUPTS
   │ Type 6 │──►│                                             │
   └────────┘   └─────────────────────────────────────────────┘

   ┌────────┐   ┌─────────────────┐  affects   ┌──────────────┐
   │ Type 3 │──►│ Registry edits  │ ─────────► │ Future runs  │  OUT-OF-RUN
   │ Type 4 │──►│ (rules,policies)│            │ + stale flags│  QUEUE ITEMS
   │ Type 7 │──►│                 │            │              │
   │ Type 8 │──►│                 │            │              │
   └────────┘   └─────────────────┘            └──────────────┘

   ┌────────┐   ┌─────────────────────────────────────────────┐
   │ Type 9 │──►│   Identity + ownership + RBAC               │  CROSS-CUTTING
   │ Type 10│──►│   (referenced by everything above)          │
   └────────┘   └─────────────────────────────────────────────┘
```

**Interrupt payloads (the four in-run types):**

| Type | Payload shape | Side effect when answered |
|---|---|---|
| 1 — inline approval | `{question, default, options}` | record decision |
| 2 — data input | `{field_spec, owner}` | record decision + treat as data source |
| 5 — disambiguation | `{unmatched_value, candidates}` | record decision + **write crosswalk row** |
| 6 — refusal override | `{reason, required_role}` | record decision + **stamp output with caveat** |

> **Decision needed:** How are humans notified in V1? Recommendation: inbox-only (manual poll). Defer email/Slack to later phase.

---

## 8. Phased milestones

**In short:** Six phases. Phase 0 refactors `core/`. Phase 1 builds the foundation (durability + decisions). Each later phase layers on top without changing the substrate.

```
Phase 0     Phase 1     Phase 2          Phase 3         Phase 4         Phase 5
═══════     ═══════     ═══════          ═══════         ═══════         ═══════
core/       Foundation  Full human       AI authoring    Lineage &       Policy &
refactor    (V1)        coverage         loop            auto-regen      schedules
                        + Inbox UI       + Graph diff
                        + Read-only viz                                  Type 4, Type 7
                        Types 2,3,5,6,8
```

### Phase 0 — Refactor `core/`

Goal: replace the legacy `core/` layout (built for the single-pipeline tool model) with the engine-ready structure. **No new behavior** — all 176 existing tests must still pass when Phase 0 lands. See [tool_engine_implementation.md §3](tool_engine_implementation.md#3-repository-layout--full-refactor) for the target tree.

| # | Milestone | Done when |
|---|---|---|
| P0.1 | New folder structure scaffolded | `core/engine/`, `core/steps/{data,transform,ai,output}/`, `core/lib/` exist (mostly empty) |
| P0.2 | `@step` decorator (stub) | Decorator exists in `core/engine/registry.py`; no engine wiring yet — purely a marker |
| P0.3 | Connectors → `steps/data/` | All connector logic moved + rewrapped as `@step`; tests passing |
| P0.4 | Transforms → `steps/transform/` | All deterministic + probabilistic steps moved + rewrapped; tests passing |
| P0.5 | Renderers → `steps/output/` | All renderers moved + rewrapped; tests passing |
| P0.6 | Documentation update | CLAUDE.md and `core/README.md` reflect new canonical paths. Compat shims (`core/connectors/`, `core/renderers/`, top-level `core/steps/*.py`) remain in place; full removal deferred until `core/tools/` and `core/agent/` are refactored in Phase 1+. |

**Phase 0 exit:** the new tree is the only tree. All 176 tests pass. No engine code exists yet, but every existing piece of logic is wrapped as a `@step`-decorated function in the right folder, ready to be referenced from a graph definition.

### Phase 1 — Foundation (V1)

Goal: prove durability + human-decision substrate works end-to-end with one interrupt type. Builds on top of the refactored `core/` from Phase 0.

| # | Milestone | Status | Done when |
|---|---|---|---|
| M1 | Identity & roles | ✅ minimal (folded into M3) | Users table + role registry exist; default `system` user + `admin`/`approver`/`editor` roles seeded. Full role-aware auth deferred. |
| M2 | Step registry (full) | ✅ done (2026-05-17) | `@step` registry is now consumed by the compiler — each registered step is a live target for graph definitions. |
| M3 | Graph storage | ✅ done (2026-05-17) | `graphs` / `graph_versions` tables, Pydantic `GraphDef`, registry-aware validator, async store CRUD, notifier abstraction with `inbox` channel + pluggable interface for email/Slack/push. Docker-compose Postgres + Alembic 0001 migration. |
| M4 | Compiler | ✅ done (2026-05-17) | `compile_graph(GraphDef) → LangGraph`. State is a flat `ports` dict keyed by `"<node_id>.<port>"`; entry/exit detection is automatic; supports sync + async steps, fan-out, fan-in, config-supplied inputs. Conflicting edges (two sources → one input) and bad return shapes raise `CompilationError`. |
| M5 | Run lifecycle | ✅ done — code (2026-05-17), integration verification pending | `runs` table + migration 0002, `runs` store (`create`/`mark_*`/`list`), `runner.start_run` + `runner.resume_run` wired to LangGraph's `AsyncPostgresSaver`. Runs pinned to `(graph_id, version)` at DB level. 11 integration tests written (5 runs_store + 6 runner including a durability test that disposes the engine and re-reads checkpoint state via a fresh saver). Tests skip if Postgres is unreachable; need a live DB to actually exercise. |
| M6 | Queue + Type 1 interrupt | Pending | Hand-built graph with approval node runs end-to-end across process restarts |
| M7 | Provenance log | Pending | Append-only `decisions` table; outputs reference decision IDs |

**Phase 1 exit:** a graph with one approval node can start, pause, the process can fully exit, a decision arrives later, run resumes to completion. All decisions recorded with user + timestamp.

### Phase 2 — Full human coverage + first UI
- Interrupt types 2, 5, 6 with their side effects (crosswalk writes, refusal caveats).
- Out-of-run queue items: Type 3 (signoffs, confidence promotion), Type 8 (feedback ingestion).
- Inbox UI for browsing queue items + submitting decisions.
- Read-only graph visualization (React Flow).

### Phase 3 — AI authoring loop
- AI proposes new graph versions from natural-language requests.
- Validator surfaces issues (type mismatches, unknown steps, missing approvals).
- Diff UI for proposed-vs-current graph version.

### Phase 4 — Lineage & auto-regen
- Output lineage DAG tied to policies, validated rules, decisions.
- Stale-marking propagation when upstreams change.
- Re-run / patch-input replay.

### Phase 5 — Policy & scheduled cycles
- Type 4 policy registry with diff previews for big-money changes.
- Type 7 monthly cycle state machine (preparer / reviewer / approver).

---

## 9. Storage & infra

**In short:** Postgres for everything. JSONB where the shape varies (graph definitions, queue payloads), normalized rows where it doesn't (users, runs, decisions).

```
   users ─────┐
              │ owns / decides
              ▼
   graphs ──► graph_versions ──► runs ──► checkpoints
                                   │
                                   ├──► queue_items ──► decisions
                                   │
                                   └──► outputs ──► provenance refs
```

> **Decision needed:** Postgres vs SQLite.
> - Postgres — recommended. Concurrent runs, JSONB, mature LangGraph checkpointer support.
> - SQLite — fine for solo dev, painful when more than one process touches the system.
> - Setup cost of Postgres is small relative to migration cost later.

> **Decision needed:** Hosting. V1 is local dev only — confirm.

---

## 10. UI

**In short:** No UI in V1 (CLI + API only). Phase 2 adds an inbox view and a read-only graph viewer.

```
   Phase 2 inbox sketch:

   ┌──────────────────────────────────────────────────┐
   │  Your inbox                              3 items │
   ├──────────────────────────────────────────────────┤
   │  ⚠  Override needed — org-wide rollup pre-2017   │
   │     run #421 · 2 hours ago                       │
   ├──────────────────────────────────────────────────┤
   │  ❓  New subdivision — "Mockingbird Ridge"       │
   │     run #420 · 3 hours ago                       │
   ├──────────────────────────────────────────────────┤
   │  ✅  Approve estimate — phase clustering         │
   │     run #419 · 5 hours ago                       │
   └──────────────────────────────────────────────────┘
```

> **Decision needed:** UI stack — recommend Next.js + React Flow. Defer specifics to Phase 2 kickoff.

---

## 11. Open decisions (consolidated)

| # | Topic | Decision | Status |
|---|---|---|---|
| 1 | Effect taxonomy | Use draft list, refine through use | Open |
| 2 | Graph def: JSONB blob vs rows | JSONB blob | **Locked** (2026-05-17) |
| 3 | Notification channels in V1 | Inbox-only **with `Notifier` interface scaffolded so email / Slack / push can plug in later** | **Locked** (2026-05-17) |
| 4 | Substrate database | Postgres via docker-compose | **Locked** (2026-05-17) |
| 5 | Hosting | Local dev only for V1 | **Locked** (2026-05-17) |
| 6 | UI stack | Next.js + React Flow (Phase 2) | Open |

---

## 12. Deferred

**In short:** Things explicitly left for later so V1 stays small.

- Sandboxed execution of AI-authored step bodies — only registry composition for now.
- Cost tracking and budget caps — useful but not Phase 1.
- Scheduled cycles (Type 7) — Phase 5.
- Lineage and auto-regen — Phase 4. (Decisions are *recorded* from Phase 1; consumed later.)
- Multi-tenant identity / SSO — single-team scope assumed.
