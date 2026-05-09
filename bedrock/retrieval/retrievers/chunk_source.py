"""ChunkSource — adapter over the existing lexical chunk index in financials/qa/rag_eval.

Boundary discipline: this file is the only place that imports from
financials.qa.rag_eval.retrieval_index. The wrapped module is not modified.
"""

from __future__ import annotations

import time
from typing import Any, List, Optional

from bedrock.contracts import MetadataFilter, RetrievalHit
from bedrock.retrieval.retrievers.base import Retriever, RetrieverResult, SourceTrace


class ChunkSource:
    """Lexical retrieval over the 46 agent_chunks_v2_bcpd + ~17 markdown files.

    Filters are intentionally not applied here — the chunk index has no
    entity_type/vertical/confidence facets. Callers needing filtered
    retrieval should use EntitySource. Filter is accepted in the signature
    for Protocol conformance and noted in the trace if non-trivial.
    """

    name: str = "chunk"

    def __init__(self, idx=None) -> None:
        # Lazy build to avoid the ~14-file walk at import time.
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
        from financials.qa.rag_eval.retrieval_index import retrieve as chunk_retrieve
        from financials.qa.rag_eval.retrieval_index import snippet

        t0 = time.time()
        native_hits = chunk_retrieve(self._idx, query, top_k=top_k)
        elapsed = (time.time() - t0) * 1000.0

        hits: List[RetrievalHit] = []
        for h in native_hits:
            chunk = h.chunk
            hits.append(
                RetrievalHit(
                    source=self.name,
                    entity_id=None,
                    chunk_id=chunk.chunk_id,
                    title=chunk.section_title,
                    text=snippet(chunk),
                    score=float(h.score),
                    score_components={"lexical": float(h.score)},
                    matched_aliases=[],
                    source_files=[chunk.file],
                    confidence="static",
                )
            )

        notes: List[str] = []
        if filters is not None and any(
            getattr(filters, k, None)
            for k in (
                "entity_types",
                "verticals",
                "confidences",
                "state_versions",
                "retrieval_tags_any",
                "retrieval_tags_all",
            )
        ):
            notes.append(
                "ChunkSource ignored MetadataFilter: chunk index has no entity facets. "
                "Use EntitySource for filtered retrieval."
            )

        trace = SourceTrace(
            source_name=self.name,
            query=query,
            top_k=top_k,
            hits_count=len(hits),
            ms_elapsed=elapsed,
            notes=notes,
            native_trace={
                "corpus_size": int(self._idx.n()),
                "matched_tokens_per_hit": [
                    list(h.matched_tokens) for h in native_hits
                ],
                "files_in_top_k": sorted({h.chunk.file for h in native_hits}),
            },
        )
        return RetrieverResult(source_name=self.name, hits=hits, trace=trace)
