"""RoutedSource — adapter over the 16 hardcoded routing rules in route_retrieval.py.

Boundary discipline: this file is the only place that imports from
financials.qa.llm_eval.route_retrieval. Routed hits keep the high score boost
the wrapped module assigns (~+1000) so the orchestrator's fuser naturally
keeps them at the top — guardrails always lead, by construction, without
the orchestrator needing to know what 'routed' means.
"""

from __future__ import annotations

import time
from typing import Any, List, Optional

from bedrock.contracts import MetadataFilter, RetrievalHit
from bedrock.retrieval.retrievers.base import Retriever, RetrieverResult, SourceTrace


class RoutedSource:
    """Deterministic routing rules → guardrail-grade chunks for a query."""

    name: str = "routed"

    def __init__(self, idx=None) -> None:
        self._idx = idx
        self._idx_built = idx is not None

    def _ensure_idx(self) -> None:
        if self._idx_built:
            return
        from financials.qa.rag_eval.retrieval_index import build_index

        self._idx = build_index()
        self._idx_built = True

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[MetadataFilter] = None,
        **kwargs: Any,
    ) -> RetrieverResult:
        self._ensure_idx()
        from financials.qa.llm_eval.route_retrieval import build_routed_evidence
        from financials.qa.rag_eval.retrieval_index import snippet

        t0 = time.time()
        routed_hits, rule_names = build_routed_evidence(
            self._idx, query, max_total=top_k
        )
        elapsed = (time.time() - t0) * 1000.0

        hits: List[RetrievalHit] = []
        for h in routed_hits:
            hits.append(
                RetrievalHit(
                    source=h.source,  # "routed:<rule>" or "lexical"
                    entity_id=None,
                    chunk_id=h.chunk.chunk_id,
                    title=h.chunk.section_title,
                    text=snippet(h.chunk),
                    score=float(h.score),
                    score_components={
                        "routed_boost": 1000.0 if h.source.startswith("routed:") else 0.0,
                        "lexical": float(h.score) if h.source == "lexical" else 0.0,
                    },
                    matched_aliases=[],
                    source_files=[h.chunk.file],
                    confidence="static",
                )
            )

        notes: List[str] = []
        if not rule_names:
            notes.append("no routing rule matched; all hits came from lexical fallback")
        if filters is not None:
            notes.append(
                "RoutedSource ignored MetadataFilter: routing operates on the markdown corpus."
            )

        trace = SourceTrace(
            source_name=self.name,
            query=query,
            top_k=top_k,
            hits_count=len(hits),
            ms_elapsed=elapsed,
            notes=notes,
            native_trace={
                "matched_rule_names": rule_names,
                "routed_count": sum(1 for h in routed_hits if h.source.startswith("routed:")),
                "lexical_fallback_count": sum(1 for h in routed_hits if h.source == "lexical"),
                "files_in_top_k": sorted({h.chunk.file for h in routed_hits}),
            },
        )
        return RetrieverResult(source_name=self.name, hits=hits, trace=trace)
