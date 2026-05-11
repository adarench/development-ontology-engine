"""CLI dispatcher for BCPD workflow tools.

Subcommands mirror the six tools and produce markdown deliverables under
output/runtime_demo/ by default.

Examples:
    python3 -m bedrock.workflows.cli project-brief --project "Parkway Fields"
    python3 -m bedrock.workflows.cli margin-readiness --scope bcpd
    python3 -m bedrock.workflows.cli false-precision --scope bcpd
    python3 -m bedrock.workflows.cli change-impact
    python3 -m bedrock.workflows.cli meeting-prep --scope bcpd
    python3 -m bedrock.workflows.cli owner-update --scope bcpd
    python3 -m bedrock.workflows.cli all  # run all six, write demo set

The tool implementations live in core.tools.bcpd_workflows. This module is
a thin CLI shim — it constructs the right tool, runs it, and writes output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.tools.bcpd_workflows import (
    BcpdContext,
    DraftOwnerUpdateTool,
    FindFalsePrecisionRisksTool,
    GenerateProjectBriefTool,
    PrepareFinanceLandReviewTool,
    ReviewMarginReportReadinessTool,
    SummarizeChangeImpactTool,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "runtime_demo"


# subcommand → (tool factory, default filename, default kwargs)
_DEFAULT_SCOPE = "bcpd"


def _slug(s: str) -> str:
    return (
        s.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace(".", "_")
    )


def cmd_project_brief(args, ctx: BcpdContext) -> tuple[str, str]:
    tool = GenerateProjectBriefTool(context=ctx)
    md = tool.run(project=args.project)
    name = f"project_brief_{_slug(args.project)}.md"
    return md, name


def cmd_margin_readiness(args, ctx: BcpdContext) -> tuple[str, str]:
    tool = ReviewMarginReportReadinessTool(context=ctx)
    md = tool.run(scope=args.scope)
    return md, f"margin_readiness_{_slug(args.scope)}.md"


def cmd_false_precision(args, ctx: BcpdContext) -> tuple[str, str]:
    tool = FindFalsePrecisionRisksTool(context=ctx)
    md = tool.run(scope=args.scope)
    return md, f"false_precision_{_slug(args.scope)}.md"


def cmd_change_impact(args, ctx: BcpdContext) -> tuple[str, str]:
    tool = SummarizeChangeImpactTool(context=ctx)
    md = tool.run(from_version=args.from_version, to_version=args.to_version)
    return md, f"change_impact_{_slug(args.to_version)}.md"


def cmd_meeting_prep(args, ctx: BcpdContext) -> tuple[str, str]:
    tool = PrepareFinanceLandReviewTool(context=ctx)
    md = tool.run(scope=args.scope)
    return md, "finance_land_review_prep.md"


def cmd_owner_update(args, ctx: BcpdContext) -> tuple[str, str]:
    tool = DraftOwnerUpdateTool(context=ctx)
    md = tool.run(scope=args.scope)
    return md, f"owner_update_{_slug(args.scope)}.md"


def _write(text: str, out_dir: Path, filename: str, quiet: bool) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(text)
    if not quiet:
        print(f"[wrote {path} — {len(text):,} chars]", file=sys.stderr)
    return path


def _cmd_all(args, ctx: BcpdContext, out_dir: Path) -> List[Path]:
    written: List[Path] = []
    # Six fixed-name outputs matching the user's demo file list.
    plan = [
        (
            lambda: GenerateProjectBriefTool(context=ctx).run(project="Parkway Fields"),
            "project_brief_parkway_fields.md",
        ),
        (
            lambda: ReviewMarginReportReadinessTool(context=ctx).run(scope="bcpd"),
            "margin_readiness_bcpd.md",
        ),
        (
            lambda: FindFalsePrecisionRisksTool(context=ctx).run(scope="bcpd"),
            "false_precision_bcpd.md",
        ),
        (
            lambda: SummarizeChangeImpactTool(context=ctx).run(
                from_version="v2.0", to_version="v2.1"
            ),
            "change_impact_v2_1.md",
        ),
        (
            lambda: PrepareFinanceLandReviewTool(context=ctx).run(scope="bcpd"),
            "finance_land_review_prep.md",
        ),
        (
            lambda: DraftOwnerUpdateTool(context=ctx).run(scope="bcpd"),
            "owner_update_bcpd.md",
        ),
    ]
    for fn, name in plan:
        text = fn()
        written.append(_write(text, out_dir, name, args.quiet))
    return written


_SUBCOMMAND_DISPATCH: Dict[str, Callable] = {
    "project-brief": cmd_project_brief,
    "margin-readiness": cmd_margin_readiness,
    "false-precision": cmd_false_precision,
    "change-impact": cmd_change_impact,
    "meeting-prep": cmd_meeting_prep,
    "owner-update": cmd_owner_update,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="BCPD workflow tools — generate operational deliverables from v2.1 state."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Where to write demo markdown files (default output/runtime_demo/).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of writing a file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress 'wrote' confirmation messages.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("project-brief", help="Finance-ready brief for one project")
    p.add_argument("--project", required=True, help="Canonical project name")

    p = sub.add_parser(
        "margin-readiness",
        help="'Do not include' list for lot-level margin reports",
    )
    p.add_argument("--scope", default=_DEFAULT_SCOPE)

    p = sub.add_parser(
        "false-precision",
        help="Enumerate where current reports may give false precision",
    )
    p.add_argument("--scope", default=_DEFAULT_SCOPE)

    p = sub.add_parser(
        "change-impact",
        help="Summarize v2.0 → v2.1 correction deltas with dollar magnitudes",
    )
    p.add_argument("--from-version", default="v2.0")
    p.add_argument("--to-version", default="v2.1")

    p = sub.add_parser(
        "meeting-prep",
        help="Finance / land / ops review agenda grouped by team",
    )
    p.add_argument("--scope", default=_DEFAULT_SCOPE)

    p = sub.add_parser(
        "owner-update",
        help="Concise owner / executive update (honest about scope)",
    )
    p.add_argument("--scope", default=_DEFAULT_SCOPE)

    p = sub.add_parser(
        "all",
        help="Run all six tools and write the standard demo set",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ctx = BcpdContext()

    if args.command == "all":
        _cmd_all(args, ctx, args.output_dir)
        return 0

    handler = _SUBCOMMAND_DISPATCH.get(args.command)
    if handler is None:
        parser.error(f"unknown command: {args.command!r}")
        return 2

    md, default_name = handler(args, ctx)

    if args.stdout:
        print(md)
    else:
        _write(md, args.output_dir, default_name, args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
