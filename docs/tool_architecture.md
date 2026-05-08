# Tool Architecture

## TLDR

A **Tool** is a named pipeline of **Steps**. Steps are either deterministic (guaranteed output) or probabilistic (estimated output with a confidence score). The Tool's overall confidence is the weakest probabilistic step in its chain. Every data point traces back to its source file and row.

There are three tiers of tools. **System tools** (always available) resolve entities and route requests. **User-built tools** handle repeated tasks — assembled from built-in Steps and custom Python. When no tool exists for a request, the **Tool Builder Skill** constructs one on demand: it prefers deterministic steps, surfaces every assumption to the user before running, and offers to save the result as a reusable tool.

The agent receives structured output — facts, confidence, and sources — and its job is explanation, not discovery.

---

## Overview

```
User request
      ↓
Tier 1 — System Tools        always available, pre-built into the engine
      ↓
Tier 2 — User-Built Tools    assembled from Steps, built for known repeated tasks
      ↓
Tier 3 — Tool Builder Skill  constructs a Tool on demand for novel requests
```

---

## Step types

Every Step in a Tool is either **deterministic** or **probabilistic**.

### DeterministicToolStep

Output is fully determined by input. Same input always produces the same output. No estimation, no inference, no ML. Examples: loading a file, resolving an entity ID from a crosswalk, computing a cost sum from GL rows, joining two tables on a known key.

These steps do not affect overall result confidence. They either succeed or fail.

### ProbabilisticToolStep

Output involves estimation, heuristics, or model inference. Every `ProbabilisticToolStep` must declare:

```python
probabilistic_type: "heuristic" | "llm" | "ml"
confidence_level: float          # 0.0 – 1.0, class-level default
method_description: str          # one-line plain-English description
result_caveats: list[str]        # standard warnings that always apply
```

At runtime the step also computes **instance-level confidence** — a score derived from the actual data it processed, not just the class default. This reflects the specific inputs that step saw.

```python
def assess(self, input_data, output_data) -> StepConfidence:
    ...
```

`StepConfidence` carries:

| field | type | meaning |
|---|---|---|
| `score` | float 0–1 | estimated probability this step's output is correct |
| `basis` | str | one-line explanation of how the score was derived |
| `input_coverage` | float 0–1 | what fraction of expected input was present |
| `signal_clarity` | `"clear" \| "ambiguous" \| "conflicted"` | whether the data pointed to one answer or several |
| `caveats` | list[str] | specific warnings for this instance (beyond class defaults) |

**Examples of instance-level self-assessment:**

*Phase clustering step* — confidence is high when lot number gaps between ranges are clean and wide. Confidence drops when ranges are densely packed, or when the same lot number appears in multiple ranges.

*Cost rollup step* — confidence is high when GL coverage is complete. Confidence drops in proportion to uncovered lots, and further when uncovered lots are large or in active stages.

*Entity resolution step* (fuzzy matching) — confidence reflects match score from the crosswalk lookup. Exact matches are high; fuzzy matches carry the match score directly.

---

## Tool-level accuracy aggregation

After all steps run, the Tool computes overall result confidence using the **weakest link** rule: overall confidence is the minimum confidence across all probabilistic steps that ran.

```
step 1  deterministic         —
step 2  probabilistic  0.92   high
step 3  deterministic         —
step 4  probabilistic  0.61   medium
step 5  deterministic         —

overall confidence: 0.61  (medium)
driven by: step 4
```

The `ProvenanceSummary` renders this in the output:

```markdown
## Data Provenance

**Certain (deterministic):** EntityResolutionStep, GLNormalizeStep, CostRollupStep

**Estimated (probabilistic):**
- ~ **PhaseClusterStep**: gap-based lot number clustering (confidence: 92%, type: heuristic)
  - ⚠ Phase IDs are estimated until a real plat→lot reference table is available
- ~ **CoverageAssessmentStep**: GL row coverage by lot (confidence: 61%, type: heuristic)
  - ⚠ 14 active lots have no GL transactions — costs shown as unknown, not $0
  - ⚠ DR rows deduped 2.16× before aggregation
```

