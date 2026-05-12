#!/usr/bin/env python3
"""In-process smoke test for the BCPD MCP server.

Builds the same ToolRegistry that bedrock.mcp.bcpd_server.build_server()
builds (via the registry_for_testing helper) and calls dispatch() on three
representative tools. Asserts each output contains the expected BCPD facts.
Verifies the seven protected v2.1 files are byte-identical before/after.

No MCP transport, no subprocess, no Claude Desktop required. Use this as
the developer-side gate before configuring an MCP client.

Exit code 0 = pass; non-zero = fail.

CLI:
    python scripts/smoke_test_bcpd_mcp.py

Python requirement: 3.10+ (the mcp SDK requirement).
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
# Make the repo importable when this script runs from anywhere.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Files the runtime must NEVER mutate.
PROTECTED_PATHS: Tuple[str, ...] = (
    "output/operating_state_v2_1_bcpd.json",
    "output/agent_context_v2_1_bcpd.md",
    "output/state_quality_report_v2_1_bcpd.md",
    "data/reports/v2_0_to_v2_1_change_log.md",
    "data/reports/coverage_improvement_opportunities.md",
    "data/reports/crosswalk_quality_audit_v1.md",
    "data/reports/vf_lot_code_decoder_v1_report.md",
)


@dataclass
class WorkflowCheck:
    tool_name: str
    args: Dict[str, Any]
    must_contain: List[str]
    must_not_contain: List[str] = field(default_factory=list)


CHECKS: List[WorkflowCheck] = [
    # --- v2.1 BCPD operating-state tools ---
    WorkflowCheck(
        tool_name="generate_project_brief",
        args={"project": "Parkway Fields"},
        must_contain=[
            "Project Brief — Parkway Fields",
            "AultF",
            "B1",
            "$4,006,662",
            "inferred",
        ],
    ),
    WorkflowCheck(
        tool_name="review_margin_report_readiness",
        args={"scope": "bcpd"},
        must_contain=[
            "Lot-Level Margin Report — Readiness Review",
            "Missing cost is",
            "unknown",
            "never $0",
            "range",
        ],
        must_not_contain=["treat missing cost as $0"],
    ),
    WorkflowCheck(
        tool_name="find_false_precision_risks",
        args={"scope": "bcpd"},
        must_contain=[
            "False Precision Risks",
            "$45,752,047",
            "3-tuple",
            "SctLot",
            "HarmCo",
            "commercial",
        ],
    ),
    # --- v0.2 BCP Dev forward-looking process tools ---
    WorkflowCheck(
        tool_name="query_bcp_dev_process",
        args={"question": "Why is range-row allocation refused?"},
        must_contain=[
            "BCP Dev v0.2",
            "range_row_unratified",
            "EXC-007",
            "## Provenance",
        ],
    ),
    WorkflowCheck(
        tool_name="explain_allocation_logic",
        args={"cost_type": "Land"},
        must_contain=[
            "land_at_mda",
            "ALLOC-001",
            "mda_execution",
            "131-100",
            "phase_share_usd",
        ],
    ),
    WorkflowCheck(
        tool_name="validate_crosswalk_readiness",
        args={"scope": "all"},
        must_contain=[
            "Crosswalk readiness",
            "CW-01",
            "UNRES-01",
            "## Provenance",
        ],
    ),
    WorkflowCheck(
        tool_name="check_allocation_readiness",
        args={"community": "Parkway Fields", "phase": "E1"},
        must_contain=[
            "Allocation readiness",
            "Parkway Fields",
            "compute_ready",
            "Required inputs",
        ],
    ),
    WorkflowCheck(
        tool_name="check_allocation_readiness",
        args={"community": "Lomond Heights", "phase": "2A"},
        must_contain=[
            "Allocation readiness",
            "Lomond Heights",
            "blocked",
            "aaj_error_cascade",
            "AAJ",
        ],
    ),
    WorkflowCheck(
        tool_name="generate_per_lot_output_spec",
        args={"community": "Parkway Fields", "phase": "E1"},
        must_contain=[
            "Per-Lot Output Spec",
            "Parkway Fields",
            "compute_ready",
            "warranty_at_sale",
            "Spec only",
        ],
        must_not_contain=["$0", "$1,000"],  # No numeric values emitted
    ),
    WorkflowCheck(
        tool_name="detect_accounting_events",
        args={
            "status_changes": [
                {
                    "task_id": "CU-SMOKE-1",
                    "community": "Park Way",
                    "phase": "E1",
                    "lot_number": "001",
                    "status_from": "LND_RAW_LAND",
                    "status_to": "LND_ENTITLED",
                    "fields": {
                        "MDA Execution Date": "2026-04-01",
                        "Phase Identifier": "E1",
                        "Lot Count by Type (SFR/TH/MF/Comm)": "{SFR:198}",
                        "MDA Lot Count": 198,
                        "Allocation Workbook Lot Count": 198,
                        "Raw Land Basis (per Property)": 12500000,
                    },
                }
            ]
        },
        must_contain=[
            "Detected accounting events",
            "mda_execution",
            "EVENT-002",
            "131-200",  # debit account
            "Parkway Fields",  # community resolved via CW-01
            "detection only",
        ],
    ),
    WorkflowCheck(
        tool_name="replicate_pf_satellite_per_lot_output",
        args={"phase": "E1"},
        must_contain=[
            "NOT authoritative compute",
            "PF Satellite Replication",
            "E1 (Lennar)",
            "$141,121.51",  # E1 Lennar Sales/lot
            "$30,728.10",  # E1 Lennar Margin/lot — tie-out to penny
            "Q23",  # source-owner ratification caveat
            "warranty_rate_unratified",  # warranty refused per cell
            "Negative Indirects sign convention",
            "MDA Day three-way tie not validated",
            "## Provenance",
        ],
        # Spec only — no fabricated $0 warranty, no master-engine compute
        must_not_contain=["Warranty/lot: $0.00", "master_engine"],
    ),
]


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _snapshot_protected() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for rel in PROTECTED_PATHS:
        p = REPO_ROOT / rel
        if p.exists():
            out[rel] = _sha256(p)
    return out


def main() -> int:
    # Lazy import so a missing mcp install produces a clean error message.
    try:
        from bedrock.mcp.bcpd_server import registry_for_testing
    except ImportError as e:
        print(f"[smoke] FAIL: cannot import bedrock.mcp.bcpd_server: {e}", file=sys.stderr)
        print(
            "[smoke] HINT: pip install -r requirements-mcp.txt (mcp requires Python 3.10+)",
            file=sys.stderr,
        )
        return 2

    # Snapshot BEFORE any tool runs.
    pre = _snapshot_protected()
    if not pre:
        print("[smoke] FAIL: no protected v2.1 files found to snapshot", file=sys.stderr)
        return 2

    registry = registry_for_testing()

    overall_pass = True
    for check in CHECKS:
        print(f"[smoke] dispatch: {check.tool_name}({check.args})")
        try:
            output = registry.dispatch(check.tool_name, dict(check.args))
        except Exception as e:
            print(f"  [FAIL] dispatch raised {type(e).__name__}: {e}", file=sys.stderr)
            overall_pass = False
            continue

        missing = [m for m in check.must_contain if m not in output]
        forbidden = [f for f in check.must_not_contain if f in output]
        passed = not missing and not forbidden
        overall_pass = overall_pass and passed
        if passed:
            print(f"  [PASS] {len(output)} chars")
        else:
            print(
                f"  [FAIL] missing={missing}; forbidden_present={forbidden}",
                file=sys.stderr,
            )

    # Snapshot AFTER. Any drift = bug.
    post = _snapshot_protected()
    mutated = [rel for rel, h in pre.items() if post.get(rel) != h]
    if mutated:
        overall_pass = False
        print(
            f"[smoke] FAIL: protected v2.1 files mutated during runs: {mutated}",
            file=sys.stderr,
        )
    else:
        print(
            f"[smoke] read-only contract verified ({len(pre)} protected files byte-identical)"
        )

    print()
    print(f"[smoke] OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
