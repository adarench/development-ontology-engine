# BCPD Operating State v2.0 → v2.1 Change Log

**Date**: 2026-05-01
**Author**: Terminal A (W6 of BCPD State Quality Pass)
**Scope**: Additive rebuild. v2.0 outputs unchanged; v2.1 sits alongside.

This change log enumerates every difference between
`output/operating_state_v2_bcpd.json` (v2.0) and
`output/operating_state_v2_1_bcpd.json` (v2.1) so that consumers can migrate
deliberately.

---

## What did NOT change

- `staged_gl_transactions_v2.{csv,parquet}` — read-only.
- `staged_inventory_lots.{csv,parquet}` — read-only.
- `staged_clickup_tasks.{csv,parquet}` — read-only.
- All v0 canonical tables under `data/staged/canonical_*` — unchanged.
- All v0 crosswalk tables under `data/staged/staged_*_crosswalk_v0.*` — unchanged.
- v1 outputs (`output/operating_state_v1.json`, `output/agent_context_v1.md`, `output/lot_state_real.csv`, …).
- v2.0 outputs (`output/operating_state_v2_bcpd.json` + 3 companion files).
- The DR 38-col 2.16× row-multiplication dedup (was applied in v2.0; still applied in v2.1).
- VF as the primary BCPD 2018-2025 cost source (unchanged).
- DR-dedup as the primary BCPD 2016-02→2017-02 cost source (unchanged).
- QB register as tie-out only (unchanged).
- The 9-pledged-project Collateral Report scope (unchanged).
- The 16-active-projects-from-2025Status base (unchanged; Scattered Lots is additive, not replacing).

---

## What did change

### 1. AultF B-suffix routing correction

| | v2.0 | v2.1 |
|---|---|---|
| AultF B-suffix → phase | B2 | **B1** |
| Rows affected | 1,499 | 1,499 |
| Dollars correctly routed | $0 (was wrong in v2.0) | **$4.0M** |
| Evidence | n/a | `scratch/vf_decoder_gl_finance_review.md` Q2 |
| Empirical signal | — | AultF B-suffix max lot=211 (matches B1); PWFS2 B-suffix min=273 (B2). Disjoint. |
| Confidence | n/a (incorrect) | inferred (high-evidence) |

### 2. Harmony 3-tuple join discipline

| | v2.0 | v2.1 |
|---|---|---|
| VF lot cost join key | `(canonical_project, lot_norm)` flat 2-tuple | `(canonical_project, canonical_phase, canonical_lot_number)` 3-tuple |
| Double-count risk | $6.75M (silent; MF1 lot 101 collides with B1 lot 101 — different physical lots) | $0 |
| Evidence | n/a | `scratch/vf_decoder_gl_finance_review.md` Q1+Q3 |
| Implementation | per-project totals only | every lot in v2.1 carries `vf_actual_cost_3tuple_usd` computed at (project, phase, lot) |
| Confidence | n/a (incorrect) | inferred (high-evidence) |

### 3. HarmCo split

| | v2.0 | v2.1 |
|---|---|---|
| HarmCo treatment | single rule, 0% match (validation artifact dropped alpha lots) | split: residential A01-B10 (169 rows) → MF2; commercial X-X (205 rows) → non-lot exception |
| Residential rows now matchable | 0 | **169** at 100% |
| Commercial parcels properly isolated | no (validation failed silently) | **yes** (`commercial_parcels_non_lot` field per project) |
| Evidence | n/a | `scratch/vf_decoder_ops_allocation_review.md` Q2 |
| Confidence | n/a | inferred (high on residential; ontology pending for commercial) |

### 4. SctLot → 'Scattered Lots'

| | v2.0 | v2.1 |
|---|---|---|
| `canonical_project` for SctLot rows | Scarlet Ridge | **Scattered Lots** |
| Rows moved | 1,130 | 1,130 |
| Dollars moved | $6.55M | $6.55M (off Scarlet Ridge; new project carries them) |
| Scarlet Ridge inflation in v0 | ~46% above true value | corrected |
| Evidence | n/a | `scratch/vf_decoder_gl_finance_review.md` Q4 |
| Lot-level inventory feed | (none — silently rolled into Scarlet Ridge inventory hash collision) | **none — explicitly project-grain only** |
| Confidence | (none specified) | inferred-unknown (canonical name pending) |

### 5. Range-row treatment

| | v2.0 | v2.1 |
|---|---|---|
| Range-form GL rows (e.g. `'3001-06'`) | mixed into lot-level rollups | kept at project+phase grain via `vf_unattributed_shell_dollars` |
| In-scope VF codes | not categorized | 8: HarmTo, LomHT1, PWFT1, ArroT1, MCreek, SaleTT, SaleTR, WilCrk |
| Rows | not segmented | 4,020 |
| Dollars | mixed in | **$45,752,047 explicit** |
| Per-phase field | n/a | `vf_unattributed_shell_dollars` + `vf_unattributed_shell_rows` per phase |
| Evidence | n/a | `scratch/vf_decoder_gl_finance_review.md` Q5 |
| Confidence | n/a | inferred (high on interpretation; allocation method pending) |

### 6. AultF SR-suffix isolation

