"""MCP stdio server exposing the six BCPD workflow tools.

Thin transport shim over core.tools.bcpd_workflows. Business logic stays in
core/tools/bcpd_workflows.py — this module just (a) builds a ToolRegistry via
register_bcpd_workflow_tools(), (b) provides six typed wrapper functions
whose signatures FastMCP introspects into MCP JSON schemas, and (c) serves
over stdio for Claude Desktop / Claude web / any MCP-compatible client.

Read-only by construction: every BCPD Tool.run() returns a string; this
server only ferries inputs → registry.dispatch() → outputs.

Run:
    python -m bedrock.mcp.bcpd_server

No CLI flags. No env vars required. The bundled BCPD v2.1 state is loaded
from the repo paths (BcpdContext defaults to output/operating_state_v2_1_bcpd.json).

Python requirement: 3.10+ (the mcp SDK requirement). The rest of the
runtime works on 3.9+, but this module is gated on a newer Python.
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from core.agent.registry import ToolRegistry
from core.tools.bcpd_workflows import BcpdContext, register_bcpd_workflow_tools


SERVER_NAME = "bcpd-workflows"


def build_server(context: Optional[BcpdContext] = None) -> FastMCP:
    """Construct the FastMCP server with all six BCPD tools registered.

    Returns a configured FastMCP instance. Call `.run(transport="stdio")`
    on the result to serve, or use `registry_for_testing(context)` to get
    the ToolRegistry directly for in-process tests.
    """
    registry = _build_registry(context)
    mcp = FastMCP(SERVER_NAME)
    _register_all_tools(mcp, registry)
    return mcp


def registry_for_testing(context: Optional[BcpdContext] = None) -> ToolRegistry:
    """Return the same ToolRegistry the server builds, without starting MCP.

    Used by scripts/smoke_test_bcpd_mcp.py and tests/test_bcpd_mcp_server.py
    to exercise dispatch in-process. Keeps tests free of the MCP wire layer.
    """
    return _build_registry(context)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _build_registry(context: Optional[BcpdContext]) -> ToolRegistry:
    ctx = context or BcpdContext()
    return register_bcpd_workflow_tools(ToolRegistry(), ctx)


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


def main() -> None:
    """Entry point: build server and serve over stdio."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
