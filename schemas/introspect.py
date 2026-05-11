from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import pandas as pd

from schemas.registry import DatasourceField, SourceType


def _pandas_dtype_to_str(dtype) -> str:
    name = str(dtype)
    if name.startswith("int"):       return "int"
    if name.startswith("float"):     return "float"
    if name.startswith("bool"):      return "bool"
    if "datetime" in name:           return "timestamp"
    if "date" in name:               return "date"
    return "string"


def _jsonable(value: Any) -> Any:
    """Coerce a sample value into something JSON-serializable for the registry."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):  # numpy scalars
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def fields_from_dataframe(
    df:           pd.DataFrame,
    *,
    data_source:  str,
    source_type:  SourceType   = "xlsx",
    table_name:   str | None   = None,
    id_prefix:    str | None   = None,
    sample_size:  int          = 3,
) -> list[DatasourceField]:
    """Derive one DatasourceField per column from a sample DataFrame.

    Args:
        df:          The (already-loaded, ideally small) sample DataFrame
        data_source: Stable identifier for the source (e.g. a gs:// URI)
        source_type: Tag carried into the registry (default: "xlsx")
        table_name:  Logical table name (e.g. sheet name or file stem)
        id_prefix:   Override for the registry id prefix; defaults to a slugged
                     form of table_name or data_source
        sample_size: Number of non-null sample values to capture per column
    """
    prefix = id_prefix or _slug(table_name or data_source)
    out: list[DatasourceField] = []
    for col in df.columns:
        series   = df[col]
        non_null = series.dropna()
        samples  = [_jsonable(v) for v in non_null.head(sample_size).tolist()]
        out.append(DatasourceField(
            id            = f"{prefix}.{col}",
            source_type   = source_type,
            data_source   = data_source,
            table_name    = table_name,
            field_name    = str(col),
            data_type     = _pandas_dtype_to_str(series.dtype),
            nullable      = bool(series.isna().any()),
            sample_values = samples,
        ))
    return out


def _slug(text: str) -> str:
    return (
        text.strip()
            .lower()
            .replace("/", "_")
            .replace(" ", "_")
            .replace(":", "")
    )
