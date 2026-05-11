from __future__ import annotations
from pathlib import Path

import pandas as pd

from core.connectors.base import Connector

DATE_COLUMNS = [
    "date_created", "date_updated", "date_done", "due_date",
    "start_date", "projected_close_date", "sold_date",
]
BOOL_COLUMNS = ["sold", "closed", "cancelled", "c_of_o"]


class ClickUpConnector(Connector):
    """Reads a ClickUp task CSV export and returns a normalized DataFrame.

    Owns: column name normalization (snake_case), date coercion, boolean
    coercion. Does NOT parse task names into (project, lot, stage) — that
    belongs in LotParseStep.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def validate(self) -> bool:
        if not self.path.exists():
            return False
        df = pd.read_csv(self.path, nrows=1, dtype=str)
        cols = {c.strip().lower().replace(" ", "_") for c in df.columns}
        return "name" in cols

    def fetch(self, **kwargs) -> pd.DataFrame:
        df = pd.read_csv(self.path, dtype=str, keep_default_na=True)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        df = df.dropna(how="all")
        if "name" not in df.columns:
            raise ValueError("ClickUpConnector: input is missing required 'name' column")

        df["name"] = df["name"].astype("string").str.strip()
        df = df[df["name"].notna() & (df["name"].str.len() > 0)].reset_index(drop=True)

        for col in DATE_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce", utc=False)

        for col in BOOL_COLUMNS:
            if col in df.columns:
                df[col] = df[col].apply(_to_bool)

        for col in ["top_level_parent_id", "status", "subdivision", "lot_num"]:
            if col in df.columns:
                df[col] = df[col].astype("string").str.strip()

        return df


def _to_bool(v) -> bool:
    if pd.isna(v):
        return False
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"true", "1", "yes", "y", "t"}