---

## Source tracing

Every step can emit **source references** — structured pointers to the exact data used to produce its output.

```python
@dataclass
class SourceReference:
    file_path: str
    description: str
    rows: list[int] | None          # for CSV/parquet
    search_term: str | None         # for text/markdown
    line_range: tuple[int,int] | None
```

For structured files (CSV, parquet, JSON), the reference includes the file path and the row filter. For text and markdown files, the reference includes the file path and a line range — in a rendered environment this becomes a deep link to the highlighted passage.

```markdown
**Sources used:**
- `data/staged/canonical_lot.parquet` — rows where project=Harmony, phase=B1 (47 rows)
- `docs/ontology_v0.md#L54` — "Harmony lots share lot numbers across phases"
- `pipelines/config.py#L92` — lot state waterfall definition
```

Source references connect every output value back to the exact rows and passages that produced it. The system is not just confident — it is traceable.

---

## Tier 1 — System Tools

These tools are always available. The agent uses them before doing anything else.

### EntitySearchTool

Reads the entity config and identifies which entities the user's request refers to. Returns resolved canonical entity IDs and their position in the hierarchy.

```
request: "what is the cost to date on Harmony Phase 2?"

matched:
  - entity: Lot
    parent_chain: [Project("Harmony"), Phase("B1")]
    canonical_ids: [lot_a1b2, lot_c3d4, ...]
    matched_from: "Harmony Phase 2"
    confidence: high
```

### ToolRouterTool

Looks at the resolved entities and the user's intent, then identifies which registered User-Built Tool(s) best cover the request. If a strong match exists, routes directly. If no match or a weak match, hands off to the Tool Builder Skill.

### GeneralSearchTool

Broad search across state files, agent chunks, and indexed documents when no structured tool matches. Returns ranked results with source references. Used as a fallback or as a step inside a user-built tool.

---

## Tier 2 — User-Built Tools

Tools assembled by the user for tasks they run repeatedly. A user declares a Tool as a sequence of Steps — some built-in, some custom Python.

### Built-in Steps

| Step | Type | Description |
|---|---|---|
| `ArchitectureContextStep` | deterministic | loads entity config, makes structure available to all downstream steps |
| `EntityResolutionStep` | deterministic | resolves raw source values to canonical IDs via crosswalk tables |
| `DataRetrievalStep` | deterministic | fetches data from a source using a configured Connector |
| `GLAggregateStep` | deterministic | joins and aggregates GL transactions at a specified grain |
| `CostRollupStep` | deterministic | sums cost components defined in client config |
| `CoverageAssessmentStep` | probabilistic (heuristic) | measures what fraction of expected entities have data; flags gaps |
| `RAGStep` | probabilistic (llm) | embedding search over indexed documents; returns ranked passages with source references |
| `IntentClassifierStep` | probabilistic (heuristic or llm) | classifies question intent to guide downstream step selection |
| `CalculationStep` | deterministic | math operations (variance, completion %, weighted average) |
| `ValidationStep` | deterministic | checks output against declared rules; emits warnings, not errors |

### Custom Python Steps

A user can write any Step in Python by subclassing `DeterministicToolStep` or `ProbabilisticToolStep` and implementing `run()`. Custom steps plug into the same provenance and source-tracing infrastructure as built-in steps.

```python
class MyCustomStep(DeterministicToolStep):
    def run(self, data):
        # client-specific logic here
        return transformed_data
