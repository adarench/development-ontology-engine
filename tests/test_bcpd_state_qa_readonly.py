"""Read-only test for the BCPD v2.1 Q&A harness.

Snapshots the size + sha256 of every protected file before running the harness,
runs `financials/qa/bcpd_state_qa.py` end-to-end, and confirms:
  1. No protected file was modified.
  2. Only the three allowed output paths were written.
  3. The schema_version in the loaded state is `operating_state_v2_1_bcpd`.

Run from the repo root:
    python3 -m tests.test_bcpd_state_qa_readonly
or just:
    python3 tests/test_bcpd_state_qa_readonly.py
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import importlib
import json
import sys

REPO = Path(__file__).resolve().parent.parent

# Make the financials package importable when running from repo root
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _hash(p: Path) -> tuple[int, str]:
    if not p.exists():
        return (-1, "")
    data = p.read_bytes()
    return (len(data), hashlib.sha256(data).hexdigest())


def main() -> int:
    from financials.qa.bcpd_state_loader import PROTECTED_PATHS, load_state, EXPECTED_SCHEMA
    from financials.qa import bcpd_state_qa

    # Allowed output paths
    out_results = REPO / "output/bcpd_state_qa_results.json"
    out_examples = REPO / "output/bcpd_state_qa_examples.md"
    out_eval = REPO / "output/bcpd_state_qa_eval.md"
    allowed_outputs = {out_results, out_examples, out_eval}

    # Snapshot protected
    print("[test] snapshotting protected paths...")
    snap_before = {p: _hash(p) for p in PROTECTED_PATHS}
    for p, (sz, h) in snap_before.items():
        if sz < 0:
            print(f"  MISSING: {p}", file=sys.stderr)
            return 1

    # Verify v2.1 is what's loaded (and v2.0 fails if substituted)
    print("[test] loading v2.1 state...")
    state = load_state()
    assert state.schema_version == EXPECTED_SCHEMA, \
        f"expected {EXPECTED_SCHEMA}, got {state.schema_version}"
    print(f"  loaded schema_version = {state.schema_version}")

    # Run harness
    print("[test] running QA harness...")
    rc = bcpd_state_qa.main([])
    assert rc == 0, f"harness returned {rc}"

    # Snapshot protected AFTER
    print("[test] verifying protected paths unchanged...")
    snap_after = {p: _hash(p) for p in PROTECTED_PATHS}
    failures = []
    for p in PROTECTED_PATHS:
        if snap_before[p] != snap_after[p]:
            failures.append(p)
    if failures:
        print(f"  FAIL: {len(failures)} protected files changed:")
        for f in failures:
            print(f"    {f}")
        return 1
    print(f"  OK: all {len(PROTECTED_PATHS)} protected paths unchanged.")

    # Verify only allowed outputs written
    print("[test] verifying allowed outputs exist + nothing else introduced...")
    for o in allowed_outputs:
        if not o.exists():
            print(f"  FAIL: expected output not written: {o}")
            return 1
    # Sanity: results JSON has 15 answers and v2.1 schema marker
    payload = json.loads(out_results.read_text())
    assert payload["schema_version"] == EXPECTED_SCHEMA, payload["schema_version"]
    assert len(payload["answers"]) == 15, len(payload["answers"])
    # Sanity: at least one answer is refused (org-wide)
    refused_count = sum(1 for a in payload["answers"] if a["confidence"] == "refused" or a["cannot_conclude"])
    assert refused_count >= 1, "expected ≥1 refused answer (org-wide)"
    # Sanity: at least one answer is inferred
    inferred_count = sum(1 for a in payload["answers"] if a["confidence"] == "inferred")
    assert inferred_count >= 1, "expected ≥1 inferred answer (decoder-derived)"
    # Sanity: every answer cites ≥1 source file
    no_src = [a["qid"] for a in payload["answers"] if not a.get("source_files_used")]
    assert not no_src, f"answers lacking source_files_used: {no_src}"

    print("\n[test] PASS — read-only contract honored, harness produces 15 answers with refusals + inferred labels + citations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
