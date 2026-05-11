from __future__ import annotations
from pathlib import Path

import pandas as pd

from core.connectors.base import Connector

# Columns expected in a QuickBooks DataRails export.
REQUIRED_COLUMNS = {
    "Data Type", "Entity", "Account ID", "Account Name",
    "Posting Date", "Amount", "DataMapper_Name",
}
OPTIONAL_COLUMNS = {"Customer", "Vendor", "Memo/Description"}


class QuickBooksConnector(Connector):
    """Reads a QuickBooks GL export (Excel or CSV) and returns a raw DataFrame.

    Owns: file parsing, column presence validation, whitespace normalization on
    string columns. Does NOT apply business logic (entity classification,
    account bucketing) — that belongs in GLCleanStep / GLNormalizeStep.
    """

    def __init__(self, path: str | Path, sheet_name: int | str = 0):
        self.path = Path(path)
        self.sheet_name = sheet_name

    def validate(self) -> bool:
        if not self.path.exists():
            return False
        df = self._read_raw()
        return REQUIRED_COLUMNS.issubset(set(df.columns))

    def fetch(self, **kwargs) -> pd.DataFrame:
        df = self._read_raw()
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"QuickBooksConnector: missing columns {missing}")
        # Normalize string column whitespace so steps receive clean inputs.
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype("string").str.strip()
        return df.reset_index(drop=True)

    def _read_raw(self) -> pd.DataFrame:
        suffix = self.path.suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(self.path, sheet_name=self.sheet_name, dtype=str)
        if suffix == ".csv":
            return pd.read_csv(self.path, dtype=str)
        raise ValueError(f"QuickBooksConnector: unsupported file type '{suffix}'")
