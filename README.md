# Development Ontology Engine

## Financials + ClickUp Operating State Pipeline

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

### Stage vocabulary

`stage_dictionary.py` is the source-of-truth helper for the canonical stage list (`Dug → Footings → Walls → Backfill → Spec → Rough → Finish → Complete → Sold`) and the alias map.

- It validates a secondary ClickUp naming dump against the canonical vocabulary and writes `output/stage_dictionary.csv`, `output/invalid_rows.csv`, and `output/stage_summary.md`.
- `clickup_real.py` already handles every alias currently observed (`Dig`/`Dug`, `Spec`, `Footings`, `Walls`, `Backfill`, etc.). No code change is needed today.
- **When `stage_summary.md` flags an unknown stage:**
  1. Add the alias to `CANONICAL_ALIASES` in `financials/stage_dictionary.py`.
  2. Re-run `python3 financials/stage_dictionary.py` and verify it now resolves.
  3. Copy the printed integration snippet's `STAGE_ALIASES` block into `clickup_real.py` (replace the existing dict).
  4. Re-run the pipeline.
