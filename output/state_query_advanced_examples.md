# Operating State — Advanced Query Examples

_A second harness, focused on questions that are hard, annoying, or slow to answer manually across ClickUp, DataRails, GL exports, collateral files, and spreadsheets._

_Generated: 2026-04-30T00:45:30.834489+00:00. Deterministic. No LLM. No API keys._

Each query loads only the named source files, applies a deterministic rule, and returns:
answer, evidence, why-this-isn't-obvious-from-one-source, confidence, missing, sources,
and a concrete recommended next action.

---

## Q1 — Which operating claim would be most risky to present as fact right now?

**Answer.** Three claims must be presented carefully or not at all: (1) LE has $0 cost — this is missing data, not zero spend; (2) named phases — they are heuristic estimates, not plat phases; (3) per-lot cost — never computed and would be invented if shown.

**Evidence**

| claim | reality | would_validate | risk_level |
|---|---|---|---|
| "LE has $0 in costs" | Cost is unknown, not zero. The GL sample contains only Beginning Balance rows for Anderson Geneva LLC; no Activity rows. | Re-export GL with Anderson Geneva LLC Activity rows included. | HIGH — actively misleading if shown as 'cost data'. |
| "There are 4 phases" | These are heuristic clusters of lot_number, not real plat phases. The JSON labels each one phase_confidence='estimated'; consumers might miss the label. | Plat → phase → lot reference table from land/development. | MEDIUM — accurate as 'estimated'; risky if presented unlabeled. |
| "The cost per lot is $X" | Per-lot cost is NOT computed and NOT in operating_state_v1.json. If a consumer divides total_cost / lots_total, that is an arithmetic estimate, not a measurement; the GL has zero lot-level signal. | GL re-export with Class / Customer:Job populated. | HIGH — invented number; do not display anywhere. |


**Why this is not obvious from one source system.** Each claim looks defensible from a single source: the GL really does show $0 for Anderson Geneva; the JSON really does have phase_id values; you can divide cost by lots in your head. The risk only surfaces when you cross-check against confidence labels and source-file scope.

**Confidence:** high

**Missing data / caveat:** Re-export of GL with full Anderson Geneva activity; plat reference table.

**Sources:** `operating_state_v1.json`, `state_quality_report_v1.md`

**Recommended next action.** Treat the three claims above as 'do not present without label'. Always pair LE cost figures with the phrase 'unknown, not zero'.

---

## Q2 — Which project/lot cluster should leadership investigate first, and why?

**Answer.** Investigate **LE LE P1** first. 18 lots share the same stage (Backfill) at 44.4% avg completion — a coordinated stall, not 18 independent ones. We cannot measure how long this has been the case because ClickUp lacks per-task start/done dates, which is itself an investigation finding. Full ranked list below.

**Evidence**

| project | phase_id_estimated | lots_in_phase | dominant_stage | avg_completion_pct | cohort_alignment | duration_data_available | cost_data_available | priority_score |
|---|---|---|---|---|---|---|---|---|
| LE | LE P1 | 18 | Backfill | 0.4444 | 1.0 | False | False | 0.8889 |
| H MF | H MF P2 | 2 | Backfill | 0.2222 | 0.5 | False | True | 0.4333 |
| H A14 | H A14 P1 | 1 | Spec | 0.5556 | 1.0 | False | True | 0.4305 |
| H MF | H MF P1 | 1 | Spec | 0.5556 | 1.0 | False | True | 0.4305 |


**Why this is not obvious from one source system.** ClickUp alone shows 18 separate Backfill tasks — looks like routine in-progress work. The 'stuck cohort' signal only appears when you aggregate stage completion across all lots in a project AND notice the uniformity. ClickUp's UI doesn't surface this; spreadsheets rarely do.

**Confidence:** high (ranking is deterministic); estimated (phase_id used as the cluster key)

**Missing data / caveat:** ClickUp start_date / date_done per task — would distinguish a 1-week pause from a 3-month stall.

**Sources:** `operating_state_v1.json`, `phase_state_real.csv`

**Recommended next action.** Walk the LE P1 cohort with the project manager. Backfill→Spec is one handoff; identify whether the blocker is materials, subcontractor scheduling, inspection, or weather.

---

## Q3 — What is the strongest evidence that the current systems are not yet unified?

