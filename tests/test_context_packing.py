"""Phase 4 acceptance tests: deterministic packing + lineage + budget + ordering.

Run with:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_context_packing.py -v
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import List

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from bedrock.contracts import ContextPack, RetrievalHit
from bedrock.retrieval.orchestration import HybridOrchestrator, RRFFuser
from bedrock.retrieval.packing import as_llm_context, count_tokens, pack
from bedrock.retrieval.packing.budget import using_tiktoken
from bedrock.retrieval.packing.pack import _classify, _hit_identity_for_sort
from bedrock.retrieval.retrievers.chunk_source import ChunkSource
from bedrock.retrieval.retrievers.entity_source import EntitySource
from bedrock.retrieval.retrievers.routed_source import RoutedSource
from bedrock.retrieval.services.entity_retriever import default_retriever


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


def _hit(
    *,
    entity_id=None,
    chunk_id=None,
    source="x",
    score=1.0,
    title="t",
    text="x" * 100,
    source_files=None,
    confidence="static",
) -> RetrievalHit:
    return RetrievalHit(
        source=source,
        entity_id=entity_id,
        chunk_id=chunk_id,
        title=title,
        text=text,
        score=score,
        source_files=source_files or ["docs/example.md"],
        confidence=confidence,
    )


@pytest.fixture(scope="module")
def real_orch_result():
    orch = HybridOrchestrator(
        retrievers=[
            EntitySource(default_retriever()),
            ChunkSource(),
            RoutedSource(),
        ],
        fuser=RRFFuser(),
    )
    return orch.retrieve(
        "What is the Harmony 3-tuple correction and Harmony lot 101 state?",
        top_k=12,
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_pack_id_is_deterministic_on_identical_input(real_orch_result) -> None:
    p1 = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    p2 = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    assert p1.pack_id == p2.pack_id
    assert p1.token_count == p2.token_count
    assert len(p1.sections) == len(p2.sections)


def test_pack_id_changes_when_query_changes(real_orch_result) -> None:
    p1 = pack(real_orch_result.hits, query="q1", budget_tokens=2000)
    p2 = pack(real_orch_result.hits, query="q2", budget_tokens=2000)
    assert p1.pack_id != p2.pack_id


def test_pack_id_changes_when_budget_changes(real_orch_result) -> None:
    p1 = pack(real_orch_result.hits, query="q", budget_tokens=500)
    p2 = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    assert p1.pack_id != p2.pack_id


def test_section_order_deterministic_with_score_ties() -> None:
    """Three hits with identical scores must order by stable identity tiebreak."""
    hits = [
        _hit(entity_id="lot:z", source="entity", score=0.5, title="z"),
        _hit(entity_id="lot:a", source="entity", score=0.5, title="a"),
        _hit(entity_id="lot:m", source="entity", score=0.5, title="m"),
    ]
    p1 = pack(hits, query="q", budget_tokens=4000)
    p2 = pack(hits, query="q", budget_tokens=4000)
    ids1 = [s.hit.entity_id for s in p1.sections if s.hit]
    ids2 = [s.hit.entity_id for s in p2.sections if s.hit]
    assert ids1 == ids2
    # Tiebreak: identity ascending → a, m, z
    assert ids1 == ["lot:a", "lot:m", "lot:z"]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_classify_guardrail_by_path_marker() -> None:
    h = _hit(
        chunk_id="c1",
        source="chunk",
        source_files=["output/agent_chunks_v2_bcpd/guardrails/guardrail_x.md"],
    )
    assert _classify(h) == "guardrail"


def test_classify_routed_by_source_label() -> None:
    h = _hit(chunk_id="c1", source="routed:my_rule", source_files=["docs/x.md"])
    assert _classify(h) == "routed"


def test_classify_routed_when_multi_source_label_includes_routed() -> None:
    h = _hit(
        chunk_id="c1",
        source="chunk+routed:my_rule",
        source_files=["docs/x.md"],
    )
    assert _classify(h) == "routed"


def test_classify_evidence_for_entity_or_lexical_chunk() -> None:
    e = _hit(entity_id="lot:x", source="entity", source_files=["x.md"])
    c = _hit(chunk_id="c1", source="chunk", source_files=["x.md"])
    assert _classify(e) == "evidence"
    assert _classify(c) == "evidence"


def test_pack_orders_guardrails_before_routed_before_evidence() -> None:
    g = _hit(
        chunk_id="g1",
        source="routed:r",
        score=0.1,
        source_files=["agent_chunks/guardrails/g.md"],
    )
    r = _hit(chunk_id="r1", source="routed:r", score=0.9, source_files=["x.md"])
    e = _hit(entity_id="e1", source="entity", score=0.99, source_files=["x.md"])
    p = pack([e, r, g], query="q", budget_tokens=4000)
    kinds = [s.section_kind for s in p.sections]
    assert kinds == ["guardrail", "routed", "evidence"]


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


def test_budget_enforced_drops_overflow(real_orch_result) -> None:
    # Tiny budget should drop most hits and set truncated=True
    p = pack(real_orch_result.hits, query="q", budget_tokens=300)
    assert p.token_count <= 300
    assert p.truncated is True
    assert len(p.sections) < len(real_orch_result.hits)


def test_budget_not_truncated_when_input_fits() -> None:
    h = _hit(entity_id="x", text="short")
    p = pack([h], query="q", budget_tokens=1000)
    assert p.truncated is False
    assert len(p.sections) == 1


def test_token_count_matches_section_sum(real_orch_result) -> None:
    p = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    assert p.token_count == sum(s.token_count for s in p.sections)


def test_dedup_skips_duplicate_identities() -> None:
    h1 = _hit(entity_id="lot:x", title="t1", text="body")
    h2 = _hit(entity_id="lot:x", title="t2", text="body 2")  # same identity
    p = pack([h1, h2], query="q", budget_tokens=4000)
    # Only one section should land for identity "E:lot:x"
    matching = [s for s in p.sections if s.hit and s.hit.entity_id == "lot:x"]
    assert len(matching) == 1
    # The dedup-skip note should be recorded under the synthetic _pack_notes lineage entry
    notes_entries = [
        ref for ref in p.lineage if ref.source_file == "_pack_notes"
    ]
    assert notes_entries, "expected _pack_notes lineage entry capturing dedup"
    assert any("dedup-skip" in n for n in notes_entries[0].cited_by_facts)


# ---------------------------------------------------------------------------
# Lineage + content-hash verification (round-trip integrity)
# ---------------------------------------------------------------------------


def test_lineage_has_one_entry_per_unique_source_file(real_orch_result) -> None:
    p = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    # Drop the synthetic _pack_notes entry if present
    files = [r.source_file for r in p.lineage if r.source_file != "_pack_notes"]
    assert len(files) == len(set(files)), "lineage has duplicate source_file entries"


def test_lineage_content_hashes_match_disk(real_orch_result) -> None:
    """Every lineage entry whose path exists on disk must carry the actual file's sha256."""
    p = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    for ref in p.lineage:
        if ref.source_file == "_pack_notes":
            continue
        path = REPO / ref.source_file
        if not path.exists():
            # Acceptable for synthetic / virtual sources, but content_hash must be None
            assert ref.content_hash is None
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        assert ref.content_hash == actual, (
            f"content_hash drift for {ref.source_file}: "
            f"pack says {ref.content_hash}, disk says {actual}"
        )


