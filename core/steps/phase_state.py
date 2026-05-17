"""Compatibility shim. Canonical home is core.steps.transform.phase_state.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.phase_state import PhaseStateStep, phase_state

__all__ = ["PhaseStateStep", "phase_state"]
