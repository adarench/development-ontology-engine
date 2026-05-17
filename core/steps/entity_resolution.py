"""Compatibility shim. Canonical home is core.steps.transform.entity_resolution.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.entity_resolution import EntityResolutionStep, EntityResolver

__all__ = ["EntityResolutionStep", "EntityResolver"]
