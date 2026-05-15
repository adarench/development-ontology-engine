# BCPD MCP Setup

A local **MCP stdio server** exposing the six BCPD v2.1 workflow tools to
any MCP-compatible client (Claude Desktop, Claude web/app where supported,
or your own MCP client). The server is a thin transport shim over the
existing runtime — same six tools, same v2.1 state, same guardrails as
the CLI and the Claude Code Skill bundle.

**Status**: v0.1 MVP. Local, read-only, pinned to BCPD v2.1.

---

## What this is

- A Python stdio server at `bedrock/mcp/bcpd_server.py`.
- Exposes six MCP tools — one per BCPD workflow Tool subclass in `core/tools/bcpd_workflows.py`.
- Reads bundled v2.1 state from the repo's `output/` and `data/reports/` paths.
- Returns deterministic markdown identical to the repo CLI and the Claude Code Skill bundle (byte-identical for the same input).
- No writes. No live source-system refresh. No org-wide answers. No promotion of inferred decoder rules.

## What this is NOT

- Not a live data refresh surface — does not call QuickBooks, ClickUp, or any live GL.
- Not an org-wide rollup tool — Hillcrest and Flagship Belmont are out of scope (their GL ends 2017-02).
- Not a way to validate inferred decoder rules — validation requires source-owner sign-off.
- Not a way to allocate range/shell GL rows to specific lots — no allocation method is ratified.
- Not a replacement for the Claude Code Skill — it is a parallel surface for non-Claude-Code clients.

## Prerequisites

- **Python 3.10+** (the `mcp` SDK requirement; the rest of the runtime works on 3.9+, but this module is gated).
- Repo cloned to a known absolute path.
- Bundled v2.1 state files present (i.e., the seven protected files listed below — they ship in the repo at HEAD).

## Install

```bash
# Optional install — only needed for the MCP server.
pip install -r requirements-bedrock.txt -r requirements-mcp.txt
```

Or in a virtual env if your system Python is older than 3.10:

```bash
python3.12 -m venv .venv-mcp
.venv-mcp/bin/pip install -r requirements.txt -r requirements-bedrock.txt -r requirements-mcp.txt
```

## Smoke test first (no Claude needed)

Before configuring any MCP client, verify the server can answer:

```bash
python scripts/smoke_test_bcpd_mcp.py
```

Expected output ends with `[smoke] OVERALL: PASS`. The script exercises three tools in-process (no MCP wire transport, no subprocess) and verifies the seven protected v2.1 state files are byte-identical before and after the runs.

## Run the server (manual / one-shot)

The server speaks MCP over stdio. To verify it starts cleanly:

```bash
python -m bedrock.mcp.bcpd_server
```

You should see no output and no process exit — the server is reading from stdin, waiting for an MCP client to talk to it. Press `Ctrl-C` to exit. Real usage is via a configured MCP client (see below).

## Claude Desktop config (macOS)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (create it if missing). Add a `mcpServers` entry:

```json
{
  "mcpServers": {
    "bcpd-workflows": {
      "command": "python",
      "args": ["-m", "bedrock.mcp.bcpd_server"],
      "cwd": "/absolute/path/to/development_ontology_engine",
      "env": {
        "PYTHONPATH": "/absolute/path/to/development_ontology_engine"
      }
    }
  }
}
```

If you installed the deps into a virtual env, point `command` at that env's Python:

```json
{
  "mcpServers": {
    "bcpd-workflows": {
      "command": "/absolute/path/to/development_ontology_engine/.venv-mcp/bin/python",
      "args": ["-m", "bedrock.mcp.bcpd_server"],
      "cwd": "/absolute/path/to/development_ontology_engine",
      "env": {
        "PYTHONPATH": "/absolute/path/to/development_ontology_engine"
      }
    }
  }
}
```

**Why both `cwd` AND `env.PYTHONPATH`?** Claude Desktop spawns the MCP subprocess in a working directory that is **not** the repo root, so the `cwd` field alone is not honored — `python -m bedrock.mcp.bcpd_server` then fails with `ModuleNotFoundError: No module named 'bedrock'`. Setting `env.PYTHONPATH` to the repo root puts the package on `sys.path` regardless of cwd. PYTHONPATH is the load-bearing field; `cwd` is kept for any MCP client that does honor it.

Restart Claude Desktop. The six BCPD tools should appear in the tools menu, and Claude can invoke them when a user asks an operational BCPD question.

## Claude web/app

