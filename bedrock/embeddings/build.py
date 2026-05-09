"""Build the entity vector index — the inspectable artifact at output/bedrock/entity_index.parquet.

CLI:
    python -m bedrock.embeddings.build                                  # default: hashing provider
    python -m bedrock.embeddings.build --provider local                 # sentence-transformers
    python -m bedrock.embeddings.build --provider voyage                # voyage-3 (needs VOYAGE_API_KEY)
    python -m bedrock.embeddings.build --provider hashing --dim 256
    python -m bedrock.embeddings.build --limit 100                      # smoke-test with 100 entities

Idempotency: re-running with no changes is a no-op. Cache hits skip the embed
call entirely.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional

from bedrock.contracts import CanonicalEntity, EmbeddingPayload
from bedrock.embeddings.cache import EmbeddingCache
from bedrock.embeddings.payload import build_payload
from bedrock.ontology.runtime import OntologyRegistry
from bedrock.registry import StateRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_PATH = REPO_ROOT / "output" / "bedrock" / "entity_index.parquet"
DEFAULT_CACHE_PATH = REPO_ROOT / "output" / "bedrock" / "embeddings_cache.parquet"


def _build_provider(name: str, dim: Optional[int] = None):
    name = name.lower()
    if name == "hashing":
        from bedrock.embeddings.hashing import HashingEmbeddingProvider

        return HashingEmbeddingProvider(dim=dim or 256)
    if name == "local":
        from bedrock.embeddings.local import LocalEmbeddingProvider

        return LocalEmbeddingProvider()
    if name == "voyage":
        from bedrock.embeddings.voyage import VoyageEmbeddingProvider

        return VoyageEmbeddingProvider()
    raise ValueError(f"unknown provider {name!r}; choose hashing|local|voyage")


def _payloads_for_registry(
    state: StateRegistry,
    ontology: OntologyRegistry,
    entity_types: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> Iterable[EmbeddingPayload]:
    n = 0
    for e in state.iter_entities():
        if entity_types and e.entity_type not in entity_types:
            continue
        spec = ontology.entities.get(e.entity_type)
        yield build_payload(e, spec)
        n += 1
        if limit and n >= limit:
            return


def build_index(
    provider_name: str = "hashing",
    dim: Optional[int] = None,
    entity_types: Optional[List[str]] = None,
    limit: Optional[int] = None,
    index_path: Path = DEFAULT_INDEX_PATH,
    cache_path: Path = DEFAULT_CACHE_PATH,
    quiet: bool = False,
) -> dict:
    state = StateRegistry.from_v2_1_json()
    ontology = OntologyRegistry.load(REPO_ROOT / "ontology")
    provider = _build_provider(provider_name, dim=dim)
    cache = EmbeddingCache(cache_path)

    payloads: List[EmbeddingPayload] = list(
        _payloads_for_registry(state, ontology, entity_types, limit)
    )
    n_total = len(payloads)
    if not quiet:
        print(f"[build] entities to index: {n_total}")
        print(f"[build] provider: {provider.model_id} (dim={provider.dim})")

    texts = [p.text for p in payloads]
    cached_vectors = cache.get_many(provider.model_id, texts)
    miss_idx = [i for i, v in enumerate(cached_vectors) if v is None]
    n_hits = n_total - len(miss_idx)
    if not quiet:
        print(f"[build] cache hits: {n_hits} / {n_total} ({100 * n_hits // max(n_total,1)}%)")

    miss_texts = [texts[i] for i in miss_idx]
    if miss_texts:
        if not quiet:
            print(f"[build] embedding {len(miss_texts)} new texts via {provider.model_id}...")
        t0 = time.time()
        new_vectors = provider.embed(miss_texts)
        dt = time.time() - t0
        if not quiet:
            print(f"[build] embedded in {dt:.2f}s ({len(miss_texts) / max(dt, 0.001):.1f} eps)")
        cache.put_many(provider.model_id, list(zip(miss_texts, new_vectors)))
        cache.flush()
        for i, v in zip(miss_idx, new_vectors):
            cached_vectors[i] = v

    # Now everything in cached_vectors is non-None.
    rows = []
    for p, v in zip(payloads, cached_vectors):
        assert v is not None
        facets = p.structured_facets
        rows.append(
            {
                "id": p.payload_id,
                "entity_id": p.payload_id,
                "entity_type": facets.get("entity_type"),
                "vertical": facets.get("vertical", "construction"),
                "confidence": facets.get("confidence", "unknown"),
                "state_version": facets.get("state_version", "v2.1"),
                "retrieval_tags": facets.get("retrieval_tags", []),
                "source_files": facets.get("source_files", []),
                "text_to_embed": p.text,
                "structured_facets": json.dumps(
                    facets, sort_keys=True, default=str
                ),
                "vector": v,
                "vector_dim": len(v),
                "content_hash": p.content_hash,
                "model_id": provider.model_id,
            }
        )

    import pandas as pd

    index_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(index_path, index=False)
    if not quiet:
        print(f"[build] wrote {index_path} ({len(rows)} rows)")

    return {
        "rows_written": len(rows),
        "cache_hits": n_hits,
        "cache_misses": len(miss_idx),
        "model_id": provider.model_id,
        "dim": provider.dim,
        "index_path": str(index_path),
        "cache_path": str(cache_path),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the bedrock entity vector index.")
    parser.add_argument("--provider", default="hashing", choices=["hashing", "local", "voyage"])
    parser.add_argument("--dim", type=int, default=None, help="Hashing-only: vector dim.")
    parser.add_argument(
        "--entity-types",
        nargs="+",
        default=None,
        help="Restrict to one or more entity types (lot, phase, project).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap entity count.")
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    summary = build_index(
        provider_name=args.provider,
        dim=args.dim,
        entity_types=args.entity_types,
        limit=args.limit,
        index_path=args.index_path,
        cache_path=args.cache_path,
        quiet=args.quiet,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
