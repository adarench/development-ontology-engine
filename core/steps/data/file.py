from __future__ import annotations
from pathlib import Path
from typing import Any

import pandas as pd

from core.engine.registry import step
from core.steps.data.base import Connector


class FileConnector(Connector):
    """Reads a local CSV, Parquet, or Excel file.

    Primary use: mock/local data in tests and development. Swap in a real
    connector (QuickBooksConnector, DataRailsConnector, etc.) for production
    without changing downstream steps or tools.
    """

    SUPPORTED = {".csv", ".parquet", ".xlsx", ".xls", ".json"}

    def __init__(self, path: str | Path, **read_kwargs):
        self.path = Path(path)
        self.read_kwargs = read_kwargs

    def validate(self) -> bool:
        return self.path.exists() and self.path.suffix in self.SUPPORTED

    def fetch(self, **kwargs) -> Any:
        if not self.path.exists():
            raise FileNotFoundError(f"FileConnector: {self.path} not found")
        suffix = self.path.suffix.lower()
        kw = {**self.read_kwargs, **kwargs}
        if suffix == ".csv":
            return pd.read_csv(self.path, **kw)
        if suffix == ".parquet":
            return pd.read_parquet(self.path, **kw)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(self.path, **kw)
        if suffix == ".json":
            import json
            return json.loads(self.path.read_text())
        raise ValueError(f"FileConnector: unsupported file type '{suffix}'")


@step(
    name="fetch_file",
    inputs={"path": str},
    outputs={"data": object},
    effects=("read",),
    description=(
        "Read a local CSV / Parquet / Excel / JSON file and return its content "
        "(DataFrame for tabular, parsed object for JSON)."
    ),
)
def fetch_file(path: str) -> dict[str, Any]:
    return {"data": FileConnector(path).fetch()}
