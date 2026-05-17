"""Registry-aware graph validation."""
from typing import Any

import pytest

from core.engine import registry
from core.engine.schemas import GraphDef
from core.engine.validator import (
    GraphValidationError,
    ValidationIssue,
    validate,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Each test gets a fresh registry."""
    registry.clear()
    yield
    registry.clear()


def _register_default_steps() -> None:
    @registry.step(name="load", inputs={}, outputs={"lots": list})
    def load_fn() -> None: ...

    @registry.step(name="cluster", inputs={"lots": list}, outputs={"phases": dict})
    def cluster_fn() -> None: ...


def _graph_two_nodes_one_edge() -> GraphDef:
    return GraphDef.model_validate(
        {
            "nodes": [
                {"node_id": "a", "step_name": "load"},
                {"node_id": "b", "step_name": "cluster"},
            ],
            "edges": [{"from": "a.lots", "to": "b.lots"}],
        }
    )


class TestValidate:
    def test_happy_path_returns_graph(self):
        _register_default_steps()
        g = _graph_two_nodes_one_edge()
        assert validate(g) is g

    def test_unknown_step_reported(self):
        g = GraphDef.model_validate(
            {"nodes": [{"node_id": "a", "step_name": "ghost"}], "edges": []}
        )
        with pytest.raises(GraphValidationError) as exc:
            validate(g)
        issues = exc.value.issues
        assert len(issues) == 1
        assert issues[0].code == "unknown_step"
        assert "nodes[0]" == issues[0].where

    def test_unknown_output_port_reported(self):
        _register_default_steps()
        g = GraphDef.model_validate(
            {
                "nodes": [
                    {"node_id": "a", "step_name": "load"},
                    {"node_id": "b", "step_name": "cluster"},
                ],
                "edges": [{"from": "a.bogus", "to": "b.lots"}],
            }
        )
        with pytest.raises(GraphValidationError) as exc:
            validate(g)
        assert exc.value.issues[0].code == "unknown_output_port"
        assert "edges[0].from" == exc.value.issues[0].where

    def test_unknown_input_port_reported(self):
        _register_default_steps()
        g = GraphDef.model_validate(
            {
                "nodes": [
                    {"node_id": "a", "step_name": "load"},
                    {"node_id": "b", "step_name": "cluster"},
                ],
                "edges": [{"from": "a.lots", "to": "b.ghost"}],
            }
        )
        with pytest.raises(GraphValidationError) as exc:
            validate(g)
        assert exc.value.issues[0].code == "unknown_input_port"

    def test_type_mismatch_reported(self):
        _register_default_steps()

        @registry.step(name="wants_str", inputs={"x": str}, outputs={})
        def wants_str_fn(): ...

        g = GraphDef.model_validate(
            {
                "nodes": [
                    {"node_id": "a", "step_name": "load"},
                    {"node_id": "b", "step_name": "wants_str"},
                ],
                "edges": [{"from": "a.lots", "to": "b.x"}],
            }
        )
        with pytest.raises(GraphValidationError) as exc:
            validate(g)
        assert exc.value.issues[0].code == "type_mismatch"

    def test_any_accepts_anything(self):
        @registry.step(name="emitter", inputs={}, outputs={"v": int})
        def emitter(): ...

        @registry.step(name="any_sink", inputs={"x": Any}, outputs={})
        def any_sink(): ...

        g = GraphDef.model_validate(
            {
                "nodes": [
                    {"node_id": "a", "step_name": "emitter"},
                    {"node_id": "b", "step_name": "any_sink"},
                ],
                "edges": [{"from": "a.v", "to": "b.x"}],
            }
        )
        assert validate(g) is g

    def test_subclass_is_compatible(self):
        class Animal: ...

        class Dog(Animal): ...

        @registry.step(name="dog_emitter", inputs={}, outputs={"d": Dog})
        def dog_emitter(): ...

        @registry.step(name="animal_sink", inputs={"a": Animal}, outputs={})
        def animal_sink(): ...

        g = GraphDef.model_validate(
            {
                "nodes": [
                    {"node_id": "n1", "step_name": "dog_emitter"},
                    {"node_id": "n2", "step_name": "animal_sink"},
                ],
                "edges": [{"from": "n1.d", "to": "n2.a"}],
            }
        )
        assert validate(g) is g

    def test_multiple_issues_collected(self):
        g = GraphDef.model_validate(
            {
                "nodes": [
                    {"node_id": "a", "step_name": "ghost1"},
                    {"node_id": "b", "step_name": "ghost2"},
                ],
                "edges": [],
            }
        )
        with pytest.raises(GraphValidationError) as exc:
            validate(g)
        codes = [i.code for i in exc.value.issues]
        assert codes == ["unknown_step", "unknown_step"]


class TestValidationIssue:
    def test_issue_is_frozen_dataclass(self):
        i = ValidationIssue(where="x", code="c", message="m")
        with pytest.raises(Exception):
            i.code = "new"  # type: ignore[misc]
