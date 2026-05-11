"""OrchestrationTrace — aggregates per-source SourceTrace artifacts verbatim.

Per the boundary discipline, this trace never collapses or summarizes the
per-source traces. It records what the orchestrator did (which sources fired,
what fuser ran, whether re-ranking changed the order) and embeds each source's
trace under its name.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from bedrock.retrieval.retrievers.base import SourceTrace


class FusionTrace(BaseModel):
    fuser_name: str
    input_counts: Dict[str, int] = Field(default_factory=dict)
    output_count: int = 0
    weights: Dict[str, float] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)


class RerankTrace(BaseModel):
    reranker_name: str
    input_count: int = 0
    output_count: int = 0
    order_changed: bool = False
    notes: List[str] = Field(default_factory=list)


class OrchestrationTrace(BaseModel):
    """Top-level trace. Each per-source trace is preserved unchanged."""

    query: str
    top_k: int
    sources_used: List[str] = Field(default_factory=list)
    sources_skipped: List[str] = Field(default_factory=list)
    per_source: Dict[str, SourceTrace] = Field(default_factory=dict)
    fusion: FusionTrace
    rerank: RerankTrace
    ms_elapsed: float = 0.0
    notes: List[str] = Field(default_factory=list)

    def as_markdown(self) -> str:
        out: List[str] = []
        out.append(f"# Orchestration Trace\n")
        out.append(f"**Query**: {self.query!r}  \n")
        out.append(
            f"**top_k**: {self.top_k} | **elapsed**: {self.ms_elapsed:.1f} ms | "
            f"**sources used**: {self.sources_used}\n"
        )
        if self.sources_skipped:
            out.append(f"**sources skipped**: {self.sources_skipped}\n")

        out.append("\n## Per-source\n\n")
        for name in self.sources_used:
            trace = self.per_source.get(name)
            if trace:
                out.append(trace.as_markdown())
                out.append("\n")

        out.append("## Fusion\n")
        out.append(f"- fuser: `{self.fusion.fuser_name}`\n")
        out.append(f"- input counts: {self.fusion.input_counts}\n")
        out.append(f"- output count: {self.fusion.output_count}\n")
        if self.fusion.weights:
            out.append(f"- weights: {self.fusion.weights}\n")
        for n in self.fusion.notes:
            out.append(f"- note: {n}\n")

        out.append("\n## Rerank\n")
        out.append(f"- reranker: `{self.rerank.reranker_name}`\n")
        out.append(
            f"- input/output: {self.rerank.input_count} → {self.rerank.output_count}\n"
        )
        out.append(f"- order changed: {self.rerank.order_changed}\n")
        for n in self.rerank.notes:
            out.append(f"- note: {n}\n")

        if self.notes:
            out.append("\n## Notes\n")
            for n in self.notes:
                out.append(f"- {n}\n")

        return "".join(out)
