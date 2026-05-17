"""Compatibility shim. Canonical home is core.steps.data.file.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.data.file import FileConnector, fetch_file

__all__ = ["FileConnector", "fetch_file"]