def test_every_section_resolves_into_lineage(real_orch_result) -> None:
    """Every source_file referenced by a section must appear in the lineage manifest."""
    p = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    lineage_files = {r.source_file for r in p.lineage}
    for s in p.sections:
        if not s.hit:
            continue
        for f in s.hit.source_files:
            assert f in lineage_files, f"{f} missing from lineage"


def test_pack_is_internally_reconstructable(real_orch_result) -> None:
    """Given the pack alone, you can identify every fact's source — no external state."""
    p = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    by_file = {r.source_file: r for r in p.lineage if r.source_file != "_pack_notes"}
    for s in p.sections:
        if not s.hit:
            continue
        ident = _hit_identity_for_sort(s.hit)
        for f in s.hit.source_files:
            ref = by_file[f]
            assert ident in ref.cited_by_facts, (
                f"section identity {ident} cites {f} but lineage entry doesn't list it back"
            )


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def test_inferred_confidence_auto_warning_fires() -> None:
    h = _hit(entity_id="lot:x", confidence="inferred")
    p = pack([h], query="q", budget_tokens=4000)
    assert any("inferred" in w.lower() for w in p.semantic_warnings)


def test_low_confidence_auto_warning_fires() -> None:
    h = _hit(entity_id="lot:x", confidence="low")
    p = pack([h], query="q", budget_tokens=4000)
    assert any("low-confidence" in w for w in p.semantic_warnings)


