"""Compatibility shim. Canonical home is core.steps.data.datarails.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.data.datarails import DataRailsConnector, fetch_datarails

__all__ = ["DataRailsConnector", "fetch_datarails"]
