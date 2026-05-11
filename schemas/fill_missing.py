"""Find every field in the registry that has no description, then fill it.

Use this after a partial enrichment run (e.g. some chunks failed, some
descriptions got dropped during a merge or commit) to backfill only the
fields that are still null. Existing descriptions are left untouched.

Usage:
    python3 -m schemas.fill_missing                    # report, then fill
    python3 -m schemas.fill_missing --report-only      # just print the gap
    python3 -m schemas.fill_missing --limit 50         # cap to first N missing
    python3 -m schemas.fill_missing --table 'Lot Data' # only fill matching tables
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from schemas.enrich_descriptions import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MODEL,
    enrich,
)
from schemas.env import load_env
from schemas.registry import DEFAULT_REGISTRY_PATH, SchemaRegistry


def report_missing(registry_path: Path) -> tuple[int, int, Counter]:
    """Returns (total_fields, missing_count, count_per_table)."""
    registry = SchemaRegistry(registry_path)
    missing  = [f for f in registry if not f.description]
    by_table = Counter(f.table_name or "<no table>" for f in missing)
    return len(registry), len(missing), by_table


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path",  type=Path, default=DEFAULT_REGISTRY_PATH,
                        help="Registry JSON path")
    parser.add_argument("--report-only", action="store_true",
                        help="Print the gap breakdown and exit; do not call the LLM.")
    parser.add_argument("--table", default=None,
                        help="Only fill fields whose table_name contains this substring.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Stop after N descriptions written (test runs).")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Anthropic model ID")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    args = parser.parse_args(argv)

    total, missing, by_table = report_missing(args.path)
    print(f"Registry: {total} fields total, {missing} missing description(s)",
          file=sys.stderr)
    if missing == 0:
        print("Nothing to do.", file=sys.stderr)
        return 0

    print("Missing per table:", file=sys.stderr)
    for tbl, n in by_table.most_common():
        marker = ""
        if args.table and args.table.lower() not in tbl.lower():
            marker = "  (excluded by --table)"
        print(f"  {n:4d}  {tbl}{marker}", file=sys.stderr)

    if args.report_only:
        return 0

    # If --table is set, temporarily set out-of-scope fields' descriptions to a
    # placeholder so enrich() skips them, then restore. This avoids forking
    # enrich()'s logic.
    if args.table:
        registry = SchemaRegistry(args.path)
        excluded = []
        for f in registry:
            if f.description:
                continue
            if args.table.lower() not in (f.table_name or "").lower():
                excluded.append(f.id)
                f.description = "__EXCLUDED__"
        registry.save()
        print(f"Marked {len(excluded)} out-of-scope field(s) as excluded for this run",
              file=sys.stderr)
    else:
        excluded = []

    try:
        updated, skipped, failed = enrich(
            args.path,
            force            = False,
            model            = args.model,
            chunk_size       = args.chunk_size,
            checkpoint_every = args.checkpoint_every,
            limit            = args.limit,
        )
    finally:
        # Restore excluded fields' descriptions to None so they're queued next time.
        if excluded:
            registry = SchemaRegistry(args.path)
            for fid in excluded:
                if fid in registry and registry.get(fid).description == "__EXCLUDED__":
                    registry.get(fid).description = None
            registry.save()
            print(f"Restored {len(excluded)} excluded field(s) to null", file=sys.stderr)

    print(f"Done. updated={updated} skipped={skipped} failed={failed}", file=sys.stderr)

    # Report what's still missing afterward
    _, still_missing, _ = report_missing(args.path)
    print(f"Registry now has {still_missing} field(s) still missing description.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