**Answer.** Five concrete gaps. Each system has a piece of the truth and silently lacks the field that would let you join it: ClickUp lacks money, GL lacks lots/phases, the LE entity is in the GL chart but not in the GL activity, stage names disagree between exports, and the GL vendor field is placeholder text.

**Evidence**

| gap | evidence | source_files |
|---|---|---|
| ClickUp has lot/stage state but no financial attribution | 22 lots in operating_state_v1.json carry stage + completion + status, but zero of them carry a cost field. ClickUp has no GL hook. | lot_state_real.csv, operating_state_v1.json |
| GL has dollars but no lot/phase fields | DataRails GL export columns Project, ProjectID, ProjectCode, Phase, Lot are 100% null. Only Entity is populated. Verified in financials_normalized.csv. | financials_normalized.csv, FInancials_Sample_Struct.xlsx |
| LE has operating state but no financial Activity rows | Anderson Geneva LLC (the GL entity for LE) appears 24× in the GL sample — all 24 are Beginning Balance rows. Zero Activity rows. LE shows project_total_cost=0 in the JSON. | operating_state_v1.json, financials_normalized.csv |
| Stage vocabulary inconsistent across exports | stage_summary.md flags 'Dig' (18×) and 'Dug' (7×) as the same canonical stage. Without a canonical alias map, any cross-export join silently drops 'Dig' rows. | stage_summary.md, stage_dictionary.csv |
| Vendor field is placeholder text in the GL | 97 of 100 GL rows have Vendor='Vendor or Supplier name' (literal placeholder). Vendor-level cost analysis is currently impossible from this export. | FInancials_Sample_Struct.xlsx (raw) |


**Why this is not obvious from one source system.** Each gap is invisible inside its own system. ClickUp looks complete to ops; the GL looks complete to finance. The unification problem only appears when you sit between them and try to answer 'how much did we spend on lot 31?' — which requires both, and currently can't be answered.

**Confidence:** high

**Missing data / caveat:** —

**Sources:** `operating_state_v1.json`, `financials_normalized.csv`, `stage_summary.md`, `FInancials_Sample_Struct.xlsx`

**Recommended next action.** Use this evidence list as the rationale for the data asks in Q12. These gaps are not opinion; they are direct file observations.

---

## Q4 — What can we automate today versus what still requires source-owner input?

**Answer.** Five capabilities are automated today (lot parsing, phase estimation, GL classification, agent-ready state, deterministic Q&A). One unlocks at full scale (lot inventory). Five are blocked behind specific source-owner asks (durations, real phases, lot-level cost, vendor breakdown, LE financials). The blocked items are not engineering work — they are data-availability work.

**Evidence**

| capability | status | evidence | blocker |
|---|---|---|---|
| Parse ClickUp tasks → LotState + ProjectState | AUTOMATED TODAY | clickup_real.py runs in seconds; 100% project_code parse rate. | — |
| Estimate phase grouping from lot_number | AUTOMATED TODAY (heuristic) | phase_state.py / assign_phases() — gap-based clustering. | — |
| GL → cost_bucket + entity classification + project totals | AUTOMATED TODAY | build_financials.py groups GL rows by entity_role and account prefix. | — |
| Generate agent-ready operating_state_v1.json | AUTOMATED TODAY | package_operating_state.py runs in seconds. | — |
| Deterministic Q&A over the state | AUTOMATED TODAY | state_query_harness.py + state_query_harness_advanced.py. | — |
| Project-level lot inventory at full scale | AUTOMATABLE AFTER FULL EXPORT | Same parser, larger CSV. No code change. | Full ClickUp export from ops owner. |
| Stage duration / cycle-time analytics | BLOCKED | ClickUp start_date + date_done populated 0–1% in current sample. | Operations team must populate per-task start/done dates. |
| Real (not estimated) phase identifiers | BLOCKED | No plat reference table currently in the data corpus. | Land/development team must provide a plat → phase → lot reference table. |
| Phase- or lot-level cost | BLOCKED | GL Class / Customer:Job / Phase / Lot fields are 100% null in the export. | Finance/DataRails owner must re-export with these QuickBooks fields restored. |
| Vendor-level cost breakdown | BLOCKED | 97% of GL Vendor field is the placeholder string 'Vendor or Supplier name'. | Finance/DataRails owner must include real vendor name in export. |
| LE financial visibility | BLOCKED | Anderson Geneva LLC has only Beginning Balance rows in the GL sample. | Finance/DataRails owner must include Anderson Geneva Activity rows. |


