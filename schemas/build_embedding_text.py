"""Build (or refresh) `embedding_text` for every field in the registry.

`embedding_text` concatenates the most retrieval-relevant signals into a
single string optimized for vector embedding:

  • a header line with the field name, table name, and data type
    (lexical anchors searchable as a unit)
  • the LLM-generated description (data-centric, semantic content)
  • a sample-values line when present (concrete value matching)

The original `description` is left untouched. Re-run this script whenever
descriptions, table names, or sample values change.

Usage:
    python3 -m schemas.build_embedding_text                # build / refresh all
    python3 -m schemas.build_embedding_text --report-only  # show stats only
    python3 -m schemas.build_embedding_text --show 5       # print 5 examples
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from schemas.registry import DEFAULT_REGISTRY_PATH, DatasourceField, SchemaRegistry


def _format_sample(v) -> str:
    """Render a sample value compactly for the embedding text."""
    if isinstance(v, str):
        s = v.strip()
        return f"'{s}'" if s else "''"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def build_embedding_text(f: DatasourceField) -> str:
    """Construct the embedding payload for one field. Pure function."""
    # Header line — high-density anchors at the top so they dominate the embedding.
    header_bits = [f.field_name]
    if f.table_name:
        header_bits.append(f.table_name)
    if f.data_type:
        header_bits.append(f.data_type)
    parts = [" — ".join(header_bits)]

    if f.description:
        parts.append(f.description)
    else:
        parts.append(f"{f.field_name}: (no description available)")

    if f.sample_values:
        sample_strs = [_format_sample(v) for v in f.sample_values]
        parts.append(f"samples: {', '.join(sample_strs)}")

    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", type=Path, default=DEFAULT_REGISTRY_PATH,
                        help="Registry JSON path")
    parser.add_argument("--report-only", action="store_true",
                        help="Compute embedding_text but don't save; just report stats.")
    parser.add_argument("--show", type=int, default=0, metavar="N",
                        help="Print the first N built embedding_text payloads.")
    args = parser.parse_args(argv)

    registry = SchemaRegistry(args.path)
    if len(registry) == 0:
        print(f"Registry at {args.path} is empty.", file=sys.stderr)
        return 0

    char_counts: list[int] = []
    samples_for_show: list[tuple[str, str]] = []  # (id, embedding_text)

    for f in registry:
        text = build_embedding_text(f)
        if not args.report_only:
            f.embedding_text = text
        char_counts.append(len(text))
        if args.show and len(samples_for_show) < args.show:
            samples_for_show.append((f.id, text))

    if not args.report_only:
        registry.save()

    n = len(char_counts)
    avg = sum(char_counts) // n
    print(f"Built embedding_text for {n} fields.", file=sys.stderr)
    print(f"  char length:  min={min(char_counts)}  avg={avg}  max={max(char_counts)}",
          file=sys.stderr)
    print(f"  approx tokens (chars/4):  min={min(char_counts)//4}  avg={avg//4}  "
          f"max={max(char_counts)//4}", file=sys.stderr)
    if args.report_only:
        print("(report-only; registry not modified)", file=sys.stderr)

    for fid, text in samples_for_show:
        print()
        print(f"--- {fid} ---")
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
