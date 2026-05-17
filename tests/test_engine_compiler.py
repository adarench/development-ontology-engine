"""GraphDef → compiled LangGraph translation.

Compile-time topology tests (edge map, entry/exit detection, conflicts) plus
invoke-time tests that confirm port values flow correctly across linear,
fan-out, and fan-in shapes.
"""
import asyncio

import pytest

from core.engine import registry
from core.engine.compiler import (
    CompilationError,
    compile_graph,
)
from core.engine.schemas import GraphDef
from core.engine.validator import GraphValidationError


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.clear()
    yield
    registry.clear()


def _make_graph(nodes, edges) -> GraphDef:
    return GraphDef.model_validate({"nodes": nodes, "edges": edges})


def _run(compiled, initial=None):
    return asyncio.run(compiled.ainvoke(initial or {"ports": {}}))


# ─── Topology ────────────────────────────────────────────────────────────────


class TestEntryExitDetection:
    def test_isolated_node_runs(self):
        @registry.step(name="iso", inputs={}, outputs={"x": int})
        def iso():
            return {"x": 1}

        g = _make_graph([{"node_id": "a", "step_name": "iso"}], [])
        result = _run(compile_graph(g))
        assert result["ports"] == {"a.x": 1}

    def test_linear_pipeline(self):
        @registry.step(name="emit", inputs={}, outputs={"x": int})
        def emit():
            return {"x": 5}

        @registry.step(name="inc", inputs={"x": int}, outputs={"x": int})
        def inc(x):
            return {"x": x + 1}

        g = _make_graph(
            [
                {"node_id": "a", "step_name": "emit"},
                {"node_id": "b", "step_name": "inc"},
                {"node_id": "c", "step_name": "inc"},
            ],
            [
                {"from": "a.x", "to": "b.x"},
                {"from": "b.x", "to": "c.x"},
            ],
        )
        result = _run(compile_graph(g))
        assert result["ports"]["c.x"] == 7

    def test_fan_out_one_source_two_consumers(self):
        @registry.step(name="emit", inputs={}, outputs={"x": int})
        def emit():
            return {"x": 10}

        @registry.step(name="sink_a", inputs={"x": int}, outputs={"r": int})
        def sink_a(x):
            return {"r": x + 1}

        @registry.step(name="sink_b", inputs={"x": int}, outputs={"r": int})
        def sink_b(x):
            return {"r": x * 2}

        g = _make_graph(
            [
                {"node_id": "src", "step_name": "emit"},
                {"node_id": "a", "step_name": "sink_a"},
                {"node_id": "b", "step_name": "sink_b"},
            ],
            [
                {"from": "src.x", "to": "a.x"},
                {"from": "src.x", "to": "b.x"},
            ],
        )
        result = _run(compile_graph(g))
        assert result["ports"]["a.r"] == 11
        assert result["ports"]["b.r"] == 20

    def test_fan_in_two_sources_one_node(self):
        @registry.step(name="emit_a", inputs={}, outputs={"v": int})
        def emit_a():
            return {"v": 3}

        @registry.step(name="emit_b", inputs={}, outputs={"v": int})
        def emit_b():
            return {"v": 7}

        @registry.step(
            name="sum_two", inputs={"a": int, "b": int}, outputs={"total": int}
        )
        def sum_two(a, b):
            return {"total": a + b}

        g = _make_graph(
            [
                {"node_id": "x", "step_name": "emit_a"},
                {"node_id": "y", "step_name": "emit_b"},
                {"node_id": "s", "step_name": "sum_two"},
            ],
            [
                {"from": "x.v", "to": "s.a"},
                {"from": "y.v", "to": "s.b"},
            ],
        )
        result = _run(compile_graph(g))
        assert result["ports"]["s.total"] == 10


# ─── Config + ports interplay ────────────────────────────────────────────────


