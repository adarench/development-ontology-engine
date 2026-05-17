"""Compatibility shim. Canonical home is core.steps.output.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.output import DashboardRenderer, Renderer

__all__ = ["Renderer", "DashboardRenderer"]
