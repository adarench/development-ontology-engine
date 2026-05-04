"""
Stage Dictionary + Data Quality Layer.

Reads a secondary ClickUp naming-structure dump (just task names) and produces
a canonical stage vocabulary + a list of invalid rows. Output is meant to
improve the main clickup_real.py pipeline, NOT build new state.

Input:  Clickup_Naming_Struct - Sheet1.csv  (column: name)
Output: output/stage_dictionary.csv
        output/invalid_rows.csv
        output/stage_summary.md
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pandas as pd

REPO_ROOT  = Path(__file__).resolve().parent.parent
INPUT_FILE = REPO_ROOT / "Clickup_Naming_Struct - Sheet1.csv"
OUT_DIR    = REPO_ROOT / "output"
OUT_DIR.mkdir(exist_ok=True)

# Canonical stage list and aliases. This is the single source of truth that
# clickup_real.py should pull from once we wire it through.
CANONICAL_ALIASES: dict[str, str] = {
    # Dig / Dug
    "dig": "Dug", "dug": "Dug", "excavation": "Dug", "excavate": "Dug",
    # Footings
    "footing": "Footings", "footings": "Footings",
    # Walls
    "wall": "Walls", "walls": "Walls", "foundation": "Walls",
    # Backfill
    "backfill": "Backfill",
    # Spec
    "spec": "Spec",
    # Rough
    "rough": "Rough", "rough in": "Rough", "rough-in": "Rough", "framing": "Rough",
    # Finish
    "finish": "Finish", "walk": "Finish", "walkthrough": "Finish",
    "walk-through": "Finish", "walk stage": "Finish",
    # Complete
    "complete": "Complete", "completed": "Complete",
    "c_of_o": "Complete", "c of o": "Complete", "cofo": "Complete",
    "co": "Complete", "close": "Complete", "closed": "Complete",
    # Sold
    "sold": "Sold",
}

CANONICAL_ORDER = ["Dug", "Footings", "Walls", "Backfill",
                   "Spec", "Rough", "Finish", "Complete", "Sold"]

# Trailing stage portion may be at most this many tokens.
MAX_STAGE_TOKENS = 3


def parse_row(name: str) -> dict:
    """Returns dict with valid flag + parsed components or rejection reason."""
    out = {
        "name": name, "valid": False, "reason": None,
        "project_code": None, "lot_number": None,
        "stage_raw": None, "stage_canonical": None,
    }
    if not isinstance(name, str) or not name.strip():
        out["reason"] = "empty"
        return out

    s = name.strip()
    tokens = re.split(r"\s+", s)
    digit_idx = [i for i, t in enumerate(tokens) if t.isdigit()]
    if not digit_idx:
        out["reason"] = "no numeric token"
        return out

    last = digit_idx[-1]
    project_code = " ".join(tokens[:last]).strip() or None
    lot_number   = tokens[last]
    trailing     = tokens[last + 1:]

    if not trailing:
        out["reason"] = "no stage token after lot number"
        return out

    if len(trailing) > MAX_STAGE_TOKENS:
        out["reason"] = f"trailing portion too long ({len(trailing)} tokens — likely a sentence, not a stage)"
        return out

    stage_raw = " ".join(trailing)
    canonical = CANONICAL_ALIASES.get(stage_raw.lower())

    out.update({
        "valid": True,
        "project_code": project_code,
        "lot_number":   lot_number,
        "stage_raw":    stage_raw,
        "stage_canonical": canonical,  # may be None → flagged later as 'unknown stage'
    })
    if canonical is None:
        out["reason"] = "unknown stage (parsed but not in CANONICAL_ALIASES)"
    return out


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    df = pd.read_csv(INPUT_FILE)
    if "name" not in df.columns:
        raise ValueError("input must have a 'name' column")
    df["name"] = df["name"].astype("string").str.strip()
    df = df[df["name"].notna() & (df["name"].str.len() > 0)].reset_index(drop=True)

    parsed = pd.DataFrame([parse_row(n) for n in df["name"]])
    valid = parsed[parsed["valid"] & parsed["stage_canonical"].notna()].copy()
    unknown_stage = parsed[parsed["valid"] & parsed["stage_canonical"].isna()].copy()
    invalid = parsed[~parsed["valid"]].copy()

    # --- stage_dictionary.csv ---
    stage_counts = Counter()
    stage_to_canonical = {}
    for _, row in parsed[parsed["valid"]].iterrows():
        raw = row["stage_raw"]
        stage_counts[raw] += 1
        if row["stage_canonical"]:
            stage_to_canonical[raw] = row["stage_canonical"]

    dict_rows = []
    for raw, count in sorted(stage_counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        dict_rows.append({
            "stage_raw":       raw,
            "stage_canonical": stage_to_canonical.get(raw, "(UNKNOWN)"),
            "count":           count,
        })
    stage_dict = pd.DataFrame(dict_rows)
    stage_dict.to_csv(OUT_DIR / "stage_dictionary.csv", index=False)

    # --- invalid_rows.csv (includes unknown-stage rows) ---
    rejected = pd.concat([invalid, unknown_stage], ignore_index=True)
    rejected[["name", "reason", "project_code", "lot_number", "stage_raw"]] \
        .to_csv(OUT_DIR / "invalid_rows.csv", index=False)

    # --- Issues ---
    by_canonical: dict[str, set] = {}
    for raw, canon in stage_to_canonical.items():
        by_canonical.setdefault(canon, set()).add(raw)
    inconsistent = {c: sorted(v) for c, v in by_canonical.items() if len(v) > 1}

    seen_canonical = set(stage_to_canonical.values())
    missing_expected = [s for s in CANONICAL_ORDER if s not in seen_canonical]

    rare_stages = [r for r, n in stage_counts.items() if n == 1]
    unknown_raw = sorted(set(unknown_stage["stage_raw"].dropna().tolist()))

    # --- stage_summary.md ---
    lines = [
        "# Stage Dictionary — Data Quality Summary",
        "",
        f"_Source: `{INPUT_FILE.name}`_",
        f"_Total rows: {len(df)} | valid: {len(valid)} | unknown stage: {len(unknown_stage)} | invalid: {len(invalid)}_",
        "",
        "## Unique stages observed",
    ]
    for raw, count in sorted(stage_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        canon = stage_to_canonical.get(raw, "(UNKNOWN)")
        lines.append(f"- `{raw}` → `{canon}`  ({count}×)")

    lines += ["", "## Canonical alias mapping (proposed)"]
    for raw in sorted(stage_to_canonical):
        lines.append(f"- `\"{raw}\"` → `\"{stage_to_canonical[raw]}\"`")

    lines += ["", "## Issues found"]
    if inconsistent:
        lines.append("**Inconsistent naming (same canonical, multiple raw forms):**")
        for canon, rawset in inconsistent.items():
            lines.append(f"- `{canon}` ← {', '.join(f'`{r}`' for r in rawset)}")
    else:
        lines.append("- (no inconsistent naming)")

    lines.append("")
    lines.append("**Missing expected stages (in canonical ordering, not seen in this sample):**")
    if missing_expected:
        for m in missing_expected:
            lines.append(f"- `{m}`")
    else:
        lines.append("- (none — all canonical stages observed)")

    lines.append("")
    lines.append("**Rare stages (count == 1):**")
    if rare_stages:
        for r in rare_stages:
            lines.append(f"- `{r}`")
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("**Unknown stages (parsed but no canonical mapping):**")
    if unknown_raw:
        for u in unknown_raw:
            lines.append(f"- `{u}`  ← add to `CANONICAL_ALIASES` if real")
    else:
        lines.append("- (none)")

    lines += ["", "## Invalid row reasons"]
    if len(invalid):
        for reason, n in invalid["reason"].value_counts().items():
            lines.append(f"- {reason}: {n}")
    else:
        lines.append("- (no invalid rows)")

    (OUT_DIR / "stage_summary.md").write_text("\n".join(lines))

    # --- Console output -------------------------------------------------------

    print(f"Rows: {len(df)}  valid: {len(valid)}  unknown-stage: {len(unknown_stage)}  invalid: {len(invalid)}")
    print()
    print("--- stage_dictionary ---")
    print(stage_dict.to_string(index=False))
    print()
    print("--- invalid rows (head 5) ---")
    if len(invalid):
        for _, r in invalid.head(5).iterrows():
            preview = (r["name"][:80] + "…") if len(r["name"]) > 80 else r["name"]
            print(f"  [{r['reason']}]  {preview!r}")
    else:
        print("  (none)")
    print()
    print("--- issues ---")
    if inconsistent:
        for canon, rawset in inconsistent.items():
            print(f"  inconsistent: {canon} ← {sorted(rawset)}")
    if missing_expected:
        print(f"  missing expected: {missing_expected}")
    if unknown_raw:
        print(f"  unknown stages: {unknown_raw}")
    print()
    print("--- INTEGRATION SNIPPET FOR clickup_real.py ---")
    print(_integration_snippet(stage_to_canonical))


def _integration_snippet(stage_to_canonical: dict[str, str]) -> str:
    """Emit the exact dict + helper that clickup_real.py should adopt."""
    lines = [
        "# === paste into clickup_real.py (replaces existing STAGE_ALIASES) ===",
        "STAGE_ORDER = {",
        '    "Dug": 1, "Footings": 2, "Walls": 3, "Backfill": 4,',
        '    "Spec": 5, "Rough": 6, "Finish": 7, "Complete": 8, "Sold": 9,',
        "}",
        "",
        "# Lowercased stage_raw → canonical. Sourced from stage_dictionary.py;",
        "# extend here when stage_summary.md flags a new unknown stage.",
        "STAGE_ALIASES = {",
    ]
    for raw in sorted(CANONICAL_ALIASES):
        lines.append(f'    "{raw}": "{CANONICAL_ALIASES[raw]}",')
    lines += [
        "}",
        "",
        "def normalize_stage(raw: str | None) -> str | None:",
        '    """Canonicalize a stage_raw token. Returns None if unrecognized."""',
        "    if not isinstance(raw, str): return None",
        "    return STAGE_ALIASES.get(raw.strip().lower())",
        "# === end snippet ===",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
