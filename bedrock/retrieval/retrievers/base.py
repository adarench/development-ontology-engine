"""Retriever Protocol — the *only* shape the orchestrator depends on.

Each retrieval source (entity, chunk, routed, plus future learned sources) lives
in its own module and implements this Protocol. The orchestrator never reaches
into a source's internals — it only calls .retrieve() and consumes the
returned (hits, trace) pair.

Discipline rules:
1. Sources never import from each other.
2. Sources never share scoring weights, alias tables, or filter logic.
3. The orchestrator never branches on `source.name` to do source-specific work.
4. Adding a source = writing a new adapter module + listing it; nothing else changes.
5. Source traces are preserved verbatim through orchestration (never collapsed).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from bedrock.contracts import MetadataFilter, RetrievalHit


class SourceTrace(BaseModel):
    """Uniform per-source trace. Native trace is preserved as opaque JSON.

    The orchestrator must not interpret `native_trace` — it exists so each
    source can keep its rich diagnostics (e.g., the EntityRetriever's
    expanded_terms, applied_filters, candidate window) without forcing
    shape conformance across very different retrievers.
    """

    source_name: str
    query: str
    top_k: int
    hits_count: int
    ms_elapsed: float
    notes: List[str] = Field(default_factory=list)
    native_trace: Optional[Dict[str, Any]] = None

    def as_markdown(self) -> str:
        out: List[str] = []
        out.append(f"### Source: `{self.source_name}`\n")
        out.append(
            f"- query: {self.query!r}; top_k={self.top_k}; "
            f"hits={self.hits_count}; elapsed={self.ms_elapsed:.1f} ms\n"
        )
        if self.notes:
            out.append("- notes:\n")
            for n in self.notes:
                out.append(f"  - {n}\n")
        if self.native_trace:
            out.append(f"- native trace keys: {sorted(self.native_trace.keys())}\n")
        return "".join(out)


class RetrieverResult(BaseModel):
    """Uniform return shape from any Retriever."""

    source_name: str
    hits: List[RetrievalHit] = Field(default_factory=list)
    trace: SourceTrace


@runtime_checkable
class Retriever(Protocol):
    """The single source-of-truth Protocol every adapter implements.

    `name` must be unique across all retrievers wired into one orchestrator —
    that uniqueness is what lets the orchestrator key per-source results
    cleanly.
    """

    name: str

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[MetadataFilter] = None,
        **kwargs: Any,
    ) -> RetrieverResult: ...
