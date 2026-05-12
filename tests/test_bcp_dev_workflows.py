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
    CheckAllocationReadinessTool,
    DetectAccountingEventsTool,
    ExplainAllocationLogicTool,
    GeneratePerLotOutputSpecTool,
    QueryBcpDevProcessTool,
    ValidateCrosswalkReadinessTool,
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
    # GL pair appears
    assert "131-100" in out
    # Provenance and verification
    assert "## Provenance" in out


def test_explain_land_at_mda_states_sales_basis_as_current_workbook_method(
    explain_tool: ExplainAllocationLogicTool,
) -> None:
    """After workbook CSV inspection, sales-basis is the current workbook
    method. The tool must surface it as such, mention lot-count only as a
    control / tie-out interpretation, and note that formal source-owner
    ratification is still pending."""
    out = explain_tool.run(cost_type="Land")
    # Headline names sales-basis as the current workbook method
    assert "Current workbook method" in out
    assert "sales_basis_weighted" in out
    # Sales-basis formula surfaces
    assert "sales_basis_pct_per_phase" in out
    assert "community_land_pool" in out
    # Lot-count form is present but explicitly labelled as control/tie-out,
    # NOT the workbook formula
    assert "Control / tie-out interpretation" in out
    assert "NOT the workbook formula" in out
    assert "raw_land_basis_per_property" in out
    # Reconciliation explains lot counts remain required for tie-out & per-lot
    assert "Reconciliation" in out
    assert "MDA Day tie-out" in out
    assert "per-lot denominator" in out
    # Formal source-owner ratification still pending
    assert "Q23" in out
    assert "ratification still pending" in out
    # And the symmetric "AMBIGUOUS / both candidates equally weighted" framing
    # is gone.
    assert "AMBIGUOUS" not in out
    assert "candidate_a_lot_count_weighted" not in out
    assert "candidate_b_sales_basis_weighted" not in out


def test_explain_land_at_mda_does_not_state_lot_count_as_current_formula(
    explain_tool: ExplainAllocationLogicTool,
) -> None:
    """Regression guard: the tool must not present lot-count weighting as
    the current workbook formula."""
    out = explain_tool.run(cost_type="Land")
    # The lot-count formula appears, but only inside the control-interpretation
    # block — never as the headline workbook method.
    headline_section = out[: out.find("Reconciliation")]
    assert "Current workbook method" in headline_section
    assert "sales_basis_weighted" in headline_section
    # The headline must not say lot-count is the current method
    assert "Current workbook method: `lot_count" not in headline_section


def test_explain_land_at_mda_mentions_lot_count_for_tie_out(
    explain_tool: ExplainAllocationLogicTool,
) -> None:
    """Lot counts are still required for MDA tie-out and per-lot math even
    though sales-basis is the allocation weighting. The reconciliation note
    must say so."""
    out = explain_tool.run(cost_type="Land")
    # Lot counts surface as required-for-tie-out / per-lot-denominator
    assert "Lot counts" in out
    assert "MDA Day tie-out" in out
    assert "per-lot denominator" in out


def test_query_land_at_mda_states_sales_basis_as_current_method(
    query_tool: QueryBcpDevProcessTool,
) -> None:
    """The query tool must mirror the explain tool: sales-basis as the
    current workbook method, lot-count as control only."""
    out = query_tool.run(question="How is land allocated at MDA?")
    assert "land_at_mda" in out
    assert "Current workbook method" in out
    assert "sales_basis_weighted" in out
    assert "community_land_pool * sales_basis_pct_per_phase" in out
    # Reconciliation message
    assert "Reconciliation" in out or "reconciliation" in out
    # No symmetric ambiguity framing in the headline
    assert "candidate_a_lot_count_weighted" not in out
    assert "candidate_b_sales_basis_weighted" not in out


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
    for name in (
        "query_bcp_dev_process",
        "explain_allocation_logic",
        "validate_crosswalk_readiness",
        "check_allocation_readiness",
        "detect_accounting_events",
        "generate_per_lot_output_spec",
    ):
        assert name in registry
    assert len(registry) == len(BCP_DEV_WORKFLOW_TOOLS) == 6


def test_descriptions_carry_scope_tag(ctx: BcpDevContext) -> None:
    # Per plan §11 routing recommendation: scope tag on every new tool's MCP
    # description so Desktop's routing between BCPD and BCP Dev is unambiguous.
    tag = "BCP Dev v0.2"
    for tool_cls in (
        QueryBcpDevProcessTool,
        ExplainAllocationLogicTool,
        ValidateCrosswalkReadinessTool,
        CheckAllocationReadinessTool,
        DetectAccountingEventsTool,
        GeneratePerLotOutputSpecTool,
    ):
        assert tag in tool_cls(context=ctx).description, (
            f"{tool_cls.__name__} description missing scope tag"
        )


