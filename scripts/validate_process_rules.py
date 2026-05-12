"""CLI: validate the v0.2 BcpDevContext state substrate.

Loads all 11 versioned JSON files, runs cross-file integrity checks, and
exits 0 on success / nonzero on failure. Intended for CI and local dev.

Usage:
    python scripts/validate_process_rules.py
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from core.agent.bcp_dev_context import (  # noqa: E402
    BcpDevContext,
    BcpDevContextError,
    BcpDevContextFileMissing,
    BcpDevContextIntegrityError,
    REQUIRED_BCP_DEV_FILES,
    REQUIRED_PROCESS_RULES_FILES,
)


def main() -> int:
    ctx = BcpDevContext()
    files_total = len(REQUIRED_PROCESS_RULES_FILES) + len(REQUIRED_BCP_DEV_FILES)

    print(f"BcpDevContext validate — repo root: {ctx.repo_root}")
    print(f"Loading {files_total} required state files ...")

    try:
        ctx.load_all()
    except BcpDevContextFileMissing as e:
        print(f"FAIL — missing file: {e.file_path}", file=sys.stderr)
        return 2
    except BcpDevContextError as e:
        print(f"FAIL — load error: {e}", file=sys.stderr)
        return 2

    try:
        ctx.validate_integrity()
    except BcpDevContextIntegrityError as e:
        print(f"FAIL — integrity validation found {len(e.issues)} issue(s):", file=sys.stderr)
        for issue in e.issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1

    print("PASS — all 11 state files load and cross-reference cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
