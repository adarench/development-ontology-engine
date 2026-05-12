"""Tests for the BcpDevContext loader, integrity validator, and helpers.

Run:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_bcp_dev_context.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.agent.bcp_dev_context import (
    ACCOUNT_SENTINEL_WHITELIST,
    BcpDevContext,
    BcpDevContextIntegrityError,
    METHOD_ID_REF_WHITELIST,
    REQUIRED_BCP_DEV_FILES,
    REQUIRED_PROCESS_RULES_FILES,
    TRIGGER_EVENT_META_RESOLUTION,
)


@pytest.fixture(scope="module")
def ctx() -> BcpDevContext:
    c = BcpDevContext()
    c.load_all()
    return c


def test_bcp_dev_context_loads_all_files(ctx: BcpDevContext) -> None:
    # Process rules — six files
    assert "statuses" in ctx.status_taxonomy()
    assert "events" in ctx.event_map()
    assert "posting_accounts" in ctx.account_prefix_matrix()
    assert "alloc_accounts" in ctx.account_prefix_matrix()
    assert "methods" in ctx.allocation_methods()
    assert "checks" in ctx.monthly_review_checks()
    assert "rules" in ctx.exception_rules()

    # BCP Dev state — five files
    assert "workbooks" in ctx.allocation_workbook_schema()
    assert ctx.allocation_input_requirements() is not None
    assert "fields" in ctx.per_lot_output_schema()
    assert "tables" in ctx.source_crosswalks()
    assert "files" in ctx.source_file_manifest()

    # Count is exactly 11
    assert len(REQUIRED_PROCESS_RULES_FILES) + len(REQUIRED_BCP_DEV_FILES) == 11


def test_bcp_dev_context_integrity_passes(ctx: BcpDevContext) -> None:
    # Must not raise. If it does, surface every issue so the failure is reviewable.
    try:
        ctx.validate_integrity()
    except BcpDevContextIntegrityError as e:
        pytest.fail("Integrity validation failed:\n  - " + "\n  - ".join(e.issues))


def test_bcp_dev_context_immutability(ctx: BcpDevContext) -> None:
    methods_doc = ctx.allocation_methods()
    # Top-level dict is a MappingProxyType — mutation must raise TypeError.
    with pytest.raises(TypeError):
        methods_doc["new_key"] = "value"  # type: ignore[index]

    # Nested list is now a tuple — no append.
    methods_tuple = methods_doc["methods"]
    assert isinstance(methods_tuple, tuple)
    with pytest.raises(AttributeError):
        methods_tuple.append({})  # type: ignore[attr-defined]

    # Nested dict element is also a MappingProxyType.
    first_method = methods_tuple[0]
    assert isinstance(first_method, MappingProxyType)
    with pytest.raises(TypeError):
        first_method["method_id"] = "tampered"  # type: ignore[index]


def test_resolve_canonical_known_value(ctx: BcpDevContext) -> None:
    result = ctx.resolve_canonical(
        source_system="ClickUp",
        source_value="Park Way",
        canonical_type="community",
    )
    assert result.found is True
    assert result.canonical_value == "Parkway Fields"
    assert result.confidence in {"high", "medium", "low"}
    assert result.canonical_type == "community"


def test_resolve_canonical_unmapped_returns_none(ctx: BcpDevContext) -> None:
    # Crosswalk row exists for 'P2 14' with canonical_value=null and
    # confidence='inferred-unknown' — this is "explicitly unmapped".
    held = ctx.resolve_canonical(
        source_system="ClickUp",
        source_value="P2 14",
        canonical_type="community",
    )
    assert held.found is True
    assert held.canonical_value is None
    assert held.confidence == "inferred-unknown"

    # No crosswalk row at all — unknown value entirely.
    missing = ctx.resolve_canonical(
        source_system="ClickUp",
        source_value="ZZZ_NotARealValue",
        canonical_type="community",
    )
    assert missing.found is False
    assert missing.canonical_value is None
    assert missing.confidence == "inferred-unknown"


def test_mda_day_check_partial_tie() -> None:
    # Two-of-three counts available and they agree → 'partial', not 'fail'.
    ctx = BcpDevContext(
        manifest_overrides={
            "mda_counts": {
                "Parkway Fields": {
                    "E1": {"clickup": None, "mda": 198, "workbook": 198}
                }
            }
        }
    )
    result = ctx.mda_day_check("Parkway Fields", "E1")
    assert result.status == "partial"
    assert result.counts["clickup"] is None
    assert result.counts["mda"] == 198
    assert result.counts["workbook"] == 198

    # Two-of-three but disagreeing → 'fail'.
    ctx2 = BcpDevContext(
        manifest_overrides={
            "mda_counts": {
                "Parkway Fields": {"E1": {"mda": 198, "workbook": 200}}
            }
        }
    )
    assert ctx2.mda_day_check("Parkway Fields", "E1").status == "fail"

    # Three available and agree → 'pass'.
    ctx3 = BcpDevContext(
        manifest_overrides={
            "mda_counts": {
                "Parkway Fields": {
                    "E1": {"clickup": 198, "mda": 198, "workbook": 198}
                }
            }
        }
    )
    assert ctx3.mda_day_check("Parkway Fields", "E1").status == "pass"


@pytest.mark.parametrize(
    "community, phase, expected_decision, expected_reason",
    [
        ("Hillcrest", None, "blocked", "out_of_scope"),
        ("Flagship Belmont", None, "blocked", "out_of_scope"),
        ("Lomond Heights", "2A", "blocked", "aaj_error_cascade"),
        ("Eagle Vista", "1", "blocked", "not_in_workbook"),
        ("Arrowhead Springs", "AS 1-3", "blocked", "range_row_unratified"),
        ("Parkway Fields", "D2", "compute_ready", None),
        ("Parkway Fields", "E1", "compute_ready", None),
        ("Parkway Fields", "E2", "compute_ready_with_caveat",
         "estimated_direct_base_or_indirects_sign"),
        ("Parkway Fields", "F", "compute_ready_with_caveat",
         "estimated_direct_base_or_indirects_sign"),
        ("Parkway Fields", "G1 SFR", "compute_ready_with_caveat",
         "estimated_direct_base_or_indirects_sign"),
        ("Parkway Fields", "G1 Comm", "compute_ready_with_caveat",
         "estimated_direct_base_or_indirects_sign"),
        ("Parkway Fields", "G2", "compute_ready_with_caveat",
         "estimated_direct_base_or_indirects_sign"),
        ("Parkway Fields", "H", "compute_ready_with_caveat",
         "estimated_direct_base_or_indirects_sign"),
        ("Harmony", "B1", "spec_only", "master_no_pricing"),
        ("Salem Fields", "B", "spec_only", "master_no_pricing"),
        ("Scarlet Ridge", "2", "spec_only", "master_no_pricing"),
        ("Willowcreek", "WC_TH_1", "spec_only", "master_no_pricing"),
    ],
)
def test_compute_status_decision_tree(
    ctx: BcpDevContext,
    community: str,
    phase: str | None,
    expected_decision: str,
    expected_reason: str | None,
) -> None:
    result = ctx.compute_status_for(community, phase)
    assert result.decision == expected_decision, (
        f"{community}/{phase}: expected {expected_decision}, got {result.decision} "
        f"(reason={result.reason})"
    )
    assert result.reason == expected_reason
    assert result.community == community
    assert result.phase == phase


def test_warranty_at_sale_trigger_event_meta_resolution(ctx: BcpDevContext) -> None:
    methods = ctx.allocation_methods()["methods"]
    warranty = next(m for m in methods if m["method_id"] == "warranty_at_sale")
    # In the source JSON the trigger_event is the meta-event 'lot_sale'.
    assert warranty["trigger_event"] == "lot_sale"
    # The resolver maps 'lot_sale' to both lot_sale_sih and lot_sale_3rdy.
    resolved = TRIGGER_EVENT_META_RESOLUTION["lot_sale"]
    assert "lot_sale_sih" in resolved
    assert "lot_sale_3rdy" in resolved
    # And both of those event_ids exist in event_map.
    event_ids = {e["event_id"] for e in ctx.event_map()["events"]}
    for resolved_id in resolved:
        assert resolved_id in event_ids, f"meta-resolved event_id {resolved_id} missing from event_map"


def test_intercompany_sentinel_not_treated_as_account_code(ctx: BcpDevContext) -> None:
    chart_codes = {a["code"] for a in ctx.account_prefix_matrix()["posting_accounts"]} | {
        a["code"] for a in ctx.account_prefix_matrix()["alloc_accounts"]
    }
    # The sentinel strings are NOT in the chart of accounts.
    assert "intercompany_revenue_or_transfer_clearing" not in chart_codes
    assert "land_sale_revenue" not in chart_codes
    # But they ARE in the whitelist used by integrity validation.
    assert "intercompany_revenue_or_transfer_clearing" in ACCOUNT_SENTINEL_WHITELIST
    assert "land_sale_revenue" in ACCOUNT_SENTINEL_WHITELIST

    # Surface that the lot_sale events actually use these sentinels.
    events_by_id = {e["event_id"]: e for e in ctx.event_map()["events"]}
    sih_entries = events_by_id["lot_sale_sih"]["gl_entries"]
    sih_revenue = next(e for e in sih_entries if e.get("entry_id", "").endswith("intercompany"))
    assert sih_revenue["credit_account"] == "intercompany_revenue_or_transfer_clearing"
    assert sih_revenue.get("verification_status") == "pending_source_doc_review"

    rdy_entries = events_by_id["lot_sale_3rdy"]["gl_entries"]
    rdy_revenue = next(e for e in rdy_entries if e.get("entry_id", "").endswith("revenue"))
    assert rdy_revenue["credit_account"] == "land_sale_revenue"
    assert rdy_revenue.get("verification_status") == "pending_source_doc_review"


def test_method_id_ref_whitelist_shape() -> None:
    # Sanity check on whitelist values referenced in the implementation plan.
    for v in ("multiple", "computed_downstream", "none", "manual_input"):
        assert v in METHOD_ID_REF_WHITELIST
