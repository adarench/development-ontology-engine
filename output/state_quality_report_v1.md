# Operating State v1 — Quality Report

_Generated: 2026-04-29T23:38:21.864556+00:00_

## Lot coverage
- Total lots: **22**
- High confidence (real ClickUp parent_id, ≥2 stages): 20 (90.9%)
- Medium confidence: 0 (0.0%)
- Low confidence (fallback lot_key, sparse stages): 2 (9.1%)
- With valid stage progression (no skipped stages): 19 (86.4%)

## Project join coverage
- Projects: **3**
- Lots → project_state join: 100% (project_code parsed from every name)

## GL join coverage
- Projects with cost > $0: **2 of 3**

| project_code | gl_entity | total_cost | confidence |
|---|---|---:|---|
| H A14 | Flagborough LLC | $66,814 | high |
| H MF | Flagborough LLC | $66,814 | high |
| LE | Anderson Geneva LLC | $0 | low |

## Estimated vs real fields
- `phase_id_estimated` — **heuristic only** (gap-based clustering on lot_number, threshold=10). Not a plat reference.
- `phase_confidence` — fixed string `'estimated'` for all phases until a real plat→lot table is wired.
- `cost_per_lot` is **not** present in this state. If consumers compute total_cost / lots_total, mark it as an *estimate*, never as actual lot cost.
- `LE` financials show **$0**, NOT because LE has no spend, but because the GL sample we ingested has only Beginning Balance rows for Anderson Geneva LLC. Real LE activity exists outside this export.

## Top missing data (in priority order)
1. **Plat → lot reference table** — would replace gap-based phase estimation with real phase IDs (A4, B2, etc.).
2. **GL re-export with QuickBooks `Class` / `Customer:Job` populated** — single biggest unlock for project- and phase-level cost.
3. **Activity rows for Anderson Geneva LLC (LE project)** — currently absent from the GL sample.
4. **Stage timestamps (`start_date`, `date_done`)** — only 0–1 of 100 task rows have these populated; stage durations cannot be measured.
5. **Vendor names** — 97% of vendor field is a placeholder string, blocking vendor-level cost analysis.
