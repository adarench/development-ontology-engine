# Operating State v1 — What We Proved and What We Need Next

_For: Flagship leadership / data meeting_
_Date: 2026-04-29_

---

## Executive summary

- We reconstructed lot-level operating state from a real ClickUp export: **22 lots across 3 active projects (LE, H MF, H A14), 90% high-confidence parsing**, all from real task data.
- We joined GL coverage where Activity rows exist (Flagborough LLC). **LE shows $0 because Anderson Geneva LLC has no Activity rows in the GL sample** — flagged explicitly as missing, not zero.
- We built a deterministic query harness that answers cross-system business questions with evidence, confidence, and explicit missing-data caveats. **No model inference is involved.**
- We have identified exactly which inputs unlock v2 — and routed each ask to the specific source-system owner.

---

## The key shift

**This is not a dashboard. It is a repeatable state reconstruction layer.**

A small set of scripts turns messy exports into a labeled, queryable view of active work, every time. The output isn't a chart — it's a structured state file plus a Q&A layer that any agent or analyst can interrogate. The work that used to be rebuilt by hand each quarter is now produced in seconds, with explicit confidence on every claim.

---

## Three proof points

### Proof 1 — Which operating claim would be most risky to present as fact right now?

**Business question.** Where could we accidentally mislead a leader by quoting numbers from this work?

**Answer.** Three claims must be presented carefully or not at all:

1. _"LE has $0 in costs"_ — actually missing data, not zero spend.
2. _"There are 4 phases in the portfolio"_ — these are heuristic groupings of lot numbers, not real plat phases.
3. _"Cost per lot is $X"_ — never computed; would be invented if displayed.

**Evidence.** Each is labeled inside `operating_state_v1.json`: LE's `financial_notes` field reads _"GL entity 'Anderson Geneva LLC' mapped, but the GL sample contains no Activity rows for it. Cost is unknown, NOT zero."_ Every phase carries `phase_confidence: "estimated"`. Per-lot cost simply does not exist as a field — by design.

**Why this is not obvious from one source.** Each claim looks defensible inside its own system: the GL really does show $0 for Anderson Geneva; the JSON really does carry `phase_id` values; you can divide a project total by lot count in your head. The risk only surfaces when you cross-check against confidence labels and source-file scope.

**Recommended next action.** Treat these three claims as "do not present without label." Always pair LE cost figures with the phrase _"unknown, not zero."_

---

### Proof 2 — What is the strongest evidence the systems are not yet unified?

**Business question.** Why does this work matter? Why can't the existing systems just be queried directly?

**Answer.** Five concrete gaps. Each system has a piece of the truth and silently lacks the field that would let you join it:

- ClickUp has lot and stage state but **no financial attribution** — no project_id field that maps to the GL chart of accounts.
- The GL has dollars but **Project, Phase, Lot columns are 100% null** in the current export.
- LE appears in the GL chart but **not in GL activity** — only Beginning Balance rows exist for Anderson Geneva LLC.
- Stage names **disagree across exports** — "Dig" appears 18×, "Dug" appears 7×; without an alias map, any cross-export join silently drops rows.
- The GL Vendor field is the literal placeholder string "Vendor or Supplier name" in **97% of rows**, blocking any vendor-level cost analysis.

**Evidence.** All five are direct file observations from `operating_state_v1.json`, `financials_normalized.csv`, and `stage_summary.md`. Not opinion, not inference.

**Why this is not obvious from one source.** Each gap is invisible inside its own system. ClickUp looks complete to operations; the GL looks complete to finance. The unification problem only appears when you sit between them and try to answer _"how much did we spend on lot 31?"_ — which requires both, and currently cannot be answered.

**Recommended next action.** Use this evidence list as the rationale for the data asks below. The gaps are observable, not preference.

---

### Proof 3 — What is the minimum data ask that creates the biggest jump in capability?

**Business question.** Of everything we could ask source owners for, where is the leverage?

**Answer.** **GL re-export with `Class`, `Customer:Job`, `Transaction ID`, `Vendor`, and `Memo` populated.** One source-owner action unlocks four downstream capabilities: phase-level cost, lot-level cost (depending on QuickBooks Customer:Job depth), real journal-entry pairing, and vendor + memo cost explanation.

