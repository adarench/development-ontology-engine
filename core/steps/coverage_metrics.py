"""Compatibility shim. Canonical home is core.steps.transform.coverage_metrics.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.coverage_metrics import CoverageMetricsStep, coverage_metrics

__all__ = ["CoverageMetricsStep", "coverage_metrics"]
