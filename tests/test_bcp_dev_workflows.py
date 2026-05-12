"""Tests for the PR-2 BCP Dev process tools.

Run:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_bcp_dev_workflows.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.agent.bcp_dev_context import BcpDevContext
from core.agent.registry import ToolRegistry
from core.tools.bcp_dev_workflows import (
    BCP_DEV_WORKFLOW_TOOLS,
    ExplainAllocationLogicTool,
    QueryBcpDevProcessTool,
    register_bcp_dev_workflow_tools,
)


@pytest.fixture(scope="module")
def ctx() -> BcpDevContext:
    c = BcpDevContext()
    c.load_all()
    return c


@pytest.fixture(scope="module")
def query_tool(ctx: BcpDevContext) -> QueryBcpDevProcessTool:
    return QueryBcpDevProcessTool(context=ctx)


@pytest.fixture(scope="module")
def explain_tool(ctx: BcpDevContext) -> ExplainAllocationLogicTool:
    return ExplainAllocationLogicTool(context=ctx)


# ---------------------------------------------------------------------------
# query_bcp_dev_process — routing smoke (all six rule files)
# ---------------------------------------------------------------------------


def test_query_routes_status_taxonomy(query_tool: QueryBcpDevProcessTool) -> None:
    out = query_tool.run(question="What needs to happen when a lot moves to LND_RECORDED_SIH?")
    assert "STATUS-005" in out
    assert "status_taxonomy_v1.json" in out
    assert "LND_RECORDED_SIH" in out


def test_query_routes_event_map(query_tool: QueryBcpDevProcessTool) -> None:
    out = query_tool.run(question="Which ClickUp status changes trigger accounting events?")
    assert "clickup_gl_event_map_v1.json" in out
    # All eight events should be enumerated in the generic event-map summary
    for eid in ("closing", "mda_execution", "pre_con", "lot_sale_sih", "lot_sale_3rdy"):
        assert eid in out


def test_query_routes_account_prefix_matrix(query_tool: QueryBcpDevProcessTool) -> None:
    out = query_tool.run(question="What are the valid job prefixes for direct costs?")
    assert "account_prefix_matrix_v1.json" in out
    # DIR prefix-specific answer (not the generic overview)
    assert "DIR" in out
    assert "Direct" in out


def test_query_routes_allocation_methods(query_tool: QueryBcpDevProcessTool) -> None:
    out = query_tool.run(question="What is the allocation method for indirect costs?")
    assert "allocation_methods_v1.json" in out
    assert "indirect_community" in out
    # Sales-basis weighting language from the calculation block
    assert "sales_basis" in out.lower()


def test_query_routes_monthly_review_checks(query_tool: QueryBcpDevProcessTool) -> None:
    out = query_tool.run(question="What monthly review checks exist for WIP balances?")
    assert "monthly_review_checks_v1.json" in out
    assert "wip_balance_to_open_phase_check" in out
    assert "alloc_pair_balance_check" in out


def test_query_routes_exception_rules(query_tool: QueryBcpDevProcessTool) -> None:
    out = query_tool.run(question="How does the process handle a cancellation exception?")
    assert "exception_rules_v1.json" in out
    assert "cancellation_handling" in out


def test_query_routing_all_six_files_smoke(query_tool: QueryBcpDevProcessTool) -> None:
    """One question per route — every file path must appear in at least one output."""
    cases = {
        "state/process_rules/status_taxonomy_v1.json": "What does LND_DEVELOPING mean?",
        "state/process_rules/clickup_gl_event_map_v1.json": "Which event fires at MDA?",
        "state/process_rules/account_prefix_matrix_v1.json": "What is the validity matrix?",
        "state/process_rules/allocation_methods_v1.json": "Explain the land_at_mda method.",
        "state/process_rules/monthly_review_checks_v1.json": "What is the monthly review tie-out?",
        "state/process_rules/exception_rules_v1.json": "What's the cancellation exception?",
    }
    for path, question in cases.items():
        out = query_tool.run(question=question)
        assert path in out, f"route to {path} missing for question {question!r}\n--- output ---\n{out}"


# ---------------------------------------------------------------------------
# query_bcp_dev_process — content + refusal + provenance
# ---------------------------------------------------------------------------


def test_query_provenance_block_present_on_every_routed_response(
    query_tool: QueryBcpDevProcessTool,
) -> None:
    for q in (
        "What does LND_RECORDED_SIH mean?",
        "Which ClickUp changes trigger MDA?",
        "What posting accounts does CPI prefix use?",
        "Explain the warranty allocation method.",
        "Show me the monthly review checks.",
        "What's the cancellation exception?",
    ):
        out = query_tool.run(question=q)
        assert "## Provenance" in out, f"missing provenance block in answer to {q!r}"


def test_query_range_row_refusal(query_tool: QueryBcpDevProcessTool) -> None:
    out = query_tool.run(question="Why is range-row allocation refused?")
    assert "Range-row" in out or "range-row" in out
    assert "EXC-007" in out
    assert "range_row_unratified" in out
    assert "exception_rules_v1.json" in out


def test_query_warranty_caveat(query_tool: QueryBcpDevProcessTool) -> None:
    out = query_tool.run(question="How does warranty allocation work?")
    assert "warranty_at_sale" in out
    assert "ALLOC-005" in out
    # Caveat about the unratified rate
    assert "warranty rate" in out.lower() or "Q5" in out


def test_query_empty_question_errors(query_tool: QueryBcpDevProcessTool) -> None:
    out = query_tool.run(question="")
    assert "ERROR" in out


def test_query_unroutable_question_does_not_invent(
    query_tool: QueryBcpDevProcessTool,
) -> None:
    out = query_tool.run(question="What's the weather like in Salt Lake?")
    assert "does not route" in out
    assert "## Provenance" in out


def test_query_unratified_warranty_status_surfaces_caveat(
    query_tool: QueryBcpDevProcessTool,
) -> None:
    # warranty_at_sale has verification_status=inferred_from_briefing, which
    # should produce a verification caveat in the provenance block.
    out = query_tool.run(question="Explain warranty_at_sale.")
    assert "verification_status" in out or "inferred_from_briefing" in out


# ---------------------------------------------------------------------------
# explain_allocation_logic — per-method explanations
# ---------------------------------------------------------------------------


def test_explain_requires_at_least_one_input(explain_tool: ExplainAllocationLogicTool) -> None:
    out = explain_tool.run()
    assert "ERROR" in out


def test_explain_land_at_mda(explain_tool: ExplainAllocationLogicTool) -> None:
    out = explain_tool.run(cost_type="Land")
    assert "land_at_mda" in out
    assert "ALLOC-001" in out
    assert "mda_execution" in out
    # Calculation appears
    assert "phase_share_usd" in out
    # GL pair appears
    assert "131-100" in out
    # Provenance and verification
    assert "## Provenance" in out


def test_explain_direct_per_phase(explain_tool: ExplainAllocationLogicTool) -> None:
    out = explain_tool.run(cost_type="Direct")
    assert "direct_per_phase" in out
    assert "ALLOC-003" in out
    assert "per_lot_share_usd" in out
    # The worked example for direct lives here
    assert "Worked example" in out
    assert "132-500" in out


def test_explain_indirect_community(explain_tool: ExplainAllocationLogicTool) -> None:
    out = explain_tool.run(cost_type="Indirect")
    assert "indirect_community" in out
    assert "ALLOC-004" in out
    assert "sales_basis" in out.lower()
    assert "132-600" in out


def test_explain_water_by_letter(explain_tool: ExplainAllocationLogicTool) -> None:
    out = explain_tool.run(cost_type="Water")
    assert "water_by_letter" in out
    assert "ALLOC-002" in out
    assert "water_letter_units_phase" in out
    assert "132-700" in out


def test_explain_warranty_refuses_numeric(explain_tool: ExplainAllocationLogicTool) -> None:
    out = explain_tool.run(cost_type="Warranty")
    assert "warranty_at_sale" in out
    assert "ALLOC-005" in out
    # The caveat must surface the rate question and unresolved pool source
    lowered = out.lower()
    assert "warranty rate" in lowered
    assert "q5" in lowered or "unres-07" in lowered
    # And the tool refuses to substitute a numeric default
    assert "refus" in lowered  # refuse / refusal / refuses


def test_explain_range_row_refuses(explain_tool: ExplainAllocationLogicTool) -> None:
    out = explain_tool.run(cost_type="shell_range_row")
    assert "range_row_unratified" in out
    assert "ALLOC-006" in out
    # Refusal section with reason
    assert "Refusal" in out or "refusal" in out
    assert "unratified" in out.lower()
    # Cross-reference to EXC-007
    assert "EXC-007" in out


# ---------------------------------------------------------------------------
# explain_allocation_logic — event-based explanations
# ---------------------------------------------------------------------------


def test_explain_event_mda_execution(explain_tool: ExplainAllocationLogicTool) -> None:
    out = explain_tool.run(event="mda_execution")
    assert "land_at_mda" in out
    assert "EVENT-002" in out
    # GL entries section
    assert "mda_execution.JE1" in out
    assert "131-200" in out and "131-100" in out


def test_explain_event_lot_sale_sih_surfaces_sentinel_caveat(
    explain_tool: ExplainAllocationLogicTool,
) -> None:
    out = explain_tool.run(event="lot_sale_sih")
    assert "lot_sale_sih" in out
    assert "EVENT-006" in out
    # All five allocation methods fire at lot sale SIH per the method_event_matrix
    for mid in (
        "land_at_mda",
        "direct_per_phase",
        "indirect_community",
        "water_by_letter",
        "warranty_at_sale",
    ):
        assert mid in out, f"expected {mid} to be referenced for lot_sale_sih"
    # Sentinel caveat
    assert "intercompany_revenue_or_transfer_clearing" in out
    assert "pending source-doc ratification" in out or "Q17" in out


def test_explain_event_lot_sale_3rdy_surfaces_land_sale_revenue_sentinel(
    explain_tool: ExplainAllocationLogicTool,
) -> None:
    out = explain_tool.run(event="lot_sale_3rdy")
    assert "lot_sale_3rdy" in out
    assert "land_sale_revenue" in out
    assert "pending source-doc ratification" in out or "Q18" in out


def test_explain_unknown_event_refuses(explain_tool: ExplainAllocationLogicTool) -> None:
    out = explain_tool.run(event="bogus_event_id")
    assert "Refusal" in out or "refuses" in out or "not in" in out
    assert "clickup_gl_event_map_v1.json" in out


# ---------------------------------------------------------------------------
# Registration + MCP routing description sanity
# ---------------------------------------------------------------------------


def test_register_bcp_dev_workflow_tools(ctx: BcpDevContext) -> None:
    registry = ToolRegistry()
    register_bcp_dev_workflow_tools(registry, context=ctx)
    assert "query_bcp_dev_process" in registry
    assert "explain_allocation_logic" in registry
    assert len(registry) == len(BCP_DEV_WORKFLOW_TOOLS) == 2


def test_descriptions_carry_scope_tag(ctx: BcpDevContext) -> None:
    # Per plan §11 routing recommendation: scope tag on every new tool's MCP
    # description so Desktop's routing between BCPD and BCP Dev is unambiguous.
    tag = "BCP Dev v0.2"
    assert tag in QueryBcpDevProcessTool(context=ctx).description
    assert tag in ExplainAllocationLogicTool(context=ctx).description


def test_dispatch_via_registry(ctx: BcpDevContext) -> None:
    registry = ToolRegistry()
    register_bcp_dev_workflow_tools(registry, context=ctx)
    out = registry.dispatch(
        "query_bcp_dev_process",
        {"question": "Explain the land_at_mda method."},
    )
    assert "land_at_mda" in out
    assert "## Provenance" in out