def test_extra_warnings_appended_after_auto() -> None:
    h = _hit(entity_id="lot:x", confidence="inferred")
    p = pack(
        [h],
        query="q",
        budget_tokens=4000,
        extra_warnings=["[manual] do not cite without sign-off"],
    )
    assert any("manual" in w for w in p.semantic_warnings)
    assert any("inferred" in w.lower() for w in p.semantic_warnings)


def test_no_llm_in_packing_path() -> None:
    """Spot-check: the packing module imports nothing from anthropic/openai/voyage.

    This is a guard against future additions accidentally introducing an LLM
    decision into the deterministic packing layer.
    """
    pack_src = (REPO / "bedrock" / "retrieval" / "packing" / "pack.py").read_text()
    render_src = (REPO / "bedrock" / "retrieval" / "packing" / "render.py").read_text()
    budget_src = (REPO / "bedrock" / "retrieval" / "packing" / "budget.py").read_text()
    for forbidden in ("anthropic", "openai", "voyageai", "litellm"):
        assert forbidden not in pack_src
        assert forbidden not in render_src
        assert forbidden not in budget_src


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------


def test_count_tokens_returns_positive_for_nonempty() -> None:
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0


def test_count_tokens_grows_with_input() -> None:
    short = count_tokens("hello")
    long = count_tokens("hello " * 100)
    assert long > short


def test_count_tokens_works_without_tiktoken_warning() -> None:
    # Just make sure both paths return integers (the fallback heuristic)
    assert isinstance(count_tokens("anything"), int)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def test_render_includes_pack_id_and_query(real_orch_result) -> None:
    p = pack(real_orch_result.hits, query="myquery", budget_tokens=2000)
    md = as_llm_context(p)
    assert p.pack_id in md
    assert "myquery" in md


def test_render_orders_sections_guardrail_first(real_orch_result) -> None:
    p = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    md = as_llm_context(p)
    if any(s.section_kind == "guardrail" for s in p.sections):
        guardrail_idx = md.find("## Guardrails")
        evidence_idx = md.find("## Evidence")
        if guardrail_idx >= 0 and evidence_idx >= 0:
            assert guardrail_idx < evidence_idx


def test_render_includes_lineage_with_hashes(real_orch_result) -> None:
    p = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    md = as_llm_context(p)
    assert "Lineage Manifest" in md
    # Every lineage entry's sha256 should appear in the rendered table
    for ref in p.lineage:
        if ref.content_hash:
            assert ref.content_hash in md


def test_render_is_deterministic(real_orch_result) -> None:
    p = pack(real_orch_result.hits, query="q", budget_tokens=2000)
    md1 = as_llm_context(p)
    md2 = as_llm_context(p)
    assert md1 == md2


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


def test_pack_with_no_hits_produces_valid_empty_pack() -> None:
    p = pack([], query="q", budget_tokens=1000)
    assert isinstance(p, ContextPack)
    assert len(p.sections) == 0
    assert p.token_count == 0
    assert p.truncated is False
    assert p.pack_id  # still has a deterministic id


def test_pack_handles_missing_source_files_gracefully() -> None:
    h = _hit(entity_id="x", source_files=["does/not/exist.md"])
    p = pack([h], query="q", budget_tokens=4000)
    # Lineage entry exists but content_hash is None (file not found)
    refs = [r for r in p.lineage if r.source_file == "does/not/exist.md"]
    assert len(refs) == 1
    assert refs[0].content_hash is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
