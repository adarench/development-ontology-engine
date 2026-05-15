"""MCP server exposing BCPD workflow tools + BCP Dev v0.2 process tools.

Thin transport shim over `core.tools.bcpd_workflows` (v2.1, six tools) and
`core.tools.bcp_dev_workflows` (v0.2, seven tools). Business logic stays
in those modules — this module just (a) builds a ToolRegistry via both
register helpers, (b) provides typed wrapper functions whose signatures
FastMCP introspects into MCP JSON schemas, and (c) serves over stdio OR
streamable-HTTP for Claude Desktop / Claude Code / any MCP-compatible
client.

Read-only by construction: every Tool.run() returns a string; this server
only ferries inputs → registry.dispatch() → outputs.

Two transports, selected by env var:

    BCPD_MCP_TRANSPORT=stdio   (default — local, for Claude Desktop config)
    BCPD_MCP_TRANSPORT=http    (hosted streamable-HTTP)

For http, choose an auth posture:

    BCPD_MCP_AUTH_MODE=bearer  (default — requires BCPD_MCP_TOKEN; what
                                Adam's Claude Desktop config uses)
    BCPD_MCP_AUTH_MODE=none    (public; required for claude.ai web's
                                Custom Connector UI, which has no bearer
                                field — only OAuth, which we don't ship)

Optional: BCPD_MCP_HOST (default 0.0.0.0), BCPD_MCP_PORT (default 8000),
BCPD_BUILD_SHA (surfaced on /healthz), BCPD_MCP_ALLOWED_HOSTS
(comma-separated Host header allowlist; required when binding to
0.0.0.0 because the MCP SDK auto-restricts to localhost otherwise).

Run:
    python -m bedrock.mcp.bcpd_server

The bundled BCPD v2.1 state is loaded from the repo paths (BcpdContext
defaults to output/operating_state_v2_1_bcpd.json). BCP Dev v0.2 state
is loaded from `state/process_rules/*.json` and `state/bcp_dev/*.json`
via BcpDevContext.

Python requirement: 3.10+ (the mcp SDK requirement). The rest of the
runtime works on 3.9+, but this module is gated on a newer Python.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import sys
import time
from typing import Any, List, Optional

from mcp.server.fastmcp import FastMCP

from core.agent.bcp_dev_context import BcpDevContext
from core.agent.registry import ToolRegistry
from core.tools.bcp_dev_workflows import register_bcp_dev_workflow_tools
from core.tools.bcpd_workflows import BcpdContext, register_bcpd_workflow_tools


_log = logging.getLogger("bcpd_mcp")


SERVER_NAME = "bcpd-workflows"


def build_server(
    bcpd_context: Optional[BcpdContext] = None,
    bcp_dev_context: Optional[BcpDevContext] = None,
) -> FastMCP:
    """Construct the FastMCP server with all v2.1 BCPD + v0.2 BCP Dev tools.

    Returns a configured FastMCP instance. Call `.run(transport="stdio")`
    on the result to serve, or use `registry_for_testing(...)` to get the
    ToolRegistry directly for in-process tests.

    Host + transport-security wiring:
        FastMCP's default `host="127.0.0.1"` auto-enables DNS-rebinding
        protection with a localhost-only allowlist. When the operator
        sets BCPD_MCP_HOST=0.0.0.0 (or anything non-localhost) we pass
        through that listen address AND an explicit allowlist via
        BCPD_MCP_ALLOWED_HOSTS (comma-separated). Without the allowlist,
        any non-localhost Host header (e.g. `bcpd-mcp.fly.dev`) returns
        421 "Invalid Host header" — the symptom we hit on first deploy.
    """
    registry = _build_registry(bcpd_context, bcp_dev_context)
    mcp = FastMCP(SERVER_NAME, **_fastmcp_kwargs_from_env())
    _register_all_tools(mcp, registry)
    return mcp


def _fastmcp_kwargs_from_env() -> dict:
    """Resolve listen host + transport-security from env.

    Only relevant for HTTP transport. Stdio ignores these; the kwargs are
    benign there.

    Two transport-security postures:

    - **`BCPD_MCP_AUTH_MODE=none`** (public deployment for claude.ai web):
      explicitly **disable** the MCP SDK's DNS-rebinding protection. The
      protection exists to defend localhost MCP servers from a browser
      being tricked into making cross-origin requests via DNS rebinding;
      it is meaningless for a public server behind a cloud edge proxy
      with TLS (we can't be DNS-rebound the way a localhost service can,
      and there's no authenticated state to abuse via CSRF since this
      surface is anonymous and read-only).

      Empirical reason: with the protection on, Anthropic's backend
      probes our `/mcp` with `Origin: https://claude.ai`, the SDK
      rejects it `403 "Invalid Origin header"` on the CORS preflight,
      and the claude.ai UI hangs forever on "Checking connection…".
      Disabling DNS-rebinding protection unblocks the handshake.

      Host validation in this mode falls back to FastMCP's defaults
      (auto-allowlist for localhost when host=127.0.0.1; no host check
      when host=0.0.0.0).

    - **`BCPD_MCP_AUTH_MODE=bearer`** (engineering / Claude Desktop):
      keep the SDK's belt-and-suspenders host+origin allowlist driven
      by `BCPD_MCP_ALLOWED_HOSTS`. The bearer-token gate is the real
      auth, but layered host validation costs nothing on this path.
    """
    host = os.environ.get("BCPD_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("BCPD_MCP_PORT", "8000"))
    kwargs: dict = {"host": host, "port": port}

    auth_mode = os.environ.get("BCPD_MCP_AUTH_MODE", "bearer").lower()

    from mcp.server.transport_security import TransportSecuritySettings

    if auth_mode == "none":
        # Explicitly disable DNS-rebinding protection. Without this kwarg,
        # FastMCP's auto-enable (host==127.0.0.1 → localhost-only allowlist)
        # would fire when running locally, and BCPD_MCP_ALLOWED_HOSTS would
        # configure a host+origin allowlist that excludes claude.ai. Both
        # paths cause the claude.ai "Checking connection…" hang.
        kwargs["transport_security"] = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )
        return kwargs

    # bearer mode — original posture
    raw = os.environ.get("BCPD_MCP_ALLOWED_HOSTS", "").strip()
    if raw:
        hosts = [h.strip() for h in raw.split(",") if h.strip()]
        # Allow both the bare host (Fly's Host header) and the "host:*"
        # wildcard form (covers local dev on any port).
        wildcards = [f"{h}:*" for h in hosts if ":" not in h]
        origins = [f"https://{h}" for h in hosts if ":" not in h]
        origins += [f"http://{h}" for h in hosts if ":" not in h]
        kwargs["transport_security"] = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts + wildcards,
            allowed_origins=origins,
        )
    return kwargs


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
        return _safe_dispatch(registry,"generate_project_brief", {"project": project})

    @mcp.tool(name="review_margin_report_readiness", description=desc_margin)
    async def review_margin_report_readiness(scope: str = "bcpd") -> str:
        """List BCPD projects safe vs unsafe for lot-level margin reporting.

        Surfaces the missing-cost-is-unknown hard rule and the projects
        with no GL coverage. Returns markdown.
        """
        return _safe_dispatch(registry,"review_margin_report_readiness", {"scope": scope})

    @mcp.tool(name="find_false_precision_risks", description=desc_false)
    async def find_false_precision_risks(scope: str = "bcpd") -> str:
        """Enumerate where current BCPD reports may give false precision.

        Six numbered risks: range/shell rows, inferred decoder, Harmony
        3-tuple, SctLot vs Scarlet Ridge, HarmCo commercial, AultF B-suffix.
        Returns markdown.
        """
        return _safe_dispatch(registry,"find_false_precision_risks", {"scope": scope})

    @mcp.tool(name="summarize_change_impact", description=desc_change)
    async def summarize_change_impact(
        from_version: str = "v2.0", to_version: str = "v2.1"
    ) -> str:
        """Summarize v2.0 → v2.1 correction deltas with dollar magnitudes.

        Default args produce the canonical v2.0→v2.1 change-impact view.
        Returns markdown.
        """
        return _safe_dispatch(registry,
            "summarize_change_impact",
            {"from_version": from_version, "to_version": to_version},
        )

    @mcp.tool(name="prepare_finance_land_review", description=desc_meeting)
    async def prepare_finance_land_review(scope: str = "bcpd") -> str:
        """Prepare a 30-minute finance / land / ops review agenda.

        Groups source-owner validation queue items by team. Returns markdown.
        """
        return _safe_dispatch(registry,"prepare_finance_land_review", {"scope": scope})

    @mcp.tool(name="draft_owner_update", description=desc_owner)
    async def draft_owner_update(scope: str = "bcpd") -> str:
        """Draft a concise owner / executive update on BCPD v2.1 state.

        Honest about scope (BCPD only — Hillcrest / Flagship Belmont not
        available). Does NOT claim org-wide v2 is ready. Returns markdown.
        """
        return _safe_dispatch(registry,"draft_owner_update", {"scope": scope})

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
        return _safe_dispatch(registry,"query_bcp_dev_process", {"question": question})

    @mcp.tool(name="explain_allocation_logic", description=desc_explain)
    async def explain_allocation_logic(
        cost_type: str = "", event: str = ""
    ) -> str:
        """Explain the allocation method for a cost_type or accounting event.

        At least one of `cost_type` or `event` must be provided. Refuses
        to fabricate methods for unratified cases (range_row, warranty
        rate, SIH/3RDY revenue sentinels). Returns markdown.
        """
        return _safe_dispatch(registry,
            "explain_allocation_logic",
            {"cost_type": cost_type, "event": event},
        )

    @mcp.tool(name="validate_crosswalk_readiness", description=desc_validate_cw)
    async def validate_crosswalk_readiness(scope: str = "all") -> str:
        """Report unmapped, ambiguous, or stale crosswalk entries across
        the 13 BCP Dev v0.2 crosswalk tables. Returns markdown.
        """
        return _safe_dispatch(registry,"validate_crosswalk_readiness", {"scope": scope})

    @mcp.tool(name="check_allocation_readiness", description=desc_check_alloc)
    async def check_allocation_readiness(
        community: str, phase: str = ""
    ) -> str:
        """Given a (community, phase?) pair, report whether allocation can
        run today: compute_status decision, MDA Day tie-status, input
        checklist, blocker list. Refuses to claim ready for LH, range-row
        methods, or master communities with no pricing. Returns markdown.
        """
        return _safe_dispatch(registry,
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
        return _safe_dispatch(registry,
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
        return _safe_dispatch(registry,
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
        return _safe_dispatch(registry,
            "replicate_pf_satellite_per_lot_output",
            {"community": community, "phase": phase},
        )


# ---------------------------------------------------------------------------
# Hosted-transport helpers (M2–M6 in the deployment plan)
# ---------------------------------------------------------------------------

# Outcome label = "ok" | "refusal" | "unknown_tool" | "error"
_REFUSAL_PREFIX = "## Refused"


def _safe_dispatch(registry: ToolRegistry, name: str, args: dict) -> str:
    """Wrap ToolRegistry.dispatch with refusal-shaped error handling.

    KeyError (unknown tool) and any unexpected exception are converted into
    a markdown string that begins with `## Refused` and carries
    `(provenance: mcp_boundary)` so MCP clients see the same refusal posture
    that tool-level refusals use. This prevents raw stacktraces from leaking
    over the wire and keeps client-side rendering uniform.

    Missing-state-at-boot is NOT caught here — `_warmup` runs before serving
    HTTP so the process exits non-zero and the orchestrator (Fly machine,
    docker, etc.) makes the failure visible.

    Logs one JSON line per call to stderr. Arguments are NEVER logged
    (project names and queries may be confidential); only tool name,
    outcome, duration, and result length.
    """
    t0 = time.monotonic()
    outcome = "ok"
    result_len = 0
    try:
        out = registry.dispatch(name, args)
        if isinstance(out, str) and out.lstrip().startswith(_REFUSAL_PREFIX):
            outcome = "refusal"
        result_len = len(out) if isinstance(out, str) else 0
        return out
    except KeyError as exc:
        outcome = "unknown_tool"
        msg = (
            f"{_REFUSAL_PREFIX}\n\n"
            f"Unknown tool `{name}` at the MCP boundary. "
            f"(provenance: mcp_boundary)\n\n"
            f"Detail: {exc}"
        )
        result_len = len(msg)
        return msg
    except Exception as exc:  # noqa: BLE001 — boundary wrapper, intentional
        outcome = "error"
        # Log the full exception only on stderr; never include it in the
        # response payload because tool input is in scope. The response
        # surfaces only the exception class to aid client-side triage.
        _log.exception("tool_error", extra={"tool": name})
        msg = (
            f"{_REFUSAL_PREFIX}\n\n"
            f"Tool `{name}` raised `{type(exc).__name__}` at the MCP "
            f"boundary. (provenance: mcp_boundary)\n\n"
            f"Detail: {exc}"
        )
        result_len = len(msg)
        return msg
    finally:
        duration_ms = int((time.monotonic() - t0) * 1000)
        # Single JSON line per dispatch — `fly logs | jq` friendly.
        _log.info(
            json.dumps(
                {
                    "evt": "dispatch",
                    "tool": name,
                    "outcome": outcome,
                    "duration_ms": duration_ms,
                    "result_len": result_len,
                }
            )
        )


class BearerAuthMiddleware:
    """ASGI middleware enforcing `Authorization: Bearer <token>`.

    Constant-time comparison via `hmac.compare_digest`. Returns HTTP 401
    with a `WWW-Authenticate: Bearer realm="bcpd-mcp"` header on missing or
    mismatched tokens. Paths in `exempt_paths` are passed through without
    auth — used for `/healthz` so the orchestrator's health check does not
    need to carry the secret.

    Not used in stdio mode. Not used in tests. Only wired up in `main()`
    when transport=http.
    """

    def __init__(
        self,
        app,
        token: str,
        exempt_paths: tuple = ("/healthz",),
    ) -> None:
        if not token:
            raise ValueError("BearerAuthMiddleware: token must be non-empty")
        self._app = app
        self._expected = f"Bearer {token}".encode("utf-8")
        self._exempt = set(exempt_paths)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            # Lifespan / websocket etc — pass through untouched.
            await self._app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in self._exempt:
            await self._app(scope, receive, send)
            return
        auth_header = b""
        for k, v in scope.get("headers") or []:
            if k.lower() == b"authorization":
                auth_header = v
                break
        if auth_header and hmac.compare_digest(auth_header, self._expected):
            await self._app(scope, receive, send)
            return
        # Reject — minimal JSON body, WWW-Authenticate per RFC 6750.
        body = b'{"error":"unauthorized"}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"www-authenticate", b'Bearer realm="bcpd-mcp"'),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def _warmup(bcpd_ctx: BcpdContext, bcp_dev_ctx: BcpDevContext) -> None:
    """Force both contexts to load before serving.

    Reuses existing entry points — `BcpdContext.state` property and
    `BcpDevContext.load_all()` — so any state-file regression surfaces
    here rather than on first user request. Any failure propagates;
    the orchestrator will see a non-zero exit and surface it in logs.
    """
    _log.info(json.dumps({"evt": "warmup_start"}))
    _ = bcpd_ctx.state  # forces FileConnector load of v2.1 JSON
    bcp_dev_ctx.load_all()  # forces all 11 v0.2 JSON files + validation
    _log.info(json.dumps({"evt": "warmup_done"}))


def _install_healthz(app, registry: ToolRegistry) -> None:
    """Append GET /healthz to the Starlette app.

    Public (no auth, exempt via the bearer middleware). Returns the tool
    count, contexts-loaded flag, and the build SHA from env. Used as the
    orchestrator's HTTP health check.
    """
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    tool_count = len(registry._tools)  # private attr — single source of truth
    build_sha = os.environ.get("BCPD_BUILD_SHA", "unknown")

    async def healthz(_request):
        return JSONResponse(
            {
                "status": "ok",
                "tool_count": tool_count,
                "contexts_loaded": True,
                "build_sha": build_sha,
            }
        )

    app.router.routes.append(Route("/healthz", healthz, methods=["GET"]))


def _configure_http_logging() -> None:
    """One-shot stderr logger config for the http transport.

    JSON-shaped lines so `fly logs | jq` works. Logger name `bcpd_mcp`
    is used by `_safe_dispatch` and the warmup helpers.
    """
    if _log.handlers:
        return  # already configured (e.g., test harness reusing the module)
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            '{"ts":"%(asctime)s","lvl":"%(levelname)s","logger":'
            '"%(name)s","msg":%(message)s}',
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    _log.addHandler(handler)
    _log.setLevel(logging.INFO)
    _log.propagate = False


def _run_http(server: FastMCP, bcpd_ctx: BcpdContext, bcp_dev_ctx: BcpDevContext) -> None:
    """Serve streamable-HTTP under uvicorn with optional bearer-token middleware.

    Auth mode comes from `BCPD_MCP_AUTH_MODE` (default `bearer`):

      - `bearer` — requires `BCPD_MCP_TOKEN`; rejects unauthenticated `/mcp`
        requests with 401. Original posture; used by Adam's Claude Desktop
        client and the existing bearer-flavored hosted smoke.

      - `none`   — no auth middleware at all. `/mcp` is public. This is the
        posture required for claude.ai web's Custom Connector UI today
        because that UI cannot paste static bearer tokens — it only does
        OAuth, and we don't ship an OAuth 2.1 authorization server. The
        tools are read-only and the data is internal-but-not-secret BCPD
        operational content, so URL-only access is an acceptable v1 trade.
        Boot emits a loud `auth_disabled` log line as the operator's
        reminder. See plan / risks doc for the full rationale.

    Order matters: warmup BEFORE we accept connections so the orchestrator
    sees boot failures, not request-time errors. Health route mounted
    before any middleware so /healthz remains reachable in both modes.
    """
    _configure_http_logging()
    _warmup(bcpd_ctx, bcp_dev_ctx)

    mode = os.environ.get("BCPD_MCP_AUTH_MODE", "bearer").lower()
    if mode not in {"bearer", "none"}:
        raise SystemExit(
            f"Unknown BCPD_MCP_AUTH_MODE={mode!r} — expected 'bearer' or 'none'."
        )

    app = server.streamable_http_app()
    # Rebuild the registry independently for /healthz so we don't reach
    # into FastMCP internals.
    registry = _build_registry(bcpd_ctx, bcp_dev_ctx)
    _install_healthz(app, registry)

    if mode == "bearer":
        token = os.environ.get("BCPD_MCP_TOKEN")
        if not token:
            raise SystemExit(
                "BCPD_MCP_TOKEN env var is required when "
                "BCPD_MCP_AUTH_MODE=bearer. Set a non-empty shared bearer "
                "token (e.g. `openssl rand -hex 32`) before starting, or "
                "switch to BCPD_MCP_AUTH_MODE=none for a public deployment."
            )
        app.add_middleware(BearerAuthMiddleware, token=token)
        _log.info(json.dumps({"evt": "auth_mode", "mode": "bearer"}))
    else:
        # No bearer middleware. Boot log line is the operator's reminder
        # that /mcp is now publicly reachable from any client on the
        # internet.
        _log.warning(
            json.dumps(
                {
                    "evt": "auth_disabled",
                    "warning": "MCP /mcp endpoint is public (no bearer); "
                    "intended for claude.ai web Custom Connector. Read-only "
                    "contract still applies. Set BCPD_MCP_AUTH_MODE=bearer "
                    "to re-enable token gating.",
                }
            )
        )
        # Add CORS middleware so OPTIONS preflight succeeds (the MCP SDK
        # streamable-HTTP app only handles GET/POST/DELETE on /mcp and
        # returns 405 on OPTIONS). claude.ai's backend fetchers are
        # server-side and theoretically don't trigger preflight, but
        # browser-side probes from the connector UI configuration step
        # might. allow_origins="*" is safe here because the surface is
        # anonymous and read-only — no cookies, no credentials, no
        # CSRF target. Same reasoning as disabling DNS-rebinding above.
        from starlette.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["*"],
            allow_credentials=False,
            # Expose the MCP session ID header so clients can read it.
            expose_headers=["mcp-session-id"],
        )
        _log.info(json.dumps({"evt": "cors_open", "origins": "*"}))

    host = os.environ.get("BCPD_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("BCPD_MCP_PORT", "8000"))
    _log.info(
        json.dumps({"evt": "http_listen", "host": host, "port": port, "auth_mode": mode})
    )

    import uvicorn

    uvicorn.run(app, host=host, port=port, log_config=None)


def main() -> None:
    """Entry point: build server and serve over stdio OR streamable-HTTP.

    Transport selected by `BCPD_MCP_TRANSPORT` env var (default `stdio`).
    """
    transport = os.environ.get("BCPD_MCP_TRANSPORT", "stdio").lower()
    if transport not in {"stdio", "http"}:
        raise SystemExit(
            f"Unknown BCPD_MCP_TRANSPORT={transport!r} — expected "
            "'stdio' or 'http'."
        )
    bcpd_ctx = BcpdContext()
    bcp_dev_ctx = BcpDevContext()
    server = build_server(bcpd_ctx, bcp_dev_ctx)
    if transport == "stdio":
        server.run(transport="stdio")
        return
    _run_http(server, bcpd_ctx, bcp_dev_ctx)


if __name__ == "__main__":
    main()
