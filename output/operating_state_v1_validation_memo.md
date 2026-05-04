# Operating State v1 — Validation Memo

_For: Flagship finance/ops leadership_
_Date: 2026-04-29_

---

## 1. What we built

A repeatable pipeline that turns a ClickUp task export and a QuickBooks GL
export into a single, agent-readable snapshot of in-flight construction:

- A per-lot view (where every lot is in its construction sequence)
- A per-project rollup (how each project is progressing on average)
- A best-effort cost picture (where the GL allows it)

The output is one JSON file plus two short markdown briefs an LLM agent can
read directly. Re-running the pipeline takes seconds and is fully
deterministic.

---

## 2. What it proves

We can reconstruct meaningful operating structure **without** waiting for
clean metadata. Specifically:

- Every task name in the ClickUp sample parsed cleanly into
  `(project_code, lot_number, stage)` — 100% parse rate on 100 rows.
- 22 unique lots were detected across 3 projects (LE, H MF, H A14).
- 86% of lots show a valid construction stage progression (no skipped
  stages).
- 90% of lots are HIGH-confidence (real ClickUp parent IDs, ≥2 stages
  observed).

The structure already surfaces a real operational signal: **18 of the 18 LE
lots are sitting at Backfill** — a single handoff appears to be blocking
the cohort.

---

## 3. What is trustworthy now

| Fact | Why it's trustworthy |
|---|---|
| Project membership of each lot | Parsed directly from ClickUp task names |
| Lot number | Parsed directly from ClickUp task names |
| Current stage of each lot | Derived from real, non-empty ClickUp tasks |
| Completion % per lot, per project | Computed from observed stages in a defined ordering |
| Last activity date per lot | From `date_updated` on ClickUp tasks |
| Project-level GL totals for **H A14** and **H MF** | Direct sum of GL Activity rows for `Flagborough LLC` |

---

## 4. What is explicitly estimated (and labeled as such)

These fields are useful for visibility but are **not** ground truth. They
are flagged in every output:

- **`phase_id_estimated`** — phases are inferred by clustering lot numbers
  (consecutive numbers with gaps ≥10 break into a new phase). They are
  **not** real plat phases. Every phase carries the literal tag
  `"phase_confidence": "estimated"`.
- **No per-lot cost is computed.** The GL has no lot-level signal. If a
  consumer divides project total by lot count, that is an *estimate*,
  never an actual lot cost — and the documentation says so.
- **LE shows $0 cost** because the GL sample has no Activity rows for
  Anderson Geneva LLC. This is missing data, **not** zero spend, and the
  output explicitly says so wherever LE cost appears.

---

## 5. What data is missing

The pipeline is correct; the input is partial. Three things limit it:

1. **Cost cannot be tied to lots or phases** with the current GL export.
   Project-level rollups are the floor, not the ceiling.
2. **Phase IDs are heuristic** because no plat → lot reference table is
   wired in.
3. **Stage timing cannot be measured.** ClickUp `start_date` and
   `date_done` are populated on 0–1 of 100 rows in the sample. We can see
   *what* stage a lot is at, but not *how long* it has been there.

---

## 6. Exact next data asks from Flagship

To move from "operating visibility" to "operating decisions," we need:

1. **Full ClickUp export** — not the 100-row preview. The same parser
   handles any volume; we just need the complete file.
2. **Real plat / phase / lot reference table** — a sheet listing each plat
   (e.g., `Harmony A14`, `LE Phase 2`) and the lot numbers it contains.
   This replaces the heuristic phase model with the real one.
3. **QuickBooks / DataRails GL re-export** with these fields populated:
   - `Class` (the QB segmentation field — typically the project)
   - `Customer:Job` (the QB sub-customer hierarchy — typically project/phase/lot)
   - `Transaction ID` / `Journal Entry ID` (so we can pair debits and
     credits)
   - `Vendor` (currently 97% placeholder text)
   - `Memo` (currently 2% populated)

   Restoring these in the export is the single highest-leverage change.
   It moves cost visibility from project-level to phase- or lot-level.
4. **Activity rows for Anderson Geneva LLC (the LE project)** — the
   current sample has only Beginning Balance rows for this entity, which
   is why LE cost reads as $0.
5. **Intercompany allocation schedule** — only required if Flagship EM
   Holdings (the holdco) costs need to be allocated to projects.
   Currently those costs sit at the holdco unassigned.
6. **ClickUp `start_date` and `date_done` filled per task** if possible —
   this would unlock stage-duration analytics (how long Backfill takes,
   where lots are sticking, average days from Dug → Spec, etc.).

---

## Bottom line

The system is real, deterministic, and honest about what it knows. With
items 1–3 above (full ClickUp + plat reference + re-exported GL),
Operating State v1 becomes Operating State v2 with measured cost per
phase and real phase IDs — no architecture changes required, just better
input.
