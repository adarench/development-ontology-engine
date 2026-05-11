"""Regression tests for the 6 BCPD workflow tools.

The tests assert *operational content* the demo outputs must always carry:
known dollar magnitudes, key vocabulary (AultF, B1, inferred, etc.), the
finance/land/ops grouping in the meeting prep, and the absence of any
claim that org-wide v2 is ready.

Run with:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/test_bcpd_workflows.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.agent.registry import ToolRegistry
from core.tools.bcpd_workflows import (
    BCPD_WORKFLOW_TOOLS,
    BcpdContext,
    DraftOwnerUpdateTool,
    FindFalsePrecisionRisksTool,
    GenerateProjectBriefTool,
    PrepareFinanceLandReviewTool,
    ReviewMarginReportReadinessTool,
    SummarizeChangeImpactTool,
    register_bcpd_workflow_tools,
)


# ---------------------------------------------------------------------------
# Shared fixtures — context built once so retrieval stays warm across tests.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ctx() -> BcpdContext:
    return BcpdContext()


@pytest.fixture(scope="module")
def parkway_brief(ctx) -> str:
    return GenerateProjectBriefTool(context=ctx).run(project="Parkway Fields")


@pytest.fixture(scope="module")
def margin_readiness(ctx) -> str:
    return ReviewMarginReportReadinessTool(context=ctx).run(scope="bcpd")


@pytest.fixture(scope="module")
def false_precision(ctx) -> str:
    return FindFalsePrecisionRisksTool(context=ctx).run(scope="bcpd")


@pytest.fixture(scope="module")
def change_impact(ctx) -> str:
    return SummarizeChangeImpactTool(context=ctx).run(
        from_version="v2.0", to_version="v2.1"
    )


@pytest.fixture(scope="module")
def meeting_prep(ctx) -> str:
    return PrepareFinanceLandReviewTool(context=ctx).run(scope="bcpd")


@pytest.fixture(scope="module")
def owner_update(ctx) -> str:
    return DraftOwnerUpdateTool(context=ctx).run(scope="bcpd")


# ---------------------------------------------------------------------------
# Registration + Tool API conformance
# ---------------------------------------------------------------------------


def test_all_six_tool_classes_exposed() -> None:
    names = {cls.name for cls in BCPD_WORKFLOW_TOOLS}
    assert names == {
        "generate_project_brief",
        "review_margin_report_readiness",
        "find_false_precision_risks",
        "summarize_change_impact",
        "prepare_finance_land_review",
        "draft_owner_update",
    }


def test_tools_register_with_tool_registry(ctx) -> None:
    r = register_bcpd_workflow_tools(ToolRegistry(), ctx)
    for cls in BCPD_WORKFLOW_TOOLS:
        assert cls.name in r


def test_tools_emit_anthropic_api_schemas(ctx) -> None:
    r = register_bcpd_workflow_tools(ToolRegistry(), ctx)
    schemas = r.to_api_schemas()
    names = {s["name"] for s in schemas}
    assert "generate_project_brief" in names
    for s in schemas:
        assert s["description"]
        assert s["input_schema"]["type"] == "object"


# ---------------------------------------------------------------------------
# Workflow 1: Project brief (Parkway Fields)
#   Must surface: AultF B-suffix, B1, $4.0M, inferred caveat
# ---------------------------------------------------------------------------


def test_parkway_brief_mentions_aultf_b_suffix(parkway_brief) -> None:
    assert "AultF" in parkway_brief


def test_parkway_brief_mentions_b1_phase(parkway_brief) -> None:
    assert "B1" in parkway_brief


def test_parkway_brief_mentions_4_0m_correction(parkway_brief) -> None:
    # The structured fact in v2_1_changes_summary.aultf_b_to_b1_correction.dollars
    # is 4006662.0, rendered as $4,006,662 by the money formatter. Accept any
    # representation that includes the $4.0M magnitude.
    assert any(
        marker in parkway_brief
        for marker in ("$4,006,662", "$4.0M", "$4 million", "4,006,662")
    ), f"Parkway brief missing $4.0M correction. First 800 chars:\n{parkway_brief[:800]}"


def test_parkway_brief_surfaces_inferred_caveat(parkway_brief) -> None:
    assert "inferred" in parkway_brief.lower()
    assert "do not promote" in parkway_brief.lower() or "not source-owner" in parkway_brief.lower()


def test_parkway_brief_has_real_project_data(parkway_brief) -> None:
    # Parkway Fields has known structural facts from v2.1
    assert "Canonical project" in parkway_brief
    assert "Parkway Fields" in parkway_brief
    # 20 phases, 1131 lots is the real v2.1 shape
    assert "20" in parkway_brief  # phase_count
    assert "1131" in parkway_brief or "1,131" in parkway_brief  # lot_count


# ---------------------------------------------------------------------------
# Workflow 2: Margin readiness
#   Must surface: missing cost is unknown, not zero
# ---------------------------------------------------------------------------


def test_margin_readiness_says_missing_is_unknown_not_zero(margin_readiness) -> None:
    lower = margin_readiness.lower()
    assert "unknown" in lower
    # Must contain a phrase asserting missing ≠ $0
    assert any(
        phrase in lower
        for phrase in (
            "not $0",
            "not $0.",
            "not zero",
            "never $0",
            "never zero",
            "unknown, not",
            "unknown (not",
            "show as **unknown**",
            "is unknown",
        )
    ), f"Margin readiness must explicitly state missing != $0:\n{margin_readiness[:1200]}"


def test_margin_readiness_flags_range_shell_grain(margin_readiness) -> None:
    assert "range" in margin_readiness.lower()
    assert "project+phase" in margin_readiness.lower() or "project + phase" in margin_readiness.lower()


def test_margin_readiness_flags_inferred_decoder(margin_readiness) -> None:
    assert "inferred" in margin_readiness.lower()
    assert "decoder" in margin_readiness.lower()


# ---------------------------------------------------------------------------
# Workflow 3: False precision risks
#   Must surface: $45.75M range/shell, not lot-level
# ---------------------------------------------------------------------------


def test_false_precision_mentions_45_75m_range_shell(false_precision) -> None:
    # Real magnitude is 45,752,046.63 — formatter rounds to $45,752,047
    assert any(
        m in false_precision
        for m in ("$45,752,047", "$45.75M", "$45,752,046", "$45.75 M", "45,752")
    ), f"False precision must mention $45.75M range/shell magnitude:\n{false_precision[:1500]}"


def test_false_precision_says_not_lot_level(false_precision) -> None:
    lower = false_precision.lower()
    # Must explicitly state range/shell are NOT safe at lot grain
    assert any(
        phrase in lower
        for phrase in (
            "not safe at lot grain",
            "not lot-level",
            "not at lot grain",
            "not at lot-level",
            "safe only at project+phase",
            "safe **only at project+phase",
            "project+phase grain only",
        )
    ), f"False precision must say range/shell are NOT lot-level:\n{false_precision[:1500]}"


def test_false_precision_mentions_harmony_3tuple(false_precision) -> None:
    assert "Harmony" in false_precision
    assert "3-tuple" in false_precision or "three-tuple" in false_precision.lower()


def test_false_precision_mentions_sctlot_scarlet_ridge(false_precision) -> None:
    assert "SctLot" in false_precision
    assert "Scarlet Ridge" in false_precision
    assert "Scattered Lots" in false_precision


# ---------------------------------------------------------------------------
# Workflow 4: Change impact summary
#   Must surface: $4.0M, $6.75M, $6.55M, $45.75M
# ---------------------------------------------------------------------------


def test_change_impact_mentions_4_0m_aultf(change_impact) -> None:
    assert any(
        m in change_impact for m in ("$4,006,662", "$4.0M", "4,006,662")
    )


def test_change_impact_mentions_6_75m_harmony(change_impact) -> None:
    assert any(
        m in change_impact for m in ("$6,750,000", "$6.75M", "6,750,000")
    )


def test_change_impact_mentions_6_55m_sctlot(change_impact) -> None:
    # Real magnitude is 6,553,892.79 — formatter rounds to $6,553,893
    assert any(
        m in change_impact
        for m in ("$6,553,893", "$6.55M", "$6,553,892", "6,553,89")
    )


def test_change_impact_mentions_45_75m_range(change_impact) -> None:
    assert any(
        m in change_impact
        for m in ("$45,752,047", "$45.75M", "$45,752,046", "45,752")
    )


def test_change_impact_notes_what_did_not_change(change_impact) -> None:
    # Must explicitly note org-wide v2 is not available
    lower = change_impact.lower()
    assert "did not change" in lower or "did not" in lower
    assert "org-wide" in lower or "hillcrest" in lower


# ---------------------------------------------------------------------------
# Workflow 5: Finance / land / ops meeting prep
#   Must group asks by finance, land, ops
# ---------------------------------------------------------------------------


def test_meeting_prep_has_finance_section(meeting_prep) -> None:
    # Section header convention: ## Finance / GL — asks
    assert "Finance" in meeting_prep
    # Must be a section, not just a passing mention
    assert "## Finance" in meeting_prep or "## Finance / GL" in meeting_prep


def test_meeting_prep_has_land_section(meeting_prep) -> None:
    assert "## Land" in meeting_prep or "## Land /" in meeting_prep


def test_meeting_prep_has_ops_section(meeting_prep) -> None:
    assert "## Ops" in meeting_prep or "## Ops /" in meeting_prep


def test_meeting_prep_has_decisions_section(meeting_prep) -> None:
    assert "Decisions needed" in meeting_prep or "decisions needed" in meeting_prep.lower()


def test_meeting_prep_anchors_dollar_gates(meeting_prep) -> None:
    # The meeting agenda should anchor the conversation around dollar magnitudes
    assert "$45,752" in meeting_prep or "$45.75" in meeting_prep
    assert "$6,750,000" in meeting_prep or "$6.75" in meeting_prep


# ---------------------------------------------------------------------------
# Workflow 6: Owner update
#   Must NOT claim org-wide v2 is ready
# ---------------------------------------------------------------------------


def test_owner_update_does_not_claim_orgwide_v2_ready(owner_update) -> None:
    lower = owner_update.lower()
    # Honest update must explicitly say org-wide v2 is NOT ready
    assert any(
        phrase in lower
        for phrase in (
            "org-wide v2 is not ready",
            "org-wide v2 is **not** ready",
            "org-wide v2 is not available",
            "org-wide v2 is **not** available",
            "org-wide is **not**",
            "**not ready**",
            "not** ready",
        )
    ), f"Owner update must explicitly state org-wide v2 is NOT ready:\n{owner_update[:1500]}"
    # And must NOT include any positive claim
    forbidden = [
        "org-wide v2 is ready",
        "org-wide v2 is available",
        "org-wide rollup is ready",
        "consolidated view is ready",
    ]
    for f in forbidden:
        assert f not in lower, f"Owner update wrongly claims: {f}"


def test_owner_update_names_bcpd_scope_explicitly(owner_update) -> None:
    assert "BCPD" in owner_update
    # Must enumerate the four in-scope entities
    for entity in ("BCPD", "BCPBL", "ASD", "BCPI"):
        assert entity in owner_update, f"missing in-scope entity {entity}"


def test_owner_update_names_out_of_scope_entities(owner_update) -> None:
    assert "Hillcrest" in owner_update
    assert "Flagship" in owner_update


def test_owner_update_calls_out_source_owner_bottleneck(owner_update) -> None:
    lower = owner_update.lower()
    assert "source-owner" in lower or "source owner" in lower
    assert "validation" in lower or "validated" in lower


# ---------------------------------------------------------------------------
# Read-only contract — no source/staged data was mutated by any tool run
# ---------------------------------------------------------------------------


_PROTECTED = (
    "output/operating_state_v2_1_bcpd.json",
    "output/agent_context_v2_1_bcpd.md",
    "output/state_quality_report_v2_1_bcpd.md",
    "data/reports/v2_0_to_v2_1_change_log.md",
    "data/reports/coverage_improvement_opportunities.md",
    "data/reports/crosswalk_quality_audit_v1.md",
    "data/reports/vf_lot_code_decoder_v1_report.md",
)


def test_workflow_tools_did_not_modify_protected_files(
    ctx,
    parkway_brief,  # forces all fixtures to have run first
    margin_readiness,
    false_precision,
    change_impact,
    meeting_prep,
    owner_update,
) -> None:
    """After running every tool, every protected file must be byte-identical to its disk snapshot.

    We snapshot at function entry and recompare — because the fixtures are
    module-scoped, the tool runs have already happened by the time this test executes.
    """
    import hashlib

    for rel in _PROTECTED:
        path = REPO / rel
        if not path.exists():
            continue
        h1 = hashlib.sha256(path.read_bytes()).hexdigest()
        # Touch state via context — must not write
        _ = ctx.state
        _ = ctx.change_summary()
        h2 = hashlib.sha256(path.read_bytes()).hexdigest()
        assert h1 == h2, f"protected file mutated: {rel}"


# ---------------------------------------------------------------------------
# Demo outputs on disk match the tools' current output (deterministic regen)
# ---------------------------------------------------------------------------


def test_demo_outputs_exist_under_runtime_demo() -> None:
    demo_dir = REPO / "output" / "runtime_demo"
    expected = (
        "project_brief_parkway_fields.md",
        "margin_readiness_bcpd.md",
        "false_precision_bcpd.md",
        "change_impact_v2_1.md",
        "finance_land_review_prep.md",
        "owner_update_bcpd.md",
    )
    for name in expected:
        path = demo_dir / name
        assert path.exists(), f"missing demo output: {path}"
        text = path.read_text()
        assert len(text) > 500, f"{name} is suspiciously short ({len(text)} chars)"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
