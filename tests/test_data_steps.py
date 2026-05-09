"""Tests for ConnectorStep, QueryStep, and ConnectorRegistry."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from core.connectors.base import Connector
from core.steps.data_steps import ConnectorRegistry, ConnectorStep, QueryStep
from core.steps.registry import StepRegistry, ToolLoader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _FakeConnector(Connector):
    def __init__(self, data, **kwargs):
        self._data = data

    def fetch(self, **kwargs):
        return self._data

    def validate(self):
        return True


LOTS = [
    {"lot": "101", "phase": "B1", "status": "active",   "cost": 85_000},
    {"lot": "102", "phase": "B1", "status": "closed",   "cost": 42_000},
    {"lot": "103", "phase": "B1", "status": "active",   "cost": 130_000},
    {"lot": "104", "phase": "B2", "status": "inactive", "cost": 0},
]

LOTS_DF = pd.DataFrame(LOTS)


# ---------------------------------------------------------------------------
# ConnectorRegistry
# ---------------------------------------------------------------------------

class TestConnectorRegistry:
    def setup_method(self):
        self._original = dict(ConnectorRegistry._registry)

    def teardown_method(self):
        ConnectorRegistry._registry.clear()
        ConnectorRegistry._registry.update(self._original)

    def test_register_and_get(self):
        ConnectorRegistry.register(_FakeConnector)
        assert ConnectorRegistry.get("_FakeConnector") is _FakeConnector

    def test_register_as_decorator(self):
        @ConnectorRegistry.register
        class _Temp(Connector):
            def fetch(self, **kwargs): return []
            def validate(self): return True

        assert ConnectorRegistry.get("_Temp") is _Temp

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="No connector registered"):
            ConnectorRegistry.get("Nonexistent")

    def test_builtins_registered(self):
        for name in ("FileConnector", "QuickBooksConnector", "ClickUpConnector", "DataRailsConnector"):
            assert name in ConnectorRegistry.names()


# ---------------------------------------------------------------------------
# ConnectorStep
# ---------------------------------------------------------------------------

class TestConnectorStep:
    def test_fetch_with_connector_instance(self):
        step = ConnectorStep(connector=_FakeConnector(LOTS))
        assert step.run() == LOTS

    def test_ignores_upstream_data(self):
        step = ConnectorStep(connector=_FakeConnector(LOTS))
        assert step.run("ignored") == LOTS

    def test_fetch_via_registry_name(self):
        ConnectorRegistry.register(_FakeConnector)
        step = ConnectorStep(
            connector_type="_FakeConnector",
            connector_config={"data": LOTS},
        )
        assert step.run() == LOTS
        del ConnectorRegistry._registry["_FakeConnector"]

    def test_requires_connector_or_type(self):
        with pytest.raises(ValueError, match="requires either"):
            ConnectorStep()

    def test_unknown_connector_type_raises(self):
        with pytest.raises(KeyError, match="No connector registered"):
            ConnectorStep(connector_type="Bogus")

    def test_name_in_provenance(self):
        step = ConnectorStep(
            connector=_FakeConnector(LOTS),
            name="Load GL Data",
            description="fetches GL transactions",
        )
        md = step.provenance_metadata()
        assert md["step"] == "Load GL Data"
        assert md["description"] == "fetches GL transactions"
        assert md["step_type"] == "deterministic"

    def test_default_name_in_provenance(self):
        step = ConnectorStep(connector=_FakeConnector(LOTS))
        assert step.provenance_metadata()["step"] == "ConnectorStep"

    def test_description_falls_back_to_connector_class(self):
        step = ConnectorStep(connector=_FakeConnector(LOTS))
        assert "_FakeConnector" in step.provenance_metadata()["description"]

    def test_registered_in_step_registry(self):
        assert StepRegistry.get("ConnectorStep") is ConnectorStep

    def test_from_json_via_tool_loader(self):
        ConnectorRegistry.register(_FakeConnector)
        spec = {
            "name": "t",
            "description": "",
            "steps": [
                {
                    "type": "ConnectorStep",
                    "config": {
                        "name": "Load Lots",
                        "description": "load lot data",
                        "connector_type": "_FakeConnector",
                        "connector_config": {"data": LOTS},
                    },
                }
            ],
        }
        tool = ToolLoader().from_dict(spec)
        assert tool.run() == LOTS
        del ConnectorRegistry._registry["_FakeConnector"]


# ---------------------------------------------------------------------------
# QueryStep — list of dicts
# ---------------------------------------------------------------------------

class TestQueryStepList:
    def test_filter_by_status(self):
        step = QueryStep(query="status == 'active'")
        result = step.run(LOTS)
        assert len(result) == 2
        assert all(r["status"] == "active" for r in result)

    def test_filter_by_phase(self):
        step = QueryStep(query="phase == 'B1'")
        result = step.run(LOTS)
        assert len(result) == 3

    def test_filter_numeric(self):
        step = QueryStep(query="cost > 50000")
        result = step.run(LOTS)
        assert all(r["cost"] > 50_000 for r in result)

    def test_compound_query(self):
        step = QueryStep(query="status == 'active' and cost > 100000")
        result = step.run(LOTS)
        assert len(result) == 1
        assert result[0]["lot"] == "103"

    def test_returns_list_of_dicts(self):
        step = QueryStep(query="status == 'active'")
        result = step.run(LOTS)
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_empty_result(self):
        step = QueryStep(query="status == 'pending'")
        result = step.run(LOTS)
        assert result == []

    def test_none_input_passthrough(self):
        step = QueryStep(query="status == 'active'")
        assert step.run(None) is None


# ---------------------------------------------------------------------------
# QueryStep — DataFrame
# ---------------------------------------------------------------------------

class TestQueryStepDataFrame:
    def test_filter_returns_dataframe(self):
        step = QueryStep(query="status == 'active'")
        result = step.run(LOTS_DF)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    def test_compound_query_on_dataframe(self):
        step = QueryStep(query="phase == 'B1' and cost > 50000")
        result = step.run(LOTS_DF)
        assert len(result) == 2

    def test_wrong_type_raises(self):
        step = QueryStep(query="x == 1")
        with pytest.raises(TypeError, match="expects a DataFrame or list of dicts"):
            step.run("not a dataframe")


# ---------------------------------------------------------------------------
# QueryStep — provenance and registry
# ---------------------------------------------------------------------------

class TestQueryStepProvenance:
    def test_name_in_provenance(self):
        step = QueryStep(
            query="status == 'active'",
            name="Filter Active Lots",
            description="keeps only active lots",
        )
        md = step.provenance_metadata()
        assert md["step"] == "Filter Active Lots"
        assert md["description"] == "keeps only active lots"

    def test_description_falls_back_to_query(self):
        step = QueryStep(query="cost > 0")
        assert "cost > 0" in step.provenance_metadata()["description"]

    def test_registered_in_step_registry(self):
        assert StepRegistry.get("QueryStep") is QueryStep

    def test_from_json_via_tool_loader(self):
        spec = {
            "name": "t",
            "description": "",
            "steps": [
                {
                    "type": "QueryStep",
                    "config": {
                        "name": "Active Only",
                        "description": "filter to active lots",
                        "query": "status == 'active'",
                    },
                }
            ],
        }
        tool = ToolLoader().from_dict(spec)
        result = tool.run(LOTS)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Combined pipeline: ConnectorStep → QueryStep → ScriptStep
# ---------------------------------------------------------------------------

class TestCombinedPipeline:
    def test_connector_then_query(self):
        from core.tools.pipeline import PipelineTool

        tool = PipelineTool(
            name="active_lot_cost",
            description="total cost of active lots",
            steps=[
                ConnectorStep(connector=_FakeConnector(LOTS), name="Load Lots", description="load lot data"),
                QueryStep(query="status == 'active'", name="Filter Active", description="keep active lots"),
            ],
        )
        result = tool.run()
        assert len(result) == 2
        assert all(r["status"] == "active" for r in result)
        assert len(tool._provenance.deterministic_steps) == 2
