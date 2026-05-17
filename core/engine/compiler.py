"""Compile a `GraphDef` into an executable LangGraph.

The compiler is a pure function: given a validated `GraphDef` and the live
step registry, it returns a compiled `langgraph` object that callers can
`invoke` / `ainvoke` / `astream`.

Design
══════

State carries port values across the run. We use a single TypedDict field
`ports` that holds a flat dict keyed by `"<node_id>.<port>"`:

    {
        "n1.lots":   [...],
        "n2.phases": {...},
    }

A custom dict-merge reducer lets each node return only its own outputs and
have them folded into the running state.

Each wrapper:

    1. reads its declared inputs from `ports` (via the edge map)
    2. falls back to `node.config` for unconnected inputs
    3. calls the registered step (async or sync)
    4. writes its outputs back as `{"<node_id>.<port>": value, ...}`

Entry / exit
════════════
Nodes with no incoming edges connect from `START`. Nodes with no outgoing
edges connect to `END`. An isolated node is both.

What the compiler does NOT do
══════════════════════════════
- It does not enforce that every required input has a source. That belongs
  in the validator (future); for now an unbound input surfaces as a Python
  `TypeError` at invoke time.
- It does not own the checkpointer. The runner (M5) attaches one.
- It does not handle interrupts. Steps that pause (M6) call into engine
  helpers that emit LangGraph interrupts; the compiler is unaware.
"""
from __future__ import annotations

import asyncio
from typing import Annotated, Any, Callable, Dict, Optional, Tuple, TypedDict

from langgraph.graph import END, START, StateGraph

from core.engine import registry as step_registry
from core.engine.registry import StepSpec
from core.engine.schemas import GraphDef, NodeDef
from core.engine.validator import validate


# ─── State plumbing ─────────────────────────────────────────────────────────


def _merge_ports(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow dict merge — later writes win for the same key."""
    merged = dict(a)
    merged.update(b)
    return merged


class GraphState(TypedDict, total=False):
    """LangGraph state container.

    A single field, `ports`, holds the flat port-value map. Each node returns
    `{"ports": {"node.port": value}}` and the reducer folds it into the
    accumulating dict.
    """

    ports: Annotated[Dict[str, Any], _merge_ports]


# ─── Errors ─────────────────────────────────────────────────────────────────


class CompilationError(Exception):
    """Raised when a graph passes structural / registry validation but cannot
    be compiled (e.g. conflicting edges targeting the same input port)."""


# ─── Public entry point ─────────────────────────────────────────────────────


def compile_graph(
    graph_def: GraphDef,
    *,
    registry_lookup: Optional[Callable[[str], StepSpec]] = None,
    checkpointer: Optional[Any] = None,
):
    """Translate a `GraphDef` into a compiled LangGraph.

    Args:
        graph_def: The graph to compile.
        registry_lookup: Resolves step_name → StepSpec. Injected for tests;
            defaults to `core.engine.registry.get`.
        checkpointer: Optional LangGraph checkpointer (e.g. `AsyncPostgresSaver`).
            When provided, every step persists state to the checkpointer's
            backing store; pause / resume becomes durable across process
            restarts. Not passed → no checkpointing (compile-only fast path
            for unit tests).

    Returns:
        A compiled LangGraph (callable via `.invoke` / `.ainvoke`).

    Raises:
        GraphValidationError: structural or registry-aware validation failed.
        CompilationError: graph topology cannot be lowered (e.g. duplicate
            edges to the same input port).
    """
    lookup = registry_lookup or step_registry.get
    validate(graph_def)

    edge_map, in_count, out_count = _build_edge_map(graph_def)

    sg = StateGraph(GraphState)

    for node in graph_def.nodes:
        spec = lookup(node.step_name)
        sg.add_node(node.node_id, _make_wrapper(node, spec, edge_map))

    for edge in graph_def.edges:
        sg.add_edge(edge.from_.node_id, edge.to.node_id)

    for node_id, count in in_count.items():
        if count == 0:
            sg.add_edge(START, node_id)
    for node_id, count in out_count.items():
        if count == 0:
            sg.add_edge(node_id, END)

    return sg.compile(checkpointer=checkpointer) if checkpointer else sg.compile()


# ─── Internals ──────────────────────────────────────────────────────────────


def _build_edge_map(
    graph_def: GraphDef,
) -> Tuple[Dict[Tuple[str, str], str], Dict[str, int], Dict[str, int]]:
    """Index edges for fast lookup at wrapper-build time.

    Returns:
        edge_map: (target_node_id, input_port) -> "source_node_id.port"
        in_count: node_id -> incoming edge count
        out_count: node_id -> outgoing edge count
    """
    edge_map: Dict[Tuple[str, str], str] = {}
    in_count: Dict[str, int] = {n.node_id: 0 for n in graph_def.nodes}
    out_count: Dict[str, int] = {n.node_id: 0 for n in graph_def.nodes}

    for i, edge in enumerate(graph_def.edges):
        key = (edge.to.node_id, edge.to.port)
        if key in edge_map:
            raise CompilationError(
                f"edges[{i}]: multiple edges target "
                f"{key[0]}.{key[1]} (existing source {edge_map[key]!r}, "
                f"new source {edge.from_.node_id}.{edge.from_.port!r})"
            )
        edge_map[key] = f"{edge.from_.node_id}.{edge.from_.port}"
        in_count[edge.to.node_id] += 1
        out_count[edge.from_.node_id] += 1

    return edge_map, in_count, out_count


def _make_wrapper(
    node: NodeDef,
    spec: StepSpec,
    edge_map: Dict[Tuple[str, str], str],
) -> Callable[[Dict[str, Any]], Any]:
    """Build the LangGraph-node callable for one graph node.

    The wrapper closes over `node`, `spec`, and `edge_map`. It's always async
    so that LangGraph's async machinery is uniform; sync step functions are
    awaited via `run_in_executor` semantics handled by the caller layer.
    """
    is_async_step = asyncio.iscoroutinefunction(spec.fn)
    node_id = node.node_id
    config = dict(node.config or {})

    async def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
        ports = state.get("ports", {}) if state else {}
        kwargs: Dict[str, Any] = {}

        for input_port in spec.inputs:
            source_key = edge_map.get((node_id, input_port))
            if source_key is not None:
                if source_key not in ports:
                    raise CompilationError(
                        f"node {node_id!r}: input {input_port!r} expects upstream "
                        f"value at {source_key!r} but it has not been produced"
                    )
                kwargs[input_port] = ports[source_key]
            elif input_port in config:
                kwargs[input_port] = config[input_port]
            # else: unbound — Python raises TypeError if the step requires it

        if is_async_step:
            result = await spec.fn(**kwargs)
        else:
            result = spec.fn(**kwargs)

        if result is None:
            return {"ports": {}}
        if not isinstance(result, dict):
            raise CompilationError(
                f"node {node_id!r}: step {spec.name!r} returned "
                f"{type(result).__name__}; expected dict of "
                f"{{port_name: value}}"
            )
        return {"ports": {f"{node_id}.{p}": v for p, v in result.items()}}

    wrapper.__name__ = f"node_{node_id}"  # nicer LangGraph stack traces
    return wrapper