```

### Declaring a Tool

A Tool is declared as an ordered list of steps with their configuration:

```python
CostByPhaseTool = Tool(steps=[
    ArchitectureContextStep(config="flagship/architecture.json"),
    DataRetrievalStep(connector=GLConnector(...)),
    EntityResolutionStep(connector=CrosswalkConnector(...)),
    CostRollupStep(components=config.COST_TO_DATE_COMPONENTS),
    CoverageAssessmentStep(),
])
```

### Storage and runtime hydration

Every Tool and every Step can be stored in the database and reconstructed at runtime. There are two storage formats depending on the step type.

**Built-in steps** are stored as JSON — a type name and a config object. The engine looks up the class by name in the step registry and instantiates it with the config.

**Custom Python steps** are stored as a code string alongside the class name and base type. The engine executes the code string in a sandboxed namespace at load time and retrieves the class.

#### Stored format

```json
{
  "name": "CostByPhaseTool",
  "description": "Cost to date by phase for a given project",
  "steps": [
    {
      "type": "ArchitectureContextStep",
      "config": {
        "config_path": "flagship/architecture.json"
      }
    },
    {
      "type": "DataRetrievalStep",
      "config": {
        "connector": "GLConnector",
        "connector_config": { "path": "data/staged/staged_gl_transactions_v2.parquet" }
      }
    },
    {
      "type": "CostRollupStep",
      "config": {
        "components": ["Permits and Fees", "Direct Construction - Lot", "Shared Cost Alloc."]
      }
    },
    {
      "type": "custom",
      "class_name": "HarmonyJoinStep",
      "step_base": "DeterministicToolStep",
      "code": "class HarmonyJoinStep(DeterministicToolStep):\n    def run(self, data):\n        ..."
    },
    {
      "type": "CoverageAssessmentStep",
      "config": {}
    }
  ]
}
```

#### Runtime hydration

A `ToolLoader` reconstructs a Tool from its stored dict. For built-in steps it looks up the class in the `StepRegistry`. For custom steps it executes the code string and retrieves the declared class.

```python
class ToolLoader:
    def from_dict(self, tool_dict: dict) -> Tool:
        steps = [self._hydrate_step(s) for s in tool_dict["steps"]]
        return Tool(name=tool_dict["name"], steps=steps)

    def _hydrate_step(self, step_dict: dict) -> ToolStep:
        if step_dict["type"] == "custom":
            return self._exec_custom(step_dict)
        cls = StepRegistry.get(step_dict["type"])
        return cls(**step_dict.get("config", {}))

    def _exec_custom(self, step_dict: dict) -> ToolStep:
        namespace = {"DeterministicToolStep": DeterministicToolStep,
                     "ProbabilisticToolStep": ProbabilisticToolStep}
        exec(step_dict["code"], namespace)
        return namespace[step_dict["class_name"]]()
```

#### StepRegistry

The `StepRegistry` maps type name strings to classes. Built-in steps are registered automatically. User-defined steps can be registered by name, making them reusable across multiple tool definitions without repeating the code string.

```python
StepRegistry = {
    "ArchitectureContextStep": ArchitectureContextStep,
    "EntityResolutionStep":    EntityResolutionStep,
    "DataRetrievalStep":       DataRetrievalStep,
    "GLAggregateStep":         GLAggregateStep,
    "CostRollupStep":          CostRollupStep,
    "CoverageAssessmentStep":  CoverageAssessmentStep,
    "RAGStep":                 RAGStep,
    "IntentClassifierStep":    IntentClassifierStep,
    "CalculationStep":         CalculationStep,
    "ValidationStep":          ValidationStep,
}
```

This format is also what the Tool Builder Skill produces when it saves a constructed Tool — the output of the Builder is a JSON dict in this schema, ready to be written to the database and loaded on the next request.

---

## Tier 3 — Tool Builder Skill

When no User-Built Tool covers the request, the Tool Builder Skill constructs one on demand.

This is not a Tool — it is a Skill (an LLM-driven meta-process). Its output is a Tool that runs and returns a result, not a direct answer to the user's question.

### What it does

1. **Parses the request** — identifies intent, required entities, required metrics
2. **Designs a step sequence** — selects the minimum set of Steps needed to answer the question
3. **Prefers deterministic** — adds probabilistic steps only where deterministic steps cannot produce the answer
4. **Verifies each step** — before moving to the next step, checks that the previous step's output is valid and sufficient
5. **Flags assumptions** — every non-obvious decision is recorded as an explicit assumption
6. **Runs the constructed Tool** — executes it and returns the result alongside a full account of what was built and why

### Preference for deterministic steps

The Tool Builder always attempts to answer a question with deterministic steps first. It adds a probabilistic step only when it can state a specific reason why determinism is not possible. Each probabilistic step is presented to the user for acknowledgment before the Tool runs:

```
I need to estimate Phase IDs for Harmony because GL does not carry phase grain.
I will use PhaseClusterStep (gap-based heuristic, ~85% confidence).

