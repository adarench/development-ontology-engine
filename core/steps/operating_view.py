"""Compatibility shim. Canonical home is core.steps.transform.operating_view.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.operating_view import (
    DEFAULT_PROJECT_TO_ENTITY,
    OUTPUT_COLS,
    OperatingViewStep,
    operating_view,
)

__all__ = ["DEFAULT_PROJECT_TO_ENTITY", "OUTPUT_COLS", "OperatingViewStep", "operating_view"]
