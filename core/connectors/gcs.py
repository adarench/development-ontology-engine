"""Compatibility shim. Canonical home is core.steps.data.gcs.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.data.gcs import (
    GCSConnector,
    fetch_gcs,
    list_blobs,
    download_prefix,
)

__all__ = ["GCSConnector", "fetch_gcs", "list_blobs", "download_prefix"]