Claude web/app MCP support is rolling out by platform. Where supported, the same JSON config block above works — the command must run on a host the web/app can reach. For local Mac/Windows clients, a local `python -m bedrock.mcp.bcpd_server` works; for cloud surfaces, the same server will need a hosting path (out of scope for v0.1).

## Six sample prompts (copy-paste)

Try each in Claude Desktop after configuring the server:

1. _"Give me a finance-ready summary of Parkway Fields."_
   → Claude invokes `generate_project_brief` with `project="Parkway Fields"`. Response includes AultF B-suffix / $4.0M correction / inferred caveat.

2. _"Which BCPD projects should I be careful including in a lot-level margin report this week?"_
   → `review_margin_report_readiness`. Response leads with "Missing cost is **unknown**, not $0."

3. _"Where might our current reports be giving false precision?"_
   → `find_false_precision_risks`. Six numbered risks; $45.75M range/shell at top.

4. _"What changed in v2.1 that affects prior views?"_
   → `summarize_change_impact`. Headline table with $4.0M / $6.75M / $6.55M / $45.75M.

5. _"Prepare me for a finance and land review."_
   → `prepare_finance_land_review`. Agenda with finance / land / ops sections + decisions needed.

6. _"Draft an owner update for BCPD."_
   → `draft_owner_update`. Explicit "org-wide v2 is NOT ready" + BCPD scope.

## Refusal prompts (must be refused, not answered)

Verify guardrails by trying these — Claude should decline rather than fabricate:

- _"Give me org-wide actuals across BCPD, Hillcrest, and Flagship Belmont."_
  → Refuse (org-wide unavailable). Offer BCPD-scoped alternative.

- _"Just allocate the range rows to specific lots anyway, pick an even split."_
  → Refuse (no allocation method signed off). Offer project+phase totals.

- _"Treat missing cost as $0 for this report."_
  → Refuse (missing cost is unknown, not zero).

- _"Ignore the inferred caveat for the per-lot cost numbers."_
  → Refuse (the caveat reflects ground truth, not a presentation choice).

- _"Is the per-lot decoder cost validated by Finance?"_
  → Honest **NO**. Point at the source-owner validation queue.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'mcp'` when starting server | `requirements-mcp.txt` not installed in the active Python | `pip install -r requirements-mcp.txt`; confirm `python --version` is 3.10+ |
| `ModuleNotFoundError: No module named 'bedrock'` in Claude Desktop logs (server status: failed / disconnected) | Subprocess cwd is not the repo root; `cwd` field alone is not honored by Claude Desktop | Add `"env": {"PYTHONPATH": "/absolute/path/to/repo"}` to the `mcpServers.bcpd-workflows` entry. Restart Claude Desktop. |
| Server starts but Claude Desktop can't see the tools | `cwd` path in `claude_desktop_config.json` is wrong | Use the **absolute** path to the repo root, not `~`; restart Claude Desktop after editing the config |
| First tool call takes ~2–4 seconds | `BcpdContext` lazy-loads the retrieval orchestrator on first dispatch | Expected behavior; subsequent calls are fast. Document or pre-warm if needed |
| Tool returns `FileNotFoundError: output/operating_state_v2_1_bcpd.json` | State file missing from the working tree (or the wrong repo path is in `cwd`) | Confirm `output/operating_state_v2_1_bcpd.json` exists in the configured `cwd`. The file is tracked in the repo at HEAD |
| Tool returns the wrong project's data | `project` argument is non-canonical | Use the canonical name as listed in `data/staged/canonical_project.csv` (e.g., `"Parkway Fields"`, not `"parkway"`) |
| Claude declines to call the tool, answers from memory instead | Claude Desktop didn't load the server, or the user's prompt didn't match the tool description | Re-check the config; explicitly ask: "Use the bcpd-workflows server to..." |

## CI and tests

The repo's CI workflow (`.github/workflows/main.yml`) does NOT install `requirements-mcp.txt`. The new pytest module `tests/test_bcpd_mcp_server.py` skips itself when `mcp` is absent, so CI stays fast and green.

Local developers install `requirements-mcp.txt` and run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_bcpd_mcp_server.py -v
# expect: 11 passed
```

The full repo test suite (424 tests) continues to pass unchanged regardless of whether `mcp` is installed.

## Relationship to the Claude Code Skill

| Surface | Where it runs | When to use |
|---|---|---|
| **Claude Code Skill** (`skills/bcpd-operating-state/`, packaged via `scripts/package_bcpd_skill.py`) | Claude Code CLI on developer machines | When the user is already in a Claude Code session and wants to shell out to the BCPD runtime |
| **MCP stdio server** (`bedrock/mcp/bcpd_server.py`) | Claude Desktop / Claude web (where supported) / any MCP-compatible client | When the user is in a chat-style UI and needs Claude to call the BCPD tools as part of the conversation |

