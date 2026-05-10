"""Refresh sample_values by scanning the FULL column instead of the first 5 rows.

Original registration read only N rows (default 5) of each file, so any column
whose leading rows were NaN ended up with empty sample_values. This script
reads each source file/sheet in full, picks up to `--count` distinct non-null
values per column, and rewrites `sample_values` in the registry. After running,
it also rebuilds `embedding_text` so the new samples flow into search payloads.

Usage:
    python3 -m schemas.refresh_samples                   # default: 5 distinct
    python3 -m schemas.refresh_samples --count 8         # 8 distinct samples
    python3 -m schemas.refresh_samples --report-only     # don't save
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd

from schemas.build_embedding_text import build_embedding_text
from schemas.introspect import _jsonable
from schemas.register_xlsx import (
    DEFAULT_HEADER_OVERRIDES_PATH,
    _header_for_file,
    _load_header_overrides,
)
from schemas.registry import DEFAULT_REGISTRY_PATH, DatasourceField, SchemaRegistry


def _file_path_from_uri(uri: str) -> Path | None:
    """Decode a `file://` URI to a local Path. Returns None for non-local URIs."""
    if not uri.startswith("file://"):
        return None
    parsed = urlparse(uri)
    return Path(unquote(parsed.path))


def _sheet_from_table_name(table_name: str | None, file_stem: str) -> str | None:
    """For xlsx with `--all-sheets`, table_name is `<file_stem>/<sheet_name>`.
    Returns the sheet portion, or None for a CSV / single-sheet table."""
    if not table_name:
        return None
    prefix = file_stem + "/"
    if table_name.startswith(prefix):
        return table_name[len(prefix):]
    return None


def _distinct_non_null(series: pd.Series, count: int) -> list:
    """Return up to `count` distinct non-null sample values from a Series.
    Uses `repr` as the dedup key (pandas-friendly, handles dates/numbers)."""
    out: list = []
    seen: set = set()
    for v in series.dropna():
        key = repr(v)
        if key in seen:
            continue
        seen.add(key)
        out.append(_jsonable(v))
        if len(out) >= count:
            break
    return out


def _read_table(path: Path, sheet: str | None, header: int,
                xlsx_cache: dict[Path, pd.ExcelFile]) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, header=header, low_memory=False)
    if suffix in {".xlsx", ".xls"}:
        if path not in xlsx_cache:
            xlsx_cache[path] = pd.ExcelFile(path)
        return pd.read_excel(xlsx_cache[path], sheet_name=sheet or 0, header=header)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def refresh_samples(
    registry: SchemaRegistry,
    *,
    count:    int  = 5,
    overrides: list[dict] | None = None,
    verbose:  bool = True,
) -> dict[str, int]:
    """Mutates `registry` in place. Returns stats dict."""
    overrides = overrides or []

    # Group fields by (file_path, sheet) so we read each table once.
    groups: dict[tuple[Path, str | None], list[DatasourceField]] = defaultdict(list)
    skipped_no_path: list[str] = []
    for f in registry:
        fp = _file_path_from_uri(f.data_source)
        if fp is None:
            skipped_no_path.append(f.id)
            continue
        sheet = _sheet_from_table_name(f.table_name, fp.stem)
        groups[(fp, sheet)].append(f)

    xlsx_cache: dict[Path, pd.ExcelFile] = {}
    stats = {
        "groups": len(groups), "files_read": 0, "fields_total": 0,
        "fields_updated": 0, "fields_unchanged": 0, "fields_missing_column": 0,
        "fields_no_uri": len(skipped_no_path), "files_failed": 0,
    }

    for (fp, sheet), fields in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1] or "")):
        if not fp.exists():
            if verbose:
                print(f"  MISSING FILE  {fp.name}", file=sys.stderr)
            stats["files_failed"] += 1
            continue
        header = _header_for_file(fp.name, overrides, sheet=sheet)
        try:
            df = _read_table(fp, sheet, header, xlsx_cache)
        except Exception as exc:
            if verbose:
                print(f"  FAILED READ   {fp.name}{('#'+sheet) if sheet else ''}: {exc}",
                      file=sys.stderr)
            stats["files_failed"] += 1
            continue
        stats["files_read"] += 1

        updated_in_group = 0
        missing_in_group = 0
        for f in fields:
            stats["fields_total"] += 1
            if f.field_name not in df.columns:
                missing_in_group += 1
                stats["fields_missing_column"] += 1
                continue
            new_samples = _distinct_non_null(df[f.field_name], count)
            if new_samples != f.sample_values:
                f.sample_values = new_samples
                stats["fields_updated"] += 1
                updated_in_group += 1
            else:
                stats["fields_unchanged"] += 1

        if verbose:
            label = f"{fp.name}" + (f" #{sheet}" if sheet else "")
            print(f"  {label}: {len(fields)} field(s), updated={updated_in_group}, "
                  f"missing_col={missing_in_group}", file=sys.stderr)

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path",  type=Path, default=DEFAULT_REGISTRY_PATH,
                        help="Registry JSON path")
    parser.add_argument("--count", type=int, default=5,
                        help="Max distinct samples to collect per column (default 5).")
    parser.add_argument("--header-overrides", type=Path,
                        default=DEFAULT_HEADER_OVERRIDES_PATH,
                        help="Header-row override config (same format as register_xlsx).")
    parser.add_argument("--report-only", action="store_true",
                        help="Compute changes but don't save the registry.")
    parser.add_argument("--no-rebuild-embedding", action="store_true",
                        help="Skip the embedding_text rebuild after sample refresh.")
    args = parser.parse_args(argv)

    overrides = _load_header_overrides(args.header_overrides)
    registry  = SchemaRegistry(args.path)
    print(f"Registry: {len(registry)} field(s)", file=sys.stderr)

    stats = refresh_samples(registry, count=args.count, overrides=overrides)

    print(file=sys.stderr)
    print(f"Stats: {stats}", file=sys.stderr)

    if args.report_only:
        print("(report-only; registry not modified)", file=sys.stderr)
        return 0

    if not args.no_rebuild_embedding:
        for f in registry:
            f.embedding_text = build_embedding_text(f)
        print("Rebuilt embedding_text for all fields.", file=sys.stderr)

    registry.save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
