# BCPD Operating State v2.1 — State Quality Report

_Generated: 2026-05-01_
_Schema: `operating_state_v2_1_bcpd`_
_Supersedes: v2.0 (additive — v2.0 not modified)_

Companion to `output/operating_state_v2_1_bcpd.json`. Documents what changed from
v2.0, where v2.1 is more accurate, what coverage looks like, and the
remaining source-owner questions.

---

## v2.0 → v2.1 high-level deltas

| dimension | v2.0 | v2.1 | delta |
|---|---:|---:|---:|
| Lots in canonical body | 5,366 | 5,366 | 0 |
| High-confidence lots (BCP-built) | 2,797 | 2,797 | 0 |
| Inventory base (project_confidence=high) | 1,285 | 1,285 | 0 |
| **Lots with ≥1 GL row** | 810 (63.0%) | **864 (67.2%)** | **+54 (+4.2pp)** |
| Lots with ≥1 ClickUp task | 811 (63.1%) | 811 (63.1%) | 0 |
| **Full triangle** | 476 (37.0%) | **478 (37.2%)** | +2 |
| VF rows newly attached at 3-tuple lot grain | n/a (2-tuple) | ~63,000 | first-time 3-tuple discipline |
| AultF B-suffix dollars correctly routed (B1 not B2) | 0 | $4.0M | corrected |
| Harmony double-count risk on flat 2-tuple | $6.75M | $0 | eliminated by 3-tuple rule |
| Scarlet Ridge v0 silent inflation | $6.55M | $0 | SctLot moved to 'Scattered Lots' |
| Range/shell dollars surfaced explicitly at project+phase | not surfaced | $45.75M | new field per phase |
| Commercial parcel rows kept out of residential LotState | not segmented | 205 rows | new exception bucket |
| AultF SR-suffix rows isolated as inferred-unknown | unmapped | 401 rows / $1.2M | now explicit |
| New canonical project: 'Scattered Lots' | n/a | 1,130 rows / $6.55M | added |

**Headline**: binary coverage moves modestly (+4.2pp GL, +0.2pp triangle); the
larger v2.1 wins are **correctness**: $4M re-routed, $6.75M double-count
prevented, $6.55M un-inflated, $45.75M shell costs surfaced explicitly.

---

## Per-project coverage (v0 → v2.1)

Inventory base = 1,285 distinct (canonical_project, lot_num) pairs at
project_confidence=high.

| project | inventory lots | v0 GL% | v2.1 GL% | delta GL | v0 tri% | v2.1 tri% | comment |
|---|---:|---:|---:|---:|---:|---:|---|
| Harmony | 391 | 53.7% | 53.7% | +0 | 35.0% | 35.0% | binary unchanged; 3-tuple discipline now prevents $6.75M double-count |
| Parkway Fields | 317 | 61.5% | 78.0% | +52 | 23.0% | 23.7% | AultF B→B1 correction reaches 11 new B1 lots; 3-tuple now correct |
| Arrowhead Springs | 206 | 65.0% | 65.0% | +0 | 9.7% | 9.7% | unchanged |
| Salem Fields | 139 | 100.0% | 100.0% | +0 | 87.8% | 87.8% | unchanged (already 100%) |
| Lomond Heights | 114 | 43.9% | 43.9% | +0 | 43.0% | 43.0% | unchanged; LomHT1 low rate confirmed as range-row noise |
| Willowcreek | 62 | 100.0% | 100.0% | +0 | 100.0% | 100.0% | unchanged |
| Lewis Estates | 34 | 0.0% | 0.0% | +0 | 0.0% | 0.0% | structural gap (no GL) |
| Scarlet Ridge | 22 | 90.9% | 90.9% | +0 | 59.1% | 59.1% | binary unchanged; SctLot inflation removed |
| **Scattered Lots (new)** | n/a | n/a | project-grain only | n/a | n/a | n/a | 1,130 rows / $6.55M moved off Scarlet Ridge |

---

## VF rows by treatment (v2.1)

