from __future__ import annotations

from typing import Any

import pandas as pd

from core.connectors.base import Connector
from core.steps.base import DeterministicToolStep
from core.steps.registry import StepRegistry


# ---------------------------------------------------------------------------
# ConnectorRegistry — maps connector type-name strings to classes
# ---------------------------------------------------------------------------

class ConnectorRegistry:
    """Maps connector type-name strings to Connector classes.

    Built-in connectors are registered at import time. Additional connectors
    can be registered with @ConnectorRegistry.register or by calling it directly.
    """

    _registry: dict[str, type[Connector]] = {}

    @classmethod
    def register(cls, connector_cls: type[Connector]) -> type[Connector]:
        cls._registry[connector_cls.__name__] = connector_cls
        return connector_cls

    @classmethod
    def get(cls, name: str) -> type[Connector]:
        if name not in cls._registry:
            registered = list(cls._registry)
            raise KeyError(
                f"No connector registered as '{name}'. Registered: {registered}"
            )
        return cls._registry[name]

    @classmethod
    def names(cls) -> list[str]:
        return list(cls._registry)


# Register built-in connectors
def _register_builtins() -> None:
    from core.connectors.file import FileConnector
    from core.connectors.quickbooks import QuickBooksConnector
    from core.connectors.clickup import ClickUpConnector
    from core.connectors.datarails import DataRailsConnector

    for cls in (FileConnector, QuickBooksConnector, ClickUpConnector, DataRailsConnector):
        ConnectorRegistry.register(cls)

_register_builtins()


# ---------------------------------------------------------------------------
# ConnectorStep
# ---------------------------------------------------------------------------

@StepRegistry.register
class ConnectorStep(DeterministicToolStep):
    """Fetches data from a Connector. Always the first step in a pipeline.

    Programmatic use — pass a live Connector instance:
        ConnectorStep(
            connector=FileConnector("data/staged/gl.parquet"),
            name="Load GL Data",
            description="fetches staged GL transactions",
        )

    JSON config — connector resolved by name from ConnectorRegistry:
        {
            "type": "ConnectorStep",
            "config": {
                "name": "Load GL Data",
                "description": "fetches staged GL transactions",
                "connector_type": "FileConnector",
                "connector_config": {"path": "data/staged/gl.parquet"}
            }
        }

    Upstream input is ignored — ConnectorStep is always a data source.
    Pass fetch_kwargs to forward extra arguments to connector.fetch().
    """

    def __init__(
        self,
        name: str = "",
        description: str = "",
        connector: Connector | None = None,
        connector_type: str = "",
        connector_config: dict | None = None,
        fetch_kwargs: dict | None = None,
    ):
        if connector is not None:
            self._connector = connector
        elif connector_type:
            cls = ConnectorRegistry.get(connector_type)
            self._connector = cls(**(connector_config or {}))
        else:
            raise ValueError(
                "ConnectorStep requires either a 'connector' instance "
                "or 'connector_type' + optional 'connector_config'"
            )
        self._fetch_kwargs = fetch_kwargs or {}
        self._step_name = name or "ConnectorStep"
        self._step_description = description

    def run(self, data: Any = None) -> Any:
        return self._connector.fetch(**self._fetch_kwargs)

    def provenance_metadata(self) -> dict:
        connector_name = self._connector.__class__.__name__
        return {
            "step": self._step_name,
            "description": self._step_description or f"fetches data via {connector_name}",
            "step_type": "deterministic",
        }


# ---------------------------------------------------------------------------
# QueryStep
# ---------------------------------------------------------------------------

@StepRegistry.register
class QueryStep(DeterministicToolStep):
    """Filters a DataFrame or list of dicts using a pandas query expression.

    The query string uses pandas .query() syntax:
        "status == 'active'"
        "cost > 0 and phase == 'B1'"
        "lot_number in [101, 102, 104]"

    Lists of dicts are converted to a DataFrame for filtering, then returned
    as a list of dicts. DataFrames are returned as DataFrames.

    JSON config:
        {
            "type": "QueryStep",
            "config": {
                "name": "Filter Active Lots",
                "description": "keeps only lots where status is active",
                "query": "status == 'active'"
            }
        }
    """

    def __init__(self, query: str, name: str = "", description: str = ""):
        self._query = query
        self._step_name = name or "QueryStep"
        self._step_description = description

    def run(self, data: Any = None) -> Any:
        if data is None:
            return data

        if isinstance(data, list):
            df = pd.DataFrame(data)
            result = df.query(self._query)
            return result.to_dict(orient="records")

        if isinstance(data, pd.DataFrame):
            return data.query(self._query)

        raise TypeError(
            f"QueryStep expects a DataFrame or list of dicts, got {type(data).__name__}"
        )

    def provenance_metadata(self) -> dict:
        return {
            "step": self._step_name,
            "description": self._step_description or f"query: {self._query}",
            "step_type": "deterministic",
        }
