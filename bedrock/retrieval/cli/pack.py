"""CLI: run the orchestrator + packer end-to-end and emit a deterministic ContextPack.

Examples:
    python -m bedrock.retrieval.cli.pack "What is the Harmony 3-tuple correction?"
    python -m bedrock.retrieval.cli.pack "Parkway Fields phase budgets" --budget 2000
    python -m bedrock.retrieval.cli.pack "Harmony lot 101 cost" --top-k 15 --format json --save
    python -m bedrock.retrieval.cli.pack "scope of BCPD" --sources routed entity --no-warnings
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from bedrock.retrieval.orchestration import (
    HybridOrchestrator,
    NoOpReranker,
    RRFFuser,
)
from bedrock.retrieval.packing import as_llm_context, pack
from bedrock.retrieval.retrievers.chunk_source import ChunkSource
from bedrock.retrieval.retrievers.entity_source import EntitySource
from bedrock.retrieval.retrievers.routed_source import RoutedSource
from bedrock.retrieval.services.entity_retriever import default_retriever


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PACK_DIR = REPO_ROOT / "output" / "bedrock" / "packs"


def _gather_warnings_from_trace(trace) -> List[str]:
    """Pull ontology-derived warnings out of per-source traces.

    Entity source emits semantic warnings into its trace notes (e.g.,
    "[lot.cost_to_date] Per-lot actual cost is derived via the v1 VF decoder...").
    The packer doesn't see traces, so we extract warnings here and pass them
    via extra_warnings.
    """
    warnings: List[str] = []
    for src_name, src_trace in trace.per_source.items():
        for n in src_trace.notes:
            # Surface notes that look like warnings (heuristic: bracketed tag
            # or "inferred" / "warning" / "caveat" keywords)
            if (
                n.startswith("[")
                or "inferred" in n.lower()
                or "warning" in n.lower()
                or "caveat" in n.lower()
                or "do not promote" in n.lower()
            ):
                warnings.append(f"[from {src_name}] {n}")
    return warnings


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pack hybrid retrieval results into an LLM-ready ContextPack."
    )
    parser.add_argument("query", type=str)
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Hits to request from the orchestrator before packing.",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=4000,
        help="Token budget for the pack (default: 4000).",
    )
    parser.add_argument(
        "--per-source-top-k",
        type=int,
        default=None,
        help="Per-source top-k passed to the orchestrator.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        choices=["entity", "chunk", "routed"],
        help="Restrict to a subset of sources (default: all 3).",
    )
    parser.add_argument(
        "--format",
        default="markdown",
        choices=["markdown", "json", "raw"],
        help="markdown=LLM-context, json=full pack JSON, raw=both",
    )
    parser.add_argument(
        "--no-warnings",
        action="store_true",
        help="Skip wiring trace warnings into extra_warnings.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help=f"Save the pack to {DEFAULT_PACK_DIR}/pack_<id>.<ext>",
    )
    args = parser.parse_args(argv)

    only = set(args.sources) if args.sources else {"entity", "chunk", "routed"}
    retrievers = []
    if "entity" in only:
        retrievers.append(EntitySource(default_retriever()))
    if "chunk" in only:
        retrievers.append(ChunkSource())
    if "routed" in only:
        retrievers.append(RoutedSource())

    orch = HybridOrchestrator(
        retrievers=retrievers,
        fuser=RRFFuser(),
        reranker=NoOpReranker(),
    )
    res = orch.retrieve(
        query=args.query,
        top_k=args.top_k,
        per_source_top_k=args.per_source_top_k,
        only_sources=args.sources,
    )

    extra_warnings = [] if args.no_warnings else _gather_warnings_from_trace(res.trace)
    p = pack(
        hits=res.hits,
        query=args.query,
        budget_tokens=args.budget,
        extra_warnings=extra_warnings,
    )

    if args.format == "markdown":
        text = as_llm_context(p)
    elif args.format == "json":
        text = json.dumps(p.model_dump(mode="json"), indent=2, default=str)
    else:  # raw
        text = (
            "===== LLM CONTEXT =====\n"
            + as_llm_context(p)
            + "\n\n===== FULL PACK JSON =====\n"
            + json.dumps(p.model_dump(mode="json"), indent=2, default=str)
        )
    print(text)

    if args.save:
        DEFAULT_PACK_DIR.mkdir(parents=True, exist_ok=True)
        ext = "md" if args.format == "markdown" else "json"
        path = DEFAULT_PACK_DIR / f"pack_{p.pack_id}.{ext}"
        path.write_text(text)
        print(f"\n[saved pack to {path}]", file=sys.stderr)
        # Always also write the JSON sidecar for reproducibility.
        json_path = DEFAULT_PACK_DIR / f"pack_{p.pack_id}.json"
        if not json_path.exists():
            json_path.write_text(json.dumps(p.model_dump(mode="json"), indent=2, default=str))
            print(f"[saved JSON sidecar to {json_path}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
