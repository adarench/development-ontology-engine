from __future__ import annotations

import io
from typing import Any

import pandas as pd

from core.connectors.base import Connector


class GCSConnector(Connector):
    """Reads an xlsx (or other supported) blob from a Google Cloud Storage bucket.

    Authentication uses Application Default Credentials. Set up with:
        gcloud auth application-default login
    or by exporting GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON.

    Args:
        bucket:     GCS bucket name (no gs:// prefix)
        blob_path:  Object path within the bucket, e.g. "exports/q4/budget.xlsx"
        sheet_name: Sheet to read (name or 0-indexed int). Default: 0 (first sheet)
        nrows:      Optional row cap — useful for cheap schema inspection
        client:     Injectable storage.Client (for testing or custom auth)
    """

    SUPPORTED_SUFFIXES = {".xlsx", ".xls"}

    def __init__(
        self,
        bucket:     str,
        blob_path:  str,
        *,
        sheet_name: str | int = 0,
        nrows:      int | None = None,
        client                  = None,
    ) -> None:
        self.bucket     = bucket
        self.blob_path  = blob_path
        self.sheet_name = sheet_name
        self.nrows      = nrows
        self._client    = client

    def _get_client(self):
        if self._client is None:
            try:
                from google.cloud import storage
            except ImportError as exc:
                raise SystemExit(
                    "google-cloud-storage not installed. Run: pip3 install google-cloud-storage"
                ) from exc
            self._client = storage.Client()
        return self._client

    def _blob(self):
        return self._get_client().bucket(self.bucket).blob(self.blob_path)

    def validate(self) -> bool:
        suffix = "." + self.blob_path.rsplit(".", 1)[-1].lower() if "." in self.blob_path else ""
        if suffix not in self.SUPPORTED_SUFFIXES:
            return False
        try:
            return bool(self._blob().exists())
        except Exception:
            return False

    def fetch_bytes(self) -> bytes:
        """Download the blob's raw bytes. Useful when you need to read multiple
        sheets from one xlsx without re-downloading."""
        return self._blob().download_as_bytes()

    def fetch(self, **kwargs) -> pd.DataFrame:
        """Download the blob and parse it as a pandas DataFrame."""
        data = self.fetch_bytes()
        kw: dict[str, Any] = {"sheet_name": self.sheet_name}
        if self.nrows is not None:
            kw["nrows"] = self.nrows
        kw.update(kwargs)
        return pd.read_excel(io.BytesIO(data), **kw)

    def peek(self, n: int = 5) -> pd.DataFrame:
        """Cheap inspection: download the blob and return only the first n rows."""
        return self.fetch(nrows=n)

    def gcs_uri(self) -> str:
        return f"gs://{self.bucket}/{self.blob_path}"


def _default_client(project: str | None = None):
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise SystemExit(
            "google-cloud-storage not installed. Run: pip3 install google-cloud-storage"
        ) from exc
    # storage.Client requires *some* project for billing/quota — even when
    # reading a bucket where the caller already has IAM access. A placeholder
    # works for read-only operations against external buckets.
    return storage.Client(project=project or "dev-placeholder")


def list_blobs(
    bucket:  str,
    prefix:  str = "",
    *,
    suffix:  str | tuple[str, ...] | None = None,
    client                                  = None,
) -> list[str]:
    """List blob paths under a bucket/prefix, optionally filtered by suffix.

    Args:
        bucket: GCS bucket name
        prefix: Object name prefix (e.g. "exports/2026-q1/")
        suffix: Optional suffix or tuple of suffixes to filter by, e.g. ".xlsx"
        client: Injectable storage.Client (for testing)
    """
    if client is None:
        client = _default_client()

    suffixes: tuple[str, ...] | None
    if suffix is None:
        suffixes = None
    elif isinstance(suffix, str):
        suffixes = (suffix.lower(),)
    else:
        suffixes = tuple(s.lower() for s in suffix)

    paths: list[str] = []
    for blob in client.list_blobs(bucket, prefix=prefix):
        if blob.name.endswith("/"):  # skip "directory" placeholders
            continue
        if suffixes and not blob.name.lower().endswith(suffixes):
            continue
        paths.append(blob.name)
    return paths


def download_prefix(
    bucket:  str,
    prefix:  str,
    dest:    "Path | str",
    *,
    suffix:  str | tuple[str, ...] | None = None,
    flatten: bool = True,
    client                                  = None,
) -> list["Path"]:
    """Download every blob under bucket/prefix to a local directory.

    Args:
        bucket:  GCS bucket name
        prefix:  Object name prefix to walk
        dest:    Local directory (created if missing)
        suffix:  Optional suffix filter (e.g. ".csv" or (".csv", ".xlsx"))
        flatten: If True, write `dest/<basename>`. If False, preserve the full
                 prefix-relative path under dest.
        client:  Injectable storage.Client

    Returns:
        List of local Paths actually written.
    """
    from pathlib import Path
    if client is None:
        client = _default_client()
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)

    suffixes: tuple[str, ...] | None
    if suffix is None:
        suffixes = None
    elif isinstance(suffix, str):
        suffixes = (suffix.lower(),)
    else:
        suffixes = tuple(s.lower() for s in suffix)

    written: list[Path] = []
    for blob in client.list_blobs(bucket, prefix=prefix):
        if blob.name.endswith("/"):
            continue
        if suffixes and not blob.name.lower().endswith(suffixes):
            continue
        if flatten:
            local = dest_path / Path(blob.name).name
        else:
            rel   = blob.name[len(prefix):].lstrip("/") if blob.name.startswith(prefix) else blob.name
            local = dest_path / rel
            local.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(local)
        written.append(local)
    return written