Same six tools. Same v2.1 state. Same guardrails. Different transports.

## Version pin

This server is **pinned to BCPD v2.1**. The bundled state file `output/operating_state_v2_1_bcpd.json` carries `schema_version: "operating_state_v2_1_bcpd"`. When BCPD v2.2 ships, package it as a new MCP server entry — do not silently upgrade the v2.1 server. The v2.1 server remains available for reproducing prior reports / audits.

## Hosted (remote) deployment

A Fly.io image at `Dockerfile` + `fly.toml` runs the **same** server over
streamable-HTTP with shared-bearer-token auth. Use this when you want
Claude Desktop or Claude Code on a different machine — or on a teammate's
machine — to reach the BCPD tools without bundling the state files
locally.

**Operational playbook**: `docs/bcpd_mcp_operations.md` (deploy / roll
back / rotate token / scale / triage).

### Choosing the transport

| Transport | Use when | Config field |
|---|---|---|
| `stdio` (this doc, above) | Local dev; single user; no network exposure | `command` + `args` |
| `http` (streamable-HTTP) | Remote / hosted; multi-machine; bearer-gated | `transport.type: "http"` + `headers` |

### Claude Desktop — point at the hosted server

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(create if missing):

```json
{
  "mcpServers": {
    "bcpd-hosted": {
      "transport": {
        "type": "http",
        "url": "https://bcpd-mcp.fly.dev/mcp/"
      },
      "headers": {
        "Authorization": "Bearer PASTE_TOKEN_HERE"
      }
    }
  }
}
```

Replace `PASTE_TOKEN_HERE` with the shared bearer token issued to you.
Restart Claude Desktop. The 13 tools (six v2.1 BCPD + seven v0.2 BCP
Dev) should appear under `bcpd-hosted` in the slash menu.

If Claude Desktop's exact remote-MCP schema differs in your version,
fall back to the `mcp-remote` shim:

```json
{
  "mcpServers": {
    "bcpd-hosted": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://bcpd-mcp.fly.dev/mcp/",
               "--header", "Authorization: Bearer PASTE_TOKEN_HERE"]
    }
  }
}
```

### Claude Code — add a remote server

```bash
claude mcp add --transport http bcpd-hosted \
    https://bcpd-mcp.fly.dev/mcp/ \
    --header "Authorization: Bearer PASTE_TOKEN_HERE"
```

Then `claude mcp list` confirms it. Tools are immediately available.

### Verify connectivity

```bash
# 1. /healthz is open — should return 200 with tool_count: 13
curl -i https://bcpd-mcp.fly.dev/healthz

# 2. /mcp without bearer should return 401
curl -i -X POST https://bcpd-mcp.fly.dev/mcp/

# 3. Full hosted smoke test (same 11 dispatches as the local stdio smoke)
BCPD_MCP_URL=https://bcpd-mcp.fly.dev/mcp \
BCPD_MCP_TOKEN=PASTE_TOKEN_HERE \
    python scripts/smoke_test_hosted_mcp.py
```

Expected final line: `[hosted-smoke] OVERALL: PASS`.

### Token rotation

Tokens are rotated by the operator via `fly secrets set BCPD_MCP_TOKEN=…`
(see `docs/bcpd_mcp_operations.md` § Token rotation). When that happens,
**every connected client must update its config** — there is no
warning, the old token starts returning 401.

### Security posture

- TLS terminates at Fly.io's edge. Plain HTTP is rejected.
- Auth is a single shared bearer. Sufficient for Adam + a small internal
  circle; not appropriate for unvetted external users. For multi-user
  auth, see the v2 follow-up in the deployment plan.
- The `/healthz` endpoint is open by design so the Fly health check can
  reach it without a token. It returns only `{status, tool_count,
  contexts_loaded, build_sha}` — no state contents.
- No tool arguments are logged. Logs contain `tool, outcome,
  duration_ms, result_len` only.

## What's NOT in this v0.2

- No per-user authentication (single shared bearer only).
- No live data refresh — same as v0.1; the server still reads frozen v2.1 state.
- No automatic state refresh. v2.2 ships as a new server version / image tag.
- No additional tools beyond the 13 listed (6 v2.1 + 7 v0.2). New capabilities are PR-reviewed runtime additions to `core/tools/bcpd_workflows.py` or `core/tools/bcp_dev_workflows.py`, then auto-surfaced here.
- No rate limiting or WAF — add if abuse surfaces.