| | v2.0 | v2.1 |
|---|---|---|
| AultF SR rows (0139SR, 0140SR) | unmapped (decoder undecoded) | explicitly isolated as inferred-unknown |
| Rows | 401 | 401 |
| Dollars | not surfaced | $1.18M explicit |
| Lot-level inclusion | accidentally excluded | deliberately excluded |
| Evidence | n/a | `scratch/vf_decoder_ops_allocation_review.md` Q1 |
| Confidence | n/a | inferred-unknown |

---

## New fields in v2.1 JSON

| field | grain | meaning |
|---|---|---|
| `vf_actual_cost_3tuple_usd` | per lot | VF dollars for this lot using the 3-tuple key |
| `vf_actual_cost_rows` | per lot | row count contributing to the dollars |
| `vf_actual_cost_join_key` | per lot (constant) | documents the join-key contract |
| `vf_actual_cost_confidence` | per lot (constant) | reminds consumers the value is decoder-derived |
| `vf_unattributed_shell_dollars` | per phase | range-row dollars not yet allocated to specific lots |
| `vf_unattributed_shell_rows` | per phase | row count for the above |
| `vf_unattributed_shell_note` | per phase (constant) | explanation |
| `commercial_parcels_non_lot` | per project (Harmony only in v2.1) | array of `{pad, rows, dollars, treatment}` |
| `vf_lot_grain_sum_usd` | per project | dollars attributed to specific lots |
| `vf_range_grain_sum_usd` | per project | dollars at project+phase grain (range rows) |
| `vf_commercial_grain_sum_usd` | per project | dollars on commercial parcels (Harmony only) |
| `vf_sr_inferred_unknown_sum_usd` | per project (Parkway Fields only) | AultF SR dollars |
| `v2_1_changes_summary` | top-level | machine-readable summary of all 6 changes |
| `source_owner_questions_open` | top-level | 8 open questions blocking confidence promotion |

---

## Replaced or moved fields

No fields were removed or renamed. v2.0 fields are all present in v2.1; new
fields are additive.

The `actuals` block per project gained 4 new dollar partitions
(`vf_lot_grain_*`, `vf_range_grain_*`, `vf_commercial_grain_*`,
`vf_sr_inferred_unknown_*`). The total `vf_2018_2025_sum_usd` is the sum of
these partitions, not just the lot-grain figure.

---

## Coverage delta (v0 → v2.1; per `data/reports/join_coverage_simulation_v1.md`)

| metric | v0 baseline | v2.1 | delta |
|---|---:|---:|---:|
| Inventory base lots | 1,285 | 1,285 | 0 |
| Lots with ≥1 GL row | 810 (63.0%) | 864 (67.2%) | +54 (+4.2pp) |
| Lots with ≥1 ClickUp task | 811 (63.1%) | 811 (63.1%) | 0 |
| Full triangle | 476 (37.0%) | 478 (37.2%) | +2 (+0.2pp) |

The binary metric understates the v2.1 wins. The qualitative deltas are larger:

- **$4.0M correctly routed** (AultF B→B1).
- **$6.75M double-count avoided** (Harmony 3-tuple discipline).
- **$6.55M un-inflated** (Scarlet Ridge no longer carries SctLot).
- **$45.75M shell costs surfaced** at project+phase grain (was buried in lot rollups).
- **205 commercial parcel rows isolated** (was creating false-negatives in v0 join coverage).
- **401 SR rows surfaced** as inferred-unknown rather than silently undecoded.

---

## Migration guidance

If a v2.0 consumer wants to migrate to v2.1:

1. **Switch the JSON path** from `output/operating_state_v2_bcpd.json` to `output/operating_state_v2_1_bcpd.json`. Field schema is a strict superset; existing reads continue to work.
2. **Update lot-cost queries to use 3-tuple key** if joining lot data manually. The `vf_actual_cost_3tuple_usd` field already does this for you per lot.
3. **Add 'Scattered Lots' to the project enumeration**. v2.0 had 25 BCPD projects in body; v2.1 has 26.
4. **Treat `vf_unattributed_shell_dollars` as a separate line item** in any per-phase or per-project cost report.
5. **Treat `commercial_parcels_non_lot` as a separate line item** in Harmony cost reports. Do not roll it into residential lot totals.
6. **Use the v2.1 agent context** (`output/agent_context_v2_1_bcpd.md`) for citation patterns; v2.0 agent context's rules still hold but lack the 5 new explicit rules.

If a v2.0 consumer cannot migrate yet:
- v2.0 still loads. Consumers should be aware of the four silent defects: AultF B routing, Harmony double-count, Scarlet Ridge inflation, range pollution. Treat any per-lot cost number from v2.0 with caution.

---

## Reproducibility

```bash
python3 financials/build_vf_lot_decoder_v1.py
python3 financials/build_crosswalk_audit_v1.py
python3 financials/build_coverage_simulation_v1.py
python3 financials/build_operating_state_v2_1_bcpd.py
```

All inputs are versioned under `data/staged/` and `data/reports/`. The build is deterministic.

---

## Hard guardrails honored

- ✅ v2.0 outputs not modified.
- ✅ Org-wide v2 untouched.
- ✅ All decoder-derived mappings carry `confidence='inferred'` and `validated_by_source_owner=False`.
- ✅ Range rows not allocated to lots.
- ✅ HarmCo commercial parcels not modeled as residential.
- ✅ SctLot is its own canonical project, not folded into Scarlet Ridge.
- ✅ Harmony cost rollups use the 3-tuple join key.
