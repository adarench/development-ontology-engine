"""Compatibility shim. Canonical home is core.steps.output.base.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.output.base import Renderer

__all__ = ["Renderer"]