| treatment | rows | $ | notes |
|---|---:|---:|---|
| **Lot grain** (3-tuple decoded; in scope of v1 decoder) | ~63,000 | (varies by project) | confidence: inferred (decoder-derived) |
| **Project-grain passthrough** (Salem, Willowcreek, Meadow Creek) | ~10,000 | (already 100% in v0) | confidence: high (corroborated; no decoder change) |
| **Range / shell allocation** (8 VF codes) | 4,020 | $45,752,047 | confidence: inferred; kept at project+phase grain via `vf_unattributed_shell_dollars` |
| **Commercial parcels** (HarmCo X-X) | 205 | ~$2.6M | confidence: inferred; non-lot inventory exception |
| **AultF SR-suffix** (inferred-unknown) | 401 | $1,183,859 | excluded from lot-level cost until source-owner explains |
| **SctLot** → 'Scattered Lots' project-grain | 1,130 | $6,553,893 | confidence: inferred-unknown (canonical name pending) |
| **DR 38-col (post-dedup, 2016-17)** | 51,694 | (~$331M debit ~$331M credit; balanced) | confidence: high after dedup |

---

## Per-field quality (v2.1)

| field | fill rate | confidence | safe to use? | v2.1 change |
|---|---|---|---|---|
| `canonical_entity` | 100% | high | yes | unchanged |
| `canonical_project` | 100% | high | yes | new project: 'Scattered Lots' |
| `canonical_phase` | ~100% | high if 2+ ops sources; medium otherwise | yes | now used as primary join key for VF |
| `canonical_lot_id` | 100% | derived | yes | unchanged |
| `canonical_lot_number` | 100% | high | yes | unchanged |
| `lot_status` | 100% (inventory rows) | high | yes | unchanged |
| `current_stage` | ~98% (BCP-built) | high | yes | unchanged |
| `vf_actual_cost_3tuple_usd` | per-lot, decoder-scope only | **inferred** | yes with caveat | NEW field; decoder-derived |
| `vf_actual_cost_rows` | per-lot | inferred | yes | NEW field |
| `vf_actual_cost_join_key` | constant string | n/a | yes | NEW; documents 3-tuple key |
| `vf_actual_cost_confidence` | constant 'inferred' | n/a | yes | NEW; reminds consumers of confidence label |
| `vf_unattributed_shell_dollars` | per-phase | inferred | yes (project+phase grain only) | NEW field; surfaces $45.75M not-yet-allocated |
| `vf_unattributed_shell_rows` | per-phase | inferred | yes | NEW field |
| `commercial_parcels_non_lot` | per-project (Harmony only in v2.1) | inferred | yes (non-lot exception) | NEW field |
| `posting_date`, `account_code`, `account_name` | 100% (GL) | high | yes within source_schema | unchanged |
| `cost_category` | rule-derived | high for explicit; medium derived | yes | unchanged from v2.0 starter |
| `actual_cost` (rollup) | varies by project | high (VF) / high after dedup (DR) / inferred (decoder-derived per-lot) | yes within era | v2.1 adds 3-tuple discipline for VF |
| `budget_cost` | LH + PF only | high for those | yes for LH+PF | unchanged |
| `collateral_value` | 9 of 16 active projects | high | yes | unchanged |
| `inventory_status` | 100% (inventory rows) | high | yes | unchanged |
| `clickup_status` | within lot-tagged subset | high | yes within subset | unchanged |
| `source_confidence` | 100% | derived (worst-link) | yes | unchanged |

---

## Decoder-rule confidence summary (per `vf_lot_code_decoder_v1.csv`)

All rules ship `confidence='inferred'`, `validated_by_source_owner=False`.

| rule | rule_quality | recommendation |
|---|---|---|
| `harmony_lot_range_to_phase` (Harm3) | high-evidence | safe for v2.1 simulation as inferred mapping (3-tuple required) |
| `harmony_mf2_residential` (HarmCo subset) | high-evidence | safe for v2.1 simulation as inferred mapping |
| `harmony_commercial_pad_nonlot` (HarmCo X-X) | non-lot-only | non-lot inventory only; do not feed lot-level cost |
| `harmony_townhome_mf1_only` (HarmTo) | high-evidence | safe for v2.1; range rows excluded |
| `lomondheights_sfr_phase_2a` (LomHS1) | high-evidence | safe for v2.1 |
| `lomondheights_th_phase_2a` (LomHT1) | high-evidence | safe for v2.1; range rows excluded |
| `parkway_sfr_phase2_range_route` (PWFS2) | high-evidence | safe for v2.1 |
| `parkway_th_phase1_c1c2_route` (PWFT1) | high-evidence | safe for v2.1; range rows excluded |
| `aultf_suffix_a_b_phase_route_v1` (AultF) — **CORRECTED v2.1** | high-evidence | safe for v2.1; B-suffix → B1 (was B2 in v0) |
| `arrowhead_sfr_123_456_route` (ArroS1) | high-evidence | safe for v2.1 |
| `arrowhead_th_123_456_route` (ArroT1) | high-evidence | safe for v2.1 |
| `scarletridge_lot_range_phase` (ScaRdg) | high-evidence | safe for v2.1 |
| `sctlot_project_grain_only_v1` (SctLot) | non-lot-only | project-grain only; canonical_project='Scattered Lots' |
| `range_entry_passthrough` (8 VF codes) | non-lot-only | project+phase grain only |

