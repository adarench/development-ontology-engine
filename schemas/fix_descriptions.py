"""Audit-driven fixer for datasource_schema.json descriptions.

Detects six systematic failure modes (see plan in the audit report), applies
deterministic rewrites where possible, and otherwise injects the structural
context the original generator was missing into `raw_description` and clears
`description` so the existing enrich pipeline regenerates with that context.

Usage:
    # Inspect what would change (no writes, no API calls)
    python3 -m schemas.fix_descriptions

    # Apply mechanical fixes + write structural hints for LLM regen
    python3 -m schemas.fix_descriptions --apply

    # Same plus call Claude to refill cleared descriptions
    python3 -m schemas.fix_descriptions --apply --regenerate
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import pandas as pd

from schemas.registry import DEFAULT_REGISTRY_PATH, DatasourceField, SchemaRegistry
from schemas.build_embedding_text import build_embedding_text
from schemas.enrich_descriptions import (
    DEFAULT_MODEL,
    _has_code_reference,
    describe_table,
    get_anthropic_client,
)

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

DATA_BEARING = re.compile(
    r"\b(variance|actual|goal|amount|count|date|value|cost|price|metric|"
    r"figure|balance|total|sum|quantity|advance|loan)\b",
    re.I,
)
ACK_EMPTY = re.compile(
    r"\b(empty|null|spacer|separator|unpopulated|placeholder|blank|"
    r"not populated|no values|no data|fully empty)\b",
    re.I,
)
# Phrases that claim a SPECIFIC active data role for the column — if the
# column is actually empty, this is a fabrication regardless of any "null"
# hedge elsewhere in the description.
EMPTY_BUT_ACTIVE_ROLE = re.compile(
    r"\b(variance|delta|"
    r"actual\s+(numeric|closings|sales|starts|count|result|metric)|"
    r"realized\s+(count|amount|closings|sales|starts|metric)|"
    r"reserved\s+for\s+(variance|computation|calculation))\b",
    re.I,
)
SUFFIX = re.compile(r"\.(\d+)\s*$")

# Phrases that, if found in a description AND contradicted by sample_values,
# are evidence the LLM hallucinated.
CONTRADICTION_PHRASES = [
    "all samples show $0",
    "always $0",
    "always null",
    "empty numeric column",
    "no active data rows",
    "null in sampled rows",
    "no populated values",
    "no semantic content",
]

# Patterns where the description claims a column is locked to a single value
# (e.g. "hardcoded 'xx'", "always 'X'", "exclusively contains 'foo'"). If
# sample_values contains a different non-empty value, the claim is wrong.
SINGLETON_CLAIM = re.compile(
    r"\b(hardcoded|always|exclusively|invariably|only ever|single value)\s+"
    r"(?:contains?\s+|is\s+|equals?\s+|set to\s+)?"
    r"['\"]([^'\"]{1,40})['\"]",
    re.I,
)


def _samples_are_empty(samples: list) -> bool:
    if not samples:
        return True
    return all(
        (s is None) or (isinstance(s, str) and not s.strip())
        for s in samples
    )


def _samples_have_text(samples: list) -> bool:
    """True if any sample contains an alphabetic character."""
    return any(isinstance(s, str) and any(c.isalpha() for c in s)
               for s in samples)


def _samples_have_nonzero(samples: list) -> bool:
    """True if any sample is non-empty AND not zero/dash/blank."""
    for s in samples:
        if s is None:
            continue
        if isinstance(s, str):
            t = s.strip().strip("$").replace(",", "").strip()
            if t and t not in ("0", "0.0", "-", "—"):
                return True
        elif isinstance(s, (int, float)):
            if s != 0:
                return True
    return False


def detect_issues(registry: SchemaRegistry) -> list[tuple[str, list[str]]]:
    """Returns [(field_id, [issue_kinds...])] for every entry with at least one issue."""
    out: list[tuple[str, list[str]]] = []
    for f in registry:
        kinds: list[str] = []
        desc = (f.description or "").strip()
        samples = f.sample_values or []

        # Skip blanks — enrich_descriptions handles those.
        if not desc:
            continue

        # A. Empty column described as data-bearing
        if _samples_are_empty(samples) \
                and DATA_BEARING.search(desc) \
                and not ACK_EMPTY.search(desc):
            kinds.append("empty_described_as_data")

        # A2. Empty column with an explicit active-role claim
        # (catches "variance for X. Null across all rows" — the null hedge
        # doesn't excuse the fabricated role).
        if _samples_are_empty(samples) and EMPTY_BUT_ACTIVE_ROLE.search(desc):
            if "empty_described_as_data" not in kinds:
                kinds.append("empty_with_active_role_claim")

        # B. Self-contradicting (description claim refuted by samples)
        desc_l = desc.lower()
        if any(p in desc_l for p in CONTRADICTION_PHRASES):
            if _samples_have_nonzero(samples):
                kinds.append("self_contradiction")

        # B2. Singleton claim refuted by sample diversity (e.g. "hardcoded 'xx'"
        # when samples include 'A7', 'A8' etc.)
        m = SINGLETON_CLAIM.search(desc)
        if m and samples:
            claimed = m.group(2).strip()
            distinct_non_claimed = [
                s for s in samples
                if isinstance(s, str) and s.strip() and s.strip() != claimed
                or (not isinstance(s, str) and s not in (None, '') and str(s).strip() != claimed)
            ]
            if distinct_non_claimed:
                kinds.append("singleton_claim_refuted")

        # C. Type-vs-samples mismatch (numeric type but alpha samples)
        if f.data_type in ("int", "float") and _samples_have_text(samples):
            kinds.append("type_vs_samples_mismatch")

        # D. Repeating-bucket suffix in Collateral Report / PriorCR
        table = f.table_name or ""
        if ("Collateral Report" in table or "PriorCR" in table) \
                and SUFFIX.search(f.field_name):
            kinds.append("repeating_bucket_suffix")

        # E. Forecast triplet mislabeled — "prior-year" applied to a
        # current-year column (Goal/Actual/aggregate). Use the column's
        # position in the LY/Goal/Actual/spacer block to decide: only the
        # LY column (offset%4 == 0) should ever be called prior-year.
        if "Forecast" in table and "prior-year" in desc_l:
            col_idx = _col_idx_from_unnamed(f.field_name)
            if col_idx is not None and col_idx >= 2:
                _, role_idx = divmod(col_idx - 2, 4)
                if role_idx != 0:
                    kinds.append("forecast_triplet_misattribution")
            elif col_idx is None:
                # Named-header columns (e.g. "February 2023", "Q3") are the
                # LY anchors at the start of each block — "prior-year" is
                # correct for them. Leave alone.
                pass

        # F. Specific ClickUp sparsity mis-attribution
        if f.field_name == "date_done" and "22.77" in desc:
            kinds.append("misattributed_sparsity_stat")

        if kinds:
            out.append((f.id, kinds))
    return out


# ---------------------------------------------------------------------------
# Mechanical rewrites
# ---------------------------------------------------------------------------

EMPTY_TEMPLATE = (
    "{field_name}: Structural / unpopulated column from {source_label}; "
    "no values present in the source ({data_type}, nullable). "
    "Likely a layout artifact (block separator or reserved slot) rather than "
    "an active data field."
)


def _source_label(f: DatasourceField) -> str:
    table = f.table_name or "the source workbook"
    return table


EMPTY_KINDS = {"empty_described_as_data", "empty_with_active_role_claim"}


def apply_mechanical_fixes(
    registry: SchemaRegistry,
    issues: list[tuple[str, list[str]]],
) -> list[str]:
    """For entries whose issues are purely 'this column is empty but described
    as if it carried data', overwrite the description deterministically.
    Returns the list of changed ids."""
    changed: list[str] = []
    for fid, kinds in issues:
        if not kinds or any(k not in EMPTY_KINDS for k in kinds):
            continue
        f = registry.get(fid)
        new_desc = EMPTY_TEMPLATE.format(
            field_name=f.field_name,
            source_label=_source_label(f),
            data_type=f.data_type or "type unknown",
        )
        f.description = new_desc
        changed.append(fid)
    return changed


# ---------------------------------------------------------------------------
# Structural-context hints (injected into raw_description for LLM regen)
# ---------------------------------------------------------------------------

# Collateral Report / PriorCR repeating-bucket layout.
# Built by re-reading the source CSV with header=8 and grouping suffixed
# columns under each "# of Lots[.N]" anchor.
COLLATERAL_BUCKETS = [
    # (anchor_column_pattern,  bucket_label)
    ("# of Lots",      "Lot Pool (paper + finished lots collateral). "
                       "Advance rate per Lot Type (typ. 50–60%)."),
    ("# of Lots.1",    "Production Unit WIP (homes under construction). "
                       "Advance rate 70%."),
    ("# of Lots.2",    "Model Homes (display / sales-office inventory). "
                       "Advance rate 75%."),
    ("# of Lots.3",    "Finished Homes (vertical complete, unsold). "
                       "Advance rate 80%."),
    ("# of Lots.4",    "Sold-but-Not-Closed Homes (under contract, awaiting close). "
                       "Advance rate 90%."),
    ("# of Lots.5",    "Residual / unallocated trailing bucket. "
                       "Advance rate 0% — not pledged."),
]


def _bucket_for_collateral_column(field_name: str) -> str | None:
    """Map a Collateral Report / PriorCR column to its bucket label.

    Strategy: each bucket starts at a `# of Lots[.N]` anchor and includes the
    suffixed columns up to the next anchor. We don't read the source file here
    — we use the known anchor positions.
    """
    name = field_name.strip()
    m = SUFFIX.search(name)
    suffix = m.group(1) if m else None

    if not suffix:
        # No-suffix columns belong to the first (lot pool) bucket
        return COLLATERAL_BUCKETS[0][1]

    n = int(suffix)
    if 0 <= n - 1 < len(COLLATERAL_BUCKETS) - 1:
        return COLLATERAL_BUCKETS[n][1]

    # Per Home Value.1/.2 etc. don't follow strict per-bucket indexing; map by
    # nearest # of Lots.N section heuristically — bucket .4 (sold-not-closed)
    # is the most common owner of these residual numeric columns.
    return COLLATERAL_BUCKETS[min(n, len(COLLATERAL_BUCKETS) - 1)][1]


# Forecast sheet: every period block is (LY, Goal, Actual, spacer).
# Layout (0-indexed columns, 0/1 = section / blank):
#   2,3,4   = Oct 2015 LY/Goal/Actual; 5 = spacer
#   6,7,8   = Nov 2015 LY/Goal/Actual; 9 = spacer
#   ...
# The "year" of each block is sheet-specific (2018 Forecast → 2015 Q4 then
# 2018 months; same for 2019/2020/2021/2023). We compute the (period, role)
# from the column index and known block ordering.

# 0-indexed positions of column-block ANCHORS within each Forecast sheet.
# Each entry: (start_col, period_label, is_quarter)
# Pattern: after the initial 2015-Q4 historic block, the rest is the sheet's
# focal year (Jan, Feb, Mar, Q1, Apr, May, Jun, Q2, Jul, Aug, Sep, Q3, Oct, Nov, Dec, Q4).
FORECAST_BLOCKS_TEMPLATE = [
    "{historic_year} Q4 historic, October",
    "{historic_year} Q4 historic, November",
    "{historic_year} Q4 historic, December",
    "{historic_year} Q4 historic, aggregate",
    "{year} January",
    "{year} February",
    "{year} March",
    "{year} Q1 aggregate",
    "{year} April",
    "{year} May",
    "{year} June",
    "{year} Q2 aggregate",
    "{year} July",
    "{year} August",
    "{year} September",
    "{year} Q3 aggregate",
    "{year} October",
    "{year} November",
    "{year} December",
    "{year} Q4 aggregate",
]

FORECAST_YEARS = {
    "Inventory _ Closing Report/2017 Forecast": (2015, 2017),
    "Inventory _ Closing Report/2018 Forecast": (2015, 2018),
    "Inventory _ Closing Report/2019 Forecast": (2015, 2019),
    "Inventory _ Closing Report/2020 Forecast": (2015, 2020),
    "Inventory _ Closing Report/2021 Forecast": (2015, 2021),
    "Inventory _ Closing Report/2023 Forecast": (2015, 2023),
}


def _forecast_label(table_name: str, col_idx: int) -> str | None:
    """Return a structural hint for an Unnamed: N column in a Forecast sheet."""
    years = FORECAST_YEARS.get(table_name)
    if not years:
        return None
    historic_year, year = years

    # First 2 columns are the row-label / section gutter
    if col_idx < 2:
        return None

    offset = col_idx - 2  # 0-indexed within the period blocks
    block_idx, role_idx = divmod(offset, 4)

    if block_idx >= len(FORECAST_BLOCKS_TEMPLATE):
        return None

    period = FORECAST_BLOCKS_TEMPLATE[block_idx].format(
        historic_year=historic_year, year=year,
    )
    role = ["LY (prior-year reference)", "Goal (target)",
            "Actual (realized)", "spacer (no data)"][role_idx]

    return f"Period: {period}. Role in LY/Goal/Actual triplet: {role}."


def _col_idx_from_unnamed(field_name: str) -> int | None:
    m = re.match(r"Unnamed:\s*(\d+)\s*$", field_name)
    return int(m.group(1)) if m else None


def build_structural_hint(f: DatasourceField) -> str | None:
    """Return a one-paragraph hint that names the column's role within its
    table's layout. Returned text goes into `raw_description` so the LLM sees
    it during regeneration."""
    table = f.table_name or ""

    # Repeating-bucket columns in Collateral Report / PriorCR
    if "Collateral Report" in table or "PriorCR" in table:
        bucket = _bucket_for_collateral_column(f.field_name)
        if bucket:
            return (
                f"STRUCTURAL CONTEXT: This column belongs to the collateral-package "
                f"bucket below. The Collateral Report / PriorCR layout repeats "
                f"`# of Lots`, `Per Home Value`, `Advance %`, `Loan $` per bucket; "
                f"pandas suffixes duplicates `.1`/`.2`/.../`.5`. Use the bucket "
                f"label to ground the description. — Bucket: {bucket}"
            )

    # Forecast LY/Goal/Actual triplet
    if "Forecast" in table:
        col_idx = _col_idx_from_unnamed(f.field_name)
        if col_idx is not None:
            label = _forecast_label(table, col_idx)
            if label:
                return (
                    f"STRUCTURAL CONTEXT: Inventory _ Closing Report forecast sheets "
                    f"use 4-column period blocks (LY, Goal, Actual, spacer). "
                    f"Note: the LY column carries prior-year actuals for comparison; "
                    f"the Actual column carries the CURRENT-year actual for this "
                    f"period — never call the Actual column a 'prior-year actual'. "
                    f"For this column — {label}"
                )

    # date_done sparsity correction
    if f.field_name == "date_done":
        return (
            "STRUCTURAL CONTEXT: `date_done` is the ClickUp task completion "
            "timestamp. Do NOT cite the 22.77% sparsity figure here — that "
            "figure belongs to `actual_c_of_o` per the source map. Sparsity "
            "for `date_done` itself is undocumented; describe only what the "
            "sample values support."
        )

    return None


def prepare_for_regen(
    registry: SchemaRegistry,
    issues: list[tuple[str, list[str]]],
    already_fixed: set[str],
) -> list[str]:
    """For entries that need LLM regeneration, write a structural hint into
    `raw_description` and clear `description`. Returns the list of cleared ids.
    """
    cleared: list[str] = []
    for fid, kinds in issues:
        if fid in already_fixed:
            continue
        f = registry.get(fid)
        hint = build_structural_hint(f)
        if hint is None:
            # No targeted hint — still clear so enrich rewrites with current
            # business context. The model may still produce a vague answer,
            # but at least it won't carry the old contradiction forward.
            f.raw_description = None
        else:
            f.raw_description = hint
        f.description = None
        cleared.append(fid)
    return cleared


# ---------------------------------------------------------------------------
# LLM regeneration (calls enrich's describe_table with the prepared fields)
# ---------------------------------------------------------------------------

def regenerate_cleared(
    registry: SchemaRegistry,
    cleared_ids: list[str],
    *,
    model: str = DEFAULT_MODEL,
    chunk_size: int = 30,
) -> tuple[int, int]:
    """Call Claude on every field whose description was cleared.

    Returns (updated, failed). Reuses enrich_descriptions.describe_table,
    which already grounds on the business-context system prompt.
    """
    if not cleared_ids:
        return 0, 0

    client = get_anthropic_client()
    by_table: dict[tuple[str, str | None], list[DatasourceField]] = defaultdict(list)
    for fid in cleared_ids:
        f = registry.get(fid)
        by_table[(f.data_source, f.table_name)].append(f)

    updated = 0
    failed = 0
    for table_key, fields in by_table.items():
        for i in range(0, len(fields), chunk_size):
            chunk = fields[i:i + chunk_size]
            label = f"{table_key[1] or '<no table>'} ({len(chunk)} fields)"
            print(f"  [llm] {label}", file=sys.stderr)
            try:
                results = describe_table(client, model, table_key, chunk)
            except Exception as exc:
                print(f"    FAILED: {exc}", file=sys.stderr)
                failed += len(chunk)
                continue

            for f in chunk:
                desc = results.get(f.id)
                if not desc or _has_code_reference(desc):
                    failed += 1
                    continue
                f.description = desc
                updated += 1
    return updated, failed


# ---------------------------------------------------------------------------
# embedding_text refresh
# ---------------------------------------------------------------------------

def rebuild_embedding_text(registry: SchemaRegistry, changed_ids: Iterable[str]) -> int:
    n = 0
    for fid in changed_ids:
        f = registry.get(fid)
        f.embedding_text = build_embedding_text(f)
        n += 1
    return n


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _summarize(issues: list[tuple[str, list[str]]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for _, kinds in issues:
        for k in kinds:
            counts[k] += 1
    lines = [f"Detected {len(issues)} flagged entries:"]
    for k in sorted(counts, key=lambda x: -counts[x]):
        lines.append(f"  {k:<40} {counts[k]:>4}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", type=Path, default=DEFAULT_REGISTRY_PATH,
                        help="Registry JSON path")
    parser.add_argument("--apply", action="store_true",
                        help="Persist changes to the registry "
                             "(mechanical fixes + structural hints).")
    parser.add_argument("--regenerate", action="store_true",
                        help="After clearing flagged entries, call Claude to "
                             "refill descriptions. Requires --apply.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--chunk-size", type=int, default=30)
    parser.add_argument("--show", type=int, default=15,
                        help="In dry-run, show up to N example flagged entries.")
    args = parser.parse_args(argv)

    if args.regenerate and not args.apply:
        parser.error("--regenerate requires --apply")

    registry = SchemaRegistry(args.path)
    issues = detect_issues(registry)
    print(_summarize(issues), file=sys.stderr)

    if not issues:
        return 0

    if not args.apply:
        # Dry-run preview
        print("\nDry run. Example flagged entries (use --apply to act):",
              file=sys.stderr)
        for fid, kinds in issues[:args.show]:
            f = registry.get(fid)
            desc = (f.description or "").replace("\n", " ")[:120]
            print(f"\n  [{fid}] {f.field_name} @ {f.table_name}", file=sys.stderr)
            print(f"    kinds: {', '.join(kinds)}", file=sys.stderr)
            print(f"    samples: {f.sample_values[:4]}", file=sys.stderr)
            print(f"    desc:    {desc}", file=sys.stderr)
            hint = build_structural_hint(f)
            if hint:
                print(f"    hint:    {hint[:200]}", file=sys.stderr)
        return 0

    # Apply mode
    mech_changed = apply_mechanical_fixes(registry, issues)
    print(f"\nMechanical fixes applied: {len(mech_changed)}", file=sys.stderr)

    cleared = prepare_for_regen(registry, issues, set(mech_changed))
    print(f"Structural hints written + descriptions cleared: {len(cleared)}",
          file=sys.stderr)

    changed_ids = set(mech_changed) | set(cleared)
    rebuild_embedding_text(registry, changed_ids)

    if args.regenerate and cleared:
        print(f"\nRegenerating {len(cleared)} cleared descriptions via Claude…",
              file=sys.stderr)
        updated, failed = regenerate_cleared(
            registry, cleared, model=args.model, chunk_size=args.chunk_size,
        )
        print(f"LLM regeneration: updated={updated} failed={failed}",
              file=sys.stderr)
        rebuild_embedding_text(registry, cleared)

    registry.save()
    print(f"\nSaved registry: {args.path}", file=sys.stderr)

    # Re-detect and report remaining issues
    remaining = detect_issues(registry)
    print(f"\nPost-fix re-audit: {len(remaining)} entries still flagged "
          f"(was {len(issues)})", file=sys.stderr)
    if remaining:
        print(_summarize(remaining), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
