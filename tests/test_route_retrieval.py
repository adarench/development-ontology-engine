"""Tests for the routing rules in financials.qa.llm_eval.route_retrieval.

The two new rules added in the hardening pass (aultf_correction,
harmco_commercial) close eval gaps that prior workflow runs surfaced.
These tests make sure the new rules fire on the right queries, don't
false-positive on adjacent queries, and that the previously-passing rules
still match what they used to.

Run with:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_route_retrieval.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from financials.qa.llm_eval.route_retrieval import (
    RULES,
    RoutingRule,
    matched_rules,
)
from financials.qa.rag_eval.retrieval_index import build_index
from financials.qa.llm_eval.route_retrieval import build_routed_evidence


def _names(question: str) -> list[str]:
    return [r.name for r in matched_rules(question)]


# ---------------------------------------------------------------------------
# Catalog basics — make sure both new rules are present and ordered correctly.
# ---------------------------------------------------------------------------


def test_aultf_correction_rule_exists() -> None:
    names = [r.name for r in RULES]
    assert "aultf_correction" in names


def test_harmco_commercial_rule_exists() -> None:
    names = [r.name for r in RULES]
    assert "harmco_commercial" in names


def test_aultf_correction_fires_before_version_change() -> None:
    """aultf_correction must take routed-chunk priority over version_change
    when both rules match (e.g. 'what changed for AultF')."""
    names = [r.name for r in RULES]
    assert names.index("aultf_correction") < names.index("version_change"), (
        "aultf_correction must be declared before version_change so it wins "
        "the routed-chunk budget on AultF-specific queries."
    )


# ---------------------------------------------------------------------------
# aultf_correction — positive triggers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "What changed for AultF in v2.1?",
        "AultF B-suffix correction overview",
        "Ault Farms B-suffix routing",
        "tell me about AultF SR-suffix lots",
        "AultF SR-suffix meaning",
        "PWFT1 phase routing",
        "explain the 0127B and 0211B routing change",
    ],
)
def test_aultf_correction_fires_on_aultf_specific_queries(question: str) -> None:
    assert "aultf_correction" in _names(question), f"{question!r} did not trigger aultf_correction"


def test_aultf_correction_required_files_include_parkway_and_change_log() -> None:
    rule = next(r for r in RULES if r.name == "aultf_correction")
    files = rule.required_files
    assert any("project_parkway_fields" in f for f in files)
    assert any("v2_0_to_v2_1_change_log" in f for f in files)


# ---------------------------------------------------------------------------
# aultf_correction — must NOT false-positive on generic queries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "What changed from v2.0 to v2.1?",  # version_change only
        "Parkway Fields summary",  # project_parkway_fields only
        "Harmony lot 101 cost",  # harmony_3tuple only
        "scope of BCPD",  # scope_definition only
    ],
)
def test_aultf_correction_does_not_false_positive(question: str) -> None:
    assert "aultf_correction" not in _names(question), (
        f"{question!r} should NOT trigger aultf_correction; got {_names(question)}"
    )


# ---------------------------------------------------------------------------
# harmco_commercial — positive triggers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "What is the total cost on HarmCo and per-lot averages?",
        "Tell me about HarmCo X-X commercial parcels",
        "Are HarmCo commercial pads in residential rollups?",
        "How are commercial parcels handled?",
        "non-residential HarmCo",
        "Harmony commercial — where does cost live?",
        "HarmCo total cost",
    ],
)
def test_harmco_commercial_fires_on_commercial_queries(question: str) -> None:
    assert "harmco_commercial" in _names(question), (
        f"{question!r} did not trigger harmco_commercial; got {_names(question)}"
    )


def test_harmco_commercial_required_files_include_commercial_guardrail() -> None:
    rule = next(r for r in RULES if r.name == "harmco_commercial")
    files = rule.required_files
    assert any("guardrail_commercial_not_residential" in f for f in files)
    assert any("cost_source_commercial_parcels" in f for f in files)


# ---------------------------------------------------------------------------
# harmco_commercial — must NOT false-positive on Harmony residential queries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Harmony lot 101 cost picture",  # harmony_3tuple only
        "What is the Harmony 3-tuple correction?",  # harmony_3tuple only
        "scope of BCPD",
        "Parkway Fields summary",
    ],
)
def test_harmco_commercial_does_not_false_positive(question: str) -> None:
    assert "harmco_commercial" not in _names(question), (
        f"{question!r} should NOT trigger harmco_commercial; got {_names(question)}"
    )


# ---------------------------------------------------------------------------
# Prior rules must keep firing exactly as they used to.
# ---------------------------------------------------------------------------


_PRIOR_RULE_QUERIES = [
    ("scope of BCPD", "scope_definition"),
    ("what changed from v2.0 to v2.1?", "version_change"),
    ("org-wide rollup across all entities", "org_wide"),
    ("range row treatment", "cost_grain"),
    ("Harmony 3-tuple join question", "harmony_3tuple"),
    ("Where does SctLot live?", "sctlot_scattered"),
    ("Parkway Fields phase breakdown", "project_parkway_fields"),
    ("Should I include this in a lot-level margin report?", "reporting_readiness"),
    ("where might reports give false precision", "false_precision"),
    ("I have one hour to review BCPD cost", "review_prioritization"),
    ("Support a pricing decision for active lots", "pricing_release_support"),
    ("prepare me for a 30-minute review meeting", "meeting_prep"),
    ("draft a concise owner update", "executive_update"),
    ("most useful operating questions today", "operating_capabilities"),
    ("are we ready for free-form chat?", "readiness_for_chat"),
    ("what data would improve the next version", "coverage_gaps_next_version"),
]


@pytest.mark.parametrize("question,expected_rule", _PRIOR_RULE_QUERIES)
def test_prior_rule_still_fires(question: str, expected_rule: str) -> None:
    names = _names(question)
    assert expected_rule in names, (
        f"{question!r} should still trigger {expected_rule!r}; got {names}"
    )


# ---------------------------------------------------------------------------
# End-to-end: build_routed_evidence surfaces the expected files for the
# new rules — proves the rules don't just match, they actually deliver chunks.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def idx():
    return build_index()


def test_aultf_correction_surfaces_parkway_chunk(idx) -> None:
    hits, names = build_routed_evidence(idx, "What changed for AultF in v2.1?")
    assert "aultf_correction" in names
    files = {h.chunk.file for h in hits if h.source.startswith("routed:")}
    assert any("project_parkway_fields" in f for f in files), (
        f"AultF query should surface project_parkway_fields chunk; got files: {files}"
    )
    assert any("v2_0_to_v2_1_change_log" in f for f in files), (
        f"AultF query should surface change_log; got files: {files}"
    )


def test_harmco_commercial_surfaces_commercial_guardrail(idx) -> None:
    hits, names = build_routed_evidence(
        idx, "What is the total cost on HarmCo and per-lot averages?"
    )
    assert "harmco_commercial" in names
    files = {h.chunk.file for h in hits if h.source.startswith("routed:")}
    assert any(
        "guardrail_commercial_not_residential" in f for f in files
    ), f"HarmCo query should surface commercial guardrail; got files: {files}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
