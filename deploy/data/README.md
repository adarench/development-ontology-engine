# `deploy/data/` — Docker build payload

This directory holds files that **must be inside the Docker image** but
are **gitignored at the repo root**. The Dockerfile copies from here at
build time; nothing in this directory is committed to git.

## What goes here

| File | Why it's needed | Source |
|---|---|---|
| `Parkway Allocation 2025.10.xlsx - PF.csv` | Load-bearing for `replicate_pf_satellite_per_lot_output` (tool #13). The tool reads it via the workbook-snapshot at this exact filename. | Hand-off from finance; current snapshot lives at the repo root. |

## How to prep a build

Before the first deploy, and again whenever a fresh satellite snapshot
lands:

```bash
cp "Parkway Allocation 2025.10.xlsx - PF.csv" deploy/data/
```

Then `fly deploy` (or `docker build`). The build will fail loudly if
the file is missing — the Dockerfile has an explicit `COPY` for it.

## Why gitignored

The satellite workbook contains internal allocation data and per-lot
margin figures that should not live in source control. `.gitignore`
blocks `*.csv` and `*.xlsx` repo-wide. `.dockerignore` reverses that
ban only for files under `deploy/data/`, so Docker can see what git
cannot.

## What does NOT go here

- v2.1 protected artifacts (`output/operating_state_v2_1_bcpd.json`
  etc.) — those are checked into git and the Dockerfile copies them
  directly from their canonical paths.
- BCP Dev v0.2 state files (`state/process_rules/`, `state/bcp_dev/`)
  — likewise tracked and copied wholesale.
- Raw GL extracts, ClickUp dumps, DataRails snapshots — these are not
  read by any of the 13 hosted tools.

## Verification

After populating, confirm the file is visible to Docker but not to git:

```bash
ls -la deploy/data/                    # file should be listed
git status deploy/data/                # file should NOT appear
docker build -t bcpd-mcp .             # should COPY succeed
```
