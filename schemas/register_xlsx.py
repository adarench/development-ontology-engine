"""Register one or many xlsx files into the schema registry.

Pulls just the first N rows of each sheet, derives one DatasourceField per
column (name, data_type, nullable, sample values), and persists the registry.
Run `enrich_descriptions` afterwards to fill in LLM descriptions.

Two source modes — pick whichever fits the situation:

    # GCS: walk a prefix and register every .xlsx
    python3 -m schemas.register_xlsx --bucket my-bucket --prefix exports/2026-q1/

    # GCS: explicit blobs
    python3 -m schemas.register_xlsx --bucket my-bucket \\
        --blob exports/budget.xlsx --blob exports/tasks.xlsx

    # Local: walk a directory of xlsx files (no GCP auth needed)
    python3 -m schemas.register_xlsx --dir ./data/raw/financials/

    # Either mode, every sheet in every file
    python3 -m schemas.register_xlsx --dir ./data/raw/financials/ --all-sheets

Bucket/prefix can also come from env vars (.env supported):
    GCS_BUCKET=my-bucket
    GCS_PREFIX=exports/2026-q1/
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from core.connectors.gcs import GCSConnector, list_blobs
from schemas.env import load_env
from schemas.introspect import _slug, fields_from_dataframe
from schemas.registry import DEFAULT_REGISTRY_PATH, SchemaRegistry

DEFAULT_HEADER_OVERRIDES_PATH = Path(__file__).parent / "header_overrides.json"


def _load_header_overrides(path: Path | None) -> list[dict]:
    """Returns a list of {'glob': str, 'header': int} entries (or [])."""
    if path is None or not path.exists():
        return []
    import fnmatch  # noqa - keep here to make _header_for_file dep clear
    raw = json.loads(path.read_text())
    return [p for p in raw.get("patterns", []) if "glob" in p and "header" in p]


def _header_for_file(filename: str, overrides: list[dict], sheet: str | None = None) -> int:
    """First matching pattern wins. Returns 0 if no pattern matches.

    A pattern matches when:
        - its `glob` matches the filename, AND
        - if it has a `sheet` field, that field equals the given `sheet` arg.
    For CSVs (sheet=None), patterns with a `sheet` field are skipped.
    """
    import fnmatch
    for entry in overrides:
        if not fnmatch.fnmatch(filename, entry["glob"]):
            continue
        entry_sheet = entry.get("sheet")
        if entry_sheet is None and sheet is None:
            return int(entry["header"])
        if entry_sheet is not None and sheet is not None and entry_sheet == sheet:
            return int(entry["header"])
    return 0


@dataclass
class RegistrationSummary:
    files_processed:  int = 0
    sheets_processed: int = 0
    fields_added:     int = 0
    fields_replaced:  int = 0
    skipped:          list[tuple[str, str]] = field(default_factory=list)


def _read_sheet_names(data: bytes) -> list[str]:
    return pd.ExcelFile(io.BytesIO(data)).sheet_names


def _commit_fields(fields, registry, overwrite, summary):
    for f in fields:
        existed = f.id in registry
        registry.add(f, overwrite=overwrite or existed)
        if existed:
            summary.fields_replaced += 1
        else:
            summary.fields_added += 1
    summary.sheets_processed += 1


def _register_xlsx_bytes(
    data, *, data_source_uri, file_stem, all_sheets, sheet,
    rows, sample_size, registry, overwrite, summary,
    header=0, header_lookup=None,
) -> None:
    """If `header_lookup` is provided, it's called as `header_lookup(sheet_name)`
    and its return value overrides `header` for that sheet."""
    sheet_names = _read_sheet_names(data) if all_sheets else [sheet]
    for sheet_id in sheet_names:
        per_sheet_header = header_lookup(sheet_id) if header_lookup else header
        try:
            df = pd.read_excel(io.BytesIO(data), sheet_name=sheet_id, nrows=rows,
                               header=per_sheet_header)
        except Exception as exc:
            summary.skipped.append((f"{data_source_uri}#{sheet_id}", f"read failed: {exc}"))
            continue

        if all_sheets and len(sheet_names) > 1:
            id_prefix  = f"{_slug(file_stem)}.{_slug(str(sheet_id))}"
            table_name = f"{file_stem}/{sheet_id}"
        else:
            id_prefix  = _slug(file_stem)
            table_name = file_stem

        fields = fields_from_dataframe(
            df,
            data_source = data_source_uri,
            source_type = "xlsx",
            table_name  = table_name,
            id_prefix   = id_prefix,
            sample_size = sample_size,
        )
        _commit_fields(fields, registry, overwrite, summary)


def _register_csv_bytes(
    data, *, data_source_uri, file_stem,
    rows, sample_size, registry, overwrite, summary, header=0,
) -> None:
    try:
        df = pd.read_csv(io.BytesIO(data), nrows=rows, header=header)
    except Exception as exc:
        summary.skipped.append((data_source_uri, f"read failed: {exc}"))
        return

    fields = fields_from_dataframe(
        df,
        data_source = data_source_uri,
        source_type = "csv",
        table_name  = file_stem,
        id_prefix   = _slug(file_stem),
        sample_size = sample_size,
    )
    _commit_fields(fields, registry, overwrite, summary)


def _register_from_bytes(
    data, *, data_source_uri, file_stem, ext, all_sheets, sheet,
    rows, sample_size, registry, overwrite, summary,
    header=0, header_lookup=None,
) -> None:
    """Dispatch on file extension. ext is e.g. '.xlsx' or '.csv'.

    `header_lookup`, if provided, is `lambda sheet_name -> int` for per-sheet
    xlsx headers. Ignored for csv (csv uses `header` directly).
    """
    ext = ext.lower()
    if ext in {".xlsx", ".xls"}:
        _register_xlsx_bytes(
            data, data_source_uri=data_source_uri, file_stem=file_stem,
            all_sheets=all_sheets, sheet=sheet, rows=rows,
            sample_size=sample_size, registry=registry,
            overwrite=overwrite, summary=summary,
            header=header, header_lookup=header_lookup,
        )
    elif ext == ".csv":
        _register_csv_bytes(
            data, data_source_uri=data_source_uri, file_stem=file_stem,
            rows=rows, sample_size=sample_size, registry=registry,
            overwrite=overwrite, summary=summary, header=header,
        )
    else:
        summary.skipped.append((data_source_uri, f"unsupported extension {ext!r}"))


def register_xlsx_blobs(
    *,
    bucket:        str,
    blob_paths:    list[str],
    all_sheets:    bool       = False,
    sheet:         str | int  = 0,
    rows:          int        = 5,
    sample_size:   int        = 3,
    registry_path: Path       = DEFAULT_REGISTRY_PATH,
    overwrite:     bool       = False,
    connector_factory          = None,  # callable(bucket, blob) -> GCSConnector, for tests
) -> RegistrationSummary:
    registry = SchemaRegistry(registry_path)
    summary  = RegistrationSummary()
    for blob_path in blob_paths:
        conn = connector_factory(bucket, blob_path) if connector_factory else GCSConnector(bucket, blob_path)
        try:
            data = conn.fetch_bytes()
        except Exception as exc:
            summary.skipped.append((blob_path, f"download failed: {exc}"))
            continue
        _register_from_bytes(
            data,
            data_source_uri = conn.gcs_uri(),
            file_stem       = Path(blob_path).stem,
            ext             = Path(blob_path).suffix,
            all_sheets      = all_sheets,
            sheet           = sheet,
            rows            = rows,
            sample_size     = sample_size,
            registry        = registry,
            overwrite       = overwrite,
            summary         = summary,
        )
        summary.files_processed += 1
    registry.save()
    return summary


def register_xlsx_local_dir(
    *,
    dir_path:        Path,
    all_sheets:      bool          = False,
    sheet:           str | int     = 0,
    rows:            int           = 5,
    sample_size:     int           = 3,
    registry_path:   Path          = DEFAULT_REGISTRY_PATH,
    overwrite:       bool          = False,
    recursive:       bool          = True,
    only:            list[str] | None = None,   # filename globs to include
    replace:         bool          = False,     # purge existing fields per data_source first
    header_overrides:list[dict] | None = None,
) -> RegistrationSummary:
    import fnmatch
    registry = SchemaRegistry(registry_path)
    summary  = RegistrationSummary()
    SUPPORTED = {".xlsx", ".xls", ".csv"}
    glob = Path(dir_path).rglob if recursive else Path(dir_path).glob
    files = sorted(p for p in glob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    if only:
        files = [p for p in files if any(fnmatch.fnmatch(p.name, pat) for pat in only)]
    overrides = header_overrides or []
    for p in files:
        try:
            data = p.read_bytes()
        except Exception as exc:
            summary.skipped.append((str(p), f"read failed: {exc}"))
            continue
        uri    = p.resolve().as_uri()
        # CSV: pattern matches with sheet=None. xlsx: per-sheet lookup, fallback to None.
        header = _header_for_file(p.name, overrides, sheet=None)
        header_lookup = (lambda sn, name=p.name: _header_for_file(name, overrides, sheet=sn))
        if replace:
            removed = registry.purge_data_source(uri)
            if removed:
                print(f"  purged {removed} field(s) from {p.name}", file=sys.stderr)
        _register_from_bytes(
            data,
            data_source_uri = uri,
            file_stem       = p.stem,
            ext             = p.suffix,
            all_sheets      = all_sheets,
            sheet           = sheet,
            rows            = rows,
            sample_size     = sample_size,
            registry        = registry,
            overwrite       = overwrite,
            summary         = summary,
            header          = header,
            header_lookup   = header_lookup,
        )
        summary.files_processed += 1
    registry.save()
    return summary


def main(argv: list[str] | None = None) -> int:
    load_env()

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dir",        type=Path, default=None,
                        help="Local directory of xlsx files (skips GCS entirely)")
    parser.add_argument("--bucket",     default=os.environ.get("GCS_BUCKET"),
                        help="GCS bucket name (or set GCS_BUCKET env var)")
    parser.add_argument("--blob",       action="append", default=[],
                        help="Object path inside the bucket. Repeatable.")
    parser.add_argument("--prefix",     default=os.environ.get("GCS_PREFIX"),
                        help="Walk this prefix and register every .xlsx found "
                             "(or set GCS_PREFIX env var)")
    parser.add_argument("--all-sheets", action="store_true",
                        help="Register every sheet in each xlsx (default: only --sheet)")
    parser.add_argument("--sheet",      default=0,
                        help="Sheet name or 0-indexed int (ignored if --all-sheets)")
    parser.add_argument("--rows",       type=int, default=5,
                        help="Rows read per sheet for inspection")
    parser.add_argument("--sample-size",type=int, default=3,
                        help="Sample values stored per column")
    parser.add_argument("--path",       type=Path, default=DEFAULT_REGISTRY_PATH,
                        help="Registry JSON path")
    parser.add_argument("--overwrite",  action="store_true",
                        help="Replace fields whose id already exists")
    parser.add_argument("--replace",    action="store_true",
                        help="Before registering each file, drop ALL existing fields with that "
                             "data_source. Use when re-reading with different header rows or "
                             "after column renames — stale field ids would otherwise linger.")
    parser.add_argument("--only",       action="append", default=[],
                        help="Filename glob(s) to include (repeatable). Useful with --dir to "
                             "re-register a subset, e.g. --only '*Collateral Report*.csv'")
    parser.add_argument("--header-overrides", type=Path,
                        default=DEFAULT_HEADER_OVERRIDES_PATH,
                        help="Path to JSON file with per-file header_row overrides "
                             "(default: schemas/header_overrides.json)")
    args = parser.parse_args(argv)

    sheet: str | int = args.sheet
    try:
        sheet = int(sheet)
    except (TypeError, ValueError):
        pass

    if args.dir:
        if not args.dir.exists():
            parser.error(f"--dir {args.dir} does not exist")
        overrides = _load_header_overrides(args.header_overrides)
        summary = register_xlsx_local_dir(
            dir_path         = args.dir,
            all_sheets       = args.all_sheets,
            sheet            = sheet,
            rows             = args.rows,
            sample_size      = args.sample_size,
            registry_path    = args.path,
            overwrite        = args.overwrite,
            only             = args.only or None,
            replace          = args.replace,
            header_overrides = overrides,
        )
    else:
        if not args.bucket:
            parser.error("either --dir or --bucket is required (or set GCS_BUCKET env var)")
        if not args.blob and not args.prefix:
            parser.error("with --bucket, also provide --blob (one or more) and/or --prefix")

        blob_paths = list(args.blob)
        if args.prefix:
            discovered = list_blobs(args.bucket, args.prefix, suffix=(".xlsx", ".xls", ".csv"))
            print(f"Discovered {len(discovered)} xlsx blob(s) under gs://{args.bucket}/{args.prefix}",
                  file=sys.stderr)
            blob_paths.extend(discovered)

        seen = set()
        unique = [b for b in blob_paths if not (b in seen or seen.add(b))]
        if not unique:
            print("No blobs to register.", file=sys.stderr)
            return 0

        summary = register_xlsx_blobs(
            bucket        = args.bucket,
            blob_paths    = unique,
            all_sheets    = args.all_sheets,
            sheet         = sheet,
            rows          = args.rows,
            sample_size   = args.sample_size,
            registry_path = args.path,
            overwrite     = args.overwrite,
        )

    print(
        f"Done. files={summary.files_processed} sheets={summary.sheets_processed} "
        f"added={summary.fields_added} replaced={summary.fields_replaced} "
        f"skipped={len(summary.skipped)} path={args.path}",
        file=sys.stderr,
    )
    for src, reason in summary.skipped:
        print(f"  SKIPPED {src}: {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
