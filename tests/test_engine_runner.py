"""Integration tests for the runner — start_run + durability.

These tests do NOT use the engine_session fixture's rollback because the runner
opens its own sessions via session_scope(). Each test uses unique graph names
so there's no state pollution between tests.

Skipped if Postgres isn't reachable.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from core.engine import registry
from core.engine.db import dispose_engine, session_scope
from core.engine.schemas import GraphDef
from core.engine.store import graphs as graphs_store
from core.engine.store import runs as runs_store

from tests.conftest_engine import requires_postgres  # noqa: F401


@pytest.fixture(autouse=True)
def _fresh_registry():
    registry.clear()
    yield
    registry.clear()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_after_each_test():
    """`core.engine.db` caches a module-level async engine. pytest-asyncio
    rotates event loops per test, so the cached engine ends up bound to a
    closed loop. Dispose it after every test for clean isolation."""
    yield
    await dispose_engine()


def _register_simple_pipeline():
    """Three sync steps: emit → double → record. Used by most tests."""

    @registry.step(name="emit_seed", inputs={}, outputs={"v": int})
    def emit_seed():
        return {"v": 7}

    @registry.step(name="double_val", inputs={"v": int}, outputs={"v": int})
    def double_val(v):
        return {"v": v * 2}

    @registry.step(name="record_val", inputs={"v": int}, outputs={"final": int})
    def record_val(v):
        return {"final": v}


def _three_node_graph() -> GraphDef:
    return GraphDef.model_validate(
        {
            "nodes": [
                {"node_id": "a", "step_name": "emit_seed"},
                {"node_id": "b", "step_name": "double_val"},
                {"node_id": "c", "step_name": "record_val"},
            ],
            "edges": [
                {"from": "a.v", "to": "b.v"},
                {"from": "b.v", "to": "c.v"},
            ],
        }
    )


async def _make_graph_version() -> tuple[uuid.UUID, int]:
    """Create a fresh graph + version in its own session/commit. Returns
    (graph_id, version) usable across subsequent sessions."""
    async with session_scope() as session:
        graph = await graphs_store.create_graph(
            session,
            name=f"runner_test_{uuid.uuid4().hex[:8]}",
            created_by=1,
        )
        gv = await graphs_store.save_version(
            session,
            graph_id=graph.id,
            definition=_three_node_graph(),
            created_by=1,
        )
        return graph.id, gv.version


@requires_postgres
class TestStartRun:
    @pytest.mark.asyncio
    async def test_completes_and_marks_succeeded(self):
        from core.engine import runner

        _register_simple_pipeline()
        graph_id, version = await _make_graph_version()

        run_id = await runner.start_run(
            graph_id=graph_id,
            graph_version=version,
            inputs={},
            started_by=1,
        )

        async with session_scope() as session:
            run = await runs_store.get_run(session, run_id)
            assert run is not None
            assert run.status == "succeeded"
            assert run.error is None
            assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_failure_captures_traceback_and_re_raises(self):
        from core.engine import runner

        @registry.step(name="boom", inputs={}, outputs={"x": int})
        def boom():
            raise RuntimeError("deliberate failure")

        graph_def = GraphDef.model_validate(
            {"nodes": [{"node_id": "a", "step_name": "boom"}], "edges": []}
        )

        async with session_scope() as session:
            graph = await graphs_store.create_graph(
                session,
                name=f"runner_fail_{uuid.uuid4().hex[:8]}",
                created_by=1,
            )
            gv = await graphs_store.save_version(
                session,
                graph_id=graph.id,
                definition=graph_def,
                created_by=1,
            )
            graph_id = graph.id
            version = gv.version

        with pytest.raises(Exception):
            await runner.start_run(
                graph_id=graph_id,
                graph_version=version,
                inputs={},
                started_by=1,
            )

        # status row should reflect the failure even though we re-raised
        async with session_scope() as session:
            # find the run for this graph
            runs = await runs_store.list_runs(session, graph_id=graph_id)
            assert len(runs) == 1
            run = runs[0]
            assert run.status == "failed"
            assert "deliberate failure" in (run.error or "")
            assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_pins_to_graph_version(self):
        """Editing the graph after start_run must not change what the run sees."""
        from core.engine import runner

        _register_simple_pipeline()
        graph_id, v1 = await _make_graph_version()

        # Save a NEW version that would break the run if the runner picked it up.
        broken = GraphDef.model_validate(
            {
                "nodes": [{"node_id": "n", "step_name": "emit_seed"}],
                "edges": [],
            }
        )
        async with session_scope() as session:
            v2_row = await graphs_store.save_version(
                session,
                graph_id=graph_id,
                definition=broken,
                created_by=1,
            )
            v2 = v2_row.version

        # Old version's run still completes against its original definition.
        run_id = await runner.start_run(
            graph_id=graph_id,
            graph_version=v1,
            inputs={},
            started_by=1,
        )
        async with session_scope() as session:
            run = await runs_store.get_run(session, run_id)
            assert run.status == "succeeded"
            assert run.graph_version == v1
            assert v2 == v1 + 1  # we did create a new version


@requires_postgres
class TestDurability:
    """The Postgres checkpointer is the substrate that makes pause/resume
    durable. Even without an interrupt, we can verify that checkpoint state
    survives engine disposal — a fresh process can read back the run's final
    state via the same thread_id."""

    @pytest.mark.asyncio
    async def test_checkpoint_survives_engine_dispose(self):
        from core.engine import runner
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        _register_simple_pipeline()
        graph_id, version = await _make_graph_version()

        run_id = await runner.start_run(
            graph_id=graph_id,
            graph_version=version,
            inputs={},
            started_by=1,
        )

        # Simulate process death: dispose every engine-owned resource.
        await dispose_engine()

        # Re-instantiate a fresh checkpointer and read state by thread_id.
        uri = runner._checkpointer_uri()
        async with AsyncPostgresSaver.from_conn_string(uri) as saver:
            await saver.setup()
            tuples = []
            async for ckpt in saver.alist(
                config={"configurable": {"thread_id": str(run_id)}}
            ):
                tuples.append(ckpt)

        assert len(tuples) > 0, (
            "checkpointer wrote no state for this thread_id; "
            "the run was not durably recorded"
        )
        # The latest checkpoint must contain the final port values.
        latest = tuples[0]
        ports = latest.checkpoint["channel_values"].get("ports", {})
        assert ports.get("c.final") == 14, (
            f"expected c.final=14, got ports={ports}"
        )
