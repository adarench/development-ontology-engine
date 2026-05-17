"""Persistence for `graphs` and `graph_versions`.

The store offers a narrow API on purpose:

  - `create_graph` makes a new graph row (no versions yet)
  - `save_version` appends an immutable version after validating the definition
  - `get_version`, `get_latest_version`, `get_graph`, `list_graphs` are pure reads

Version immutability is enforced at the API surface — there is no `update_version`
method. Anyone bypassing this layer with raw SQL is going outside the contract.

All functions take an `AsyncSession` so callers control transaction boundaries.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.engine.models import Graph, GraphVersion
from core.engine.schemas import GraphDef
from core.engine.validator import validate


async def create_graph(
    session: AsyncSession,
    *,
    name: str,
    created_by: int,
    status: str = "draft",
) -> Graph:
    """Create a graph row with no versions yet."""
    graph = Graph(name=name, created_by=created_by, status=status)
    session.add(graph)
    await session.flush()  # populate server defaults (id, created_at)
    await session.refresh(graph)
    return graph


async def save_version(
    session: AsyncSession,
    *,
    graph_id: uuid.UUID,
    definition: GraphDef,
    created_by: int,
) -> GraphVersion:
    """Validate `definition` against the live step registry, then append a new
    immutable version. `graphs.latest_version` is bumped atomically.

    Raises `GraphValidationError` on validation failure (transaction rolls back
    on exception by convention).
    """
    validate(definition)

    # Lock the graph row to serialize concurrent saves on the same graph.
    locked = await session.execute(
        select(Graph).where(Graph.id == graph_id).with_for_update()
    )
    graph = locked.scalar_one_or_none()
    if graph is None:
        raise KeyError(f"graph {graph_id} not found")

    next_version = graph.latest_version + 1
    version_row = GraphVersion(
        graph_id=graph_id,
        version=next_version,
        definition=definition.model_dump(by_alias=True),
        created_by=created_by,
    )
    session.add(version_row)

    await session.execute(
        update(Graph)
        .where(Graph.id == graph_id)
        .values(latest_version=next_version)
    )
    await session.flush()
    await session.refresh(version_row)
    return version_row


async def get_graph(session: AsyncSession, graph_id: uuid.UUID) -> Optional[Graph]:
    return await session.get(Graph, graph_id)


async def list_graphs(session: AsyncSession) -> List[Graph]:
    result = await session.execute(select(Graph).order_by(Graph.created_at))
    return list(result.scalars().all())


async def get_version(
    session: AsyncSession,
    graph_id: uuid.UUID,
    version: int,
) -> Optional[GraphVersion]:
    return await session.get(GraphVersion, (graph_id, version))


async def get_latest_version(
    session: AsyncSession, graph_id: uuid.UUID
) -> Optional[GraphVersion]:
    graph = await get_graph(session, graph_id)
    if graph is None or graph.latest_version == 0:
        return None
    return await get_version(session, graph_id, graph.latest_version)