def test_detect_events_description_carries_routing_hints(ctx: BcpDevContext) -> None:
    """Trial issue: prompts like 'what should accounting do if a lot moves to
    LND_RECORDED_SIH but FMV at Transfer is missing' must route to
    detect_accounting_events. Its description must signal that routing axis."""
    desc = DetectAccountingEventsTool(context=ctx).description.lower()
    # Each routing hint phrase must appear in the description.
    for phrase in (
        "status change",
        "moves to",
        "accounting event",
        "missing required",
    ):
        assert phrase in desc, (
            f"detect_accounting_events description missing routing hint: {phrase!r}"
        )


def test_query_description_carves_out_event_routing(ctx: BcpDevContext) -> None:
    """query_bcp_dev_process must explicitly NOT claim the event-routing
    territory; it must point at detect_accounting_events instead."""
    desc = QueryBcpDevProcessTool(context=ctx).description.lower()
    # Must say 'do not use' for status changes
    assert "do not use" in desc or "do not use" in desc.replace("**", "")
    assert "detect_accounting_events" in desc


def test_dispatch_via_registry(ctx: BcpDevContext) -> None:
    registry = ToolRegistry()
    register_bcp_dev_workflow_tools(registry, context=ctx)
    out = registry.dispatch(
        "query_bcp_dev_process",
        {"question": "Explain the land_at_mda method."},
    )
    assert "land_at_mda" in out
    assert "## Provenance" in out


# ---------------------------------------------------------------------------
# validate_crosswalk_readiness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def validate_cw_tool(ctx: BcpDevContext) -> ValidateCrosswalkReadinessTool:
    return ValidateCrosswalkReadinessTool(context=ctx)


def test_validate_crosswalk_readiness_lists_resolved_counts(
    validate_cw_tool: ValidateCrosswalkReadinessTool,
) -> None:
    out = validate_cw_tool.run(scope="all")
    assert "Crosswalk readiness" in out
    # Resolved counts per table — every CW-* should appear
    for tid in ("CW-01", "CW-02", "CW-04", "CW-05", "CW-13"):
        assert tid in out


def test_validate_crosswalk_readiness_surfaces_unres_mappings(
    validate_cw_tool: ValidateCrosswalkReadinessTool,
) -> None:
    out = validate_cw_tool.run(scope="all")
    # Every UNRES-* in the file should be enumerated.
    for uid in ("UNRES-01", "UNRES-02", "UNRES-03", "UNRES-07", "UNRES-08"):
        assert uid in out, f"missing {uid} in readiness output"


def test_validate_crosswalk_readiness_marks_null_canonical_explicitly(
    validate_cw_tool: ValidateCrosswalkReadinessTool,
) -> None:
    out = validate_cw_tool.run(scope="all")
    # CW-01 has 'P2 14' as canonical_value=null
    assert "P2 14" in out
    # Output should phrase this as explicitly unmapped — never blank
    assert "explicitly unmapped" in out or "inferred-unknown" in out


def test_validate_crosswalk_readiness_provenance_present(
    validate_cw_tool: ValidateCrosswalkReadinessTool,
) -> None:
    out = validate_cw_tool.run(scope="all")
    assert "## Provenance" in out


# ---------------------------------------------------------------------------
# check_allocation_readiness
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def check_alloc_tool(ctx: BcpDevContext) -> CheckAllocationReadinessTool:
    return CheckAllocationReadinessTool(context=ctx)


def test_check_alloc_readiness_pf_e1_axes_split_top_line_not_ready(
    check_alloc_tool: CheckAllocationReadinessTool,
) -> None:
    """PF E1 method path is eligible (compute_ready) but required inputs
    are incomplete today — top line MUST say 'No — not cleanly today',
    not 'compute_ready'."""
    out = check_alloc_tool.run(community="Parkway Fields", phase="E1")
    assert "Allocation readiness" in out
    # Both axes are reported separately
    assert "method_status" in out
    assert "run_readiness" in out
    # Method path is eligible
    assert "compute_ready" in out
    # But run readiness is NOT ready today (inputs incomplete)
    assert "not_ready" in out or "partial" in out
    # Top-line answer must lead with a clear no — not a hedge
    assert "Top-line answer" in out
    assert "No" in out and "not cleanly today" in out
    assert "## Provenance" in out


def test_check_alloc_readiness_pf_e1_does_not_claim_ready(
    check_alloc_tool: CheckAllocationReadinessTool,
) -> None:
    """Regression guard for the v0.2 MCP Desktop trial issue: the tool
    must not state run_readiness=ready for PF E1 with today's inputs."""
    out = check_alloc_tool.run(community="Parkway Fields", phase="E1")
    # The exact backtick'd value must not appear
    assert "`run_readiness`: `ready`" not in out
    # And the top line must not be the green checkmark
    top_section = out[: out.find("##") if "##" in out else len(out)]
    assert "✅ Yes" not in top_section


