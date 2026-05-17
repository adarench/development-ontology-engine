"""Compatibility shim. Canonical home is core.steps.output.dashboard.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.output.dashboard import DashboardRenderer, render_dashboard

__all__ = ["DashboardRenderer", "render_dashboard"]
