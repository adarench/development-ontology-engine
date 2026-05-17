"""Compatibility shim. Canonical home is core.steps.transform.gl_aggregate.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.gl_aggregate import GLAggregateStep, gl_aggregate

__all__ = ["GLAggregateStep", "gl_aggregate"]
