"""Pydantic schemas for graph definitions.

A `GraphDef` is the canonical JSON shape stored in `graph_versions.definition`.
This module enforces *structural* validity only:

  - nodes have unique IDs
  - each edge references declared nodes
  - port refs parse cleanly ("node_id.port_name")

Registry-aware validation — does the step exist? do port types line up? —
lives in `core/engine/validator.py` (M3.4).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


_NODE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PORT_REF_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$")


class PortRef(BaseModel):
    """A reference to a port on a node: `node_id.port_name`."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    port: str

    @classmethod
    def parse(cls, raw: str) -> "PortRef":
        m = _PORT_REF_PATTERN.match(raw)
        if not m:
            raise ValueError(
                f"Invalid port reference {raw!r}: expected 'node_id.port_name'"
            )
        return cls(node_id=m.group(1), port=m.group(2))

    def __str__(self) -> str:
        return f"{self.node_id}.{self.port}"


class NodeDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    step_name: str
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("node_id")
    @classmethod
    def _validate_node_id(cls, v: str) -> str:
        if not _NODE_ID_PATTERN.match(v):
            raise ValueError(
                f"Invalid node_id {v!r}: must match {_NODE_ID_PATTERN.pattern}"
            )
        return v

    @field_validator("step_name")
    @classmethod
    def _validate_step_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("step_name cannot be empty")
        return v


class EdgeDef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # `from` is a Python keyword; the JSON wire form uses "from", the Python attr is `from_`.
    from_: PortRef = Field(alias="from", serialization_alias="from")
    to: PortRef
    condition: Optional[str] = None

    @field_validator("from_", "to", mode="before")
    @classmethod
    def _coerce_port_ref(cls, v: Any) -> Any:
        if isinstance(v, str):
            return PortRef.parse(v)
        return v

    @field_serializer("from_", "to")
    def _serialize_port_ref(self, ref: PortRef) -> str:
        return str(ref)


class GraphDef(BaseModel):
    """The full graph definition stored as JSONB in `graph_versions.definition`."""

    model_config = ConfigDict(extra="forbid")

    nodes: List[NodeDef]
    edges: List[EdgeDef]

    @model_validator(mode="after")
    def _validate_structure(self) -> "GraphDef":
        if not self.nodes:
            raise ValueError("Graph must declare at least one node")

        # Unique node IDs.
        seen: Dict[str, int] = {}
        for i, node in enumerate(self.nodes):
            if node.node_id in seen:
                raise ValueError(
                    f"Duplicate node_id {node.node_id!r} "
                    f"(nodes[{seen[node.node_id]}] and nodes[{i}])"
                )
            seen[node.node_id] = i

        # Edges must reference declared nodes.
        node_ids = set(seen.keys())
        for i, edge in enumerate(self.edges):
            if edge.from_.node_id not in node_ids:
                raise ValueError(
                    f"edges[{i}].from references unknown node "
                    f"{edge.from_.node_id!r}"
                )
            if edge.to.node_id not in node_ids:
                raise ValueError(
                    f"edges[{i}].to references unknown node "
                    f"{edge.to.node_id!r}"
                )
        return self

    def node_by_id(self, node_id: str) -> NodeDef:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        raise KeyError(node_id)
