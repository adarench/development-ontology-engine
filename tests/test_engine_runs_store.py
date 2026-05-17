"""Integration tests for the runs store (create + status transitions + reads).

Skipped if Postgres isn't reachable. See conftest_engine.py.
"""
from __future__ import annotations

import uuid

import pytest

from core.engine import registry
from core.engine.schemas import GraphDef
from core.engine.store import graphs as graphs_store
from core.engine.store import runs as runs_store

from tests.conftest_engine import engine_session, requires_postgres  # noqa: F401


def _valid_graph_def() -> GraphDef:
    return GraphDef.model_validate(
        {
            "nodes": [{"node_id": "n", "step_name": "noop"}],
            "edges": [],
        }
    )


@pytest.fixture(autouse=True)
def _register_noop_step():
    registry.clear()

    @registry.step(name="noop", inputs={}, outputs={})
    def _noop():
        return {}

    yield
    registry.clear()


async def _setup_graph_with_version(engine_session) -> tuple[uuid.UUID, int]:
    g = await graphs_store.create_graph(
        engine_session, name="t_runs", created_by=1
    )
    v = await graphs_store.save_version(
        engine_session,
        graph_id=g.id,
        definition=_valid_graph_def(),
        created_by=1,
    )
    return g.id, v.version


@requires_postgres
class TestCreateRun:
    @pytest.mark.asyncio
    async def test_creates_row_with_running_status(self, engine_session):
        graph_id, version = await _setup_graph_with_version(engine_session)
        run = await runs_store.create_run(
            engine_session,
            graph_id=graph_id,
            graph_version=version,
            inputs={"k": 1},
            started_by=1,
        )
        assert run.status == "running"
        assert isinstance(run.id, uuid.UUID)
        assert run.inputs == {"k": 1}
        assert run.error is None
        assert run.completed_at is None

    @pytest.mark.asyncio
    async def test_pinning_to_unknown_version_fails(self, engine_session):
        graph_id, _ = await _setup_graph_with_version(engine_session)
        with pytest.raises(Exception):
            await runs_store.create_run(
                engine_session,
                graph_id=graph_id,
                graph_version=999,
                inputs={},
                started_by=1,
            )
            await engine_session.flush()


@requires_postgres
class TestStatusTransitions:
    @pytest.mark.asyncio
    async def test_mark_succeeded(self, engine_session):
        graph_id, v = await _setup_graph_with_version(engine_session)
        run = await runs_store.create_run(
            engine_session, graph_id=graph_id, graph_version=v,
            inputs={}, started_by=1,
        )
        await runs_store.mark_succeeded(engine_session, run.id)
        reloaded = await runs_store.get_run(engine_session, run.id)
        assert reloaded.status == "succeeded"
        assert reloaded.completed_at is not None
        assert reloaded.error is None

    @pytest.mark.asyncio
    async def test_mark_failed_records_error(self, engine_session):
        graph_id, v = await _setup_graph_with_version(engine_session)
        run = await runs_store.create_run(
            engine_session, graph_id=graph_id, graph_version=v,
            inputs={}, started_by=1,
        )
        await runs_store.mark_failed(engine_session, run.id, error="boom")
        reloaded = await runs_store.get_run(engine_session, run.id)
        assert reloaded.status == "failed"
        assert reloaded.error == "boom"
        assert reloaded.completed_at is not None

    @pytest.mark.asyncio
    async def test_mark_awaiting_human(self, engine_session):
        graph_id, v = await _setup_graph_with_version(engine_session)
        run = await runs_store.create_run(
            engine_session, graph_id=graph_id, graph_version=v,
            inputs={}, started_by=1,
        )
        await runs_store.mark_awaiting_human(engine_session, run.id)
        reloaded = await runs_store.get_run(engine_session, run.id)
        assert reloaded.status == "awaiting_human"
        assert reloaded.completed_at is None  # not terminal

    @pytest.mark.asyncio
    async def test_resume_clears_error(self, engine_session):
        graph_id, v = await _setup_graph_with_version(engine_session)
        run = await runs_store.create_run(
            engine_session, graph_id=graph_id, graph_version=v,
            inputs={}, started_by=1,
        )
        await runs_store.mark_failed(engine_session, run.id, error="old")
        await runs_store.mark_running(engine_session, run.id)
        reloaded = await runs_store.get_run(engine_session, run.id)
        assert reloaded.status == "running"
        assert reloaded.error is None


@requires_postgres
class TestListRuns:
    @pytest.mark.asyncio
    async def test_filters_by_status_and_graph(self, engine_session):
        graph_id, v = await _setup_graph_with_version(engine_session)
        r1 = await runs_store.create_run(
            engine_session, graph_id=graph_id, graph_version=v,
            inputs={}, started_by=1,
        )
        r2 = await runs_store.create_run(
            engine_session, graph_id=graph_id, graph_version=v,
            inputs={}, started_by=1,
        )
        await runs_store.mark_succeeded(engine_session, r1.id)

        running = await runs_store.list_runs(
            engine_session, graph_id=graph_id, status="running"
        )
        succeeded = await runs_store.list_runs(
            engine_session, graph_id=graph_id, status="succeeded"
        )
        assert r2.id in {r.id for r in running}
        assert r1.id in {r.id for r in succeeded}
