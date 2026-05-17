"""Compatibility shim. Canonical home is core.steps.transform.lot_parse.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.lot_parse import LotParseStep, lot_parse

__all__ = ["LotParseStep", "lot_parse"]
