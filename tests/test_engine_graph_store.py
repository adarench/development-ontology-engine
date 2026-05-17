"""Integration tests for the graph store.

These hit a real Postgres. They skip silently if `DATABASE_URL` is unset
or the database isn't reachable (see conftest_engine.py).

Run locally with:
    docker-compose up -d postgres
    alembic upgrade head
    pytest tests/test_engine_graph_store.py
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from core.engine import registry
from core.engine.models import Graph, GraphVersion
from core.engine.schemas import GraphDef
from core.engine.store import graphs as graph_store
from core.engine.validator import GraphValidationError

from tests.conftest_engine import engine_session, requires_postgres  # noqa: F401


def _valid_graph_def() -> GraphDef:
    return GraphDef.model_validate(
        {
            "nodes": [
                {"node_id": "a", "step_name": "load"},
                {"node_id": "b", "step_name": "cluster"},
            ],
            "edges": [{"from": "a.lots", "to": "b.lots"}],
        }
    )


def _register_test_steps() -> None:
    @registry.step(name="load", inputs={}, outputs={"lots": list})
    def _load() -> None: ...

    @registry.step(name="cluster", inputs={"lots": list}, outputs={"phases": dict})
    def _cluster() -> None: ...


@pytest.fixture(autouse=True)
def _fresh_registry():
    registry.clear()
    _register_test_steps()
    yield
    registry.clear()


@requires_postgres
class TestCreateGraph:
    @pytest.mark.asyncio
    async def test_create_assigns_uuid_and_defaults(self, engine_session):
        g = await graph_store.create_graph(
            engine_session, name="g1", created_by=1
        )
        assert isinstance(g.id, uuid.UUID)
        assert g.name == "g1"
        assert g.status == "draft"
        assert g.latest_version == 0


@requires_postgres
class TestSaveVersion:
    @pytest.mark.asyncio
    async def test_first_version_is_1_and_bumps_latest(self, engine_session):
        g = await graph_store.create_graph(
            engine_session, name="g1", created_by=1
        )
        v = await graph_store.save_version(
            engine_session,
            graph_id=g.id,
            definition=_valid_graph_def(),
            created_by=1,
        )
        assert v.version == 1
        await engine_session.refresh(g)
        assert g.latest_version == 1

    @pytest.mark.asyncio
    async def test_subsequent_versions_increment(self, engine_session):
        g = await graph_store.create_graph(
            engine_session, name="g1", created_by=1
        )
        v1 = await graph_store.save_version(
            engine_session, graph_id=g.id,
            definition=_valid_graph_def(), created_by=1,
        )
        v2 = await graph_store.save_version(
            engine_session, graph_id=g.id,
            definition=_valid_graph_def(), created_by=1,
        )
        assert v1.version == 1
        assert v2.version == 2
        await engine_session.refresh(g)
        assert g.latest_version == 2

    @pytest.mark.asyncio
    async def test_invalid_definition_rejected(self, engine_session):
        g = await graph_store.create_graph(
            engine_session, name="g1", created_by=1
        )
        bad_def = GraphDef.model_validate(
            {
                "nodes": [{"node_id": "x", "step_name": "ghost_step"}],
                "edges": [],
            }
        )
        with pytest.raises(GraphValidationError):
            await graph_store.save_version(
                engine_session,
                graph_id=g.id,
                definition=bad_def,
                created_by=1,
            )

    @pytest.mark.asyncio
    async def test_missing_graph_raises(self, engine_session):
        with pytest.raises(KeyError):
            await graph_store.save_version(
                engine_session,
                graph_id=uuid.uuid4(),
                definition=_valid_graph_def(),
                created_by=1,
            )

    @pytest.mark.asyncio
    async def test_stored_definition_round_trips(self, engine_session):
        g = await graph_store.create_graph(
            engine_session, name="g1", created_by=1
        )
        original = _valid_graph_def()
        v = await graph_store.save_version(
            engine_session, graph_id=g.id, definition=original, created_by=1,
        )
        # The stored definition is JSONB. It should round-trip back into GraphDef.
        reloaded = GraphDef.model_validate(v.definition)
        assert reloaded == original


@requires_postgres
class TestReads:
    @pytest.mark.asyncio
    async def test_get_version_returns_row(self, engine_session):
        g = await graph_store.create_graph(
            engine_session, name="g1", created_by=1
        )
        await graph_store.save_version(
            engine_session, graph_id=g.id,
            definition=_valid_graph_def(), created_by=1,
        )
        v = await graph_store.get_version(engine_session, g.id, 1)
        assert v is not None and v.version == 1

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_when_no_versions(self, engine_session):
        g = await graph_store.create_graph(
            engine_session, name="g1", created_by=1
        )
        v = await graph_store.get_latest_version(engine_session, g.id)
        assert v is None

    @pytest.mark.asyncio
    async def test_get_latest_returns_highest_version(self, engine_session):
        g = await graph_store.create_graph(
            engine_session, name="g1", created_by=1
        )
        await graph_store.save_version(
            engine_session, graph_id=g.id,
            definition=_valid_graph_def(), created_by=1,
        )
        await graph_store.save_version(
            engine_session, graph_id=g.id,
            definition=_valid_graph_def(), created_by=1,
        )
        v = await graph_store.get_latest_version(engine_session, g.id)
        assert v is not None and v.version == 2

    @pytest.mark.asyncio
    async def test_list_graphs(self, engine_session):
        before = await graph_store.list_graphs(engine_session)
        await graph_store.create_graph(
            engine_session, name="gA", created_by=1
        )
        await graph_store.create_graph(
            engine_session, name="gB", created_by=1
        )
        after = await graph_store.list_graphs(engine_session)
        assert len(after) == len(before) + 2
