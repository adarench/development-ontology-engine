"""Persistence for run lifecycle.

A `Run` is pinned to a `(graph_id, graph_version)` pair at creation. Versions
are immutable; the FK lock is at the DB level so even raw SQL can't drift a
run onto a different version mid-flight.

Lifecycle:

    running ──► awaiting_human ──► running ──► succeeded
                                            └► failed
                                            └► cancelled

`awaiting_human` is M6 territory; M5 only deals with `running`, `succeeded`,
`failed`. The status set is fixed by `RUN_STATUSES` in `models.py`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.engine.models import Run


async def create_run(
    session: AsyncSession,
    *,
    graph_id: uuid.UUID,
    graph_version: int,
    inputs: Optional[Dict[str, Any]] = None,
    started_by: int,
) -> Run:
    """Insert a run row pinned to a specific graph version. Status starts as
    `running`. Raises an integrity error if the (graph_id, version) pair
    doesn't exist in `graph_versions`."""
    run = Run(
        graph_id=graph_id,
        graph_version=graph_version,
        inputs=inputs or {},
        started_by=started_by,
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> Optional[Run]:
    return await session.get(Run, run_id)


async def list_runs(
    session: AsyncSession,
    *,
    graph_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Run]:
    """Most recent first. Optional filters."""
    stmt = select(Run).order_by(Run.started_at.desc()).limit(limit)
    if graph_id is not None:
        stmt = stmt.where(Run.graph_id == graph_id)
    if status is not None:
        stmt = stmt.where(Run.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_running(session: AsyncSession, run_id: uuid.UUID) -> None:
    """Transition back to `running` (used on resume)."""
    run = await session.get(Run, run_id)
    if run is None:
        raise KeyError(f"run {run_id} not found")
    run.status = "running"
    run.error = None


async def mark_awaiting_human(
    session: AsyncSession, run_id: uuid.UUID
) -> None:
    """Used by M6 when an interrupt fires."""
    run = await session.get(Run, run_id)
    if run is None:
        raise KeyError(f"run {run_id} not found")
    run.status = "awaiting_human"


async def mark_succeeded(session: AsyncSession, run_id: uuid.UUID) -> None:
    run = await session.get(Run, run_id)
    if run is None:
        raise KeyError(f"run {run_id} not found")
    run.status = "succeeded"
    run.completed_at = datetime.now(timezone.utc)
    run.error = None


async def mark_failed(
    session: AsyncSession, run_id: uuid.UUID, *, error: str
) -> None:
    run = await session.get(Run, run_id)
    if run is None:
        raise KeyError(f"run {run_id} not found")
    run.status = "failed"
    run.completed_at = datetime.now(timezone.utc)
    run.error = error


async def mark_cancelled(session: AsyncSession, run_id: uuid.UUID) -> None:
    run = await session.get(Run, run_id)
    if run is None:
        raise KeyError(f"run {run_id} not found")
    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
