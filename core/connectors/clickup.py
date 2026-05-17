"""Compatibility shim. Canonical home is core.steps.data.clickup.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.data.clickup import ClickUpConnector, fetch_clickup

__all__ = ["ClickUpConnector", "fetch_clickup"]
