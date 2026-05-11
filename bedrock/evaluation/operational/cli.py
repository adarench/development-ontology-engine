"""CLI: run the operational eval suite and emit a markdown / JSON report.

Examples:
    python -m bedrock.evaluation.operational.cli
    python -m bedrock.evaluation.operational.cli --format markdown
    python -m bedrock.evaluation.operational.cli --report-md output/bedrock/operational_eval.md
    python -m bedrock.evaluation.operational.cli --category overlapping_names crosswalk
    python -m bedrock.evaluation.operational.cli --scenario sctlot_resolves_to_scattered_lots_not_scarlet_ridge
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from bedrock.evaluation.operational.report import as_json, as_markdown
from bedrock.evaluation.operational.runner import OperationalRunner
from bedrock.evaluation.operational.scenarios import SCENARIOS


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT_DIR = REPO_ROOT / "output" / "bedrock" / "evaluation"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the operational correctness eval suite."
    )
    parser.add_argument(
        "--format",
        default="markdown",
        choices=["markdown", "json"],
        help="Report format on stdout (default: markdown).",
    )
    parser.add_argument(
        "--report-md",
        type=Path,
        default=None,
        help="Optional path to write the markdown report.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Optional path to write the JSON report.",
    )
    parser.add_argument(
        "--category",
        nargs="+",
        default=None,
        help="Restrict to one or more categories.",
    )
    parser.add_argument(
        "--scenario",
        nargs="+",
        default=None,
        help="Restrict to one or more scenario names.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout (only useful with --report-md/--report-json).",
    )
    args = parser.parse_args(argv)

    selected = SCENARIOS
    if args.category:
        cats = set(args.category)
        selected = [s for s in selected if s.category in cats]
    if args.scenario:
        names = set(args.scenario)
        selected = [s for s in selected if s.name in names]
    if not selected:
        print("ERROR: no scenarios selected", file=sys.stderr)
        return 1

    runner = OperationalRunner()
    summary = runner.run(selected)

    md = as_markdown(summary)
    js = as_json(summary)

    if not args.quiet:
        print(md if args.format == "markdown" else js)

    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(md)
        print(f"[wrote {args.report_md}]", file=sys.stderr)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(js)
        print(f"[wrote {args.report_json}]", file=sys.stderr)

    # Exit code reflects pass rate but does NOT gate on it — by design.
    # The eval surfaces gaps; CI gating happens at the test layer.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