**Why this is not obvious from one source system.** From inside any one team this looks like 'we need more analysis'. Cross-system, the bottleneck is consistently 'one missing field in a source export'.

**Confidence:** high

**Missing data / caveat:** —

**Sources:** `clickup_real.py`, `phase_state.py`, `build_financials.py`, `package_operating_state.py`, `state_query_harness*.py`

**Recommended next action.** Send Q12 (asks-by-owner) to the four owners listed there. Each ask is one source-system change, not a new project.

---

## Q5 — If we were rebuilding the collateral report, which fields are available now and which are missing?

**Answer.** Of the standard collateral-report fields: 5 available, 1 estimated, 1 partial, 4 missing. We can produce a credible operating snapshot today; we cannot produce a banking-grade collateral report without the missing four (remaining cost, stage start/done dates, advance rate / borrowing base).

**Evidence**

| field | status | source | confidence | note |
|---|---|---|---|---|
| project / community | AVAILABLE | operating_state_v1.json → project_code | high | Parsed from ClickUp task names. |
| phase | ESTIMATED | operating_state_v1.json → phase_id_estimated | estimated | Heuristic clustering, not real plat phases. |
| lot number | AVAILABLE | operating_state_v1.json → lots[].lot_number | high | Parsed from ClickUp. |
| lot count | AVAILABLE | project_state_real.csv → total_lots | high | Aggregate of lot_state. |
| lot status / stage | AVAILABLE | lot_state_real.csv → current_stage, status | high | Stage canonicalized via STAGE_ALIASES. |
| cost (spent) | PARTIAL | operating_state_v1.json → financials.project_total_cost | partial | Project-level only. LE shows $0 (missing Activity rows, not zero spend). |
| remaining cost | MISSING | — | unavailable | Requires expected-cost source (allocation sheet, budget, or Yardi). Not in current pipeline. |
| start date | MISSING | ClickUp.start_date (0/100 populated) | unavailable | ClickUp start_date is the column; populated rate is effectively zero. |
| done date | MISSING | ClickUp.date_done (1/100 populated) | unavailable | Same — column exists, almost never filled. |
| as-of date | AVAILABLE | operating_state_v1.json → generated_at | high | Snapshot timestamp. |
| advance rate / borrowing base | MISSING | — | unavailable | Lender-specific. The original ontology pipeline has these fields per phase; this pipeline does not. |


**Why this is not obvious from one source system.** Most fields exist somewhere in the company; the issue is that no single system holds all of them in the same row. A manual collateral rebuild stitches them together every quarter — that is exactly the work this pipeline is meant to remove.

**Confidence:** high

**Missing data / caveat:** Expected-cost source (budget/allocation), stage timestamps, advance-rate schedule.

**Sources:** `operating_state_v1.json`, `lot_state_real.csv`, `project_state_real.csv`

**Recommended next action.** Decide whether this pipeline should be extended to subsume collateral reporting, or whether collateral stays in the existing ontology pipeline (pipelines/build_phase_state.py) and operating_state_v1 stays focused on operations.

---

## Q6 — What is the minimum data ask that would create the biggest jump in system capability?

**Answer.** **GL re-export with Class / Customer:Job / Transaction ID / Vendor / Memo** is the highest-leverage single change — one source-owner action unlocks four downstream capabilities (phase cost, lot cost, JE pairing, vendor analysis). The plat reference table is a close second, removes the 'estimated' label, and is half a day of engineering.

**Evidence**

