"""Smoke test for the hosted BCPD MCP server (streamable-HTTP transport).

Hits the live URL and runs the same 11 dispatches the local stdio smoke
test does — reusing the `CHECKS` list directly so the two tests cannot
drift.

Two auth postures supported (server-side `BCPD_MCP_AUTH_MODE`):

  - **bearer** (legacy / Adam's Claude Desktop posture): pass a token via
    `BCPD_MCP_TOKEN`. The smoke also asserts that a request **without**
    the bearer comes back 401.

  - **none** (current production posture for claude.ai web Custom
    Connector): leave `BCPD_MCP_TOKEN` unset. The smoke skips the
    Authorization header and instead asserts that an unauthenticated
    request succeeds (returns the MCP `initialize` handshake).

The byte-identity check of the seven protected v2.1 artifacts stays in
the local smoke test (`scripts/smoke_test_bcpd_mcp.py`) — we cannot
inspect the remote filesystem from here.

Usage::

    # No-auth (current production):
    BCPD_MCP_URL=https://bcpd-mcp.fly.dev/mcp \\
        python scripts/smoke_test_hosted_mcp.py

    # Bearer-protected:
    BCPD_MCP_URL=https://bcpd-mcp.fly.dev/mcp \\
    BCPD_MCP_TOKEN=$(cat .bcpd_mcp_token.local) \\
        python scripts/smoke_test_hosted_mcp.py

Exit code 0 on PASS, 1 on FAIL. Prints one line per dispatch.
"""
from __future__ import annotations

import asyncio
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional

# Make the existing CHECKS list importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from smoke_test_bcpd_mcp import CHECKS, WorkflowCheck  # noqa: E402

# MCP client over streamable-HTTP — the official SDK path.
from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.stderr.write(
            f"[hosted-smoke] FAIL: {name} env var required\n"
            "  Example:\n"
            "    BCPD_MCP_URL=https://bcpd-mcp.fly.dev/mcp \\\n"
            "    BCPD_MCP_TOKEN=xxx \\\n"
            "        python scripts/smoke_test_hosted_mcp.py\n"
        )
        sys.exit(1)
    return val


def _check_unauthenticated(url: str, expect_401: bool) -> bool:
    """Probe `/mcp` with no Authorization header.

    Two valid outcomes depending on server posture:

      - `expect_401=True`  (bearer mode): server MUST return 401.
      - `expect_401=False` (no-auth mode): server MUST succeed — practically
        any 2xx-ish MCP response from the SSE/JSON wire is fine. We send
        an `initialize` payload so the server returns a real MCP response
        instead of complaining about missing protocol fields.
    """
    label = "no-bearer-must-401" if expect_401 else "no-bearer-must-pass"
    print(f"[hosted-smoke] auth-boundary check ({label}): POST {url}")
    init_body = (
        b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":'
        b'{"protocolVersion":"2025-03-26","capabilities":{},'
        b'"clientInfo":{"name":"hosted-smoke","version":"0"}}}'
    )
    req = urllib.request.Request(url, method="POST", data=init_body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if expect_401:
                print(f"  [FAIL] expected 401, got {resp.status}")
                return False
            # No-auth mode: any 2xx is success.
            if 200 <= resp.status < 300:
                print(f"  [PASS] {resp.status} OK (no-auth public endpoint)")
                return True
            print(f"  [FAIL] expected 2xx, got {resp.status}")
            return False
    except urllib.error.HTTPError as e:
        if expect_401 and e.code == 401:
            print("  [PASS] 401 Unauthorized (bearer enforcement works)")
            return True
        if expect_401:
            print(f"  [FAIL] expected 401, got HTTP {e.code}")
            return False
        print(f"  [FAIL] expected 2xx in no-auth mode, got HTTP {e.code}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] request error: {type(e).__name__}: {e}")
        return False


def _check_healthz(base_url: str) -> bool:
    """GET <root>/healthz must return 200 + tool_count == 13 + no auth."""
    # Trim trailing /mcp/ from BCPD_MCP_URL to find /healthz on the same host.
    healthz = base_url.rstrip("/")
    if healthz.endswith("/mcp"):
        healthz = healthz[: -len("/mcp")]
    healthz = healthz + "/healthz"
    print(f"[hosted-smoke] healthz: GET {healthz}")
    try:
        with urllib.request.urlopen(healthz, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            if resp.status != 200:
                print(f"  [FAIL] status={resp.status}")
                return False
            if '"tool_count":13' not in body.replace(" ", ""):
                print(f"  [FAIL] tool_count != 13 in body: {body}")
                return False
            print(f"  [PASS] 200 OK; body={body.strip()}")
            return True
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] request error: {type(e).__name__}: {e}")
        return False


def _extract_text(content) -> str:
    """Flatten an MCP CallToolResult into a single string for substring checks."""
    parts = []
    for piece in content:
        # MCP TextContent has a `.text` attribute; other types ignored.
        text = getattr(piece, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


async def _run_dispatches(url: str, token: Optional[str]) -> List[str]:
    """Open one streamable-HTTP session, run all CHECKS, return failure msgs.

    When `token` is None / empty, no Authorization header is sent — for
    the no-auth server posture used by claude.ai web Custom Connector.
    """
    headers: dict = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    failures: List[str] = []

    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            if len(tool_names) != 13:
                failures.append(
                    f"tool_count expected 13, got {len(tool_names)}: "
                    f"{sorted(tool_names)}"
                )

            check: WorkflowCheck
            for check in CHECKS:
                print(f"[hosted-smoke] dispatch: {check.tool_name}({check.args})")
                result = await session.call_tool(check.tool_name, check.args)
                text = _extract_text(result.content)
                missing = [m for m in check.must_contain if m not in text]
                forbidden = [f for f in check.must_not_contain if f in text]
                if missing or forbidden:
                    msg = (
                        f"  [FAIL] {check.tool_name}: "
                        f"missing={missing} forbidden_found={forbidden}"
                    )
                    print(msg)
                    failures.append(msg)
                else:
                    print(f"  [PASS] {len(text)} chars")
    return failures


def main() -> int:
    url = _require_env("BCPD_MCP_URL")
    token = os.environ.get("BCPD_MCP_TOKEN")  # optional — None means no-auth mode
    mode = "bearer" if token else "none"

    print(f"[hosted-smoke] target: {url}")
    print(f"[hosted-smoke] mode:   {mode} (set BCPD_MCP_TOKEN to force bearer)")
    print(f"[hosted-smoke] checks: {len(CHECKS)} workflows + auth-boundary + healthz")

    # In bearer mode the boundary check expects 401; in no-auth mode it
    # expects a successful unauthenticated request.
    ok_unauth = _check_unauthenticated(url, expect_401=(mode == "bearer"))
    ok_healthz = _check_healthz(url)

    try:
        failures = asyncio.run(_run_dispatches(url, token))
    except Exception as e:  # noqa: BLE001
        print(f"[hosted-smoke] FAIL: session error: {type(e).__name__}: {e}")
        return 1

    if failures or not ok_unauth or not ok_healthz:
        print()
        print(f"[hosted-smoke] OVERALL: FAIL ({len(failures)} dispatch failures, "
              f"auth_check={'pass' if ok_unauth else 'fail'}, "
              f"healthz={'pass' if ok_healthz else 'fail'})")
        return 1
    print()
    print("[hosted-smoke] OVERALL: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