def test_check_alloc_readiness_pf_e1_blocks_on_missing_projected_sales(
    check_alloc_tool: CheckAllocationReadinessTool,
) -> None:
    """Under the sales-basis weighting (now the workbook-observed method),
    a missing avg_projected_sales_price for PF E1 must surface as a blocker
    in the input checklist."""
    out = check_alloc_tool.run(community="Parkway Fields", phase="E1")
    # avg_projected_sales_price row must appear with state=missing
    assert "avg_projected_sales_price" in out
    # Find the row and verify it's flagged missing
    row_idx = out.find("avg_projected_sales_price")
    row_chunk = out[row_idx : row_idx + 220]
    assert "**missing**" in row_chunk
    # And run_readiness must not be ready
    assert "`run_readiness`: `ready`" not in out


def test_check_alloc_readiness_lh_blocked_by_aaj(
    check_alloc_tool: CheckAllocationReadinessTool,
) -> None:
    out = check_alloc_tool.run(community="Lomond Heights", phase="2A")
    assert "blocked" in out
    assert "aaj_error_cascade" in out
    assert "AAJ" in out


def test_check_alloc_readiness_eagle_blocked_not_in_workbook(
    check_alloc_tool: CheckAllocationReadinessTool,
) -> None:
    out = check_alloc_tool.run(community="Eagle Vista")
    assert "blocked" in out
    assert "not_in_workbook" in out


def test_check_alloc_readiness_range_row_blocked(
    check_alloc_tool: CheckAllocationReadinessTool,
) -> None:
    out = check_alloc_tool.run(community="Arrowhead Springs", phase="AS 1-3")
    assert "blocked" in out
    assert "range_row_unratified" in out


def test_check_alloc_readiness_spec_only_for_other_communities(
    check_alloc_tool: CheckAllocationReadinessTool,
) -> None:
    out = check_alloc_tool.run(community="Harmony", phase="B1")
    assert "spec_only" in out
    assert "master_no_pricing" in out


def test_check_alloc_readiness_requires_community(
    check_alloc_tool: CheckAllocationReadinessTool,
) -> None:
    out = check_alloc_tool.run(community="")
    assert "ERROR" in out


# ---------------------------------------------------------------------------
# detect_accounting_events
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def detect_tool(ctx: BcpDevContext) -> DetectAccountingEventsTool:
    return DetectAccountingEventsTool(context=ctx)


def test_detect_events_requires_at_least_one_input(
    detect_tool: DetectAccountingEventsTool,
) -> None:
    out = detect_tool.run()
    assert "ERROR" in out


def test_detect_events_mda_execution(detect_tool: DetectAccountingEventsTool) -> None:
    out = detect_tool.run(status_changes=[{
        "task_id": "CU-1",
        "community": "Park Way",  # exercises CW-01 mapping → Parkway Fields
        "phase": "E1",
        "lot_number": "001",
        "status_from": "LND_RAW_LAND",
        "status_to": "LND_ENTITLED",
        "fields": {
            "MDA Execution Date": "2026-04-01",
            "Phase Identifier": "E1",
            "Lot Count by Type (SFR/TH/MF/Comm)": "{SFR:198}",
            "MDA Lot Count": 198,
            "Allocation Workbook Lot Count": 198,
            "Raw Land Basis (per Property)": 12500000,
        },
    }])
    assert "mda_execution" in out
    assert "EVENT-002" in out
    # GL entry surfaces correct chart codes
    assert "131-200" in out
    assert "131-100" in out
    # Community crosswalk resolved
    assert "Parkway Fields" in out
    # MDA Day partial-tie language present
    assert "mda_day_check" in out
    assert "partial" in out


def test_detect_events_sih_missing_fmv_is_blocked(
    detect_tool: DetectAccountingEventsTool,
) -> None:
    out = detect_tool.run(status_changes=[{
        "task_id": "CU-SIH",
        "community": "Harmony",
        "phase": "B1",
        "lot_number": "042",
        "status_from": "LND_RECORDED_NOT_SOLD",
        "status_to": "LND_RECORDED_SIH",
        "fields": {
            "Sale Counterparty Name": "BCP-HB",
            "Sale Date": "2026-04-15",
            "FMV at Transfer": None,
        },
    }])
    assert "lot_sale_sih" in out
    assert "FMV at Transfer" in out
    assert "Blocker" in out or "blocker" in out
    assert "missing_required_input_refusal" in out
    # Sentinel caveat surfaces
    assert "intercompany_revenue_or_transfer_clearing" in out
    assert "pending_source_doc_review" in out or "Q17" in out


