"""Lightweight validation for output/agent_chunks_v2_bcpd/.

Verifies:
- index.json exists and is parseable.
- Every indexed chunk file exists on disk.
- Every chunk has the required frontmatter fields.
- Required guardrail chunks are present (org-wide-unavailable, missing-cost-not-zero).
- No chunk claims source-owner-validated for inferred decoder rules.
- v2.1 protected files were NOT modified by chunk generation/regeneration.

Run from repo root:
    python3 tests/test_agent_chunks_v2_bcpd.py
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import re
import sys

REPO = Path(__file__).resolve().parent.parent
CHUNK_DIR = REPO / "output/agent_chunks_v2_bcpd"
INDEX_JSON = CHUNK_DIR / "index.json"

REQUIRED_FRONTMATTER = (
    "chunk_id", "chunk_type", "title", "project", "source_files",
    "state_version", "confidence", "last_generated", "allowed_uses", "caveats",
)

# Protected v2.1 files — must not change during chunk generation.
PROTECTED = (
    REPO / "output/operating_state_v2_1_bcpd.json",
    REPO / "output/agent_context_v2_1_bcpd.md",
    REPO / "output/state_quality_report_v2_1_bcpd.md",
    REPO / "output/state_query_examples_v2_1_bcpd.md",
    REPO / "data/reports/v2_0_to_v2_1_change_log.md",
    REPO / "data/reports/vf_lot_code_decoder_v1_report.md",
    REPO / "data/reports/crosswalk_quality_audit_v1.md",
    REPO / "data/reports/coverage_improvement_opportunities.md",
    REPO / "data/reports/join_coverage_simulation_v1.md",
    REPO / "data/staged/vf_lot_code_decoder_v1.csv",
    REPO / "docs/ontology_v0.md",
    REPO / "docs/source_to_field_map.md",
    REPO / "docs/crosswalk_plan.md",
)

# Required guardrail chunks (by chunk_id)
REQUIRED_GUARDRAILS = (
    "guardrail_orgwide_unavailable",
    "guardrail_bcpd_only",
    "guardrail_inferred_decoder_rules",
    "guardrail_harmony_3tuple_join",
    "guardrail_sctlot_scattered_lots",
    "guardrail_range_rows_not_lot_level",
    "guardrail_commercial_not_residential",
    "guardrail_read_only_qa",
)
# missing-cost-is-not-zero lives under cost_sources by design
REQUIRED_COST_SOURCES = (
    "cost_source_missing_cost_is_not_zero",
    "cost_source_vertical_financials",
    "cost_source_datarails_38col_dedup",
    "cost_source_qb_register_tieout_only",
    "cost_source_range_shell_rows",
    "cost_source_commercial_parcels",
)


def _hash(p: Path) -> tuple[int, str]:
    if not p.exists():
        return (-1, "")
    data = p.read_bytes()
    return (len(data), hashlib.sha256(data).hexdigest())


def _parse_frontmatter(content: str) -> dict:
    if not content.startswith("---\n"):
        raise AssertionError("chunk does not start with frontmatter")
    end = content.find("\n---\n", 4)
    if end < 0:
        raise AssertionError("frontmatter not terminated")
    fm_text = content[4:end]
    fm: dict = {}
    cur_list_key = None
    for line in fm_text.splitlines():
        if line.startswith("  - ") and cur_list_key:
            fm[cur_list_key].append(line[4:].strip())
        elif ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v == "":
                fm[k] = []
                cur_list_key = k
            else:
                fm[k] = v
                cur_list_key = None
    return fm


def main() -> int:
    failures: list[str] = []

    # 1. Snapshot protected files
    print("[chunks-test] snapshotting protected v2.1 files...")
    snap_before = {p: _hash(p) for p in PROTECTED}
    for p, (sz, _) in snap_before.items():
        if sz < 0:
            failures.append(f"protected file missing: {p}")
    if failures:
        for f in failures: print(f"  FAIL: {f}")
        return 1

    # 2. index.json exists + parses
    if not INDEX_JSON.exists():
        print(f"FAIL: {INDEX_JSON} does not exist")
        return 1
    index = json.loads(INDEX_JSON.read_text())
    print(f"[chunks-test] index has {index['chunk_count']} chunks; types: {index['counts_by_type']}")

    # 3. Every indexed chunk file exists
    print("[chunks-test] verifying every indexed chunk file exists...")
    indexed_ids: set[str] = set()
    for entry in index["chunks"]:
        cid = entry["chunk_id"]
        path = CHUNK_DIR / entry["path"]
        if not path.exists():
            failures.append(f"chunk file missing: {path} (chunk_id={cid})")
            continue
        indexed_ids.add(cid)

    # 4. Every chunk has required frontmatter
    print("[chunks-test] verifying required frontmatter on every chunk...")
    for entry in index["chunks"]:
        cid = entry["chunk_id"]
        path = CHUNK_DIR / entry["path"]
        if not path.exists(): continue
        content = path.read_text()
        try:
            fm = _parse_frontmatter(content)
        except AssertionError as e:
            failures.append(f"{cid}: frontmatter parse: {e}")
            continue
        for req in REQUIRED_FRONTMATTER:
            if req not in fm:
                failures.append(f"{cid}: missing required frontmatter field: {req}")
        # state_version must be v2.1
        if fm.get("state_version") != "v2.1":
            failures.append(f"{cid}: state_version != v2.1 (got: {fm.get('state_version')})")
        # confidence must be one of the allowed values
        allowed_conf = {"high", "medium", "low", "inferred", "inferred-unknown", "refused"}
        if fm.get("confidence") not in allowed_conf:
            failures.append(f"{cid}: confidence value not in allowed set: {fm.get('confidence')}")

    # 5. Required guardrail chunks
    print("[chunks-test] verifying required guardrail chunks...")
    for required_id in REQUIRED_GUARDRAILS:
        if required_id not in indexed_ids:
            failures.append(f"required guardrail chunk missing: {required_id}")

    # 6. Required cost-source chunks (incl. missing-cost-is-not-zero)
    print("[chunks-test] verifying required cost-source chunks...")
    for required_id in REQUIRED_COST_SOURCES:
        if required_id not in indexed_ids:
            failures.append(f"required cost-source chunk missing: {required_id}")

    # 7. No chunk claims source-owner-validated for inferred decoder rules
    print("[chunks-test] verifying no chunk over-claims validation...")
    for entry in index["chunks"]:
        cid = entry["chunk_id"]
        path = CHUNK_DIR / entry["path"]
        if not path.exists(): continue
        text = path.read_text()
        # Must NOT contain the literal claim
        bad_phrases = (
            "validated_by_source_owner: True",
            "validated_by_source_owner=True",
            "validated by source owner: yes",
        )
        for bad in bad_phrases:
            if bad.lower() in text.lower():
                failures.append(f"{cid}: claims source-owner validation: '{bad}'")

    # 8. Re-run the chunk builder to confirm idempotency and verify protected files unchanged
    print("[chunks-test] re-running chunk builder to verify protected files unchanged...")
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from financials import build_agent_chunks_v2_bcpd as builder
    rc = builder.main()
    if rc != 0:
        failures.append(f"chunk builder returned {rc}")

    snap_after = {p: _hash(p) for p in PROTECTED}
    for p in PROTECTED:
        if snap_before[p] != snap_after[p]:
            failures.append(f"protected file changed: {p}")

    # 9. Verify the safe-questions/refused-questions sections are present in every chunk
    print("[chunks-test] verifying body sections...")
    required_sections = ("Plain-English summary", "Key facts", "Evidence", "Confidence",
                         "Caveats", "Safe questions", "Questions to refuse")
    for entry in index["chunks"]:
        cid = entry["chunk_id"]
        path = CHUNK_DIR / entry["path"]
        if not path.exists(): continue
        body = path.read_text()
        for s in required_sections:
            if s.lower() not in body.lower():
                failures.append(f"{cid}: missing body section '{s}'")

    # Report
    if failures:
        print(f"\n[chunks-test] FAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"\n[chunks-test] PASS — {index['chunk_count']} chunks valid; protected files unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
