"""Phase 3 acceptance tests: orchestration boundaries + fusion + per-source isolation.

Run with:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_hybrid_orchestration.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from bedrock.contracts import MetadataFilter, RetrievalHit
from bedrock.retrieval.orchestration import (
    HybridOrchestrator,
    NoOpReranker,
    OrchestrationTrace,
    RRFFuser,
    Reranker,
)
from bedrock.retrieval.orchestration.fusion import hit_identity
from bedrock.retrieval.orchestration.hybrid import OrchestrationResult
from bedrock.retrieval.retrievers import Retriever, RetrieverResult, SourceTrace
from bedrock.retrieval.retrievers.chunk_source import ChunkSource
from bedrock.retrieval.retrievers.entity_source import EntitySource
from bedrock.retrieval.retrievers.routed_source import RoutedSource
from bedrock.retrieval.services.entity_retriever import default_retriever


# ---------------------------------------------------------------------------
# Fakes — minimal Retriever stubs prove the orchestrator doesn't depend on
# any specific source's internals.
# ---------------------------------------------------------------------------


class _FakeSource:
    def __init__(self, name: str, hits: List[RetrievalHit]) -> None:
        self.name = name
        self._hits = hits

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[MetadataFilter] = None,
        **kwargs: Any,
    ) -> RetrieverResult:
        trace = SourceTrace(
            source_name=self.name,
            query=query,
            top_k=top_k,
            hits_count=len(self._hits[:top_k]),
            ms_elapsed=0.1,
            notes=[f"fake_source({self.name}) returned {len(self._hits)} hits"],
        )
        return RetrieverResult(
            source_name=self.name,
            hits=self._hits[:top_k],
            trace=trace,
        )


class _RaisingSource:
    name: str = "raising"

    def retrieve(self, query, top_k=10, filters=None, **kwargs) -> RetrieverResult:
        raise RuntimeError("simulated source failure")


def _hit(
    entity_id: Optional[str] = None,
    chunk_id: Optional[str] = None,
    source: str = "fake",
    score: float = 1.0,
    title: str = "t",
    text: str = "x",
) -> RetrievalHit:
    return RetrievalHit(
        source=source,
        entity_id=entity_id,
        chunk_id=chunk_id,
        title=title,
        text=text,
        score=score,
        source_files=[f"{source}_file.md"],
    )


# ---------------------------------------------------------------------------
# Boundary discipline: the orchestrator only depends on the Protocol.
# ---------------------------------------------------------------------------


def test_orchestrator_runs_pure_fakes() -> None:
    a = _FakeSource("a", [_hit(entity_id="e1", source="a", score=0.9)])
    b = _FakeSource("b", [_hit(entity_id="e2", source="b", score=0.8)])
    orch = HybridOrchestrator(retrievers=[a, b])
    res = orch.retrieve("query", top_k=5)
    assert {h.entity_id for h in res.hits} == {"e1", "e2"}
    assert res.trace.sources_used == ["a", "b"]


def test_orchestrator_rejects_duplicate_source_names() -> None:
    a = _FakeSource("dup", [])
    a2 = _FakeSource("dup", [])
    with pytest.raises(ValueError, match="Duplicate"):
        HybridOrchestrator(retrievers=[a, a2])


def test_orchestrator_rejects_empty_retrievers() -> None:
    with pytest.raises(ValueError, match="at least one"):
        HybridOrchestrator(retrievers=[])


def test_orchestrator_isolates_source_failure() -> None:
    """A single source raising must not crash the orchestrator — other sources still fire."""
    good = _FakeSource("good", [_hit(entity_id="e1", source="good")])
    bad = _RaisingSource()
    orch = HybridOrchestrator(retrievers=[good, bad])
    res = orch.retrieve("q", top_k=5)
    assert "good" in res.trace.sources_used
    assert "raising" in res.trace.sources_skipped
    # Failure trace is preserved
    assert res.trace.per_source["raising"].notes
    assert "raised" in res.trace.per_source["raising"].notes[0]


def test_only_sources_filters_active_retrievers() -> None:
    a = _FakeSource("a", [_hit(entity_id="e1", source="a")])
    b = _FakeSource("b", [_hit(entity_id="e2", source="b")])
    orch = HybridOrchestrator(retrievers=[a, b])
    res = orch.retrieve("q", top_k=5, only_sources=["a"])
    assert res.trace.sources_used == ["a"]
    assert "b" in res.trace.sources_skipped


def test_per_source_traces_preserved_verbatim() -> None:
    a = _FakeSource("a", [_hit(entity_id="e1", source="a")])
    orch = HybridOrchestrator(retrievers=[a])
    res = orch.retrieve("q", top_k=5)
    # The orchestrator must hand back the exact SourceTrace the source emitted
    assert res.trace.per_source["a"].source_name == "a"
    assert "fake_source(a)" in res.trace.per_source["a"].notes[0]


# ---------------------------------------------------------------------------
# Fusion: RRF math + cross-source dedup.
# ---------------------------------------------------------------------------


def test_hit_identity_prefers_entity_id() -> None:
    h = _hit(entity_id="lot:x", chunk_id="c:y")
    assert hit_identity(h) == "E:lot:x"
    h2 = _hit(entity_id=None, chunk_id="c:y")
    assert hit_identity(h2) == "C:c:y"
    h3 = _hit(entity_id=None, chunk_id=None, source="src", title="title")
    assert hit_identity(h3) == "S:src::title"


def test_rrf_fuses_same_entity_across_sources() -> None:
    """Same entity_id from two sources should appear once with combined score."""
    a_hits = [_hit(entity_id="shared", source="a", score=0.5)]
    b_hits = [_hit(entity_id="shared", source="b", score=0.7)]
    fuser = RRFFuser()
    fused = fuser.fuse({"a": a_hits, "b": b_hits}, k=5)
    assert len(fused) == 1
    # Source label captures both
    assert "a" in fused[0].source and "b" in fused[0].source
    # rrf score = 1/(60+1) + 1/(60+1) ≈ 0.0328
    assert abs(fused[0].score - (1 / 61 + 1 / 61)) < 1e-9
    # Score components carry per-source-namespaced contributions
    assert "a.rank" in fused[0].score_components
    assert "b.rank" in fused[0].score_components
    assert "rrf" in fused[0].score_components


def test_rrf_respects_source_weights() -> None:
    a_hits = [_hit(entity_id="only_in_a", source="a")]
    b_hits = [_hit(entity_id="only_in_b", source="b")]
    fuser = RRFFuser(source_weights={"a": 2.0, "b": 1.0})
    fused = fuser.fuse({"a": a_hits, "b": b_hits}, k=5)
    assert fused[0].entity_id == "only_in_a"
    assert fused[1].entity_id == "only_in_b"
    # 2.0 weight > 1.0 weight → a's hit ranks first
    assert fused[0].score > fused[1].score


def test_rrf_unions_source_files() -> None:
    a = _hit(entity_id="x", source="a")
    a.source_files = ["file_a.md"]
    b = _hit(entity_id="x", source="b")
    b.source_files = ["file_b.md", "file_a.md"]
    fused = RRFFuser().fuse({"a": [a], "b": [b]}, k=5)
    assert set(fused[0].source_files) == {"file_a.md", "file_b.md"}


# ---------------------------------------------------------------------------
# Reranker seam: separable, never collapsed into the orchestrator.
# ---------------------------------------------------------------------------


def test_noop_reranker_preserves_order() -> None:
    hits = [_hit(entity_id=f"e{i}", source="x", score=1.0 / i) for i in range(1, 4)]
    out = NoOpReranker().rerank("q", hits, k=10)
    assert [h.entity_id for h in out] == ["e1", "e2", "e3"]


def test_custom_reranker_changes_order_observed_in_trace() -> None:
    class _ReverseReranker:
        name = "reverse"
        def rerank(self, query, hits, k):
            return list(reversed(hits))[:k]
    a = _FakeSource(
        "a",
        [
            _hit(entity_id="e1", source="a", score=0.9),
            _hit(entity_id="e2", source="a", score=0.8),
            _hit(entity_id="e3", source="a", score=0.7),
        ],
    )
    orch = HybridOrchestrator(retrievers=[a], reranker=_ReverseReranker())
    res = orch.retrieve("q", top_k=3)
    assert res.trace.rerank.reranker_name == "reverse"
    assert res.trace.rerank.order_changed is True
    assert [h.entity_id for h in res.hits] == ["e3", "e2", "e1"]


# ---------------------------------------------------------------------------
# Real adapters — each works in isolation.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_orch() -> HybridOrchestrator:
    return HybridOrchestrator(
        retrievers=[
            EntitySource(default_retriever()),
            ChunkSource(),
            RoutedSource(),
        ]
    )


def test_entity_source_protocol_isinstance() -> None:
    e = EntitySource(default_retriever())
    assert isinstance(e, Retriever)
    assert e.name == "entity"


def test_chunk_source_protocol_isinstance() -> None:
    c = ChunkSource()
    assert isinstance(c, Retriever)
    assert c.name == "chunk"


def test_routed_source_protocol_isinstance() -> None:
    r = RoutedSource()
    assert isinstance(r, Retriever)
    assert r.name == "routed"


def test_chunk_source_returns_chunk_id_hits() -> None:
    res = ChunkSource().retrieve("Harmony 3-tuple", top_k=3)
    assert all(h.chunk_id is not None for h in res.hits)
    assert all(h.entity_id is None for h in res.hits)
    assert all(h.source == "chunk" for h in res.hits)


def test_routed_source_fires_on_known_rule() -> None:
    res = RoutedSource().retrieve("Harmony 3-tuple correction", top_k=8)
    assert res.trace.native_trace is not None
    assert "harmony_3tuple" in res.trace.native_trace.get("matched_rule_names", [])


def test_routed_source_notes_no_filter_support() -> None:
    res = RoutedSource().retrieve(
        "scope of BCPD",
        top_k=3,
        filters=MetadataFilter(entity_types=["lot"]),
    )
    assert any("ignored MetadataFilter" in n for n in res.trace.notes)


# ---------------------------------------------------------------------------
# End-to-end with the real 3-source orchestrator.
# ---------------------------------------------------------------------------


def test_hybrid_engages_all_three_sources(real_orch: HybridOrchestrator) -> None:
    res = real_orch.retrieve("Harmony 3-tuple correction", top_k=10)
    assert set(res.trace.sources_used) == {"entity", "chunk", "routed"}
    # Each source contributed at least one hit pre-fusion
    assert res.trace.fusion.input_counts["entity"] > 0
    assert res.trace.fusion.input_counts["chunk"] > 0
    assert res.trace.fusion.input_counts["routed"] > 0


def test_hybrid_preserves_per_source_native_traces(real_orch: HybridOrchestrator) -> None:
    res = real_orch.retrieve("Parkway Fields", top_k=5)
    # Entity native trace carries score_weights + expanded_terms
    e_trace = res.trace.per_source["entity"].native_trace
    assert e_trace is not None
    assert "score_weights" in e_trace
    # Chunk native trace carries corpus_size
    c_trace = res.trace.per_source["chunk"].native_trace
    assert c_trace is not None
    assert "corpus_size" in c_trace
    # Routed native trace carries matched_rule_names
    r_trace = res.trace.per_source["routed"].native_trace
    assert r_trace is not None
    assert "matched_rule_names" in r_trace


def test_hybrid_fuses_chunk_and_routed_when_they_overlap(real_orch: HybridOrchestrator) -> None:
    """RoutedSource and ChunkSource often vote for the same chunk — fusion must
    merge them into one hit with both source labels."""
    res = real_orch.retrieve("Harmony 3-tuple", top_k=10)
    multi_source_hits = [h for h in res.hits if "+" in h.source]
    assert multi_source_hits, "expected at least one fused multi-source hit"


def test_hybrid_trace_renders_markdown(real_orch: HybridOrchestrator) -> None:
    res = real_orch.retrieve("Parkway Fields lot count", top_k=3)
    md = res.trace.as_markdown()
    assert "# Orchestration Trace" in md
    assert "## Per-source" in md
    assert "## Fusion" in md
    assert "## Rerank" in md
    # Each per-source trace renders its sub-block
    for src in res.trace.sources_used:
        assert f"`{src}`" in md


# ---------------------------------------------------------------------------
# Boundary enforcement check — orchestrator file must NOT import retrievers.
# ---------------------------------------------------------------------------


def test_orchestrator_does_not_import_concrete_sources() -> None:
    """The orchestrator/hybrid.py module should depend only on the base Protocol —
    never on any concrete adapter (entity_source, chunk_source, routed_source).
    """
    src = (REPO / "bedrock" / "retrieval" / "orchestration" / "hybrid.py").read_text()
    for forbidden in (
        "from bedrock.retrieval.retrievers.entity_source",
        "from bedrock.retrieval.retrievers.chunk_source",
        "from bedrock.retrieval.retrievers.routed_source",
        "from bedrock.retrieval.services.entity_retriever",
        "import EntitySource",
        "import ChunkSource",
        "import RoutedSource",
    ):
        assert forbidden not in src, (
            f"orchestrator/hybrid.py imports {forbidden!r} — "
            f"that violates the boundary discipline (it should depend only on "
            f"the Retriever Protocol)."
        )


def test_sources_do_not_import_each_other() -> None:
    """Source adapters must be siblings, never depend on each other's internals."""
    sources_dir = REPO / "bedrock" / "retrieval" / "retrievers"
    for src_path in sources_dir.glob("*_source.py"):
        text = src_path.read_text()
        for sibling in ("entity_source", "chunk_source", "routed_source"):
            sibling_import = f"from bedrock.retrieval.retrievers.{sibling}"
            if sibling in src_path.name:
                continue  # a file can import from itself trivially
            assert sibling_import not in text, (
                f"{src_path.name} imports from {sibling} — sources must stay independent."
            )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
