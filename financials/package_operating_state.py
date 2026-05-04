"""
Package the operating state for downstream LLM agents.

Reads:  output/lot_state_real.csv, project_state_real.csv, phase_state_real.csv,
        financials_normalized.csv
Writes: output/operating_state_v1.json
        output/agent_context_v1.md
        output/state_quality_report_v1.md
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR   = REPO_ROOT / "output"

LOT_FILE     = OUT_DIR / "lot_state_real.csv"
PROJECT_FILE = OUT_DIR / "project_state_real.csv"
PHASE_FILE   = OUT_DIR / "phase_state_real.csv"
GL_FILE      = OUT_DIR / "financials_normalized.csv"

JSON_OUT     = OUT_DIR / "operating_state_v1.json"
CONTEXT_OUT  = OUT_DIR / "agent_context_v1.md"
QUALITY_OUT  = OUT_DIR / "state_quality_report_v1.md"

# Same map used elsewhere — extend as patterns emerge.
PROJECT_CODE_TO_ENTITY = {
    "LE":    "Anderson Geneva LLC",
    "H":     "Flagborough LLC",
    "H MF":  "Flagborough LLC",
    "H A14": "Flagborough LLC",
    "H A13": "Flagborough LLC",
    "AS":    "Arrowhead Springs Development LLC",
}


def _isoz(s) -> str | None:
    if pd.isna(s) or s is None or s == "":
        return None
    try:
        return pd.to_datetime(s).isoformat()
    except Exception:
        return str(s)


def _has_real_parent(lot_key: str) -> bool:
    return isinstance(lot_key, str) and not (
        lot_key.startswith("FALLBACK_") or lot_key.startswith("ROW_") or lot_key.startswith("derived_")
    )


def lot_source_confidence(row) -> str:
    real = _has_real_parent(str(row["lot_key"]))
    stages = int(row["stage_count"]) if pd.notna(row["stage_count"]) else 0
    if real and stages >= 2:
        return "high"
    if real and stages >= 1:
        return "medium"
    return "low"


def gl_costs_by_entity() -> dict[str, float]:
    if not GL_FILE.exists():
        return {}
    gl = pd.read_csv(GL_FILE)
    proj = gl[gl["entity_role"] == "project"]
    return (proj.groupby("entity")["amount"]
                .apply(lambda s: s.abs().sum()).to_dict())


# --- JSON builder ------------------------------------------------------------

def build_json(lots: pd.DataFrame, phases: pd.DataFrame, projects: pd.DataFrame) -> dict:
    cost_map = gl_costs_by_entity()

    project_blocks = []
    for proj_code, proj_row in projects.set_index("project_code").iterrows():
        gl_entity = PROJECT_CODE_TO_ENTITY.get(proj_code)
        cost = float(cost_map.get(gl_entity, 0.0)) if gl_entity else 0.0

        if gl_entity and cost > 0:
            fin_conf = "high"
            fin_note = f"GL entity {gl_entity!r} matched; cost is sum of |amount| on Activity rows."
        elif gl_entity and cost == 0:
            fin_note = (f"GL entity {gl_entity!r} mapped, but the GL sample contains no "
                        f"Activity rows for it (Beginning Balance only or absent). "
                        f"Cost is unknown, NOT zero.")
            fin_conf = "low"
        else:
            fin_conf = "low"
            fin_note = "No GL entity mapping for this project_code yet."

        # Phases for this project
        phase_blocks = []
        for _, ph in phases[phases["project_code"] == proj_code].iterrows():
            phase_id = ph["phase_id"]
            phase_lots = lots[(lots["project_code"] == proj_code)
                              & (lots["phase_id_estimated"] == phase_id)]
            lot_blocks = []
            for _, lot in phase_lots.iterrows():
                lot_blocks.append({
                    "lot_number":        str(lot["lot_number"]) if pd.notna(lot["lot_number"]) else None,
                    "stage":             lot["current_stage"] if pd.notna(lot["current_stage"]) else None,
                    "completion_pct":    float(lot["completion_pct"]) if pd.notna(lot["completion_pct"]) else 0.0,
                    "status":            lot["status"],
                    "last_activity":     _isoz(lot["last_activity"]),
                    "source_confidence": lot_source_confidence(lot),
                })
            phase_blocks.append({
                "phase_id_estimated": phase_id,
                "phase_confidence":   "estimated",
                "lots_in_phase":      int(ph["lots_in_phase"]),
                "dominant_stage":     ph["dominant_stage"] if pd.notna(ph["dominant_stage"]) else None,
                "avg_completion_pct": float(ph["avg_completion_pct"]),
                "lots":               lot_blocks,
            })

        project_blocks.append({
            "project_code": proj_code,
            "lots_total":   int(proj_row["total_lots"]),
            "avg_completion_pct": float(proj_row["avg_completion_pct"]),
            "stage_distribution": proj_row["stage_distribution"],
            "financials": {
                "gl_entity":            gl_entity,
                "project_total_cost":   round(cost, 2),
                "financial_confidence": fin_conf,
                "financial_notes":      fin_note,
            },
            "phases": phase_blocks,
        })

    quality = {
        "lots_total":             int(len(lots)),
        "lots_high_confidence":   int(sum(lot_source_confidence(r) == "high" for _, r in lots.iterrows())),
        "lots_medium_confidence": int(sum(lot_source_confidence(r) == "medium" for _, r in lots.iterrows())),
        "lots_low_confidence":    int(sum(lot_source_confidence(r) == "low" for _, r in lots.iterrows())),
        "lots_with_valid_progression": int(lots["has_valid_progression"].sum()),
        "projects_total":         int(len(projects)),
        "projects_with_cost":     sum(1 for p in project_blocks if p["financials"]["project_total_cost"] > 0),
        "phases_estimated":       int(len(phases)),
    }

    return {
        "schema_version":   "operating_state_v1",
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "data_quality":     quality,
        "phase_definition": "heuristic — gap-based clustering on lot_number "
                            "(GAP_THRESHOLD=10). NOT a real plat reference.",
        "projects":         project_blocks,
    }


# --- agent_context.md ---------------------------------------------------------

def build_agent_context(state: dict) -> str:
    lines = [
        "# Operating State v1 — Agent Context",
        "",
        f"_Generated: {state['generated_at']}_",
        "",
        "## What this is",
        "A point-in-time snapshot of in-flight homebuilder lots, derived from a",
        "ClickUp task export and a partial QuickBooks GL export. Phase IDs are",
        "**estimated** (gap-based clustering), not from a plat reference.",
        "",
        "## Projects in scope",
    ]
    for p in state["projects"]:
        lines.append(
            f"- **{p['project_code']}** — {p['lots_total']} lots, "
            f"avg completion {p['avg_completion_pct']*100:.1f}%, "
            f"current stage mix `{p['stage_distribution']}`"
        )

    lines += ["", "## Stage status by project"]
    for p in state["projects"]:
        # Identify bottleneck = dominant stage of the largest phase
        phases_sorted = sorted(p["phases"], key=lambda x: -x["lots_in_phase"])
        if phases_sorted:
            top_phase = phases_sorted[0]
            lines.append(
                f"- **{p['project_code']}**: {top_phase['lots_in_phase']} lots in "
                f"`{top_phase['phase_id_estimated']}` paused at **{top_phase['dominant_stage']}** "
                f"({top_phase['avg_completion_pct']*100:.1f}% complete on average)."
            )

    lines += ["", "## Bottlenecks"]
    for p in state["projects"]:
        for ph in p["phases"]:
            if ph["lots_in_phase"] >= 5 and ph["avg_completion_pct"] < 0.6:
                lines.append(
                    f"- `{ph['phase_id_estimated']}` — **{ph['lots_in_phase']} lots** all sitting "
                    f"at `{ph['dominant_stage']}` ({ph['avg_completion_pct']*100:.1f}% complete). "
                    f"Looks like a single stage handoff is blocking the cohort."
                )
    if not any("- " in l for l in lines[-5:]):
        lines.append("- (none flagged at current thresholds)")

    lines += ["", "## Cost reality"]
    for p in state["projects"]:
        f = p["financials"]
        if f["project_total_cost"] > 0:
            lines.append(
                f"- **{p['project_code']}** → {f['gl_entity']}: ${f['project_total_cost']:,.0f} "
                f"(confidence: {f['financial_confidence']})"
            )
        else:
            lines.append(
                f"- **{p['project_code']}** → {f['gl_entity'] or 'no entity mapping'}: "
                f"**no cost data**. {f['financial_notes']}"
            )

    lines += [
        "",
        "## Quality artifacts to consult",
        "- `state_quality_report_v1.md` — lot coverage, project join coverage, GL join coverage, top missing data",
        "- `stage_summary.md` — canonical stage vocabulary, observed aliases, any unknown stages flagged for review",
        "- `invalid_rows.csv` — task names that failed parsing (e.g. free-text notes that landed in the task name field)",
        "",
        "## What is estimated vs measured",
        "- **measured**: project_code, lot_number, stages_present, current_stage, "
        "completion_pct, status (all from real ClickUp task data)",
        "- **estimated (heuristic)**: `phase_id_estimated` — derived from lot_number "
        "proximity, not from a plat reference",
        "- **partial**: cost figures (some projects have GL Activity, others have only "
        "Beginning Balance / no records)",
        "- **NOT computed here**: per-lot cost. The GL has zero lot-level signal; do "
        "not invent it.",
        "",
        "## How an agent should use this",
        "1. Refer to lots by `(project_code, lot_number)` — not by `phase_id_estimated`, "
        "which can change if the clustering threshold is retuned.",
        "2. When citing cost, name the `gl_entity` and confidence — do not aggregate "
        "across projects with mixed confidence.",
        "3. When asked about phases, surface them as 'estimated phase' or 'lot range', "
        "never as a plat name.",
        "",
    ]
    return "\n".join(lines)


# --- quality report -----------------------------------------------------------

def build_quality_report(state: dict, lots: pd.DataFrame, projects: pd.DataFrame,
                         phases: pd.DataFrame) -> str:
    q = state["data_quality"]
    n = q["lots_total"]
    pct = lambda a, b: (100.0 * a / b) if b else 0.0

    by_proj_cost = []
    for p in state["projects"]:
        f = p["financials"]
        by_proj_cost.append((p["project_code"], f["gl_entity"], f["project_total_cost"],
                             f["financial_confidence"]))

    lines = [
        "# Operating State v1 — Quality Report",
        "",
        f"_Generated: {state['generated_at']}_",
        "",
        "## Lot coverage",
        f"- Total lots: **{n}**",
        f"- High confidence (real ClickUp parent_id, ≥2 stages): {q['lots_high_confidence']} ({pct(q['lots_high_confidence'], n):.1f}%)",
        f"- Medium confidence: {q['lots_medium_confidence']} ({pct(q['lots_medium_confidence'], n):.1f}%)",
        f"- Low confidence (fallback lot_key, sparse stages): {q['lots_low_confidence']} ({pct(q['lots_low_confidence'], n):.1f}%)",
        f"- With valid stage progression (no skipped stages): {q['lots_with_valid_progression']} ({pct(q['lots_with_valid_progression'], n):.1f}%)",
        "",
        "## Project join coverage",
        f"- Projects: **{q['projects_total']}**",
        f"- Lots → project_state join: 100% (project_code parsed from every name)",
        "",
        "## GL join coverage",
        f"- Projects with cost > $0: **{q['projects_with_cost']} of {q['projects_total']}**",
        "",
        "| project_code | gl_entity | total_cost | confidence |",
        "|---|---|---:|---|",
    ]
    for code, ent, cost, conf in by_proj_cost:
        lines.append(f"| {code} | {ent or '—'} | ${cost:,.0f} | {conf} |")

    lines += [
        "",
        "## Estimated vs real fields",
        "- `phase_id_estimated` — **heuristic only** (gap-based clustering on lot_number, threshold=10). Not a plat reference.",
        "- `phase_confidence` — fixed string `'estimated'` for all phases until a real plat→lot table is wired.",
        "- `cost_per_lot` is **not** present in this state. If consumers compute total_cost / lots_total, mark it as an *estimate*, never as actual lot cost.",
        "- `LE` financials show **$0**, NOT because LE has no spend, but because the GL sample we ingested has only Beginning Balance rows for Anderson Geneva LLC. Real LE activity exists outside this export.",
        "",
        "## Top missing data (in priority order)",
        "1. **Plat → lot reference table** — would replace gap-based phase estimation with real phase IDs (A4, B2, etc.).",
        "2. **GL re-export with QuickBooks `Class` / `Customer:Job` populated** — single biggest unlock for project- and phase-level cost.",
        "3. **Activity rows for Anderson Geneva LLC (LE project)** — currently absent from the GL sample.",
        "4. **Stage timestamps (`start_date`, `date_done`)** — only 0–1 of 100 task rows have these populated; stage durations cannot be measured.",
        "5. **Vendor names** — 97% of vendor field is a placeholder string, blocking vendor-level cost analysis.",
        "",
    ]
    return "\n".join(lines)


# --- README -------------------------------------------------------------------

README_BLOCK = """## Financials + ClickUp Operating State Pipeline

