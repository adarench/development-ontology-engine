"""Reranker — separate stage for re-ordering fused results.

This module exists to lock in the re-ranking seam now, before any specific
implementation lands. A future LLM-based or learned reranker plugs in here
as a new class implementing the Protocol. The orchestrator never branches
on reranker type — it just calls .rerank().
"""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable

from bedrock.contracts import RetrievalHit


@runtime_checkable
class Reranker(Protocol):
    name: str

    def rerank(
        self,
        query: str,
        hits: List[RetrievalHit],
        k: int,
    ) -> List[RetrievalHit]: ...


class NoOpReranker:
    """Default — preserves order, truncates to k. Establishes the seam without doing work."""

    name: str = "noop"

    def rerank(
        self,
        query: str,
        hits: List[RetrievalHit],
        k: int,
    ) -> List[RetrievalHit]:
        return hits[:k]