| rank | ask | owner | unlocks_count | unlocks | engineering_work | why_top |
|---|---|---|---|---|---|---|
| 1 | GL re-export with Class / Customer:Job / Transaction ID / Vendor / Memo | Finance / DataRails | 4 | phase-level cost; lot-level cost (if Customer:Job goes that deep); real journal-entry pairing (DR/CR via Transaction ID); vendor + memo cost explanation | Extend account_mapping; add Customer:Job parser. ~1 day. | One source-owner action unlocks the most downstream capabilities. |
| 2 | Plat → phase → lot reference table | Land / Development | 2 | replace heuristic phase clustering with real phase IDs; true phase rollups (lots per real plat phase) | Replace assign_phases() with a left-join. ~30 minutes. | Removes the only 'estimated' label currently on the operating state. |
| 3 | Anderson Geneva LLC Activity rows in GL | Finance / DataRails | 1 | LE financial coverage (currently $0 placeholder) | None — automatic on next pipeline run. | Single biggest visibility gap in the snapshot. |
| 4 | Full ClickUp export (vs 100-row preview) | Operations | 1 | complete lot inventory at scale | None — same parser. | Volume only; no new capability. Important but not a force-multiplier. |
| 5 | ClickUp start_date / date_done populated per task | Operations | 1 | stage-duration analytics; quantified bottleneck duration | None — fields already in the loader; populated values just light up. | Quantifies the bottleneck signal we can already detect. |


**Why this is not obvious from one source system.** Looking at the list of asks in isolation, full ClickUp export sounds biggest because it's the largest file. But measured by 'capabilities unlocked per ask', restoring two QuickBooks fields outranks the volume play.

**Confidence:** high

**Missing data / caveat:** —

**Sources:** `agent_context_v1.md`, `state_quality_report_v1.md`

**Recommended next action.** Lead with the GL re-export ask in the next finance conversation. Frame as 'two QuickBooks fields, four downstream capabilities'.

---

## Q7 — What would change if we received the full ClickUp export?

**Answer.** Volume increases; capabilities do not. Lot count grows from 22 to the full active inventory; bottleneck and confidence signals become statistically stronger. Same parser, same architecture, same outputs. No code change.

**Evidence**

| area | before | after |
|---|---|---|
| Lot count | 22 lots (sample) | Full active inventory (likely 100s) |
| Confidence distribution | 20 high / 0 medium / 2 low | Higher absolute count of high-confidence; FALLBACK_ keys disappear when child tasks exist |
| Stage distribution | Backfill-heavy (because LE dominates) | Full multi-project mix; bottleneck signals can be compared across projects |
| Project count | 3 (LE, H MF, H A14) | All active project_codes the company uses |
| Parser | 100% parse rate on sample | Same parser, no change |
| Pipeline architecture | 5 scripts | Same 5 scripts |
| Code change required | — | None — input file path swap only |


**Why this is not obvious from one source system.** It's tempting to think 'more data = more capability'. In this case the parser is already general; what changes is signal strength, not what the system can answer.

**Confidence:** high

**Missing data / caveat:** —

**Sources:** `clickup_real.py`

**Recommended next action.** Request as a one-time export with no schema change. Pipeline verifies on first run.

---

## Q8 — What would change if we received the plat→phase→lot reference table?

**Answer.** Phase identity becomes ground truth. assign_phases() becomes a join; phase_id_estimated → phase_id; phase_confidence → 'high' across the board. Every downstream artifact regenerates with real phase IDs. No schema change, no architecture change. The 'estimated' label currently on the operating state disappears.

**Evidence**

| field/output | before | after |
|---|---|---|
| phase_id_estimated | Heuristic (gap-based clustering) | Real phase_id sourced from authoritative table |
| phase_confidence | 'estimated' on every phase | 'high' on every phase |
| lot → phase membership | Approximate | Exact lookup |
| phase rollups (lot counts, stage distribution) | Useful but labeled estimated | Trustworthy as plat-level reporting |
| operating_view_v1.csv, lot_state_real.csv, operating_state_v1.json | Carry phase_id_estimated | Regenerate with real phase_id; same shape |
| Code change required | — | Replace assign_phases() with a left-join (~30 minutes) |
| Architecture change | — | None |


**Why this is not obvious from one source system.** From outside the codebase, replacing a heuristic with a join sounds like a redesign. It is one function in one file (~30 lines); the shape of the rest of the pipeline is unchanged because phase identity is the only thing that depends on it.

**Confidence:** high

**Missing data / caveat:** —

**Sources:** `phase_state.py`, `operating_state_v1.json`

**Recommended next action.** Define table schema with land/development: minimum columns = [project_code, phase_id, lot_number]. Anything richer is additive.

---

## Q9 — What would change if we received GL Class / Customer:Job / Transaction ID?

**Answer.** Financial attribution moves from entity/project-level toward phase- or lot-level. Journal entries become reconstructable. Vendor and memo context turns on. Lot-level cost MAY become possible — depends on how deep Customer:Job goes in QuickBooks. This is the single highest-leverage data ask in the entire system.