class TestConfigSupplements:
    def test_config_supplies_unconnected_input(self):
        @registry.step(name="emit", inputs={}, outputs={"v": int})
        def emit():
            return {"v": 5}

        @registry.step(
            name="scale",
            inputs={"v": int, "factor": int},
            outputs={"scaled": int},
        )
        def scale(v, factor):
            return {"scaled": v * factor}

        g = _make_graph(
            [
                {"node_id": "a", "step_name": "emit"},
                {
                    "node_id": "b",
                    "step_name": "scale",
                    "config": {"factor": 3},
                },
            ],
            [{"from": "a.v", "to": "b.v"}],
        )
        result = _run(compile_graph(g))
        assert result["ports"]["b.scaled"] == 15

    def test_edge_wins_over_config(self):
        @registry.step(name="emit", inputs={}, outputs={"v": int})
        def emit():
            return {"v": 100}

        @registry.step(name="echo", inputs={"v": int}, outputs={"v": int})
        def echo(v):
            return {"v": v}

        g = _make_graph(
            [
                {"node_id": "a", "step_name": "emit"},
                {
                    "node_id": "b",
                    "step_name": "echo",
                    "config": {"v": 0},
                },
            ],
            [{"from": "a.v", "to": "b.v"}],
        )
        result = _run(compile_graph(g))
        assert result["ports"]["b.v"] == 100


# ─── Conflict detection ──────────────────────────────────────────────────────


class TestCompilationErrors:
    def test_duplicate_edges_to_same_input_rejected(self):
        @registry.step(name="emit", inputs={}, outputs={"v": int})
        def emit():
            return {"v": 1}

        @registry.step(name="sink", inputs={"v": int}, outputs={})
        def sink(v):
            return {}

        g = _make_graph(
            [
                {"node_id": "a", "step_name": "emit"},
                {"node_id": "b", "step_name": "emit"},
                {"node_id": "s", "step_name": "sink"},
            ],
            [
                {"from": "a.v", "to": "s.v"},
                {"from": "b.v", "to": "s.v"},
            ],
        )
        with pytest.raises(CompilationError) as exc:
            compile_graph(g)
        assert "s.v" in str(exc.value)

    def test_step_returning_non_dict_rejected_at_run_time(self):
        @registry.step(name="bad", inputs={}, outputs={"v": int})
        def bad():
            return 42  # not a dict

        g = _make_graph([{"node_id": "a", "step_name": "bad"}], [])
        compiled = compile_graph(g)
        with pytest.raises(CompilationError) as exc:
            _run(compiled)
        assert "expected dict" in str(exc.value)

    def test_validator_runs_first(self):
        g = _make_graph(
            [{"node_id": "a", "step_name": "ghost_step"}], []
        )
        with pytest.raises(GraphValidationError):
            compile_graph(g)


# ─── Async steps ─────────────────────────────────────────────────────────────


class TestAsyncSteps:
    def test_async_step_is_awaited(self):
        @registry.step(name="async_emit", inputs={}, outputs={"v": int})
        async def async_emit():
            await asyncio.sleep(0)
            return {"v": 99}

        g = _make_graph(
            [{"node_id": "a", "step_name": "async_emit"}], []
        )
        result = _run(compile_graph(g))
        assert result["ports"]["a.v"] == 99

    def test_mixed_async_and_sync(self):
        @registry.step(name="emit", inputs={}, outputs={"v": int})
        def emit():
            return {"v": 1}

        @registry.step(name="async_inc", inputs={"v": int}, outputs={"v": int})
        async def async_inc(v):
            await asyncio.sleep(0)
            return {"v": v + 100}

        g = _make_graph(
            [
                {"node_id": "a", "step_name": "emit"},
                {"node_id": "b", "step_name": "async_inc"},
            ],
            [{"from": "a.v", "to": "b.v"}],
        )
        result = _run(compile_graph(g))
        assert result["ports"]["b.v"] == 101


# ─── Return shape ────────────────────────────────────────────────────────────


class TestReturnShapes:
    def test_step_returning_none_is_treated_as_empty(self):
        @registry.step(name="silent", inputs={}, outputs={})
        def silent():
            return None

        g = _make_graph([{"node_id": "a", "step_name": "silent"}], [])
        result = _run(compile_graph(g))
        # No ports were written; the field still exists from the seed.
        assert result["ports"] == {}

    def test_multiple_output_ports_all_persist(self):
        @registry.step(
            name="multi",
            inputs={},
            outputs={"x": int, "y": str},
        )
        def multi():
            return {"x": 1, "y": "hi"}

        g = _make_graph([{"node_id": "n", "step_name": "multi"}], [])
        result = _run(compile_graph(g))
        assert result["ports"] == {"n.x": 1, "n.y": "hi"}
