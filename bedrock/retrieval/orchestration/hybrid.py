"""HybridOrchestrator — the thin glue layer.

Calls each retriever, hands the per-source hits to the Fuser, then to the
Reranker. Aggregates an OrchestrationTrace from the per-source SourceTraces
verbatim. Never branches on source name to do source-specific work.

Adding a new retriever:
    orchestrator = HybridOrchestrator(retrievers=[entity, chunk, routed, my_new_one])

That's it. The orchestrator does not need to learn anything about the new
source — only that it implements the Retriever Protocol.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from bedrock.contracts import MetadataFilter, RetrievalHit
from bedrock.retrieval.orchestration.fusion import Fuser, RRFFuser
from bedrock.retrieval.orchestration.rerank import NoOpReranker, Reranker
from bedrock.retrieval.orchestration.trace import (
    FusionTrace,
    OrchestrationTrace,
    RerankTrace,
)
from bedrock.retrieval.retrievers.base import Retriever, RetrieverResult


@dataclass
class OrchestrationResult:
    hits: List[RetrievalHit]
    trace: OrchestrationTrace


class HybridOrchestrator:
    """Composes any number of Retrievers via a Fuser and (optional) Reranker."""

    def __init__(
        self,
        retrievers: List[Retriever],
        fuser: Optional[Fuser] = None,
        reranker: Optional[Reranker] = None,
    ) -> None:
        if not retrievers:
            raise ValueError("HybridOrchestrator needs at least one retriever")
        # Detect duplicate source names — the orchestrator keys per-source results by name.
        seen: set = set()
        for r in retrievers:
            if r.name in seen:
                raise ValueError(f"Duplicate Retriever.name {r.name!r}")
            seen.add(r.name)
        self.retrievers = list(retrievers)
        self.fuser: Fuser = fuser or RRFFuser()
        self.reranker: Reranker = reranker or NoOpReranker()

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[MetadataFilter] = None,
        per_source_top_k: Optional[int] = None,
        only_sources: Optional[List[str]] = None,
    ) -> OrchestrationResult:
        t0 = time.time()
        per_source_k = per_source_top_k or max(top_k * 2, 10)

        per_source_results: Dict[str, RetrieverResult] = {}
        sources_used: List[str] = []
        sources_skipped: List[str] = []

        for r in self.retrievers:
            if only_sources is not None and r.name not in only_sources:
                sources_skipped.append(r.name)
                continue
            try:
                res = r.retrieve(
                    query=query,
                    top_k=per_source_k,
                    filters=filters,
                )
            except Exception as e:  # one source failure must not kill the orchestrator
                sources_skipped.append(r.name)
                per_source_results[r.name] = RetrieverResult(
                    source_name=r.name,
                    hits=[],
                    trace=_failure_trace(r.name, query, per_source_k, str(e)),
                )
                continue
            per_source_results[r.name] = res
            sources_used.append(r.name)

        # Fusion: pure function over per-source hits.
        per_source_hits: Dict[str, List[RetrievalHit]] = {
            n: res.hits for n, res in per_source_results.items() if res.hits
        }
        fused = self.fuser.fuse(per_source_hits, k=top_k)

        # Rerank.
        pre_rerank_ids = [_hit_key(h) for h in fused]
        reranked = self.reranker.rerank(query=query, hits=fused, k=top_k)
        post_rerank_ids = [_hit_key(h) for h in reranked]
        order_changed = pre_rerank_ids != post_rerank_ids

        elapsed_ms = (time.time() - t0) * 1000.0

        trace = OrchestrationTrace(
            query=query,
            top_k=top_k,
            sources_used=sources_used,
            sources_skipped=sources_skipped,
            per_source={n: res.trace for n, res in per_source_results.items()},
            fusion=FusionTrace(
                fuser_name=self.fuser.name,
                input_counts={n: len(h) for n, h in per_source_hits.items()},
                output_count=len(fused),
                weights=getattr(self.fuser, "source_weights", {}) or {},
            ),
            rerank=RerankTrace(
                reranker_name=self.reranker.name,
                input_count=len(fused),
                output_count=len(reranked),
                order_changed=order_changed,
            ),
            ms_elapsed=elapsed_ms,
        )
        return OrchestrationResult(hits=reranked, trace=trace)


def _hit_key(h: RetrievalHit) -> str:
    return h.entity_id or h.chunk_id or f"{h.source}::{h.title}"


def _failure_trace(name: str, query: str, top_k: int, err: str):
    from bedrock.retrieval.retrievers.base import SourceTrace

    return SourceTrace(
        source_name=name,
        query=query,
        top_k=top_k,
        hits_count=0,
        ms_elapsed=0.0,
        notes=[f"source raised: {err}"],
        native_trace=None,
    )
