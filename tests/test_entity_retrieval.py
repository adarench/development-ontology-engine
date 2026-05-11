"""Phase 2 acceptance tests: entity retrieval correctness, trace artifact, lineage preservation.

Run with:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_entity_retrieval.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from bedrock.contracts import CanonicalEntity, EmbeddingPayload, MetadataFilter
from bedrock.embeddings.build import DEFAULT_INDEX_PATH, build_index
from bedrock.embeddings.cache import EmbeddingCache, cache_key
from bedrock.embeddings.hashing import HashingEmbeddingProvider
from bedrock.embeddings.payload import build_payload
from bedrock.ontology.runtime import OntologyRegistry
from bedrock.registry import StateRegistry
from bedrock.retrieval.services.entity_retriever import (
    EntityRetriever,
    default_retriever,
)
from bedrock.retrieval.services.trace import RetrievalTrace


# ---------------------------------------------------------------------------
# Embedding payload — entity instances are individually discoverable.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ontology() -> OntologyRegistry:
    return OntologyRegistry.load(REPO / "ontology")


@pytest.fixture(scope="module")
def state() -> StateRegistry:
    return StateRegistry.from_v2_1_json()


def test_payload_includes_instance_identifiers(state: StateRegistry, ontology: OntologyRegistry) -> None:
    a_lot = next(state.iter_entities("lot"))
    p = build_payload(a_lot, ontology.entities["lot"])
    # Project, phase, lot number must all appear in the embedded text
    assert a_lot.fields["canonical_project"] in p.text
    assert str(a_lot.fields["canonical_phase"]) in p.text
    # And in the structured facets
    assert p.structured_facets["canonical_project"] == a_lot.fields["canonical_project"]
    assert p.structured_facets["entity_type"] == "lot"


def test_payload_includes_entity_aliases(state: StateRegistry, ontology: OntologyRegistry) -> None:
    a_lot = next(state.iter_entities("lot"))
    p = build_payload(a_lot, ontology.entities["lot"])
    # The 'lot' alias should appear inline so query 'lot' hits the payload
    assert "lot" in p.text.lower()
    aliases = p.structured_facets["aliases"]
    assert any(a == "actual cost" for a in aliases)


def test_payload_content_hash_is_deterministic(state: StateRegistry, ontology: OntologyRegistry) -> None:
    a_lot = next(state.iter_entities("lot"))
    p1 = build_payload(a_lot, ontology.entities["lot"])
    p2 = build_payload(a_lot, ontology.entities["lot"])
    assert p1.content_hash == p2.content_hash


# ---------------------------------------------------------------------------
# Embedding cache — content-addressed, idempotent.
# ---------------------------------------------------------------------------


def test_cache_key_is_stable() -> None:
    k1 = cache_key("hashing-v1-d256", "abc")
    k2 = cache_key("hashing-v1-d256", "abc")
    k3 = cache_key("hashing-v1-d256", "abd")
    assert k1 == k2
    assert k1 != k3


def test_cache_round_trip(tmp_path) -> None:
    cache_path = tmp_path / "cache.parquet"
    cache = EmbeddingCache(cache_path)
    cache.put_many("model-x", [("hello", [1.0, 2.0, 3.0])])
    cache.flush()
    # New instance reads from disk
    cache2 = EmbeddingCache(cache_path)
    assert cache2.get("model-x", "hello") == [1.0, 2.0, 3.0]
    assert cache2.get("model-x", "world") is None


def test_hashing_provider_is_deterministic() -> None:
    p = HashingEmbeddingProvider(dim=64)
    v1 = p.embed(["Harmony lot 101"])
    v2 = p.embed(["Harmony lot 101"])
    assert v1 == v2
    assert len(v1[0]) == 64


# ---------------------------------------------------------------------------
# Index builder — produces an inspectable parquet artifact.
# ---------------------------------------------------------------------------


def test_index_round_trip_with_limit(tmp_path) -> None:
    summary = build_index(
        provider_name="hashing",
        limit=20,
        index_path=tmp_path / "idx.parquet",
        cache_path=tmp_path / "cache.parquet",
        quiet=True,
    )
    assert summary["rows_written"] == 20
    import pandas as pd

    df = pd.read_parquet(tmp_path / "idx.parquet")
    assert len(df) == 20
    assert {"id", "entity_type", "vector", "structured_facets", "content_hash"} <= set(df.columns)


# ---------------------------------------------------------------------------
# EntityRetriever — operational, explainable, lineage-aware.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def retriever() -> EntityRetriever:
    if not DEFAULT_INDEX_PATH.exists():
        # Build a fresh index — Phase 2 needs the full registry indexed for tests
        build_index(provider_name="hashing", quiet=True)
    return default_retriever()


def test_returns_canonical_entity_hits(retriever: EntityRetriever) -> None:
    res = retriever.retrieve("Harmony lot cost", top_k=5)
    assert len(res.hits) > 0
    for h in res.hits:
        assert isinstance(h.entity, CanonicalEntity)
        # The entity_id must match the registry shape
        assert h.entity.entity_id.startswith(("lot:", "phase:", "project:"))


def test_score_components_present_per_hit(retriever: EntityRetriever) -> None:
    res = retriever.retrieve("phase budget variance", top_k=5)
    for h in res.hits:
        # Every hit must expose all four components for explainability
        assert set(h.score_components.keys()) == {
            "lexical",
            "vector",
            "alias_match",
            "metadata_boost",
        }
        assert h.combined_score >= 0


def test_lineage_preserved_per_hit(retriever: EntityRetriever) -> None:
    res = retriever.retrieve("Parkway Fields phase actuals", top_k=3)
    for h in res.hits:
        assert h.source_files, f"{h.entity.entity_id} missing source_files"
        # source_files must round-trip through the trace's lineage_summary
        assert h.entity.entity_id in res.trace.lineage_summary
        assert res.trace.lineage_summary[h.entity.entity_id] == h.source_files


def test_metadata_filter_narrows_candidates(retriever: EntityRetriever) -> None:
    # Without filter
    res_all = retriever.retrieve("phase", top_k=5)
    assert res_all.trace.candidate_count_after_filters == 5576

    # With entity_types=[phase] filter
    res_phase = retriever.retrieve(
        "phase", top_k=5, filters=MetadataFilter(entity_types=["phase"])
    )
    assert res_phase.trace.candidate_count_after_filters == 184  # confirmed via StateRegistry counts
    assert all(h.entity.entity_type == "phase" for h in res_phase.hits)
    # Filter application captured in trace
    assert any(f.filter == "entity_types" for f in res_phase.trace.applied_filters)


def test_3tuple_distinction_preserved_in_results(retriever: EntityRetriever) -> None:
    """v2.1 hard rule: Harmony lot 101 in MF1 vs B1 are different physical assets."""
    res = retriever.retrieve("Harmony lot 101", top_k=20)
    entity_ids = [h.entity.entity_id for h in res.hits]
    # Both 3-tuple variants must appear (and not be collapsed)
    assert "lot:Harmony::MF1::101" in entity_ids
    assert "lot:Harmony::B1::101" in entity_ids


def test_alias_expansion_observable_in_trace(retriever: EntityRetriever) -> None:
    res = retriever.retrieve("actual cost picture for Harmony", top_k=3)
    expansion_terms = [e.original_term for e in res.trace.expanded_terms]
    # 'actual cost' is a registered alias on lot.cost_to_date
    assert "actual cost" in expansion_terms or any(
        "cost" in e.expansion for e in res.trace.expanded_terms
    )


def test_inferred_cost_warning_fires_on_cost_query(retriever: EntityRetriever) -> None:
    res = retriever.retrieve("what is the actual cost for Harmony lot 101", top_k=3)
    # The cost_is_inferred warning must surface
    assert any(
        "inferred" in w.lower() and ("decoder" in w.lower() or "validated" in w.lower())
        for w in res.trace.semantic_warnings
    ), f"No inferred-cost warning surfaced. Got: {res.trace.semantic_warnings}"


def test_trace_top_candidates_include_window(retriever: EntityRetriever) -> None:
    """The trace must show rejected candidates near the cutoff for diagnostics."""
    res = retriever.retrieve("Harmony lot cost", top_k=3)
    in_top_k = [c for c in res.trace.top_candidates if c.in_top_k]
    not_in_top_k = [c for c in res.trace.top_candidates if not c.in_top_k]
    assert len(in_top_k) <= 3
    # We requested trace_window=10 (default), so we should see >0 rejected candidates if any matched
    assert len(not_in_top_k) > 0, "trace did not include the rejected window"


def test_trace_serializes_to_markdown(retriever: EntityRetriever) -> None:
    res = retriever.retrieve("phase budget variance", top_k=3)
    md = res.trace.as_markdown()
    assert "# Retrieval Trace" in md
    assert "Score weights" in md
    assert "Pipeline" in md


def test_trace_serializes_to_json(retriever: EntityRetriever) -> None:
    res = retriever.retrieve("Parkway Fields", top_k=3)
    payload = res.trace.model_dump(mode="json")
    s = json.dumps(payload, default=str)
    rebuilt = RetrievalTrace.model_validate(json.loads(s))
    assert rebuilt.query == res.trace.query
    assert rebuilt.top_k == res.trace.top_k


def test_lexical_only_mode_returns_no_vector_score(retriever: EntityRetriever) -> None:
    res = retriever.retrieve("Harmony lot cost", top_k=3, mode="lexical")
    for h in res.hits:
        assert h.score_components["vector"] == 0.0


def test_unmatchable_query_returns_only_noise_floor(retriever: EntityRetriever) -> None:
    """Hashing provider can't produce a zero-score hit on an unmatched query —
    random hash buckets create ~0.07 cosine noise. The operational signal we
    care about is: zero lexical overlap, zero alias match, zero metadata boost.
    Any 'hit' is pure vector noise that a real embedder (Voyage) would suppress."""
    res = retriever.retrieve("xqwzplkmnbvc1234567890qwerty", top_k=5, mode="hybrid")
    for h in res.hits:
        assert h.score_components["lexical"] == 0.0
        assert h.score_components["alias_match"] == 0.0
        assert h.score_components["metadata_boost"] == 0.0
        assert h.matched_terms == []
        assert h.matched_aliases == []
        # Vector-only score should remain in the noise floor
        assert h.score_components["vector"] < 0.2
    # Lexical-only mode (which a real eval would prefer for high-precision queries)
    # must return zero hits when no token overlaps.
    res_lex = retriever.retrieve("xqwzplkmnbvc1234567890qwerty", top_k=5, mode="lexical")
    assert len(res_lex.hits) == 0
    assert any("No candidates" in n for n in res_lex.trace.notes)


# ---------------------------------------------------------------------------
# Index file integrity — the parquet artifact stays inspectable.
# ---------------------------------------------------------------------------


def test_index_has_5576_rows() -> None:
    if not DEFAULT_INDEX_PATH.exists():
        pytest.skip("entity_index.parquet missing — run `python -m bedrock.embeddings.build`.")
    import pandas as pd

    df = pd.read_parquet(DEFAULT_INDEX_PATH)
    assert len(df) == 5576
    # Every row carries a vector + facets + lineage
    assert df["vector"].notna().all()
    assert df["structured_facets"].notna().all()
    # Type distribution matches StateRegistry counts
    counts = df["entity_type"].value_counts().to_dict()
    assert counts.get("lot") == 5366
    assert counts.get("phase") == 184
    assert counts.get("project") == 26


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
