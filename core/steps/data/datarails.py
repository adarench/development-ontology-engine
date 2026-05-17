from __future__ import annotations
from pathlib import Path

import pandas as pd

from core.engine.registry import step
from core.steps.data.base import Connector

_DEDUP_KEY_COLS = [
    "entity_name", "posting_date", "account_code", "amount",
    "project_code", "lot", "memo_1", "description", "batch_description",
]
_META_COLS = ["account_name", "account_type"]


class DataRailsConnector(Connector):
    """Reads a DataRails staged GL parquet and returns a deduplicated DataFrame.

    Owns the dr_dedup_key() deduplication logic: DataRails exports multiply
    rows ~2.16× due to internal denormalization. This must run before any
    aggregation. Steps and Tools must not re-apply it.

    Accepts Parquet or CSV (CSV useful for tests/mocks).
    """

    def __init__(self, path: str | Path, entity_filter: str | None = None):
        self.path = Path(path)
        self.entity_filter = entity_filter  # e.g. "Building Construction Partners, LLC"

    def validate(self) -> bool:
        return self.path.exists()

    def fetch(self, **kwargs) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(f"DataRailsConnector: {self.path} not found")

        suffix = self.path.suffix.lower()
        if suffix == ".parquet":
            df = pd.read_parquet(self.path)
        elif suffix == ".csv":
            df = pd.read_csv(self.path, dtype=str)
            if "amount" in df.columns:
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        else:
            raise ValueError(f"DataRailsConnector: unsupported file type '{suffix}'")

        if self.entity_filter and "entity_name" in df.columns:
            df = df[df["entity_name"] == self.entity_filter].copy()

        return self._dedup(df).reset_index(drop=True)

    def _dedup(self, df: pd.DataFrame) -> pd.DataFrame:
        key_cols = [c for c in _DEDUP_KEY_COLS if c in df.columns]
        meta_cols = [c for c in _META_COLS if c in df.columns]
        if not key_cols:
            return df
        df = df.copy()
        if meta_cols:
            df["_meta_score"] = sum(df[c].notna().astype(int) for c in meta_cols)
            df = df.sort_values("_meta_score", ascending=False)
            df = df.drop_duplicates(subset=key_cols, keep="first")
            df = df.drop(columns=["_meta_score"])
        else:
            df = df.drop_duplicates(subset=key_cols, keep="first")
        return df


@step(
    name="fetch_datarails",
    inputs={"path": str, "entity_filter": str},
    outputs={"gl": pd.DataFrame},
    effects=("read",),
    description=(
        "Read a DataRails staged GL parquet/csv; apply the 2.16× "
        "row-multiplication dedup before any aggregation."
    ),
)
def fetch_datarails(path: str, entity_filter: str | None = None) -> dict[str, pd.DataFrame]:
    return {"gl": DataRailsConnector(path, entity_filter=entity_filter).fetch()}
