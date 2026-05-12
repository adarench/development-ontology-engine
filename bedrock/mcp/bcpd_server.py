"""MCP stdio server exposing BCPD workflow tools + BCP Dev v0.2 process tools.

Thin transport shim over `core.tools.bcpd_workflows` (v2.1, six tools) and
`core.tools.bcp_dev_workflows` (v0.2, six tools). Business logic stays in
those modules — this module just (a) builds a ToolRegistry via both
register helpers, (b) provides typed wrapper functions whose signatures
FastMCP introspects into MCP JSON schemas, and (c) serves over stdio for
Claude Desktop / Claude web / any MCP-compatible client.

Read-only by construction: every Tool.run() returns a string; this server
only ferries inputs → registry.dispatch() → outputs.

The v0.2 read-only tool family adds six new handlers:
    query_bcp_dev_process
    explain_allocation_logic
    validate_crosswalk_readiness
    check_allocation_readiness
    detect_accounting_events
    generate_per_lot_output_spec

`generate_per_lot_output` (PR 5) is **not** exposed here — it lands later
when Finance signs off on the PF satellite replication.

Run:
    python -m bedrock.mcp.bcpd_server

No CLI flags. No env vars required. The bundled BCPD v2.1 state is loaded
from the repo paths (BcpdContext defaults to output/operating_state_v2_1_bcpd.json).
BCP Dev v0.2 state is loaded from `state/process_rules/*.json` and
`state/bcp_dev/*.json` via BcpDevContext.

Python requirement: 3.10+ (the mcp SDK requirement). The rest of the
runtime works on 3.9+, but this module is gated on a newer Python.
"""
from __future__ import annotations

from typing import Any, List, Optional

from mcp.server.fastmcp import FastMCP

from core.agent.bcp_dev_context import BcpDevContext
from core.agent.registry import ToolRegistry
from core.tools.bcp_dev_workflows import register_bcp_dev_workflow_tools
from core.tools.bcpd_workflows import BcpdContext, register_bcpd_workflow_tools


SERVER_NAME = "bcpd-workflows"


def build_server(
    bcpd_context: Optional[BcpdContext] = None,
    bcp_dev_context: Optional[BcpDevContext] = None,
) -> FastMCP:
    """Construct the FastMCP server with all v2.1 BCPD + v0.2 BCP Dev tools.

    Returns a configured FastMCP instance. Call `.run(transport="stdio")`
    on the result to serve, or use `registry_for_testing(...)` to get the
    ToolRegistry directly for in-process tests.
    """
    registry = _build_registry(bcpd_context, bcp_dev_context)
    mcp = FastMCP(SERVER_NAME)
    _register_all_tools(mcp, registry)
    return mcp


def registry_for_testing(
    bcpd_context: Optional[BcpdContext] = None,
    bcp_dev_context: Optional[BcpDevContext] = None,
) -> ToolRegistry:
    """Return the same ToolRegistry the server builds, without starting MCP.

    Used by scripts/smoke_test_bcpd_mcp.py and tests/test_bcpd_mcp_server.py
    to exercise dispatch in-process. Keeps tests free of the MCP wire layer.
    """
    return _build_registry(bcpd_context, bcp_dev_context)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _build_registry(
    bcpd_context: Optional[BcpdContext],
    bcp_dev_context: Optional[BcpDevContext],
) -> ToolRegistry:
    registry = ToolRegistry()
    register_bcpd_workflow_tools(registry, bcpd_context or BcpdContext())
    register_bcp_dev_workflow_tools(registry, bcp_dev_context or BcpDevContext())
    return registry


