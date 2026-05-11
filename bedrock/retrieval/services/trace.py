"""RetrievalTrace — the explainability artifact emitted by every EntityRetriever.retrieve() call.

Captures enough state to reconstruct *why* each entity ranked where it did:
expanded query terms, applied filters, candidate counts at each stage, top
ranked candidates AND a window of rejected ones, lineage summary, semantic
warnings raised. Serializable to JSON for persistent inspection.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExpansionRecord(BaseModel):
    """One semantic alias expansion applied to a query term."""

    original_term: str
    expansion: str
    source_alias: str
    resolved_to: str


class CandidateInfo(BaseModel):
    """A single candidate considered by the retriever, ranked or not."""

    entity_id: str
    entity_type: str
    rank: int
    in_top_k: bool
    combined_score: float
    score_components: Dict[str, float] = Field(default_factory=dict)
    matched_terms: List[str] = Field(default_factory=list)
    matched_aliases: List[str] = Field(default_factory=list)
    confidence: str = "unknown"
    source_files: List[str] = Field(default_factory=list)


class FilterApplication(BaseModel):
    """One metadata filter clause and the count it pruned."""

    filter: str
    value: Any
    candidates_before: int
    candidates_after: int


class RetrievalTrace(BaseModel):
    """The trace handed back with every retrieval call. Inspectable; serializable."""

    query: str
    mode: str
    top_k: int
    expanded_terms: List[ExpansionRecord] = Field(default_factory=list)
    applied_filters: List[FilterApplication] = Field(default_factory=list)
    candidate_count_initial: int = 0
    candidate_count_after_filters: int = 0
    top_candidates: List[CandidateInfo] = Field(default_factory=list)
    semantic_warnings: List[str] = Field(default_factory=list)
    lineage_summary: Dict[str, List[str]] = Field(default_factory=dict)
    ms_elapsed: float = 0.0
    score_weights: Dict[str, float] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)

    def as_markdown(self) -> str:
        """Render the trace as a human-readable markdown block for inspection."""
        out: List[str] = []
        out.append(f"# Retrieval Trace\n")
        out.append(f"**Query**: {self.query!r}\n")
        out.append(f"**Mode**: `{self.mode}` | **top_k**: {self.top_k} | "
                   f"**elapsed**: {self.ms_elapsed:.1f} ms\n")

        if self.score_weights:
            wstr = ", ".join(f"{k}={v}" for k, v in sorted(self.score_weights.items()))
            out.append(f"**Score weights**: {wstr}\n")

        out.append("\n## Pipeline\n")
        out.append(f"- Initial candidates: **{self.candidate_count_initial}**\n")
        out.append(f"- After filters: **{self.candidate_count_after_filters}**\n")

        if self.expanded_terms:
            out.append("\n## Query Expansion\n")
            for e in self.expanded_terms:
                out.append(f"- `{e.original_term}` → `{e.expansion}` (alias `{e.source_alias}` → `{e.resolved_to}`)\n")

        if self.applied_filters:
            out.append("\n## Applied Filters\n")
            for f in self.applied_filters:
                out.append(
                    f"- `{f.filter} = {f.value}` — pruned "
                    f"{f.candidates_before - f.candidates_after} "
                    f"({f.candidates_before} → {f.candidates_after})\n"
                )

        if self.top_candidates:
            out.append("\n## Ranked Candidates (top + window of rejected)\n\n")
            out.append("| Rank | In top-k | Entity | Score | Components | Conf |\n")
            out.append("|---|---|---|---|---|---|\n")
            for c in self.top_candidates:
                comps = ", ".join(f"{k}={v:.3f}" for k, v in sorted(c.score_components.items()))
                in_k = "✓" if c.in_top_k else "—"
                out.append(
                    f"| {c.rank} | {in_k} | `{c.entity_id}` | {c.combined_score:.3f} | "
                    f"{comps} | {c.confidence} |\n"
                )

        if self.semantic_warnings:
            out.append("\n## Semantic Warnings\n")
            for w in self.semantic_warnings:
                out.append(f"- ⚠ {w}\n")

        if self.lineage_summary:
            out.append("\n## Lineage\n")
            for eid, files in self.lineage_summary.items():
                files_str = ", ".join(f"`{f}`" for f in files)
                out.append(f"- `{eid}` → {files_str}\n")

        if self.notes:
            out.append("\n## Notes\n")
            for n in self.notes:
                out.append(f"- {n}\n")

        return "".join(out)
