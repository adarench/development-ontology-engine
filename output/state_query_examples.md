# Operating State Console — Query Examples

_Deterministic, no-LLM proof that Operating State v1 is queryable as a state layer._
_Generated: 2026-04-30T00:27:24.674814+00:00_

Each query loads only the named source files, applies a deterministic rule, and
returns an answer with evidence, confidence, sources, and a missing-data caveat.
No model inference is involved.

---

## Q1 — What projects exist?

**Answer.** Three projects in the current snapshot: H A14, H MF, LE.

**Evidence**

| project_code | total_lots | avg_completion_pct | stage_distribution |
|---|---|---|---|
| H A14 | 1 | 0.5556 | Spec:1 |
| H MF | 3 | 0.3333 | (none):1|Backfill:1|Spec:1 |
| LE | 18 | 0.4444 | Backfill:18 |

**Confidence:** high  
_All three project_code values are parsed from real ClickUp task names with 100% parse rate._

**Sources:** `project_state_real.csv`, `operating_state_v1.json`

**Missing / Caveat:** None for this question.

---

## Q2 — Which lots are currently stuck?

**Answer.** All 18 active LE lots (LE 17–34) are sitting at Backfill — the entire cohort is paused at the Backfill→Spec handoff.

**Evidence**

| lot_number | stage | completion_pct | status |
|---|---|---|---|
| 17 | Backfill | 0.4444 | in_progress |
| 18 | Backfill | 0.4444 | in_progress |
| 19 | Backfill | 0.4444 | in_progress |
| 20 | Backfill | 0.4444 | in_progress |
| 21 | Backfill | 0.4444 | in_progress |
| 22 | Backfill | 0.4444 | in_progress |
| 23 | Backfill | 0.4444 | in_progress |
| 24 | Backfill | 0.4444 | in_progress |
| 25 | Backfill | 0.4444 | in_progress |
| 26 | Backfill | 0.4444 | in_progress |
| 27 | Backfill | 0.4444 | in_progress |
| 28 | Backfill | 0.4444 | in_progress |
| 29 | Backfill | 0.4444 | in_progress |
| 30 | Backfill | 0.4444 | in_progress |
| 31 | Backfill | 0.4444 | in_progress |
| 32 | Backfill | 0.4444 | in_progress |
| 33 | Backfill | 0.4444 | in_progress |
| 34 | Backfill | 0.4444 | in_progress |

**Confidence:** high (lot identity + current stage); estimated (phase grouping)  
_Lot identity and current_stage parsed from real ClickUp data. Phase 'LE P1' is heuristic._

**Sources:** `operating_view_v1.csv`, `lot_state_real.csv`

**Missing / Caveat:** ClickUp start_date / date_done populated per task — would let us measure how long the cohort has been at Backfill and confirm bottleneck duration.

---

## Q3 — Which project appears to have the biggest operational bottleneck?

**Answer.** LE. 18 lots in estimated phase LE P1 are stuck at Backfill (44.4% avg complete). The size of the cohort and uniform completion percentage strongly suggest a single handoff blocker.

**Evidence**

| project_code | phase_id_estimated | lots_in_phase | dominant_stage | avg_completion_pct |
|---|---|---|---|---|
| LE | LE P1 | 18 | Backfill | 0.4444 |

**Confidence:** high (cohort + stage); estimated (phase identifier)  
_Detection is deterministic. The fact that 18 lots show identical completion is itself strong evidence of a coordinated stall._

**Sources:** `operating_state_v1.json`

**Missing / Caveat:** Stage-duration data (start_date / date_done) would tell us how long this has been the case.

---

## Q4 — Which projects have financial coverage?

**Answer.** 2 of 3 projects have GL Activity rows: H A14, H MF.

**Evidence**

| project_code | gl_entity | total_cost | confidence |
|---|---|---|---|
| H A14 | Flagborough LLC | 66814.0 | high |
| H MF | Flagborough LLC | 66814.0 | high |

**Confidence:** high  
_Cost is the absolute-value sum of GL Activity rows for the mapped entity._

**Sources:** `operating_state_v1.json`, `financials_normalized.csv`

**Missing / Caveat:** GL re-export with Class / Customer:Job would let us split this project-level cost into phase- or lot-level cost.

---

## Q5 — Which projects are missing financials?

**Answer.** LE. Cost is unknown, NOT zero.

**Evidence**

| project_code | gl_entity | reason |
|---|---|---|
| LE | Anderson Geneva LLC | GL entity 'Anderson Geneva LLC' mapped, but the GL sample contains no Activity rows for it (Beginning Balance only or absent). Cost is unknown, NOT zero. |

**Confidence:** high  
_We are highly confident the financials are missing from the sample, not that the project has no spend._

**Sources:** `operating_state_v1.json`, `financials_normalized.csv`

**Missing / Caveat:** Anderson Geneva LLC Activity rows in the GL export.

---

## Q6 — Which lots are low confidence?