def test_detect_events_3rdy_missing_sale_price_is_blocked(
    detect_tool: DetectAccountingEventsTool,
) -> None:
    out = detect_tool.run(status_changes=[{
        "task_id": "CU-3RDY",
        "community": "Salem Fields",
        "phase": "B",
        "lot_number": "101",
        "status_from": "LND_RECORDED_NOT_SOLD",
        "status_to": "LND_RECORDED_SOLD_3RDY",
        "fields": {
            "Sale Counterparty Name": "Third Party LLC",
            "Sale Date": "2026-04-15",
            "Sale Price": None,
        },
    }])
    assert "lot_sale_3rdy" in out
    assert "Sale Price" in out
    assert "Blocker" in out or "blocker" in out
    # 3RDY revenue sentinel caveat
    assert "land_sale_revenue" in out
    assert "pending_source_doc_review" in out or "Q18" in out


def test_detect_events_unmapped_subdivision_yields_inferred_unknown(
    detect_tool: DetectAccountingEventsTool,
) -> None:
    # 'P2 14' is in CW-01 with canonical_value=null (held)
    out = detect_tool.run(status_changes=[{
        "task_id": "CU-UNMAPPED",
        "community": "P2 14",
        "phase": "?",
        "status_from": None,
        "status_to": "LND_ENTITLED",
        "fields": {},
    }])
    assert "inferred-unknown" in out


def test_detect_events_does_not_post(detect_tool: DetectAccountingEventsTool) -> None:
    out = detect_tool.run(status_changes=[{
        "task_id": "CU-1",
        "community": "Parkway Fields",
        "phase": "E1",
        "lot_number": "001",
        "status_from": "LND_RAW_LAND",
        "status_to": "LND_ENTITLED",
        "fields": {},
    }])
    # The tool must explicitly state it does not post and is detection only
    assert "detection only" in out.lower()
    assert "never posts" in out.lower() or "does not post" in out.lower()


# ---------------------------------------------------------------------------
# generate_per_lot_output_spec
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def spec_tool(ctx: BcpDevContext) -> GeneratePerLotOutputSpecTool:
    return GeneratePerLotOutputSpecTool(context=ctx)


def test_spec_tool_requires_community(spec_tool: GeneratePerLotOutputSpecTool) -> None:
    out = spec_tool.run(community="")
    assert "ERROR" in out


def test_spec_pf_e1_shape_compute_ready(
    spec_tool: GeneratePerLotOutputSpecTool,
) -> None:
    out = spec_tool.run(community="Parkway Fields", phase="E1")
    assert "Per-Lot Output Spec" in out
    assert "Parkway Fields" in out
    # Scope decision
    assert "compute_ready" in out
    # All key fields surface in the table
    for fid in (
        "community", "phase", "lot_type", "lots",
        "effective_direct_budget", "land_allocated", "indirect_allocated",
        "water_allocated", "warranty_allocated", "total_cost",
        "sales_price_per_lot", "margin_per_lot",
    ):
        assert f"`{fid}`" in out, f"field {fid!r} missing from spec table"
    # Warranty must be refused (rate unratified)
    assert "warranty_rate_unratified" in out
    # PF-specific Indirect negative-sign note
    assert "PF-specific notes" in out
    assert "negative" in out.lower()
    # Spec only — no numeric dollar values
    assert "$0" not in out


def test_spec_lh_blocked_with_aaj(spec_tool: GeneratePerLotOutputSpecTool) -> None:
    out = spec_tool.run(community="Lomond Heights")
    assert "blocked" in out
    assert "aaj_error_cascade" in out
    assert "AAJ" in out


def test_spec_eagle_vista_blocked_not_in_workbook(
    spec_tool: GeneratePerLotOutputSpecTool,
) -> None:
    out = spec_tool.run(community="Eagle Vista")
    assert "blocked" in out
    assert "not_in_workbook" in out
    # Block explanation present
    assert "Allocation Engine" in out or "workbook" in out


def test_spec_refusal_patterns_render(
    spec_tool: GeneratePerLotOutputSpecTool,
) -> None:
    out = spec_tool.run(community="Arrowhead Springs", phase="AS 1-3")
    # Refusal-pattern table present and range-row marked applies
    assert "refuse_range_row" in out
    assert "range_row_unratified" in out
    # All fields marked refused
    assert "refused" in out


def test_spec_never_emits_numeric_values(
    spec_tool: GeneratePerLotOutputSpecTool,
) -> None:
    """Spec is for shape + status only. No computed dollar values should leak."""
    for community in ("Parkway Fields", "Lomond Heights", "Harmony", "Eagle Vista"):
        out = spec_tool.run(community=community, phase="E1")
        # Allow $-1.25M to appear in the PF Indirects caveat string only.
        # No $0, $X,XXX patterns from compute output.
        assert "$0.00" not in out
        assert "$1,000,000" not in out
        assert "Computed value:" not in out