def _register_all_tools(mcp: FastMCP, registry: ToolRegistry) -> None:
    """Bind six typed handlers; FastMCP infers JSON Schema from signatures."""
    # We close over the registry by reading it from the enclosing scope inside
    # each handler. Tool descriptions come from the registered Tool instance
    # (.description) so the MCP-visible text matches what Claude sees today.

    desc_brief = registry._tools["generate_project_brief"].description
    desc_margin = registry._tools["review_margin_report_readiness"].description
    desc_false = registry._tools["find_false_precision_risks"].description
    desc_change = registry._tools["summarize_change_impact"].description
    desc_meeting = registry._tools["prepare_finance_land_review"].description
    desc_owner = registry._tools["draft_owner_update"].description

    @mcp.tool(name="generate_project_brief", description=desc_brief)
    async def generate_project_brief(project: str) -> str:
        """Generate a finance-ready brief for a single BCPD v2.1 project.

        `project` is the canonical project name (e.g. "Parkway Fields",
        "Harmony", "Scattered Lots"). Returns markdown.
        """
        return registry.dispatch("generate_project_brief", {"project": project})

    @mcp.tool(name="review_margin_report_readiness", description=desc_margin)
    async def review_margin_report_readiness(scope: str = "bcpd") -> str:
        """List BCPD projects safe vs unsafe for lot-level margin reporting.

        Surfaces the missing-cost-is-unknown hard rule and the projects
        with no GL coverage. Returns markdown.
        """
        return registry.dispatch("review_margin_report_readiness", {"scope": scope})

    @mcp.tool(name="find_false_precision_risks", description=desc_false)
    async def find_false_precision_risks(scope: str = "bcpd") -> str:
        """Enumerate where current BCPD reports may give false precision.

        Six numbered risks: range/shell rows, inferred decoder, Harmony
        3-tuple, SctLot vs Scarlet Ridge, HarmCo commercial, AultF B-suffix.
        Returns markdown.
        """
        return registry.dispatch("find_false_precision_risks", {"scope": scope})

    @mcp.tool(name="summarize_change_impact", description=desc_change)
    async def summarize_change_impact(
        from_version: str = "v2.0", to_version: str = "v2.1"
    ) -> str:
        """Summarize v2.0 → v2.1 correction deltas with dollar magnitudes.

        Default args produce the canonical v2.0→v2.1 change-impact view.
        Returns markdown.
        """
        return registry.dispatch(
            "summarize_change_impact",
            {"from_version": from_version, "to_version": to_version},
        )

    @mcp.tool(name="prepare_finance_land_review", description=desc_meeting)
    async def prepare_finance_land_review(scope: str = "bcpd") -> str:
        """Prepare a 30-minute finance / land / ops review agenda.

        Groups source-owner validation queue items by team. Returns markdown.
        """
        return registry.dispatch("prepare_finance_land_review", {"scope": scope})

    @mcp.tool(name="draft_owner_update", description=desc_owner)
    async def draft_owner_update(scope: str = "bcpd") -> str:
        """Draft a concise owner / executive update on BCPD v2.1 state.

        Honest about scope (BCPD only — Hillcrest / Flagship Belmont not
        available). Does NOT claim org-wide v2 is ready. Returns markdown.
        """
        return registry.dispatch("draft_owner_update", {"scope": scope})

    # ----------------- BCP Dev v0.2 forward-looking process tools -----------------

    desc_query_dev = registry._tools["query_bcp_dev_process"].description
    desc_explain = registry._tools["explain_allocation_logic"].description
    desc_validate_cw = registry._tools["validate_crosswalk_readiness"].description
    desc_check_alloc = registry._tools["check_allocation_readiness"].description
    desc_detect_events = registry._tools["detect_accounting_events"].description
    desc_spec = registry._tools["generate_per_lot_output_spec"].description

    @mcp.tool(name="query_bcp_dev_process", description=desc_query_dev)
    async def query_bcp_dev_process(question: str) -> str:
        """Answer process questions about BCP Dev v0.2 lifecycle, events,
        accounts, allocation methods, monthly review checks, or exception
        rules. Returns markdown with rule citations and provenance.
        """
        return registry.dispatch("query_bcp_dev_process", {"question": question})

    @mcp.tool(name="explain_allocation_logic", description=desc_explain)
    async def explain_allocation_logic(
        cost_type: str = "", event: str = ""
    ) -> str:
        """Explain the allocation method for a cost_type or accounting event.

        At least one of `cost_type` or `event` must be provided. Refuses
        to fabricate methods for unratified cases (range_row, warranty
        rate, SIH/3RDY revenue sentinels). Returns markdown.
        """
        return registry.dispatch(
            "explain_allocation_logic",
            {"cost_type": cost_type, "event": event},
        )

    @mcp.tool(name="validate_crosswalk_readiness", description=desc_validate_cw)
    async def validate_crosswalk_readiness(scope: str = "all") -> str:
        """Report unmapped, ambiguous, or stale crosswalk entries across
        the 13 BCP Dev v0.2 crosswalk tables. Returns markdown.
        """
        return registry.dispatch("validate_crosswalk_readiness", {"scope": scope})

    @mcp.tool(name="check_allocation_readiness", description=desc_check_alloc)
    async def check_allocation_readiness(
        community: str, phase: str = ""
    ) -> str:
        """Given a (community, phase?) pair, report whether allocation can
        run today: compute_status decision, MDA Day tie-status, input
        checklist, blocker list. Refuses to claim ready for LH, range-row
        methods, or master communities with no pricing. Returns markdown.
        """
        return registry.dispatch(
            "check_allocation_readiness",
            {"community": community, "phase": phase},
        )

    @mcp.tool(name="detect_accounting_events", description=desc_detect_events)
    async def detect_accounting_events(
        clickup_export_path: str = "",
        status_changes: Optional[List[Any]] = None,
    ) -> str:
        """Detect which ClickUp→GL events should fire for the supplied
        status changes (or CSV path). Detection only — never posts entries.
        Surfaces sentinel SIH/3RDY credit-account caveats and missing
        required inputs. Returns markdown.
        """
        return registry.dispatch(
            "detect_accounting_events",
            {
                "clickup_export_path": clickup_export_path,
                "status_changes": status_changes,
            },
        )

    @mcp.tool(name="generate_per_lot_output_spec", description=desc_spec)
    async def generate_per_lot_output_spec(
        community: str, phase: str = ""
    ) -> str:
        """Return the canonical Per-Lot Output shape for a (community, phase?)
        with per-field compute_status and blocker list. SPEC ONLY — never
        emits numeric dollar values. Returns markdown.
        """
        return registry.dispatch(
            "generate_per_lot_output_spec",
            {"community": community, "phase": phase},
        )

    desc_pf_replicate = registry._tools[
        "replicate_pf_satellite_per_lot_output"
    ].description

    @mcp.tool(
        name="replicate_pf_satellite_per_lot_output",
        description=desc_pf_replicate,
    )
    async def replicate_pf_satellite_per_lot_output(
        community: str = "Parkway Fields",
        phase: str = "",
    ) -> str:
        """PF-only read-through of the Parkway Allocation 2025.10 satellite
        workbook. NOT authoritative compute. Refuses Previous-section phases
        (B2, D1, G1 Church), all non-PF communities (point at
        `generate_per_lot_output_spec`), warranty cells, and range rows.
        Returns markdown.
        """
        return registry.dispatch(
            "replicate_pf_satellite_per_lot_output",
            {"community": community, "phase": phase},
        )


def main() -> None:
    """Entry point: build server and serve over stdio."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
