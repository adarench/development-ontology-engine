"""Compatibility shim. Canonical home is core.steps.data.quickbooks.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.data.quickbooks import QuickBooksConnector, fetch_quickbooks

__all__ = ["QuickBooksConnector", "fetch_quickbooks"]
