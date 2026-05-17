"""Compatibility shim. Canonical home is core.steps.transform.gl_clean.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.gl_clean import GLCleanStep, gl_clean

__all__ = ["GLCleanStep", "gl_clean"]
