"""Compatibility shim. Canonical home is core.steps.transform.lot_state.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.lot_state import (
    DEFAULT_STAGE_ORDER,
    LotStateStep,
    _stage_rank,
    lot_state,
)

__all__ = ["DEFAULT_STAGE_ORDER", "LotStateStep", "_stage_rank", "lot_state"]
