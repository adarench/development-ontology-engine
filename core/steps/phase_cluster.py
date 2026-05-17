"""Compatibility shim. Canonical home is core.steps.transform.phase_cluster.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.phase_cluster import PhaseClusterStep, phase_cluster

__all__ = ["PhaseClusterStep", "phase_cluster"]
