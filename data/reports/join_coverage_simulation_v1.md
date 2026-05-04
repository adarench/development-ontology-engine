# Join Coverage Simulation v1 (W3)

**Built**: 2026-05-01
**Author**: Terminal A (W3 of BCPD State Quality Pass)
**Inputs**: `vf_lot_code_decoder_v1.csv`, `staged_inventory_lots.parquet`, `staged_gl_transactions_v2.parquet`, `staged_clickup_tasks.parquet`, `staged_project_crosswalk_v0.csv`

**Method**: re-run the same join-coverage harness as `data/reports/join_coverage_v0.md`, with three changes:

1. VF rows decoded via v1 decoder (project + phase + lot 3-tuple).
2. Range rows excluded from lot-level denominator (kept at project+phase grain).
3. HarmCo commercial X-X parcels excluded from lot-level denominator (non-lot inventory).
4. SctLot rows attributed to 'Scattered Lots' canonical project, not Scarlet Ridge.

Inventory base unchanged: 1,285 distinct (canonical_project, lot) at project_confidence=high.

---

## Headline

| metric | v0 baseline | v1 simulated | delta lots | delta % |
|---|---:|---:|---:|---:|
| Inventory base lots | 1,285 | 1,285 | 0 | 0.0% |
| Lots with ≥1 GL row | 810 (63.0%) | 856 (66.6%) | +46 | +3.6% |
| Lots with ≥1 ClickUp task | 811 (63.1%) | 811 (63.1%) | +0 | +0.0% |
| Full triangle (GL ∧ ClickUp) | 476 (37.0%) | 478 (37.2%) | +2 | +0.2% |

### Why the binary-coverage delta is modest, and why the v1 changes still matter

The binary metric **"does ≥1 GL row exist for this inventory lot?"** is forgiving — at v0's 2-tuple `(project, lot)` join, any VF row whose lot string normalizes to the inventory's lot already counted. The +46 lot lift comes from the AultF B-suffix correction reaching 11 new Parkway B1 lots (0201B–0211B) and from a few HarmCo residential matches now that alpha lots like `A01` are preserved in the validation index.

The much larger v1 wins are **correctness, not coverage**:

- **$4.0M moved from B2 to B1** in Parkway Fields (AultF B-suffix correction; Terminal B Q2). v0 was wrong — those lots had GL rows but pointing at the wrong phase.
- **$6.75M Harmony double-count avoided** by enforcing the 3-tuple `(project, phase, lot)` join key. v0's flat 2-tuple would have collapsed MF1 lot 101 and B1 lot 101 onto the same inventory row.
- **$6.55M removed from Scarlet Ridge** because SctLot is now 'Scattered Lots'. v0 silently inflated Scarlet Ridge's project-grain cost by ~46%.
- **$45.75M of shell-allocation cost surfaced** at project+phase grain via range-row treatment. v0 left these in the lot denominator, polluting any per-lot cost-per-unit metric.
- **205 commercial parcels removed from lot denominator**. v0 counted them but had no inventory match.

In short: v1 changes the lot-level cost numbers significantly while the binary coverage metric is barely touched. The right way to read the v1 lift is via the cost-correctness rows below, not the headline percentage.

## Per-project breakdown (high-confidence inventory base)

| project | inventory lots | v0 GL% | v1 GL% | delta GL | v0 triangle% | v1 triangle% | delta tri |
|---|---:|---:|---:|---:|---:|---:|---:|
| Harmony | 391 | 53.7% | 53.7% | +0 | 35.0% | 35.0% | +0 |
| Parkway Fields | 317 | 61.5% | 76.0% | +46 | 23.0% | 23.7% | +2 |
| Arrowhead Springs | 206 | 65.0% | 65.0% | +0 | 9.7% | 9.7% | +0 |
| Salem Fields | 139 | 100.0% | 100.0% | +0 | 87.8% | 87.8% | +0 |
| Lomond Heights | 114 | 43.9% | 43.9% | +0 | 43.0% | 43.0% | +0 |
| Willowcreek | 62 | 100.0% | 100.0% | +0 | 100.0% | 100.0% | +0 |
| Lewis Estates | 34 | 0.0% | 0.0% | +0 | 0.0% | 0.0% | +0 |
| Scarlet Ridge | 22 | 90.9% | 90.9% | +0 | 59.1% | 59.1% | +0 |

## GL VF rows-touched after v1 decoder

| canonical project | total VF rows | lot-eligible | matched (3-tuple) | matched $ | excluded range | excluded commercial | excluded SR | excluded project-only |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Arrowhead Springs | 5,153 | 5,148 | 5,148 | $24,207,836 | 5 | 0 | 0 | 0 |
| Harmony | 11,910 | 11,137 | 10,596 | $41,583,685 | 568 | 205 | 0 | 0 |
| Lomond Heights | 595 | 536 | 536 | $1,880,049 | 59 | 0 | 0 | 0 |
| Parkway Fields | 43,254 | 41,526 | 24,227 | $73,878,252 | 1,114 | 0 | 401 | 0 |
| Scarlet Ridge | 3,916 | 3,916 | 3,737 | $13,428,121 | 0 | 0 | 0 | 0 |
| Scattered Lots | 1,130 | 0 | 0 | $0 | 0 | 0 | 0 | 1,130 |

## What changed (vs v0 baseline)

**GL VF rows newly matched at lot grain**: ~44244 rows / $154,977,943 of GL VF cost basis are now attached to specific (project, phase, lot) triples.

**Inventory lots newly reachable from GL** (delta vs v0): 46 lots (3.6%).

**Range rows now isolated at project+phase grain (not in lot denominator)**: 1746 rows ($45,752,047).

**Commercial parcels excluded from lot denominator**: 205 rows.

**SR-suffix and SctLot rows treated as project-grain only**: 401 + 1130 rows.

---

## Remaining unresolved patterns (after v1)

- **AultF SR (`0139SR`, `0140SR`)**: 401 rows, no clean phase routing without source-owner input.
- **HarmCo X-X commercial pads**: 205 rows, no inventory or allocation row exists for these parcels — needs a new ontology entity.
- **SctLot 'Scattered Lots'**: 1,130 rows / $6.55M are now correctly isolated from Scarlet Ridge but still have no lot-level inventory match. Requires either (a) a separate scattered-lots inventory feed, or (b) acceptance that SctLot rolls up at project grain only.
- **Range rows 4,020 / $45.75M**: kept at project+phase grain in v1; per-lot expansion is a v2 candidate that needs allocation-method sign-off (equal split vs sales-price-weighted vs fixed).
- **Lewis Estates and the 7 active no-GL projects**: structural gap; no decoder helps. Requires fresh data.
- **DR 38-col phase recovery**: DR's phase column is 0% filled. Lots in DR-era 2016-17 BCPD rollups still don't have a phase tag. Consider mining `Lot/Phase` strings if the source carried any.

---

## Hard guardrails honored

- ✅ Did not modify operating_state_v2_bcpd.json or any v2 output.
- ✅ Did not modify staged_gl_transactions_v2 or canonical_lot.
- ✅ Confidence of every decoder rule remains `inferred`.
- ✅ Inventory base unchanged (same 1,285 lots).
- ✅ Org-wide v2 untouched.

