# Operating State v1 — Agent Context

_Generated: 2026-04-29T23:38:21.864556+00:00_

## What this is
A point-in-time snapshot of in-flight homebuilder lots, derived from a
ClickUp task export and a partial QuickBooks GL export. Phase IDs are
**estimated** (gap-based clustering), not from a plat reference.

## Projects in scope
- **H A14** — 1 lots, avg completion 55.6%, current stage mix `Spec:1`
- **H MF** — 3 lots, avg completion 33.3%, current stage mix `(none):1|Backfill:1|Spec:1`
- **LE** — 18 lots, avg completion 44.4%, current stage mix `Backfill:18`

## Stage status by project
- **H A14**: 1 lots in `H A14 P1` paused at **Spec** (55.6% complete on average).
- **H MF**: 2 lots in `H MF P2` paused at **Backfill** (22.2% complete on average).
- **LE**: 18 lots in `LE P1` paused at **Backfill** (44.4% complete on average).

## Bottlenecks
- `LE P1` — **18 lots** all sitting at `Backfill` (44.4% complete). Looks like a single stage handoff is blocking the cohort.

## Cost reality
- **H A14** → Flagborough LLC: $66,814 (confidence: high)
- **H MF** → Flagborough LLC: $66,814 (confidence: high)
- **LE** → Anderson Geneva LLC: **no cost data**. GL entity 'Anderson Geneva LLC' mapped, but the GL sample contains no Activity rows for it (Beginning Balance only or absent). Cost is unknown, NOT zero.

## Quality artifacts to consult
- `state_quality_report_v1.md` — lot coverage, project join coverage, GL join coverage, top missing data
- `stage_summary.md` — canonical stage vocabulary, observed aliases, any unknown stages flagged for review
- `invalid_rows.csv` — task names that failed parsing (e.g. free-text notes that landed in the task name field)

## What is estimated vs measured
- **measured**: project_code, lot_number, stages_present, current_stage, completion_pct, status (all from real ClickUp task data)
- **estimated (heuristic)**: `phase_id_estimated` — derived from lot_number proximity, not from a plat reference
- **partial**: cost figures (some projects have GL Activity, others have only Beginning Balance / no records)
- **NOT computed here**: per-lot cost. The GL has zero lot-level signal; do not invent it.

## How an agent should use this
1. Refer to lots by `(project_code, lot_number)` — not by `phase_id_estimated`, which can change if the clustering threshold is retuned.
2. When citing cost, name the `gl_entity` and confidence — do not aggregate across projects with mixed confidence.
3. When asked about phases, surface them as 'estimated phase' or 'lot range', never as a plat name.
