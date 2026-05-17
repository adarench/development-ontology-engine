"""Compatibility shim. Canonical home is core.steps.transform.gl_normalize.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.gl_normalize import (
    DEFAULT_ACCOUNT_RULES,
    DEFAULT_ENTITY_MAP,
    DEFAULT_PHASE_RULES,
    GLNormalizeStep,
    gl_normalize,
)

__all__ = [
    "DEFAULT_ACCOUNT_RULES",
    "DEFAULT_ENTITY_MAP",
    "DEFAULT_PHASE_RULES",
    "GLNormalizeStep",
    "gl_normalize",
]
