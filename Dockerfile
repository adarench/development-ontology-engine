# BCPD MCP — hosted streamable-HTTP image.
#
# Stage 1: build a deps layer (cached unless requirements change).
# Stage 2: copy only the runtime-needed source + state into a slim image.
#
# Build:   docker build -t bcpd-mcp --build-arg BUILD_SHA=$(git rev-parse --short HEAD) .
# Run:     docker run -p 8000:8000 -e BCPD_MCP_TOKEN=xxx bcpd-mcp
# Health:  curl http://localhost:8000/healthz
#
# The PF satellite CSV (`Parkway Allocation 2025.10.xlsx - PF.csv`) is
# gitignored at the repo root but lives ALSO at `deploy/data/` so the
# build can pick it up. See `deploy/data/README.md`.

# syntax=docker/dockerfile:1.7

# ---- deps stage --------------------------------------------------------------
FROM python:3.11-slim AS deps

WORKDIR /build

# gcc only needed during install for any packages with native extensions
# (pyarrow ships wheels but kept here defensively for arm builds).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-bedrock.txt requirements-mcp.txt ./
RUN pip install --no-cache-dir \
        -r requirements.txt \
        -r requirements-bedrock.txt \
        -r requirements-mcp.txt \
        'uvicorn>=0.27,<1'

# ---- runtime stage -----------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Bring deps over from the build stage so we skip apt + gcc in the final image.
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Source — only what the MCP server actually imports at runtime.
COPY bedrock/ ./bedrock/
COPY core/    ./core/
COPY state/   ./state/

# The seven protected v2.1 artifacts that BcpdContext and the workflow tools
# read. List matches scripts/smoke_test_bcpd_mcp.py:PROTECTED_PATHS so the
# read-only contract has the same surface on disk as in dev.
COPY output/operating_state_v2_1_bcpd.json     ./output/operating_state_v2_1_bcpd.json
COPY output/agent_context_v2_1_bcpd.md         ./output/agent_context_v2_1_bcpd.md
COPY output/state_quality_report_v2_1_bcpd.md  ./output/state_quality_report_v2_1_bcpd.md
COPY data/reports/v2_0_to_v2_1_change_log.md             ./data/reports/v2_0_to_v2_1_change_log.md
COPY data/reports/coverage_improvement_opportunities.md  ./data/reports/coverage_improvement_opportunities.md
COPY data/reports/crosswalk_quality_audit_v1.md          ./data/reports/crosswalk_quality_audit_v1.md
COPY data/reports/vf_lot_code_decoder_v1_report.md       ./data/reports/vf_lot_code_decoder_v1_report.md

# PF satellite CSV (gitignored at root; staged in deploy/data/ for the build).
# JSON-array COPY form to handle the spaces in the filename. The destination
# path matches `PF_SATELLITE_PATH` in core/tools/bcp_dev_workflows.py
# (data/raw/datarails_unzipped/phase_cost_starter/...). Keep both paths in
# sync — they are the contract between the runtime image and the tool.
COPY ["deploy/data/Parkway Allocation 2025.10.xlsx - PF.csv", "./data/raw/datarails_unzipped/phase_cost_starter/Parkway Allocation 2025.10.xlsx - PF.csv"]

ARG BUILD_SHA=unknown
ENV BCPD_BUILD_SHA=${BUILD_SHA} \
    BCPD_MCP_TRANSPORT=http \
    BCPD_MCP_HOST=0.0.0.0 \
    BCPD_MCP_PORT=8000 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Non-root user for defense in depth. App lives at /app; we chown only
# the app dir so site-packages stay root-owned (immutable at runtime).
RUN useradd --no-create-home --uid 10001 bcpd && chown -R bcpd:bcpd /app
USER bcpd

CMD ["python", "-m", "bedrock.mcp.bcpd_server"]
