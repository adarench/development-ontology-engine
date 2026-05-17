"""Data-fetching steps.

Each module here owns one source: file system, ClickUp, QuickBooks, DataRails, GCS.
Modules export both the connector class (for direct use / testing) and a thin
@step-decorated wrapper function used by graphs.
"""

from core.steps.data.base import Connector
from core.steps.data.file import FileConnector, fetch_file
from core.steps.data.quickbooks import QuickBooksConnector, fetch_quickbooks
from core.steps.data.clickup import ClickUpConnector, fetch_clickup
from core.steps.data.datarails import DataRailsConnector, fetch_datarails
from core.steps.data.gcs import GCSConnector, fetch_gcs, list_blobs, download_prefix

__all__ = [
    "Connector",
    "FileConnector",
    "QuickBooksConnector",
    "ClickUpConnector",
    "DataRailsConnector",
    "GCSConnector",
    "fetch_file",
    "fetch_quickbooks",
    "fetch_clickup",
    "fetch_datarails",
    "fetch_gcs",
    "list_blobs",
    "download_prefix",
]
