"""Registry-aware validation for graph definitions.

`GraphDef` (in `schemas.py`) enforces structural validity. This module checks
the graph against the live step registry:

  - every node's `step_name` resolves to a registered step
  - every edge's `from.port` exists in the source step's outputs
  - every edge's `to.port` exists in the target step's inputs
  - port types are compatible (source output type → target input type)

A successful validation returns the same `GraphDef`. Failures raise
`GraphValidationError` with a list of structured issues so an authoring UI
can surface all problems at once instead of one-at-a-time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from core.engine import registry
from core.engine.schemas import EdgeDef, GraphDef, NodeDef


@dataclass(frozen=True)
class ValidationIssue:
    """One problem found during validation.

    `where` identifies the offending location (e.g. "nodes[2]", "edges[0].from").
    `code` is a short tag for programmatic handling; `message` is human-readable.
    """

    where: str
    code: str
    message: str


class GraphValidationError(Exception):
    """Raised when a graph fails registry-aware validation.

    `issues` carries every detected problem, not just the first one.
    """

    def __init__(self, issues: List[ValidationIssue]) -> None:
        self.issues = issues
        details = "\n  - ".join(f"{i.where}: {i.message}" for i in issues)
        super().__init__(f"Graph validation failed ({len(issues)} issue(s)):\n  - {details}")


def _types_compatible(source: type, target: type) -> bool:
    """Is a value declared as `source` assignable to a port declared as `target`?

    Simple V1 rule: identical types, source is a subclass of target, or
    target is `Any`. Pydantic model schema-compat is a future refinement.
    """
    if target is Any:
        return True
    if source is target:
        return True
    try:
        return issubclass(source, target)
    except TypeError:
        return False


def _validate_node_step(
    node: NodeDef, where: str, issues: List[ValidationIssue]
) -> Optional[registry.StepSpec]:
    try:
        return registry.get(node.step_name)
    except KeyError:
        issues.append(
            ValidationIssue(
                where=where,
                code="unknown_step",
                message=f"step {node.step_name!r} is not registered",
            )
        )
        return None


def _validate_edge_ports(
    edge: EdgeDef,
    where: str,
    source_spec: registry.StepSpec,
    target_spec: registry.StepSpec,
    issues: List[ValidationIssue],
) -> None:
    src_port = edge.from_.port
    dst_port = edge.to.port

    src_type = source_spec.outputs.get(src_port)
    if src_type is None:
        issues.append(
            ValidationIssue(
                where=f"{where}.from",
                code="unknown_output_port",
                message=(
                    f"step {source_spec.name!r} has no output port {src_port!r} "
                    f"(declared: {sorted(source_spec.outputs)})"
                ),
            )
        )
        return

    dst_type = target_spec.inputs.get(dst_port)
    if dst_type is None:
        issues.append(
            ValidationIssue(
                where=f"{where}.to",
                code="unknown_input_port",
                message=(
                    f"step {target_spec.name!r} has no input port {dst_port!r} "
                    f"(declared: {sorted(target_spec.inputs)})"
                ),
            )
        )
        return

    if not _types_compatible(src_type, dst_type):
        issues.append(
            ValidationIssue(
                where=where,
                code="type_mismatch",
                message=(
                    f"{source_spec.name}.{src_port} ({src_type.__name__}) is not "
                    f"assignable to {target_spec.name}.{dst_port} "
                    f"({dst_type.__name__})"
                ),
            )
        )


def validate(graph: GraphDef) -> GraphDef:
    """Validate `graph` against the live registry. Returns it on success;
    raises `GraphValidationError` on failure."""
    issues: List[ValidationIssue] = []

    node_specs: dict[str, registry.StepSpec] = {}
    for i, node in enumerate(graph.nodes):
        spec = _validate_node_step(node, f"nodes[{i}]", issues)
        if spec is not None:
            node_specs[node.node_id] = spec

    for i, edge in enumerate(graph.edges):
        where = f"edges[{i}]"
        src_spec = node_specs.get(edge.from_.node_id)
        dst_spec = node_specs.get(edge.to.node_id)
        if src_spec is None or dst_spec is None:
            # Already reported as unknown_step on the node; skip port checks.
            continue
        _validate_edge_ports(edge, where, src_spec, dst_spec, issues)

    if issues:
        raise GraphValidationError(issues)
    return graph
