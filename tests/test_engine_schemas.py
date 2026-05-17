"""Structural validation for GraphDef / NodeDef / EdgeDef / PortRef.

Registry-aware checks (step exists, port types compatible) live in
tests/test_engine_validator.py.
"""
import pytest
from pydantic import ValidationError

from core.engine.schemas import EdgeDef, GraphDef, NodeDef, PortRef


def _valid_graph() -> dict:
    return {
        "nodes": [
            {"node_id": "a", "step_name": "load"},
            {"node_id": "b", "step_name": "cluster"},
        ],
        "edges": [{"from": "a.lots", "to": "b.lots"}],
    }


class TestPortRef:
    def test_parse_valid(self):
        p = PortRef.parse("node1.port_x")
        assert p.node_id == "node1" and p.port == "port_x"

    def test_str_roundtrip(self):
        assert str(PortRef.parse("a.b")) == "a.b"

    @pytest.mark.parametrize("bad", ["nodot", "a.", ".b", "a.b.c", "1bad.port", ""])
    def test_parse_rejects(self, bad: str):
        with pytest.raises(ValueError):
            PortRef.parse(bad)


class TestNodeDef:
    def test_minimal(self):
        n = NodeDef(node_id="a", step_name="load")
        assert n.config == {}

    def test_with_config(self):
        n = NodeDef(node_id="a", step_name="load", config={"gap": 50})
        assert n.config["gap"] == 50

    @pytest.mark.parametrize("bad_id", ["1abc", "a-b", "", "has space"])
    def test_rejects_bad_node_id(self, bad_id: str):
        with pytest.raises(ValidationError):
            NodeDef(node_id=bad_id, step_name="load")

    def test_rejects_empty_step_name(self):
        with pytest.raises(ValidationError):
            NodeDef(node_id="a", step_name="   ")

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            NodeDef(node_id="a", step_name="load", extra_key="oops")


class TestEdgeDef:
    def test_from_string_form(self):
        e = EdgeDef.model_validate({"from": "a.x", "to": "b.y"})
        assert e.from_.node_id == "a" and e.from_.port == "x"
        assert e.to.node_id == "b" and e.to.port == "y"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            EdgeDef.model_validate({"from": "a.x", "to": "b.y", "extra": 1})

    def test_serializes_as_dotted_strings(self):
        e = EdgeDef.model_validate({"from": "a.x", "to": "b.y"})
        out = e.model_dump(by_alias=True)
        assert out["from"] == "a.x"
        assert out["to"] == "b.y"


class TestGraphDef:
    def test_happy_path(self):
        g = GraphDef.model_validate(_valid_graph())
        assert len(g.nodes) == 2
        assert len(g.edges) == 1

    def test_empty_nodes_rejected(self):
        with pytest.raises(ValidationError):
            GraphDef.model_validate({"nodes": [], "edges": []})

    def test_duplicate_node_id_rejected(self):
        with pytest.raises(ValidationError) as exc:
            GraphDef.model_validate(
                {
                    "nodes": [
                        {"node_id": "a", "step_name": "x"},
                        {"node_id": "a", "step_name": "y"},
                    ],
                    "edges": [],
                }
            )
        assert "Duplicate node_id" in str(exc.value)

    def test_edge_references_unknown_node(self):
        with pytest.raises(ValidationError) as exc:
            GraphDef.model_validate(
                {
                    "nodes": [{"node_id": "a", "step_name": "x"}],
                    "edges": [{"from": "a.lots", "to": "ghost.lots"}],
                }
            )
        assert "ghost" in str(exc.value)

    def test_round_trip_through_json(self):
        g = GraphDef.model_validate(_valid_graph())
        dumped = g.model_dump(by_alias=True)
        back = GraphDef.model_validate(dumped)
        assert back == g

    def test_node_by_id(self):
        g = GraphDef.model_validate(_valid_graph())
        assert g.node_by_id("a").step_name == "load"
        with pytest.raises(KeyError):
            g.node_by_id("ghost")
