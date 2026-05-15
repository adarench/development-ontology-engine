# BCPD MCP — Operational Runbook

Operator-facing reference for the hosted BCPD MCP server on Fly.io.
For client-side connection setup see `docs/bcpd_mcp_setup.md` §
"Hosted (remote) deployment".

**App name (Fly.io):** `bcpd-mcp`
**Primary region:** `iad`
**Source of truth:** `Dockerfile`, `fly.toml`, `bedrock/mcp/bcpd_server.py`

---

## Deploy

```bash
# Stage the PF satellite CSV (gitignored at root → not in the image otherwise).
cp "Parkway Allocation 2025.10.xlsx - PF.csv" deploy/data/

# Deploy. Build runs on Fly's remote builders — no local Docker needed.
BUILD_SHA=$(git rev-parse --short HEAD)
fly deploy --build-arg BUILD_SHA=$BUILD_SHA
```

First deploy of a fresh app:

```bash
fly launch --no-deploy --copy-config --name bcpd-mcp --region iad
fly secrets set BCPD_MCP_TOKEN=$(openssl rand -hex 32)
fly deploy --build-arg BUILD_SHA=$(git rev-parse --short HEAD)
```

Note the secret value when you set it — there is no read-back. Store it
in a password manager.

---

## Rollback

```bash
fly releases                   # list versions
fly releases rollback <n>      # roll back to release n
```

Releases are immutable images tagged by version; rollback is instant.

---

## Logs

```bash
fly logs                       # tail live
fly logs --no-tail | tail -200 # one-shot recent
```

Dispatch logs are JSON-shaped on stderr:

```json
{"ts":"2026-05-15T00:25:45-0600","lvl":"INFO","logger":"bcpd_mcp",
 "msg":{"evt":"dispatch","tool":"generate_project_brief",
        "outcome":"ok","duration_ms":12,"result_len":4198}}
```

Useful filters:

```bash
fly logs | grep '"evt":"dispatch"'                       # only dispatches
fly logs | grep '"outcome":"error"'                      # only failures
fly logs | grep '"outcome":"refusal"'                    # tool-level refusals
fly logs | grep '"tool":"replicate_pf_satellite'         # one tool
```

Tool arguments are **never** logged (PII / confidential project names).
Only tool name, outcome, duration, and result length.

---

## Token rotation

```bash
fly secrets set BCPD_MCP_TOKEN=$(openssl rand -hex 32)
```

This restarts the machine within ~30 seconds. **Every connected client
must update its config** — old token returns 401 immediately.

Rotate when:
- a token is suspected of leaking,
- an operator with the old value rotates off,
- on a fixed schedule (90-day default).

---

## Health check

```bash
curl -i https://bcpd-mcp.fly.dev/healthz
```

Expected response:

```
HTTP/2 200
content-type: application/json
{"status":"ok","tool_count":13,"contexts_loaded":true,"build_sha":"<sha>"}
```

`build_sha` is the value of `--build-arg BUILD_SHA` from the last
deploy. `tool_count: 13` means both tool families registered.

The Fly platform check polls `/healthz` every 15s with a 3s timeout.
Failures show in `fly status` as `unhealthy`.

---

## Scale

```bash
fly status                              # see machine state
fly scale memory 1024                   # bump RAM if OOMs appear
fly scale count 1                       # always 1 — this app is stateful-warm
fly scale vm shared-cpu-2x              # rare; bump only if CPU-bound
```

Default sizing: `shared-cpu-1x`, 512 MB RAM. State is ~5 MB but pandas
and pyarrow add load — watch `fly logs` for `Out of memory: Killed
process` if traffic grows.

---

## Triage table

| Symptom | Root cause | Fix |
|---|---|---|
| `curl /healthz` returns 200 but tools fail with **HTTP 401** | Client lacks `Authorization: Bearer <token>` header, or token mismatch | Update client config with the current token (`fly secrets set` rotates it) |
| Tool response is `200` with body starting `## Refused\n\nTool xxx raised SomeError at the MCP boundary. (provenance: mcp_boundary)` | An uncaught exception inside the tool body was caught by `_safe_dispatch` in `bedrock/mcp/bcpd_server.py`. Distinguishable from a genuine tool refusal by the `(provenance: mcp_boundary)` marker. | `fly logs | grep error` for the stacktrace; fix root cause in the tool. |
| Tool response is `200` with body starting `## Refused` and **no** `(provenance: mcp_boundary)` marker | Genuine tool-level refusal (expected behavior — e.g. range-row allocation, AAJ cascade, missing required field, non-PF community through the PF replication tool) | Operator behavior — the refusal is correct. Address the upstream input. |
| `curl /healthz` returns **5xx** or hangs | Machine is restarting or down | `fly status`; `fly logs` to see the crash reason; common: missing state file → see "boot loop" below |
| Boot loop — machine restarts every ~30s, `fly logs` shows `BcpDevContextFileMissing` or `FileNotFoundError` near startup | Required state file missing from the image | Confirm the file is present in the repo, in `.dockerignore` not over-excluding, then rebuild + redeploy |
| Boot loop with `Out of memory: Killed process` | 512 MB exhausted at warmup | `fly scale memory 1024` |
| Boot loop with `SystemExit: BCPD_MCP_TOKEN env var is required` | Secret not set | `fly secrets set BCPD_MCP_TOKEN=…` |
| `curl /mcp/` returns 401 even with correct token | Token header malformed (wrong scheme, extra whitespace, wrong env var on client) | Check exact format: `Authorization: Bearer <token>` (capital B, single space) |

---

## PF satellite refresh

The Parkway Allocation 2025.10 satellite CSV is bundled into the image
at build time. When Finance ships a new snapshot:

```bash
# 1. Replace the local copy at repo root (operator does this manually).
cp ~/Downloads/"Parkway Allocation 2026.04.xlsx - PF.csv" .

# 2. Mirror it into deploy/data/ — Dockerfile reads from here.
cp "Parkway Allocation 2026.04.xlsx - PF.csv" deploy/data/

# 3. If the filename changed, update the COPY line in Dockerfile AND the
#    snapshot path in core/tools/bcp_dev_workflows.py (the
#    ReplicatePfSatellitePerLotOutputTool's snapshot constant).

# 4. Rebuild + redeploy.
fly deploy --build-arg BUILD_SHA=$(git rev-parse --short HEAD)
```

Run `replicate_pf_satellite_per_lot_output phase=E1` against the live
server after redeploy and confirm the Lennar 173-lot row still ties
to the penny (`$141,121.51`, `$30,728.10`).

---

## Smoke after every deploy

```bash
BCPD_MCP_URL=https://bcpd-mcp.fly.dev/mcp \
BCPD_MCP_TOKEN=$(cat ~/.config/bcpd_mcp.token) \
    python scripts/smoke_test_hosted_mcp.py
```

Expected final line: `[hosted-smoke] OVERALL: PASS`.

If this fails after a clean deploy, do NOT route real traffic at the
new release — `fly releases rollback <n-1>` first, then triage.

---

## What this runbook does NOT cover

- Per-user authentication (single shared bearer only).
- Live connector credentials (QuickBooks / ClickUp / DataRails).
- Rate limiting / WAF — Fly's default DDoS posture covers basic abuse;
  add app-level limiting only if behavior demands.
- Multi-region failover. v1 is a single region (`iad`); add a second
  Fly machine in another region only after sustained ops experience.
- Staging environment. v1 is one app. Add `bcpd-mcp-staging` when the
  dispatch surface stops being stable.