**Answer.** 2 low-confidence lot(s): H MF 31, H MF 77. These are bare parent rows in ClickUp with no associated child tasks.

**Evidence**

| project_code | phase_id_estimated | lot_number | stage | status |
|---|---|---|---|---|
| H MF | H MF P1 | 31 | Spec | in_progress |
| H MF | H MF P2 | 77 | None | not_started |

**Confidence:** high (classification is deterministic)  
_Confidence rule: real ClickUp parent_id + ≥2 stages = high; real id + ≥1 stage = medium; fallback key = low._

**Sources:** `operating_state_v1.json`, `lot_state_real.csv`

**Missing / Caveat:** Child task rows for these lots — once present, lots auto-promote.

---

## Q7 — What can we trust in this state?

**Answer.** Lot identity, current stage, completion %, stage distribution, and stage-progression validity. All five are derived from observed data with deterministic rules; none rely on inference.

**Evidence**

| claim | tier | n | source |
|---|---|---|---|
| lot identity (project_code + lot_number) | high | 22 | parsed from real ClickUp task names; 100% parse rate |
| current stage of each lot | high | 22 | observed; 81% of task rows mapped to canonical stage |
| completion % | high | 22 | computed deterministically from stage rank |
| stage distribution per project | high | 3 | aggregated from per-lot data |
| valid stage progression flag | high | 19 | lots whose stages_present form a contiguous sequence from rank 1 |

**Confidence:** high  
_All claims here are derived from observed data with deterministic rules._

**Sources:** `operating_state_v1.json`, `lot_state_real.csv`, `project_state_real.csv`

**Missing / Caveat:** —

---

## Q8 — What is estimated?

**Answer.** Phase identifiers are estimated (heuristic clustering). Per-lot cost and stage durations are NOT computed — they are deliberately omitted because the underlying signal does not exist in the inputs.

**Evidence**

| field | tier | method | scope |
|---|---|---|---|
| phase_id_estimated | estimated | gap-based clustering on lot_number (gap ≥ 10 starts a new phase) | 4 phases across 3 projects |
| phase_confidence | estimated | fixed string 'estimated' for every phase | all phases |
| per-lot cost | unavailable (NOT computed) | GL has no lot-level signal; not derived | all lots |
| stage durations | unavailable (NOT computed) | ClickUp start_date / date_done populated 0–1% in sample | all lots |

**Confidence:** high  
_Each estimated field is labeled in operating_state_v1.json so consumers cannot accidentally treat it as ground truth._

**Sources:** `operating_state_v1.json`, `phase_state_real.csv`

**Missing / Caveat:** See Q9.

---

## Q9 — What data do we need next to upgrade v1 to v2?

**Answer.** Five inputs: (1) full ClickUp export, (2) plat→phase→lot reference, (3) GL with Class/Customer:Job/TxID/Vendor/Memo, (4) Anderson Geneva Activity rows, (5) ClickUp stage timestamps. With these, v1 → v2 needs no architecture changes — just better input.

**Evidence**

| ask | unlocks |
|---|---|
| Full ClickUp export (not 100-row preview) | complete lot inventory; same parser handles full volume |
| Plat → phase → lot reference table | replaces phase_id_estimated with named plat phases (A4, B2, etc.) |
| GL re-export with Class, Customer:Job, Transaction ID, Vendor, Memo | moves cost visibility from project level to phase- or lot-level |
| Anderson Geneva LLC Activity rows in GL | LE financials become measurable instead of $0 placeholder |
| ClickUp start_date and date_done per task | stage durations, true bottleneck quantification |

**Confidence:** high  
_Scope is well-defined; each ask maps to specific code paths already in place._

**Sources:** `operating_state_v1_validation_memo.md`, `state_quality_report_v1.md`

**Missing / Caveat:** —

---

## Q10 — What would change if we received a plat → phase → lot table?

**Answer.** Phase identity becomes ground truth. The heuristic in phase_state.py is replaced by a join; phase_id_estimated → real phase_id; phase_confidence → 'high' across the board. Everything else (lots, stages, completion, status, financial coverage) is unaffected — those don't depend on phase identity.

**Evidence**

| impact | before | after |
|---|---|---|
| phase_id_estimated → real phase_id | 4 heuristic phases | named plat phases sourced from authoritative table |
| phase_confidence | 'estimated' on every phase | 'high' on every phase |
| lot → phase membership | approximate (gap-based) | exact (lookup join on lot_number) |
| code change required | — | replace assign_phases() in phase_state.py with a left-join on the new table |
| downstream artifacts | — | operating_view_v1.csv, lot_state_real.csv, operating_state_v1.json all regenerate with real phase IDs; no schema changes |
| what does NOT change | — | lot identity, current stage, completion %, status, financial coverage (those don't depend on phase identity) |

**Confidence:** high  
_Hypothetical but tightly bounded: only one function changes._

**Sources:** `phase_state.py`, `operating_state_v1.json`

**Missing / Caveat:** —

---