Assumption: lot number gaps ≥ 10 indicate a phase boundary.
This may be wrong for phases with irregular lot numbering.

Proceed? [yes / adjust / skip this step]
```

### Output to the user

```markdown
## Tool built for: "cost to date on Harmony Phase 2"

Steps run:
1. ArchitectureContextStep          deterministic  — loaded entity config
2. EntityResolutionStep             deterministic  — resolved "Harmony Phase 2" → 47 lot IDs
3. DataRetrievalStep (GL)           deterministic  — fetched 1,203 GL rows for those lots
4. CostRollupStep                   deterministic  — summed Permits, Direct Construction, Shared Alloc.
5. CoverageAssessmentStep           probabilistic  — checked GL coverage across 47 lots

Result: $4,812,300 (medium confidence)

Assumptions made:
- Phase "B1" matched to "Phase 2" in request via entity config description match
- 3 lots have no GL rows — shown as unknown, not $0

Confidence: 0.74  (driven by CoverageAssessmentStep — 3 of 47 lots uncovered)

Sources:
- data/staged/canonical_lot.parquet — rows where project=Harmony, phase=B1
- data/staged/staged_gl_transactions_v2.parquet — 1,203 rows
- docs/ontology_v0.md#L54 — "Harmony lots share lot numbers across phases"
```

### Saving a built Tool

If the user runs the same request more than once, the Tool Builder offers to save the constructed Tool as a User-Built Tool (Tier 2). The user can review the step sequence, adjust configuration, and register it. On future requests, the ToolRouterTool will match it directly without invoking the Tool Builder again.

---

## Full flow

```
User request
      │
      ├─ EntitySearchTool              resolve entities in request
      ├─ ToolRouterTool                match to existing User-Built Tool?
      │         │
      │         ├─ match found ────────────────────────────────────────────┐
      │         │                                                           │
      │         └─ no match → Tool Builder Skill                           │
      │                           │                                        │
      │                           ├─ parse intent + entities               │
      │                           ├─ design step sequence                  │
      │                           ├─ prefer deterministic                  │
      │                           ├─ surface probabilistic assumptions     │
      │                           ├─ verify each step before proceeding    │
      │                           └─ run constructed Tool ───────────────┐ │
      │                                                                   │ │
      └───────────────────────────────────────────────────────────────── ┘ │
                                                                            │
                    Tool result + ProvenanceSummary + SourceReferences  ◄───┘
                                        │
                                        ▼
                         Agent synthesizes user-facing answer
```

Inside a running Tool, the step sequence follows this pattern:

```
ArchitectureContextStep    deterministic  — loads entity config
IntentClassifierStep       probabilistic  — classifies question type
EntityContextStep          deterministic  — resolves entities to canonical IDs
DataRetrievalStep(s)       deterministic  — fetches relevant data
CalculationStep            deterministic  — math (rollups, variance, pct)
[custom Python step]       either         — client-specific logic
CoverageAssessmentStep     probabilistic  — flags gaps and unknown values
```

---

## Design principles

**The model explains, it does not discover.** By the time the agent sees the output, every entity has been resolved, every join has been applied, every known gap has been flagged. The model has nothing to guess.

**Uncertainty is explicit, not hidden.** A low-confidence step does not silently produce an answer that looks high-confidence. Confidence scores, their basis, and their caveats propagate forward through the Tool and appear in the final output.

**Every claim is traceable.** Source references connect every output value back to the exact rows and passages that produced it.

**Config drives structure, steps drive logic.** The `ArchitectureContextStep` loads the entity config and makes it available to all downstream steps. Steps do not hardcode client-specific assumptions — they read them from the config object they receive.

**Deterministic by default.** Probabilistic steps require a stated reason. The Tool Builder will not add estimation where a lookup or join would do.
