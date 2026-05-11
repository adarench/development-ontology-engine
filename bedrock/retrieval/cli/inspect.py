"""CLI: inspect what would be retrieved for a query, with full trace.

Examples:
    python -m bedrock.retrieval.cli.inspect "Harmony lot 101 cost"
    python -m bedrock.retrieval.cli.inspect "phase budget variance" --entity-types phase --top-k 5
    python -m bedrock.retrieval.cli.inspect "Parkway Fields lots in vertical" --mode hybrid --explain --save
    python -m bedrock.retrieval.cli.inspect "what is SctLot" --confidences high --format json

Output formats:
    --format markdown   (default) human-readable trace block
    --format json       full RetrievalTrace serialized
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

from bedrock.contracts import MetadataFilter
from bedrock.embeddings.build import DEFAULT_INDEX_PATH
from bedrock.retrieval.services.entity_retriever import default_retriever


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRACE_DIR = REPO_ROOT / "output" / "bedrock" / "traces"


def _build_filter(args) -> Optional[MetadataFilter]:
    has_any = any(
        [
            args.entity_types,
            args.verticals,
            args.confidences,
            args.state_versions,
            args.tags_any,
            args.tags_all,
        ]
    )
    if not has_any:
        return None
    return MetadataFilter(
        entity_types=args.entity_types,
        verticals=args.verticals,
        confidences=args.confidences,
        state_versions=args.state_versions,
        retrieval_tags_any=args.tags_any,
        retrieval_tags_all=args.tags_all,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect retrieval for a query — what would be returned and why."
    )
    parser.add_argument("query", type=str, help="The query string.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--mode", default="hybrid", choices=["lexical", "vector", "hybrid"])
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--format", default="markdown", choices=["markdown", "json"])
    parser.add_argument(
        "--save",
        action="store_true",
        help=f"Write the trace to {DEFAULT_TRACE_DIR} keyed by query hash.",
    )
    parser.add_argument(
        "--no-explain",
        action="store_true",
        help="Skip the candidate window in the trace (faster, smaller output).",
    )
    parser.add_argument("--entity-types", nargs="+", default=None)
    parser.add_argument("--verticals", nargs="+", default=None)
    parser.add_argument("--confidences", nargs="+", default=None)
    parser.add_argument("--state-versions", nargs="+", default=None)
    parser.add_argument("--tags-any", nargs="+", default=None)
    parser.add_argument("--tags-all", nargs="+", default=None)
    args = parser.parse_args(argv)

    if not args.index_path.exists():
        print(
            f"ERROR: index not found at {args.index_path}.\n"
            f"Run: python -m bedrock.embeddings.build",
            file=sys.stderr,
        )
        return 1

    t0 = time.time()
    retriever = default_retriever(index_path=args.index_path)
    setup_ms = (time.time() - t0) * 1000.0

    filters = _build_filter(args)
    result = retriever.retrieve(
        query=args.query,
        top_k=args.top_k,
        filters=filters,
        mode=args.mode,
        explain=not args.no_explain,
    )

    if args.format == "json":
        out = result.trace.model_dump(mode="json")
        out["_setup_ms"] = setup_ms
        out["_hits"] = [
            {
                "entity_id": h.entity.entity_id,
                "entity_type": h.entity.entity_type,
                "combined_score": h.combined_score,
                "score_components": h.score_components,
                "matched_terms": h.matched_terms,
                "matched_aliases": h.matched_aliases,
                "confidence": h.confidence,
                "source_files": h.source_files,
                "fields": h.entity.fields,
            }
            for h in result.hits
        ]
        text = json.dumps(out, indent=2, default=str)
    else:
        text = result.trace.as_markdown()
        text += f"\n## Setup\n- Loaded retriever in {setup_ms:.1f} ms\n"
        text += "\n## Hit Field Snapshots\n\n"
        for h in result.hits:
            facets = {
                k: v
                for k, v in h.entity.fields.items()
                if k
                in (
                    "canonical_project",
                    "canonical_phase",
                    "canonical_lot_number",
                    "current_stage",
                    "vf_actual_cost_3tuple_usd",
                    "lot_count_observed",
                    "phase_count",
                    "lot_count",
                )
            }
            text += f"- `{h.entity.entity_id}` ({h.confidence}) — {facets}\n"

    print(text)

    if args.save:
        DEFAULT_TRACE_DIR.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256(args.query.encode("utf-8")).hexdigest()[:12]
        suffix = "json" if args.format == "json" else "md"
        path = DEFAULT_TRACE_DIR / f"trace_{h}.{suffix}"
        path.write_text(text)
        print(f"\n[saved trace to {path}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