**Evidence.** Today: 100% of GL rows have Project/Phase/Lot null; 97% of Vendor rows are placeholder text; only 28% of journal entries balance because there is no Transaction ID column to pair debits and credits. The plat → phase → lot reference table ranks second — roughly half a day of engineering, removes the only "estimated" label currently on the system.

**Why this is not obvious from one source.** Looking at the asks individually, "full ClickUp export" sounds biggest because the file is largest. Measured by **capabilities unlocked per ask**, restoring two QuickBooks fields outranks every other input.

**Recommended next action.** Lead with the GL re-export ask in the next finance conversation. Frame as _"two QuickBooks fields, four downstream capabilities."_

---

## What we can trust today

| Claim | Source / why it's reliable |
|---|---|
| Lot identity (project_code + lot_number) | Parsed directly from real ClickUp task names; 100% parse rate |
| Current stage of each lot | Observed in task data; canonicalized via the alias map |
| Completion % per lot and per project | Computed deterministically from stage rank |
| Project rollup (lot count, avg completion, stage distribution) | Aggregate of the per-lot data above |
| GL coverage where Activity rows exist | Direct sum of GL Activity rows for the mapped entity (Flagborough LLC = $66,814) |

## What we cannot claim yet

| Limit | Why |
|---|---|
| Real phase IDs | Currently heuristic (gap-based clustering on lot_number); labeled "estimated" in every output |
| Lot-level costs | GL has zero lot-level signal; not computed and deliberately not displayed |
| Stage durations | ClickUp `start_date` / `date_done` populated on 0–1% of task rows in the sample |
| LE financials | Anderson Geneva LLC has only Beginning Balance rows in the GL sample — missing data, not zero spend |

---

## Owner-specific asks

### Operations / ClickUp owner

- **Full ClickUp task export** (current is a 100-row preview).
  _Why:_ complete the active lot inventory; the parser already handles full volume.
  _Unlocks:_ statistically stronger bottleneck signals; full-scale lot inventory, no code change.
- **Populate `start_date` and `date_done` per construction task.**
  _Why:_ today these are filled on 0–1 of 100 rows. We can see what stage a lot is at; we cannot see how long it has been there.
  _Unlocks:_ stage durations, cycle-time analytics, quantified bottleneck duration.

### Finance / DataRails owner

- **Re-export GL with `Class`, `Customer:Job`, `Transaction ID` / `JE ID`, `Vendor`, `Memo` populated.**
  _Why:_ today's export has Project/Phase/Lot 100% null and Vendor 97% placeholder. This is the missing bridge between cost and operations.
  _Unlocks:_ phase-level cost; potentially lot-level cost; journal-entry reconstruction; vendor and memo analysis.
- **Include Anderson Geneva LLC Activity rows.**
  _Why:_ the entity is in the GL chart but only Beginning Balance rows reach our export. LE reads as $0 cost.
  _Unlocks:_ LE financial coverage.

### Land / Development owner

- **Plat → phase → lot reference table** (minimum columns: `project_code`, `phase_id`, `lot_number`).
  _Why:_ phase identifiers are heuristic today; clearly labeled "estimated" but cannot be presented as plat phases.
  _Unlocks:_ real phase IDs replace the heuristic (~30 minutes of code change); phase confidence becomes "high" across the board; phase rollups become trustworthy as plat-level reporting.

### Accounting / Yardi owner (if Yardi is system of record for construction cost)

- **Confirm whether QuickBooks Customer:Job carries lot-level entries, or whether lot detail lives in Yardi.**
  _Why:_ routes the lot-cost ask to the system that actually has the data.
  _Unlocks:_ certainty about which system to pull from before we ask for a re-export.
- **If Yardi: provide a Yardi extract with project / phase / lot / cost columns.**
  _Why:_ same outcome as the QB re-export, sourced from the system of record.
  _Unlocks:_ lot-level cost without waiting for QuickBooks schema changes.

---

**Better inputs improve the same pipeline — this does not require redesign.**
