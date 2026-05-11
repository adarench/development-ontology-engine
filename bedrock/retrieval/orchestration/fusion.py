"""Fuser — combines per-source ranked lists into one unified ranking.

Discipline: the Fuser sees only RetrievalHit objects + their per-source rank.
It never reads `score_components`, never branches on source name to do
source-specific math. Source-specific weighting is configured externally as
a flat dict[source_name -> weight] and applied uniformly.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, runtime_checkable

from bedrock.contracts import RetrievalHit


def hit_identity(h: RetrievalHit) -> str:
    """Stable identifier used to dedupe the same item across sources.

    entity_id wins when present; chunk_id when not; otherwise fall back to
    source+title. Two hits with the same identity from different sources
    fuse into one entry with combined score.
    """
    if h.entity_id:
        return f"E:{h.entity_id}"
    if h.chunk_id:
        return f"C:{h.chunk_id}"
    return f"S:{h.source}::{h.title or ''}"


@runtime_checkable
class Fuser(Protocol):
    name: str

    def fuse(
        self,
        per_source: Dict[str, List[RetrievalHit]],
        k: int,
    ) -> List[RetrievalHit]: ...


class RRFFuser:
    """Reciprocal Rank Fusion with optional per-source weights.

    score(d) = sum over sources s where d appears: weight[s] * 1/(k_constant + rank_s(d))

    k_constant=60 follows the original Cormack 2009 paper. With weights
    defaulting to 1.0, this is plain RRF; setting weights shifts the
    ranking deterministically. The fused hit takes the highest-scoring
    contributor's text/title, unions source_files, and keeps every
    contributor's score_components keyed by `<source>.<key>` so the trace
    layer can inspect what each source contributed.
    """

    name: str = "rrf"

    def __init__(
        self,
        k_constant: int = 60,
        source_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.k_constant = k_constant
        self.source_weights = dict(source_weights or {})

    def fuse(
        self,
        per_source: Dict[str, List[RetrievalHit]],
        k: int,
    ) -> List[RetrievalHit]:
        # rrf score per identity
        rrf_scores: Dict[str, float] = {}
        contributors: Dict[str, List[RetrievalHit]] = {}
        contrib_sources: Dict[str, Dict[str, int]] = {}  # identity -> source -> rank

        for source_name, hits in per_source.items():
            weight = self.source_weights.get(source_name, 1.0)
            for rank, h in enumerate(hits, start=1):
                ident = hit_identity(h)
                contribution = weight / (self.k_constant + rank)
                rrf_scores[ident] = rrf_scores.get(ident, 0.0) + contribution
                contributors.setdefault(ident, []).append(h)
                contrib_sources.setdefault(ident, {})[source_name] = rank

        ranked = sorted(rrf_scores.items(), key=lambda kv: kv[1], reverse=True)

        out: List[RetrievalHit] = []
        for ident, fused_score in ranked[:k]:
            contribs = contributors[ident]
            # Choose the contributor with the highest native score as the canonical
            # text-bearing hit (its title/text/source becomes the public face).
            canon = max(contribs, key=lambda h: h.score)
            # Union source_files preserving order across contributors.
            seen_files: set = set()
            files: List[str] = []
            for h in contribs:
                for f in h.source_files:
                    if f not in seen_files:
                        seen_files.add(f)
                        files.append(f)
            # Aggregate score_components, namespaced by source, plus the rrf delta.
            comp: Dict[str, float] = {}
            for h in contribs:
                for ck, cv in h.score_components.items():
                    comp[f"{h.source}.{ck}"] = float(cv)
            comp["rrf"] = float(fused_score)
            # Track per-source rank contribution for the trace.
            for src, rank in contrib_sources[ident].items():
                comp[f"{src}.rank"] = float(rank)

            # Source label captures every source that voted for this hit.
            sources_present = sorted({h.source for h in contribs})
            out.append(
                RetrievalHit(
                    source="+".join(sources_present),
                    entity_id=canon.entity_id,
                    chunk_id=canon.chunk_id,
                    title=canon.title,
                    text=canon.text,
                    score=fused_score,
                    score_components=comp,
                    matched_aliases=sorted(
                        {a for h in contribs for a in h.matched_aliases}
                    ),
                    source_files=files,
                    confidence=canon.confidence,
                )
            )
        return out
