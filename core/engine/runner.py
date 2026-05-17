"""Run lifecycle — start_run, resume_run, checkpointer integration.

A run is one execution of one immutable graph version. State persists to
Postgres via LangGraph's checkpointer at every step boundary; if the process
dies between steps, a fresh process loads the same `thread_id` (= run UUID)
and continues.

Lifecycle (M5):

    POST /runs ───► create run row (running)
                ───► compile graph version
                ───► invoke with thread_id = run.id
                ───► all steps complete  ──► mark_succeeded
                ───► step raises          ──► mark_failed

Lifecycle additions in M6:

                ───► step calls request_human()
                ───► LangGraph interrupt fires
                ───► mark_awaiting_human; process can exit
                ───► resume_run(run_id, decision) reattaches the checkpointer
                     and replays from the interrupt point

This module does not depend on FastAPI. The HTTP layer (later) calls into
`start_run` and `resume_run` directly.
"""
from __future__ import annotations

import os
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from core.engine.compiler import compile_graph
from core.engine.db import session_scope
from core.engine.schemas import GraphDef
from core.engine.store import graphs as graphs_store
from core.engine.store import runs as runs_store


class RunnerError(Exception):
    """Raised when a run cannot start (missing version, etc.). Run-step
    failures are not RunnerError — they're captured on the run row and the
    original exception is re-raised."""


# ─── Checkpointer plumbing ─────────────────────────────────────────────────


def _checkpointer_uri() -> str:
    """Translate the async runtime DSN into a psycopg-friendly URI that the
    LangGraph Postgres checkpointer accepts. asyncpg → plain postgresql."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RunnerError("DATABASE_URL is not set; cannot create checkpointer.")
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )


@asynccontextmanager
async def _make_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """Yield a configured AsyncPostgresSaver. `setup()` is idempotent and
    cheap; we call it on each enter so cold environments self-provision the
    checkpointer's tables."""
    uri = _checkpointer_uri()
    async with AsyncPostgresSaver.from_conn_string(uri) as saver:
        await saver.setup()
        yield saver


async def setup_checkpointer_schema() -> None:
    """Provision the checkpointer's tables. Safe to call at engine startup.
    Idempotent. Most callers don't need this — `start_run` and `resume_run`
    both invoke `setup()` themselves before use."""
    async with _make_checkpointer():
        pass


# ─── Public API ─────────────────────────────────────────────────────────────


async def start_run(
    *,
    graph_id: uuid.UUID,
    graph_version: int,
    inputs: Optional[Dict[str, Any]] = None,
    started_by: int,
) -> uuid.UUID:
    """Create a run row and execute the graph to completion (or interrupt).

    Returns the run id. The run row is the source of truth for status; the
    caller can poll `runs.get_run(run_id)` to see whether it succeeded,
    failed, or is awaiting a human.
    """
    inputs = inputs or {}

    # 1. Materialize the graph version and create the run row in one tx, then
    # commit so the run is visible to other processes before invocation
    # begins.
    async with session_scope() as session:
        gv = await graphs_store.get_version(
            session, graph_id, graph_version
        )
        if gv is None:
            raise RunnerError(
                f"graph_version not found: graph={graph_id} v={graph_version}"
            )
        graph_def = GraphDef.model_validate(gv.definition)

        run = await runs_store.create_run(
            session,
            graph_id=graph_id,
            graph_version=graph_version,
            inputs=inputs,
            started_by=started_by,
        )
        run_id = run.id

    # 2. Invoke with the checkpointer attached. Each step boundary persists
    # state under thread_id=run_id.
    try:
        async with _make_checkpointer() as saver:
            compiled = compile_graph(graph_def, checkpointer=saver)
            config = {"configurable": {"thread_id": str(run_id)}}
            await compiled.ainvoke({"ports": inputs}, config=config)
    except Exception:
        async with session_scope() as session:
            await runs_store.mark_failed(
                session, run_id, error=traceback.format_exc()
            )
        raise

    # 3. Success.
    async with session_scope() as session:
        await runs_store.mark_succeeded(session, run_id)
    return run_id


async def resume_run(
    run_id: uuid.UUID,
    *,
    command: Any = None,
) -> str:
    """Resume a paused run. `command` is forwarded to LangGraph as the input
    to the interrupted step; for a `Type 1` (inline approval) interrupt
    introduced in M6 this is typically a `Command(resume={...})`.

    For M5 (no interrupts yet), this is a no-op shaped like the M6 contract
    so callers can be written once.

    Returns the final run status string.
    """
    async with session_scope() as session:
        run = await runs_store.get_run(session, run_id)
        if run is None:
            raise RunnerError(f"run {run_id} not found")
        gv = await graphs_store.get_version(
            session, run.graph_id, run.graph_version
        )
        if gv is None:
            raise RunnerError(
                f"graph_version vanished for run {run_id}; "
                f"graph={run.graph_id} v={run.graph_version}"
            )
        graph_def = GraphDef.model_validate(gv.definition)
        await runs_store.mark_running(session, run_id)

    try:
        async with _make_checkpointer() as saver:
            compiled = compile_graph(graph_def, checkpointer=saver)
            config = {"configurable": {"thread_id": str(run_id)}}
            await compiled.ainvoke(command, config=config)
    except Exception:
        async with session_scope() as session:
            await runs_store.mark_failed(
                session, run_id, error=traceback.format_exc()
            )
        raise

    async with session_scope() as session:
        await runs_store.mark_succeeded(session, run_id)
        return "succeeded"