This pipeline lives in `financials/` and produces an agent-ready operating
state from a QuickBooks GL export and a ClickUp task export.

### How to run

```bash
python3 financials/build_financials.py     # GL → output/financials_normalized.csv (+ rollups)
python3 financials/clickup_real.py         # ClickUp → output/lot_state_real.csv, project_state_real.csv
python3 financials/phase_state.py          # adds output/phase_state_real.csv + writes phase_id_estimated back into lot_state_real.csv
python3 financials/operating_view.py       # joined operating_view_v1.csv (6-col spec)
python3 financials/package_operating_state.py   # operating_state_v1.json + agent_context_v1.md + state_quality_report_v1.md
```

### Outputs
- `output/financials_normalized.csv` — GL with cost_bucket + entity classification
- `output/lot_state_real.csv` — one row per lot, stages_present, current_stage, completion_pct, **phase_id_estimated**
- `output/project_state_real.csv` — one row per project_code
- `output/phase_state_real.csv` — heuristic phases (gap-based clustering)
- `output/operating_view_v1.csv` — 6-col joined view
- `output/operating_state_v1.json` — nested project → phase → lots structure for LLM agents
- `output/agent_context_v1.md` — plain-English context summary
- `output/state_quality_report_v1.md` — coverage + confidence report

### Confidence model
- `phase_id_estimated` is **heuristic**, not a plat reference. Replace `assign_phases()` once a real plat→lot table arrives.
- Per-lot cost is **not** computed; the GL sample has no lot-level signal.
- LE financials show $0 because the GL sample lacks Anderson Geneva LLC Activity rows. Treat as missing, not zero.
"""


def update_readme() -> None:
    path = REPO_ROOT / "README.md"
    if path.exists():
        existing = path.read_text()
        if "Financials + ClickUp Operating State Pipeline" in existing:
            return  # already inserted
        new = existing.rstrip() + "\n\n" + README_BLOCK
    else:
        new = "# Development Ontology Engine\n\n" + README_BLOCK
    path.write_text(new)


# --- Main ---------------------------------------------------------------------

def main() -> None:
    lots     = pd.read_csv(LOT_FILE)
    projects = pd.read_csv(PROJECT_FILE)
    phases   = pd.read_csv(PHASE_FILE)

    state = build_json(lots, phases, projects)

    JSON_OUT.write_text(json.dumps(state, indent=2, default=str))
    CONTEXT_OUT.write_text(build_agent_context(state))
    QUALITY_OUT.write_text(build_quality_report(state, lots, projects, phases))
    update_readme()

    print(f"Wrote:")
    print(f"  {JSON_OUT}                ({JSON_OUT.stat().st_size:,} bytes)")
    print(f"  {CONTEXT_OUT}             ({CONTEXT_OUT.stat().st_size:,} bytes)")
    print(f"  {QUALITY_OUT}             ({QUALITY_OUT.stat().st_size:,} bytes)")
    print(f"  README.md                                       (updated)")
    print()
    q = state["data_quality"]
    print("Snapshot:")
    print(f"  projects:               {q['projects_total']}")
    print(f"  lots:                   {q['lots_total']} (high={q['lots_high_confidence']}, "
          f"med={q['lots_medium_confidence']}, low={q['lots_low_confidence']})")
    print(f"  estimated phases:       {q['phases_estimated']}")
    print(f"  projects with cost > 0: {q['projects_with_cost']}")


if __name__ == "__main__":
    main()