**Evidence**

| capability | before | after |
|---|---|---|
| Financial attribution granularity | Project / entity level only | Phase or lot level, depending on Customer:Job depth |
| Journal entry reconstruction | Impossible — no JE/Transaction ID column; only 28% of (entity, date) groups balance | Possible — pair DR/CR by Transaction ID |
| Vendor-level cost analysis | Blocked — 97% of Vendor field is placeholder text | Vendor breakdown of project/phase/lot cost |
| Cost explanation (memo) | Blocked — Memo populated on 2% of rows | Per-cost narrative when populated |
| Lot-level cost | Not computed; would be invented if attempted | Possible IF Customer:Job hierarchy goes lot-deep (depends on QB setup) |
| Cross-system reconciliation (ClickUp lot ↔ GL cost) | Manual, requires intuition | Joinable on (project_code, phase_id, lot_number) |


**Why this is not obvious from one source system.** These five fields look like minor metadata in QuickBooks. They are the entire bridge between finance and operations. With them, ClickUp lot 31 can be joined to its actual spend; without them, the systems remain parallel universes.

**Confidence:** high (for the first four); partial (for lot-level cost — depends on QuickBooks Customer:Job structure)

**Missing data / caveat:** Confirmation that QuickBooks Customer:Job actually carries lot information in the Flagship setup.

**Sources:** `financials_normalized.csv`, `FInancials_Sample_Struct.xlsx (raw)`

**Recommended next action.** Ask the finance/DataRails owner to confirm two things: (a) Class is set per project, (b) Customer:Job hierarchy contains lot-level entries. If yes, request re-export with both visible.

---

## Q10 — What is the best 'before vs after' story from the current work?

**Answer.** Before: every quarter, truth was rebuilt by hand from ClickUp + GL + collateral files + spreadsheets. After: a deterministic 5-script pipeline produces a labeled, agent-ready state file in seconds, with explicit confidence on every claim and explicit asks for the missing inputs. The work eliminates the manual rebuild loop without overclaiming completeness.

**Evidence**

| capability | before | after |
|---|---|---|
| Source of truth for active lots | Manual spreadsheet rebuild | lot_state_real.csv — 22 lots, 20 high-confidence, deterministic |
| Project rollup | Manual aggregation across systems | project_state_real.csv — generated in seconds |
| Phase visibility | PDF / plat lookup or guess | phase_state_real.csv — labeled estimated, ready to swap when plat table arrives |
| Financial attribution | Manual pivot on entity | financials_normalized.csv — bucket + entity classified, 100% cost-bucket coverage |
| Cross-system gap visibility | Discovered by accident, lost between meetings | state_query_advanced_examples.md — Q3 lists every gap with source files |
| Agent-readiness | Not possible — no structured state | operating_state_v1.json + harness — nested project→phase→lot with confidence labels |
| Reproducibility | Each rebuild is a custom job | Five scripts, deterministic, runs in seconds |


**Why this is not obvious from one source system.** The 'after' state still has gaps (phase IDs estimated, LE financials missing). What changed is not that we have all the data — it's that we no longer rebuild what we have, and we know exactly what's missing.

**Confidence:** high

**Missing data / caveat:** —

**Sources:** `all 5 pipeline scripts; all output/ files`

**Recommended next action.** Use this as the framing slide for any leadership conversation.

---

## Q11 — What should we show in a meeting that proves progress without overclaiming?

**Answer.** Show three things in this order: (1) operating_state_v1.json — the deliverable; (2) state_query_advanced_examples.md — proof it answers hard questions with provenance; (3) the asks-by-owner list (Q12) — proof we know what's next. Do not lead with the HTML dashboard; it is the weakest framing because it looks like ordinary BI.

**Evidence**


_show_:
| rank | artifact | why | show_as |
|---|---|---|---|
| 1 | operating_state_v1.json | Proves the deliverable shape: structured, nested, labeled state ready for any agent. | Open the file in a JSON viewer; point at financial_notes for LE and phase_confidence='estimated'. |
| 2 | state_query_advanced_examples.md (this file) | Proves the state is queryable for hard questions, not just lookups. Each answer carries provenance. | Walk through Q1 (riskiest claim), Q3 (systems not unified), and Q6 (leverage ranking). |
| 3 | Asks-by-owner list (Q12 below) | Proves we know exactly what we don't know and who owns each gap. | Send before the meeting; reference during. Frame as concrete next actions, not wish list. |

