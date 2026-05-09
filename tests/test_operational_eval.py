"""Phase 5 acceptance tests: assertion primitives, runner aggregation, live eval baseline.

Run with:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_operational_eval.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from bedrock.contracts import (
    ContextPack,
    ContextSection,
    LineageRef,
    RetrievalHit,
)
from bedrock.evaluation.operational import (
    LineageHashesMustMatchDisk,
    MustCarryConfidence,
    MustDistinguishOverlappingNames,
    MustHaveLineageIncluding,
    MustNotPromoteInferredToValidated,
    MustNotReturnEntityIdMatching,
    MustResolveCrosswalk,
    MustReturnEntity,
    MustReturnGuardrailFile,
    MustSurfaceWarning,
    OperationalRunner,
    SCENARIOS,
    by_category,
)
from bedrock.evaluation.operational.report import as_json, as_markdown
from bedrock.evaluation.operational.runner import RunSummary, ScenarioResult
from bedrock.retrieval.orchestration import OrchestrationTrace
from bedrock.retrieval.orchestration.trace import FusionTrace, RerankTrace


# ---------------------------------------------------------------------------
# Helpers — build synthetic packs / traces for assertion tests
# ---------------------------------------------------------------------------


def _hit(
    *,
    entity_id=None,
    chunk_id=None,
    source="x",
    score=1.0,
    title="t",
    text="x",
    files=None,
    confidence="static",
) -> RetrievalHit:
    return RetrievalHit(
        source=source,
        entity_id=entity_id,
        chunk_id=chunk_id,
        title=title,
        text=text,
        score=score,
        source_files=files or ["x.md"],
        confidence=confidence,
    )


def _pack(hits=None, warnings=None, lineage=None) -> ContextPack:
    sections = [
        ContextSection(
            section_kind="evidence",
            title=h.title or "?",
            text=h.text,
            hit=h,
            token_count=10,
        )
        for h in (hits or [])
    ]
    return ContextPack(
        pack_id="test",
        query="q",
        sections=sections,
        lineage=lineage or [],
        semantic_warnings=warnings or [],
        confidence_summary={},
        token_count=sum(s.token_count for s in sections),
        truncated=False,
    )


def _empty_trace() -> OrchestrationTrace:
    return OrchestrationTrace(
        query="q",
        top_k=5,
        sources_used=[],
        sources_skipped=[],
        per_source={},
        fusion=FusionTrace(fuser_name="rrf"),
        rerank=RerankTrace(reranker_name="noop"),
        ms_elapsed=0.0,
    )


# ---------------------------------------------------------------------------
# Inclusion assertions
# ---------------------------------------------------------------------------


def test_must_return_entity_passes_when_present() -> None:
    a = MustReturnEntity(entity_id="lot:x")
    res = a.check("q", [_hit(entity_id="lot:x")], _pack(), _empty_trace())
    assert res.passed


def test_must_return_entity_fails_when_absent() -> None:
    a = MustReturnEntity(entity_id="lot:x")
    res = a.check("q", [_hit(entity_id="lot:y")], _pack(), _empty_trace())
    assert not res.passed
    assert "missing lot:x" in res.message


def test_must_return_guardrail_file_passes_with_substring_match() -> None:
    a = MustReturnGuardrailFile(filename_substring="harmony_3tuple")
    h = _hit(files=["output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md"])
    res = a.check("q", [h], _pack([h]), _empty_trace())
    assert res.passed


def test_must_return_guardrail_file_fails_when_no_match() -> None:
    a = MustReturnGuardrailFile(filename_substring="commercial")
    h = _hit(files=["docs/other.md"])
    res = a.check("q", [h], _pack([h]), _empty_trace())
    assert not res.passed


def test_must_have_lineage_including_passes_for_substring() -> None:
    a = MustHaveLineageIncluding(source_file_substring="vf_lot_code_decoder")
    p = _pack(
        lineage=[
            LineageRef(source_file="data/reports/vf_lot_code_decoder_v1_report.md")
        ]
    )
    res = a.check("q", [], p, _empty_trace())
    assert res.passed


def test_must_distinguish_overlapping_names_catches_collapse() -> None:
    a = MustDistinguishOverlappingNames(
        must_have_all_of=["lot:Harmony::MF1::101", "lot:Harmony::B1::101"]
    )
    # Only one of the two surfaces — collapsed
    res = a.check(
        "q",
        [_hit(entity_id="lot:Harmony::MF1::101")],
        _pack(),
        _empty_trace(),
    )
    assert not res.passed
    assert "lot:Harmony::B1::101" in res.evidence["missing"]


def test_must_distinguish_overlapping_names_passes_when_both_present() -> None:
    a = MustDistinguishOverlappingNames(
        must_have_all_of=["lot:Harmony::MF1::101", "lot:Harmony::B1::101"]
    )
    res = a.check(
        "q",
        [
            _hit(entity_id="lot:Harmony::MF1::101"),
            _hit(entity_id="lot:Harmony::B1::101"),
        ],
        _pack(),
        _empty_trace(),
    )
    assert res.passed


def test_must_resolve_crosswalk_passes_when_canonical_in_text() -> None:
    a = MustResolveCrosswalk(
        source_value="SctLot",
        canonical_substring="Scattered Lots",
    )
    h = _hit(text="SctLot rows belong to Scattered Lots")
    res = a.check("q", [h], _pack([h]), _empty_trace())
    assert res.passed


def test_must_carry_confidence_passes_with_match() -> None:
    a = MustCarryConfidence(entity_id="lot:x", expected="high")
    h = _hit(entity_id="lot:x", confidence="high")
    res = a.check("q", [h], _pack(), _empty_trace())
    assert res.passed


def test_must_carry_confidence_fails_on_mismatch() -> None:
    a = MustCarryConfidence(entity_id="lot:x", expected="high")
    h = _hit(entity_id="lot:x", confidence="low")
    res = a.check("q", [h], _pack(), _empty_trace())
    assert not res.passed


def test_must_carry_confidence_fails_when_entity_missing() -> None:
    a = MustCarryConfidence(entity_id="lot:x", expected="high")
    res = a.check("q", [_hit(entity_id="lot:y", confidence="high")], _pack(), _empty_trace())
    assert not res.passed
    assert "not returned" in res.message


# ---------------------------------------------------------------------------
# Warning / promotion assertions
# ---------------------------------------------------------------------------


def test_must_surface_warning_matches_pattern() -> None:
    a = MustSurfaceWarning(pattern=r"inferred|do not promote")
    p = _pack(warnings=["[lot.cost_to_date] inferred (v1 decoder)"])
    res = a.check("q", [], p, _empty_trace())
    assert res.passed


def test_must_surface_warning_fails_when_no_match() -> None:
    a = MustSurfaceWarning(pattern=r"inferred")
    p = _pack(warnings=["a different warning"])
    res = a.check("q", [], p, _empty_trace())
    assert not res.passed


def test_must_not_promote_inferred_catches_validated_word() -> None:
    """A section text containing 'validated' next to an inferred hit is a promotion bug."""
    h = _hit(entity_id="lot:x", confidence="inferred", text="this cost is validated.")
    p = _pack([h])
    a = MustNotPromoteInferredToValidated()
    res = a.check("q", [h], p, _empty_trace())
    assert not res.passed
    assert "lot:x" in str(res.evidence["offenders"])


def test_must_not_promote_inferred_allows_disclaimer_phrasing() -> None:
    """'not source-owner-validated' must NOT trip the assertion."""
    h = _hit(
        entity_id="lot:x",
        confidence="inferred",
        text="this cost is inferred (not source-owner-validated).",
    )
    p = _pack([h])
    a = MustNotPromoteInferredToValidated()
    res = a.check("q", [h], p, _empty_trace())
    assert res.passed


# ---------------------------------------------------------------------------
# Exclusion assertions
# ---------------------------------------------------------------------------


def test_must_not_return_pattern_catches_offender() -> None:
    a = MustNotReturnEntityIdMatching(pattern=r"^project:Scarlet Ridge$")
    res = a.check(
        "q",
        [_hit(entity_id="project:Scarlet Ridge")],
        _pack(),
        _empty_trace(),
    )
    assert not res.passed


def test_must_not_return_pattern_passes_when_clean() -> None:
    a = MustNotReturnEntityIdMatching(pattern=r"^project:Scarlet Ridge$")
    res = a.check(
        "q",
        [_hit(entity_id="project:Scattered Lots")],
        _pack(),
        _empty_trace(),
    )
    assert res.passed


# ---------------------------------------------------------------------------
# Lineage / staleness
# ---------------------------------------------------------------------------


def test_lineage_hash_passes_on_unmodified_state(tmp_path) -> None:
    f = tmp_path / "one.md"
    f.write_text("hello world")
    import hashlib

    actual = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
    p = _pack(
        lineage=[LineageRef(source_file="one.md", content_hash=actual)],
    )
    a = LineageHashesMustMatchDisk(repo_root=tmp_path)
    res = a.check("q", [], p, _empty_trace())
    assert res.passed


def test_lineage_hash_catches_drift_when_file_changes(tmp_path) -> None:
    f = tmp_path / "one.md"
    f.write_text("hello world")
    p = _pack(
        lineage=[LineageRef(source_file="one.md", content_hash="0000000000000000")],
    )
    a = LineageHashesMustMatchDisk(repo_root=tmp_path)
    res = a.check("q", [], p, _empty_trace())
    assert not res.passed
    assert res.evidence["offenders"][0]["file"] == "one.md"


# ---------------------------------------------------------------------------
# Scenario catalog basics
# ---------------------------------------------------------------------------


def test_scenarios_have_required_categories() -> None:
    cats = {s.category for s in SCENARIOS}
    expected_subset = {
        "overlapping_names",
        "crosswalk",
        "allocation_ambiguity",
        "inferred_caveat",
        "phase_ambiguity",
        "commercial_isolation",
        "canonical_promotion",
        "source_conflict",
        "margin_reconstruction",
        "org_wide_refusal",
        "aultf_b_correction",
        "lineage_integrity",
    }
    assert expected_subset.issubset(cats), f"missing categories: {expected_subset - cats}"


def test_every_scenario_has_narrative_and_assertions() -> None:
    for s in SCENARIOS:
        assert s.narrative.strip(), f"{s.name} missing narrative"
        assert s.query.strip(), f"{s.name} missing query"
        assert s.assertions, f"{s.name} has zero assertions"


def test_by_category_groups_correctly() -> None:
    cats = by_category()
    for cat, items in cats.items():
        for s in items:
            assert s.category == cat


# ---------------------------------------------------------------------------
# Runner aggregation + report shape
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def live_summary() -> RunSummary:
    return OperationalRunner().run()


def test_run_summary_counts_consistent(live_summary: RunSummary) -> None:
    assert live_summary.passed + live_summary.failed == live_summary.total
    assert 0.0 <= live_summary.pass_rate <= 1.0


def test_run_summary_by_category_totals_match(live_summary: RunSummary) -> None:
    total = sum(b["total"] for b in live_summary.by_category().values())
    assert total == live_summary.total


def test_run_summary_assertion_breakdown_nonempty(live_summary: RunSummary) -> None:
    breakdown = live_summary.assertion_breakdown()
    assert breakdown, "expected at least one assertion type to be exercised"
    for name, b in breakdown.items():
        assert b["passed"] + b["failed"] >= 1


def test_report_markdown_contains_narrative_and_verdict(live_summary: RunSummary) -> None:
    md = as_markdown(live_summary)
    assert "# Operational Correctness Eval" in md
    assert "## By category" in md
    assert "## By assertion type" in md
    # First scenario's narrative should appear verbatim (snippet check)
    assert SCENARIOS[0].narrative.split(".")[0][:60] in md


def test_report_json_round_trips(live_summary: RunSummary) -> None:
    import json

    text = as_json(live_summary)
    payload = json.loads(text)
    assert payload["total"] == live_summary.total
    assert payload["passed"] == live_summary.passed
    assert "scenarios" in payload
    assert len(payload["scenarios"]) == live_summary.total


# ---------------------------------------------------------------------------
# Live baseline — the eval is a regression bar, not a green-or-red gate.
# A lower bound prevents a silent system-wide regression that drops everything;
# an upper bound is intentionally NOT enforced — adding new scenarios that
# fail on first run is the eval doing its job.
# ---------------------------------------------------------------------------


BASELINE_MIN_SCENARIOS_PASSED = 6  # locked-in behaviors that must not regress


def test_live_eval_meets_baseline_pass_count(live_summary: RunSummary) -> None:
    """Locks in the current operational-correctness floor.

    If this drops, something regressed in the orchestrator/packer/retrievers.
    If you ADD scenarios that initially fail, that's expected — the eval is
    designed to surface gaps; it doesn't gate green/red on a coverage metric.
    """
    assert live_summary.passed >= BASELINE_MIN_SCENARIOS_PASSED, (
        f"Operational eval regressed: {live_summary.passed} passed (baseline ≥ "
        f"{BASELINE_MIN_SCENARIOS_PASSED}). Failed scenarios: "
        f"{[s.scenario_name for s in live_summary.scenarios if not s.passed]}"
    )


def test_locked_in_scenarios_continue_to_pass(live_summary: RunSummary) -> None:
    """These specific scenarios are known-good and must not regress."""
    locked = {
        "harmony_lot_101_distinct_in_mf1_vs_b1",        # 3-tuple discipline
        "phase_a_ambiguous_across_projects",            # multi-project surface
        "inferred_decoder_must_not_promote_to_validated",  # promotion bug catch
        "lineage_content_hashes_verify_against_disk",   # Phase 4 hashing
        "org_wide_query_must_surface_refusal_guardrail",  # refusal surface
        "dr_and_vf_have_disjoint_semantics_no_silent_combine",  # source guardrails
    }
    by_name = {s.scenario_name: s for s in live_summary.scenarios}
    failed_locked = [n for n in locked if not by_name[n].passed]
    assert not failed_locked, (
        f"Locked-in scenarios regressed: {failed_locked}. "
        f"These are the operational correctness floors — they must not break."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
