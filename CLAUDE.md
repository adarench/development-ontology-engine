# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip3 install -r requirements.txt

# v1 pipeline (run in order)
python3 financials/build_financials.py
python3 financials/clickup_real.py
python3 financials/phase_state.py
python3 financials/operating_view.py
python3 financials/package_operating_state.py

# v2.1 BCPD pipeline (staged parquet required first)
python3 financials/build_canonical_tables_v0.py
python3 financials/build_operating_state_v2_1_bcpd.py

# QA harness
python3 financials/qa/bcpd_state_qa.py

# Tests
python3 tests/test_bcpd_state_qa_readonly.py
python3 tests/test_agent_chunks_v2_bcpd.py

# Run a single test (they're standalone scripts, not pytest)
python3 -m tests.test_bcpd_state_qa_readonly
```

## Architecture

### Two pipeline generations

**v1** (`financials/build_financials.py` → `clickup_real.py` → `phase_state.py` → `operating_view.py` → `package_operating_state.py`) operates on raw CSV/Excel inputs and produces `output/operating_state_v1.json`. It's a single-company, single-run pipeline with hardcoded entity maps. Phases are heuristic (gap-based clustering on lot number).

**v2 / v2.1 BCPD** (`financials/build_operating_state_v2_1_bcpd.py`) operates on parquet staged under `data/staged/`. It uses a VF lot decoder (`financials/build_vf_lot_decoder_v1.py`) to resolve vendor-facing lot codes to canonical IDs, and requires a 3-tuple join `(project, phase, lot)` to avoid double-counting. Outputs land in `output/operating_state_v2_1_bcpd.json`.

### Ontology layer (`docs/ontology_v0.md`)

The canonical entity graph: `LegalEntity → Project → Phase → Lot → TaskState + FinancialTransaction`. All canonical tables live in `data/staged/canonical_*.{csv,parquet}`. Crosswalks mapping raw source values to canonical IDs are in `data/staged/staged_*_crosswalk_v0.*`. `pipelines/config.py` is the authoritative config for v1: lot state waterfall, collateral buckets, cost components, advance rates, output column ordering.

### QA harness (`financials/qa/`)

A read-only Q&A layer over the v2.1 state. `question_set.py` defines 15 fixed questions. `bcpd_state_qa.py` has one deterministic handler per question. `guardrails.py` defines answer-validation rules that fire based on question intent. `bcpd_state_loader.py` defines `PROTECTED_PATHS` — files that must never be mutated by the harness. Tests snapshot file hashes before running and verify no protected file changed.

### Agent output chunks (`output/agent_chunks_v2_bcpd/`)

Chunked markdown files indexed by `index.json`. Each chunk carries YAML frontmatter with `chunk_id`, `confidence`, `allowed_uses`, `caveats`, and `source_files`. Required guardrail chunks must be present (enforced by `tests/test_agent_chunks_v2_bcpd.py`).

### Key data integrity rules

- **Missing cost ≠ $0**: Projects absent from the GL must surface as `unknown`, never `$0`. Applies especially to LE / Anderson Geneva LLC (Beginning Balance rows only in sample).
- **DataRails dedup**: Raw DR 38-col exports have a 2.16× row-multiplication bug. `dr_dedup_key()` in `build_operating_state_v2_1_bcpd.py` deduplicates before any aggregation.
- **Org-wide is blocked**: Hillcrest and Flagship Belmont GL coverage ends 2017-02. All v2 rollups are BCPD-scoped only.
- **Phase IDs are estimated** until a real plat→lot reference table replaces `phase_state.py`'s gap-based clustering.
- **3-tuple join discipline**: Harmony lots share lot numbers across phases (MF1 vs B1). Any cost rollup must use `(project, phase, lot)` — never flat `(project, lot)`.
