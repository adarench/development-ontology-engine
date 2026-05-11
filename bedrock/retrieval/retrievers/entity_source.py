"""EntitySource — adapter that exposes the Phase 2 EntityRetriever as a uniform Retriever.

Boundary discipline: this file is the ONLY place that knows the EntityRetriever
exists. The orchestrator never imports from bedrock.retrieval.services.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from bedrock.contracts import MetadataFilter, RetrievalHit
from bedrock.retrieval.retrievers.base import Retriever, RetrieverResult, SourceTrace
from bedrock.retrieval.services.entity_retriever import EntityRetriever


class EntitySource:
    """Wraps an existing EntityRetriever; never modifies it.

    Maps the entity-native EntityHit / RetrievalTrace into the uniform
    RetrievalHit / SourceTrace shape. The original RetrievalTrace is
    embedded verbatim under SourceTrace.native_trace.
    """

    name: str = "entity"

    def __init__(self, entity_retriever: EntityRetriever, mode: str = "hybrid") -> None:
        self._inner = entity_retriever
        self._mode = mode

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[MetadataFilter] = None,
        **kwargs: Any,
    ) -> RetrieverResult:
        explain = bool(kwargs.get("explain", True))
        mode = str(kwargs.get("mode", self._mode))

        result = self._inner.retrieve(
            query=query,
            top_k=top_k,
            filters=filters,
            mode=mode,
            explain=explain,
        )

        hits: List[RetrievalHit] = []
        for h in result.hits:
            # Build a short title from the entity instance fields.
            title = _entity_title(h)
            text = _entity_text(h)
            hits.append(
                RetrievalHit(
                    source=self.name,
                    entity_id=h.entity.entity_id,
                    chunk_id=None,
                    title=title,
                    text=text,
                    score=h.combined_score,
                    score_components=dict(h.score_components),
                    matched_aliases=list(h.matched_aliases),
                    source_files=list(h.source_files),
                    confidence=h.confidence,
                )
            )

        notes: List[str] = list(result.trace.notes) + list(result.trace.semantic_warnings)
        native: Dict[str, Any] = result.trace.model_dump(mode="json")

        trace = SourceTrace(
            source_name=self.name,
            query=query,
            top_k=top_k,
            hits_count=len(hits),
            ms_elapsed=result.trace.ms_elapsed,
            notes=notes,
            native_trace=native,
        )
        return RetrieverResult(source_name=self.name, hits=hits, trace=trace)


def _entity_title(hit) -> str:
    e = hit.entity
    fields = e.fields
    if e.entity_type == "lot":
        proj = fields.get("canonical_project") or "?"
        phase = fields.get("canonical_phase") or "?"
        lot = fields.get("canonical_lot_number") or "?"
        stage = fields.get("current_stage") or ""
        return f"Lot {proj}::{phase}::{lot}" + (f" [{stage}]" if stage else "")
    if e.entity_type == "phase":
        proj = fields.get("canonical_project") or "?"
        phase = fields.get("canonical_phase") or "?"
        return f"Phase {proj}::{phase}"
    if e.entity_type == "project":
        proj = fields.get("canonical_project") or "?"
        ent = fields.get("canonical_entity") or ""
        return f"Project {proj}" + (f" ({ent})" if ent else "")
    return f"{e.entity_type} {e.entity_id}"


def _entity_text(hit) -> str:
    """Compact one-line text shown in the unified hit. The full payload text
    lives in the entity index parquet and is implicit via entity_id."""
    title = _entity_title(hit)
    fields = hit.entity.fields
    cost = fields.get("vf_actual_cost_3tuple_usd")
    cost_part = f"; cost=${cost:,.0f}" if isinstance(cost, (int, float)) and cost else ""
    conf_part = f"; conf={hit.confidence}"
    return f"{title}{cost_part}{conf_part}"
