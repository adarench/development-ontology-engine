"""Compatibility shim. Canonical home is core.steps.transform.project_state.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.project_state import ProjectStateStep, project_state

__all__ = ["ProjectStateStep", "project_state"]
