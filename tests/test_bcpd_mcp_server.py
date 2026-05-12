"""Pytest tests for the BCPD MCP server.

In-process only — never starts the MCP wire transport. Tests:
  - server registration shape (six tools, correct names, correct schemas)
  - dispatch path returns expected BCPD content
  - read-only contract (seven protected files byte-identical after runs)
  - guardrail content (owner update does NOT claim org-wide v2 ready)

The module is skip-gracefully: if the `mcp` SDK isn't installed (e.g. CI
where requirements-mcp.txt is NOT installed), every test in this module
is skipped with a clear reason. Local developers install
`requirements-mcp.txt` to run.

Run:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_bcpd_mcp_server.py -v
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Dict

import pytest


REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


try:
    from mcp.server.fastmcp import FastMCP  # noqa: F401

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not MCP_AVAILABLE,
    reason="mcp SDK not installed; pip install -r requirements-mcp.txt (Python 3.10+)",
)


# These imports are guarded by the skip marker — they only need to succeed
# when mcp is available. When mcp isn't available, every test below skips
# and these imports are never executed.
if MCP_AVAILABLE:
    from bedrock.mcp.bcpd_server import (
        SERVER_NAME,
        build_server,
        registry_for_testing,
    )


EXPECTED_TOOL_NAMES = {
    # v2.1 BCPD operating-state tools (unchanged)
    "generate_project_brief",
    "review_margin_report_readiness",
    "find_false_precision_risks",
    "summarize_change_impact",
    "prepare_finance_land_review",
    "draft_owner_update",
    # v0.2 BCP Dev forward-looking process tools (PR 4)
    "query_bcp_dev_process",
    "explain_allocation_logic",
    "validate_crosswalk_readiness",
    "check_allocation_readiness",
    "detect_accounting_events",
    "generate_per_lot_output_spec",
    # PR 5a — PF satellite workbook replication (read-through, not compute)
    "replicate_pf_satellite_per_lot_output",
}

PROTECTED_PATHS = (
    "output/operating_state_v2_1_bcpd.json",
    "output/agent_context_v2_1_bcpd.md",
    "output/state_quality_report_v2_1_bcpd.md",
    "data/reports/v2_0_to_v2_1_change_log.md",
    "data/reports/coverage_improvement_opportunities.md",
    "data/reports/crosswalk_quality_audit_v1.md",
    "data/reports/vf_lot_code_decoder_v1_report.md",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def server():
    return build_server()


@pytest.fixture(scope="module")
def registry():
    return registry_for_testing()


def _async(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _snapshot() -> Dict[str, str]:
    return {
        rel: _sha256(REPO / rel)
        for rel in PROTECTED_PATHS
        if (REPO / rel).exists()
    }


# ---------------------------------------------------------------------------
# Server registration shape
# ---------------------------------------------------------------------------


def test_server_name(server):
    assert server.name == SERVER_NAME == "bcpd-workflows"


def test_server_registers_six_tools(server):
    # Now thirteen: six v2.1 BCPD + six v0.2 BCP Dev process + one PF
    # satellite replication tool. Name preserved for back-compat with
    # existing test plans / CI labels.
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOL_NAMES
    assert len(names) == 13


def test_each_tool_schema_is_valid_json_object(server):
    tools = asyncio.run(server.list_tools())
    for t in tools:
        schema = t.inputSchema
        assert isinstance(schema, dict), f"{t.name} inputSchema is not a dict"
        assert schema.get("type") == "object", f"{t.name} inputSchema type != object"
        assert "properties" in schema, f"{t.name} inputSchema missing 'properties'"


def test_project_brief_requires_project_arg(server):
    tools = asyncio.run(server.list_tools())
    by_name = {t.name: t for t in tools}
    schema = by_name["generate_project_brief"].inputSchema
    assert "project" in schema["properties"]
    assert "project" in schema.get("required", [])


def test_scope_tools_have_scope_default(server):
    """The four `--scope bcpd` tools must have `scope` as a property but NOT required."""
    tools = asyncio.run(server.list_tools())
    by_name = {t.name: t for t in tools}
    for tool_name in (
        "review_margin_report_readiness",
        "find_false_precision_risks",
        "prepare_finance_land_review",
        "draft_owner_update",
    ):
        schema = by_name[tool_name].inputSchema
        assert "scope" in schema["properties"], f"{tool_name} missing scope property"
        assert "scope" not in schema.get("required", []), (
            f"{tool_name} should have scope as optional (has default 'bcpd')"
        )


def test_server_build_is_deterministic():
    a = build_server()
    b = build_server()
    a_names = {t.name for t in asyncio.run(a.list_tools())}
    b_names = {t.name for t in asyncio.run(b.list_tools())}
    assert a_names == b_names


# ---------------------------------------------------------------------------
# Dispatch path — content & contract
# ---------------------------------------------------------------------------


def test_dispatch_parkway_brief_returns_aultf_content(registry):
    md = registry.dispatch("generate_project_brief", {"project": "Parkway Fields"})
    assert "Parkway Fields" in md
    assert "AultF" in md
    assert "B1" in md
    assert "$4,006,662" in md
    assert "inferred" in md.lower()


def test_dispatch_unknown_tool_raises_keyerror(registry):
    with pytest.raises(KeyError):
        registry.dispatch("nonexistent_tool", {})


def test_dispatch_empty_kwargs_uses_defaults(registry):
    md = registry.dispatch("summarize_change_impact", {})
    assert "Change Impact" in md
    assert "$4,006,662" in md  # AultF — proves default path produced full content


def test_owner_update_does_not_claim_orgwide_v2_ready(registry):
    md = registry.dispatch("draft_owner_update", {"scope": "bcpd"}).lower()
    assert "bcpd" in md
    assert "hillcrest" in md
    # Must explicitly state org-wide v2 is NOT ready
    assert any(
        phrase in md
        for phrase in (
            "org-wide v2 is not ready",
            "org-wide v2 is **not** ready",
            "org-wide v2 is not available",
            "org-wide v2 is **not** available",
        )
    ), f"owner update must explicitly state org-wide v2 is NOT ready"
    # Must NOT contain any positive claim
    for forbidden in (
        "org-wide v2 is ready",
        "org-wide v2 is available",
        "org-wide rollup is ready",
    ):
        assert forbidden not in md


# ---------------------------------------------------------------------------
# Read-only contract
# ---------------------------------------------------------------------------


def test_dispatch_does_not_mutate_protected_files(registry):
    pre = _snapshot()
    assert pre, "no protected files found — test pre-condition broken"

    # Run every one of the six tools
    registry.dispatch("generate_project_brief", {"project": "Parkway Fields"})
    registry.dispatch("review_margin_report_readiness", {"scope": "bcpd"})
    registry.dispatch("find_false_precision_risks", {"scope": "bcpd"})
    registry.dispatch("summarize_change_impact", {})
    registry.dispatch("prepare_finance_land_review", {"scope": "bcpd"})
    registry.dispatch("draft_owner_update", {"scope": "bcpd"})

    post = _snapshot()
    mutated = [rel for rel, h in pre.items() if post.get(rel) != h]
    assert not mutated, f"protected files mutated: {mutated}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