---

## What's safe to put in agent answers (v2.1)

- BCPD lot inventory, status, lifecycle dates (high; 2,797 BCPD-built lots).
- BCPD VF cost rollups by project for 2018-2025, with the v1 decoder applied — at the **3-tuple lot grain** for projects in decoder scope, at the project grain otherwise. Cite confidence as `inferred (decoder-derived)`.
- BCPD DR cost rollups for 2016-02 → 2017-02 after dedup. Project-grain only (DR has no phase).
- BCPD CollateralSnapshot for the 9 pledged projects (2025-12-31 + PriorCR 2025-06-30).
- BCPD allocation/budget for Lomond Heights and Parkway Fields phases.
- ClickUp task progress for the lot-tagged subset (1,091 distinct lots).
- Per-phase **unattributed shell-allocation dollars** as a separate line item — not rolled into per-lot cost.
- Commercial parcel dollars as a separate line item under `commercial_parcels_non_lot` per project.
- Scattered Lots dollars at project grain only.

## What's not safe (unchanged from v2.0)

- BCPD vendor analysis outside 2025 (QB-only / 2025-only).
- Cost basis for the 7 active no-GL projects + Lewis Estates.
- Cross-era project rollups without the project-code crosswalk.
- Org-wide rollups including Hillcrest or Flagship Belmont.
- 2017-03 → 2018-06 cost (gap).
- Phase-level cost from GL alone (phase column 0% filled in source).
- Per-lot cost matching for Harm3 lots WITHOUT the 3-tuple discipline (would double-count).
- Per-lot range-row dollars (kept at project+phase grain pending allocation-method sign-off).
- HarmCo X-X commercial parcel cost as residential lot cost.
- SctLot dollars under Scarlet Ridge (corrected in v2.1; agents must reference 'Scattered Lots').

---

## Source-owner questions still open (gates on confidence promotion)

These are unchanged from W1.5/W2/W3. v2.1 ships `inferred` because none has been resolved.

1. **Harm3 lot-range routing** — confirm phase is recoverable only via lot range, no source-system attribute we missed. (Terminal B Q1)
2. **AultF SR-suffix meaning** — what does `0139SR` and `0140SR` mean? 401 rows / 2 lots. (Terminal C Q1)
3. **AultF B-suffix range** — confirm B1's max lot = 211 (currently empirical from VF data). (Terminal B Q2)
4. **MF1 vs B1 overlap 101-116** — sample 5-10 Harm3 rows in this range to confirm SFR/B1 (no MF1 leakage). (Terminal B Q3)
5. **SctLot canonical name** — currently 'Scattered Lots'; confirm program identity. (Terminal B Q4)
6. **Range-entry allocation method** — equal split / sales-weighted / unit-fixed for v2.2 per-lot expansion. (Terminal B Q5)
7. **HarmCo X-X commercial parcels** — which allocation source covers Harmony commercial? May need new ontology entity. (Terminal C Q2)
8. **DR 38-col phase recovery** — is there a source-system attribute we missed for pre-2018 phase? (Terminal B Q1)

Until each is resolved, the corresponding rule stays `inferred` in v2.1.

---

## Hard guardrails honored

- ✅ All decoder-derived mappings ship `confidence='inferred'` and `validated_by_source_owner=False`.
- ✅ v2.0 outputs (`output/operating_state_v2_bcpd.json` and the four companion files) are not modified.
- ✅ Org-wide v2 untouched.
- ✅ Range rows not allocated to lots; kept at project+phase grain.
- ✅ HarmCo commercial parcels NOT modeled as residential lots; tracked under `commercial_parcels_non_lot`.
- ✅ SctLot rows do NOT inflate Scarlet Ridge in v2.1; live under 'Scattered Lots' project-grain entry.
- ✅ Harmony 3-tuple join discipline enforced — every `vf_actual_cost_3tuple_usd` was computed at (project, phase, lot).
- ✅ AultF B→B1 correction applied; v2.0 had this wrong.