_do_not_show_as_main_:
| artifact | reason |
|---|---|
| operating_dashboard_v1.html | Looks like a generic SaaS dashboard. Undersells the structural work and invites comparison to BI tools we are not trying to be. |
| Raw CSVs (operating_view_v1.csv, lot_state_real.csv) | Tabular data without confidence/provenance encourages the wrong questions. |
| operating_state_console_v1.html | Better than the dashboard, but it's a presentation layer. The substance is the JSON + harness; show those first, the console is a 'see, you can also render it' moment. |


**Why this is not obvious from one source system.** The most polished artifact (the dashboard) is the most misleading framing. The least polished (a JSON file) carries the actual proof.

**Confidence:** high

**Missing data / caveat:** —

**Sources:** `all output/ artifacts`

**Recommended next action.** Build the meeting flow around the JSON + harness. Use the console / dashboard only if asked 'can you visualize this?'

---

## Q12 — What is the clearest 'ask by owner' list?

**Answer.** Four owners, six asks. Operations owns ClickUp completeness and timestamps. Finance owns GL re-export and the LE Activity gap. Land/development owns the plat reference table. Accounting/Yardi owns the question of whether lot-level cost lives in QB or Yardi. Each ask names exact fields, the reason it matters, and the capability it unlocks.

**Evidence**

| owner | asks |
|---|---|
| Operations / ClickUp owner | {'need': 'Full ClickUp task export (current is 100-row preview)', 'why': 'Pipeline currently sees 22 lots; full export likely shows the entire active inventory.', 'unlocks': 'Complete lot inventory at scale; statistically stronger bottleneck signals.'}; {'need': 'Populate start_date and date_done per construction task', 'why': 'Currently 0–1 of 100 rows have these. We can see what stage a lot is at; we cannot see how long it has been there.', 'unlocks': 'Stage-duration analytics; quantified bottleneck duration; cycle-time reporting.'} |
| Finance / DataRails owner | {'need': 'Re-export GL with Class, Customer:Job, Transaction ID / JE ID, Vendor, Memo populated', 'why': 'Current export has Project, Phase, Lot columns 100% null and Vendor 97% placeholder. The bridge between cost and operations is missing.', 'unlocks': 'Phase-level cost (immediate); lot-level cost (depends on QB setup); journal-entry reconstruction; vendor + memo analysis.'}; {'need': 'Anderson Geneva LLC Activity rows', 'why': 'Anderson Geneva is the GL entity for project LE. Current export has only Beginning Balance rows for this entity. LE shows $0 cost — which is missing data, not zero spend.', 'unlocks': 'LE financial coverage.'} |
| Land / Development owner | {'need': 'Plat → phase → lot reference table (minimum columns: project_code, phase_id, lot_number)', 'why': "Phase identifiers in this pipeline are heuristic (gap-based clustering). They are clearly labeled 'estimated' but cannot be presented as plat phases.", 'unlocks': "Real phase IDs replace heuristic IDs; 30-minute code change; every downstream artifact regenerates with phase_confidence='high'."} |
| Accounting / Yardi owner (if Yardi holds construction cost detail) | {'need': 'Confirm whether QuickBooks Customer:Job carries lot-level entries, or whether lot detail lives in Yardi', 'why': 'If lot detail is in Yardi rather than QB, we should pull from Yardi instead of waiting for a QB re-export.', 'unlocks': 'Routes the lot-cost ask to the system that actually has the data.'}; {'need': 'If Yardi: provide Yardi extract with project / phase / lot / cost columns', 'why': 'Same outcome as the QB re-export, sourced from the system of record.', 'unlocks': 'Lot-level cost without waiting for QB schema changes.'} |


**Why this is not obvious from one source system.** Each owner sees their own system as 'fine'. The asks only make sense when you sit between systems and try to answer a cross-system question. Sending one combined list — rather than four separate conversations — is itself a contribution.

**Confidence:** high

**Missing data / caveat:** —

**Sources:** `state_query_advanced_examples.md (this file)`, `operating_state_v1_validation_memo.md`

**Recommended next action.** Send this list to the four owners with a 1-line preface: 'one source-system change each, no engineering required from your side.'

---
