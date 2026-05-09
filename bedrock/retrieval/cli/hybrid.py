"""CLI: run the HybridOrchestrator and dump the per-source + orchestration trace.

Examples:
    python -m bedrock.retrieval.cli.hybrid "What is the Harmony 3-tuple correction?"
    python -m bedrock.retrieval.cli.hybrid "Parkway Fields phase budgets" --top-k 5
    python -m bedrock.retrieval.cli.hybrid "Harmony lot 101" --sources entity routed --format json
    python -m bedrock.retrieval.cli.hybrid "scope of BCPD" --weights entity=0.5 chunk=1.0 routed=2.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from bedrock.contracts import MetadataFilter
from bedrock.retrieval.orchestration import (
    HybridOrchestrator,
    NoOpReranker,
    RRFFuser,
)
from bedrock.retrieval.retrievers.chunk_source import ChunkSource
from bedrock.retrieval.retrievers.entity_source import EntitySource
from bedrock.retrieval.retrievers.routed_source import RoutedSource
from bedrock.retrieval.services.entity_retriever import default_retriever


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRACE_DIR = REPO_ROOT / "output" / "bedrock" / "traces"


def _parse_weights(items: Optional[List[str]]) -> Dict[str, float]:
    if not items:
        return {}
    out: Dict[str, float] = {}
    for raw in items:
        if "=" not in raw:
            raise SystemExit(f"--weights expects name=value, got {raw!r}")
        name, value = raw.split("=", 1)
        out[name.strip()] = float(value)
    return out


def _build_filter(args) -> Optional[MetadataFilter]:
    if not (args.entity_types or args.confidences or args.tags_any):
        return None
    return MetadataFilter(
        entity_types=args.entity_types,
        confidences=args.confidences,
        retrieval_tags_any=args.tags_any,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hybrid retrieval over entity + chunk + routed sources."
    )
    parser.add_argument("query", type=str)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--per-source-top-k", type=int, default=None)
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        choices=["entity", "chunk", "routed"],
        help="Restrict to a subset of sources (default: all 3).",
    )
    parser.add_argument(
        "--weights",
        nargs="+",
        default=None,
        help="Per-source RRF weights, e.g. --weights entity=1.0 chunk=1.0 routed=2.0",
    )
    parser.add_argument("--format", default="markdown", choices=["markdown", "json"])
    parser.add_argument(
        "--save",
        action="store_true",
        help=f"Save the trace to {DEFAULT_TRACE_DIR}/orch_<hash>.<ext>",
    )
    parser.add_argument("--entity-types", nargs="+", default=None)
    parser.add_argument("--confidences", nargs="+", default=None)
    parser.add_argument("--tags-any", nargs="+", default=None)
    args = parser.parse_args(argv)

    weights = _parse_weights(args.weights)

    retrievers = []
    # Build only the sources the user wants — keeps the CLI cheap on partial calls.
    only = set(args.sources) if args.sources else {"entity", "chunk", "routed"}
    if "entity" in only:
        retrievers.append(EntitySource(default_retriever()))
    if "chunk" in only:
        retrievers.append(ChunkSource())
    if "routed" in only:
        retrievers.append(RoutedSource())

    orch = HybridOrchestrator(
        retrievers=retrievers,
        fuser=RRFFuser(source_weights=weights),
        reranker=NoOpReranker(),
    )

    result = orch.retrieve(
        query=args.query,
        top_k=args.top_k,
        filters=_build_filter(args),
        per_source_top_k=args.per_source_top_k,
        only_sources=args.sources,
    )

    if args.format == "json":
        payload: Dict[str, Any] = {
            "trace": result.trace.model_dump(mode="json"),
            "hits": [
                {
                    "rank": i + 1,
                    "source": h.source,
                    "entity_id": h.entity_id,
                    "chunk_id": h.chunk_id,
                    "title": h.title,
                    "score": h.score,
                    "score_components": h.score_components,
                    "source_files": h.source_files,
                    "confidence": h.confidence,
                }
                for i, h in enumerate(result.hits)
            ],
        }
        text = json.dumps(payload, indent=2, default=str)
    else:
        out = [result.trace.as_markdown(), "\n## Final Hits\n\n"]
        out.append("| Rank | Source | Entity / Chunk | Score | Conf |\n")
        out.append("|---|---|---|---|---|\n")
        for i, h in enumerate(result.hits, 1):
            label = h.entity_id or h.chunk_id or "?"
            out.append(
                f"| {i} | {h.source} | `{label}` | {h.score:.4f} | {h.confidence} |\n"
            )
        out.append("\n## Score Components per Hit\n\n")
        for i, h in enumerate(result.hits, 1):
            comps = ", ".join(f"{k}={v:.3f}" for k, v in sorted(h.score_components.items()))
            out.append(f"- **{i}.** `{h.entity_id or h.chunk_id}` — {comps}\n")
        text = "".join(out)

    print(text)

    if args.save:
        DEFAULT_TRACE_DIR.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256(args.query.encode("utf-8")).hexdigest()[:12]
        ext = "json" if args.format == "json" else "md"
        path = DEFAULT_TRACE_DIR / f"orch_{h}.{ext}"
        path.write_text(text)
        print(f"\n[saved orchestration trace to {path}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
