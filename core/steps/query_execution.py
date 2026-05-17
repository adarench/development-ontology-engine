"""Compatibility shim. Canonical home is core.steps.transform.query_execution.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.query_execution import Answer, QueryExecutionStep, query_execution

__all__ = ["Answer", "QueryExecutionStep", "query_execution"]
