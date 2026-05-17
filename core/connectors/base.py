"""Compatibility shim. Canonical home is core.steps.data.base.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.data.base import Connector

__all__ = ["Connector"]
