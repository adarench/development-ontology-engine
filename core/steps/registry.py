"""Compatibility shim. Canonical home is core.steps.transform.registry.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.registry import StepRegistry, ToolLoader

__all__ = ["StepRegistry", "ToolLoader"]
