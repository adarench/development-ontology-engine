# BCP Dev v0.2 — PR 5 Compute Feasibility

> **Date:** 2026-05-11
> **Author:** Agent E
> **Status:** Recommendation only. **No compute implemented.** Awaiting user decision.

---

## 1. TL;DR

| Question | Answer |
|---|---|
| Should PR 5 start today? | **Yes — but only as PR 5a (PF satellite replication).** |
| Should we wait for official master compute? | **No — Option A is structurally blocked; the master workbook has no pricing data, and we cannot stage it.** |
| Recommended tool name | **`replicate_pf_satellite_per_lot_output`** — keeps the canonical `generate_per_lot_output` name reserved for Option A. |
| Additional Flagship data needed? | **None for PR 5a.** The PF satellite CSV is self-contained. Option A still needs Q23 + master pricing + ClickUp pull. |
| Does PR 5a relax any refusal? | **No.** All PR 4.5 readiness/caveat logic is preserved; Previous-section phases (B2, D1, G1 Church) refused; non-PF communities refused; range rows refused; warranty refused; master-engine compute still refused. |

---

## 2. Current state

PR 13 narrowed `land_at_mda`:
- `current_workbook_method: "sales_basis_weighted"` (observed via CSV inspection)
- `formula_status: "workbook_observed_pending_source_owner_ratification"`
- lot-count form retained as control / tie-out interpretation only

`generate_per_lot_output_spec` (PR 4) emits the shape; `generate_per_lot_output` (PR 5) was deferred.

`check_allocation_readiness("Parkway Fields", "E1")` returns:
- `method_status: compute_ready`
- `run_readiness: not_ready`
- Top-line: ❌ No — not cleanly today
- 2 inputs missing, 5 partial, 4 present (of 11 blocking inputs)

---

## 3. Blockers for Option A (official master-engine compute)

| Blocker | Status | Owner |
|---|---|---|
| Q23 — formal source-owner ratification of sales-basis weighting | Open. CSV inspection narrows the answer but is not a sign-off. | Finance / Streamline |
| Master `Avg Projected Sales Price` populated | **Empty for every row.** `Flagship Allocation Workbook v3.xlsx - Lot Mix & Pricing.csv` shows `$0` Total Projected Sales for all 80 rows. Cannot derive Sales Basis %. | Pricing team |
| ClickUp lot-count pull for MDA Day tie-out | Not staged. The two-of-three tie can only see LandDev + workbook counts. | Streamline |
| Negative Indirects sign convention for PF | Workbook treats Indirects pool as net credit (−$1.25M). Sign-convention sign-off pending. | Finance |
| Estimated Direct Base for E2/F/G1/G2/H | Satellite uses `Est. $60K/lot` (G1 Comm: `$60K + $300K`); D2: `Actuals plus $500k per CM/BF/SH`. Treat as estimated. | Land |

**Verdict:** Option A cannot run today. Even with Q23 ratified, the master engine produces `$0` for every allocation cell because pricing is empty. Staging master pricing is out of scope for this engine.

---

## 4. PF satellite inventory (Option B inputs)

### Files present in repo

| File | Lines | Purpose |
|---|---|---|
| `data/raw/datarails_unzipped/phase_cost_starter/Parkway Allocation 2025.10.xlsx - PF.csv` | 92 | **Primary** — Project Financial Summary, Summary-per-lot, Budgeting, Land, Indirects, Allocation sections |
| `data/raw/datarails_unzipped/phase_cost_starter/Parkway Allocation 2025.10.xlsx - JCSList.csv` | 59 | Cross-DevCo job list (BCPDev/BCPBL/ASD/BCPI). PF rows present; not strictly required for replication. |
| `data/raw/datarails_unzipped/phase_cost_starter/Parkway Allocation 2025.10.xlsx - AAJ.csv` | 51 | Allocation Adjustment Journal — phase-grain WIP/Inventory adjustments. Not required for the per-lot replication; useful for reconciliation. |

### PF.csv structure (the workhorse)

| CSV rows | Section | Contents |
|---|---|---|
| 4–11 | Summary per lot — Previous Sales/Allocations | B2 SFR (72 + 51), D1 SFR (127 + 31), G1 Church (1) — with Sales, Cost-of-{land, direct, water, indirects}, Total, Margin per lot |
| 13–24 | Summary per lot — Remaining Sales/Allocations | **D2 (30 + 52), E1 (173 + 25), E2 (76), F (61), G1 SFR (63), G1 Comm (1), G2 (145), H (248)** — fully populated per-lot values |
| 27–48 | Budgeting — Directs | Per-phase budget rows. LD budget vs estimated ($60K/lot etc.). E1 = `$15,579,985.58` LD budget. |
| 50–53 | Land | `Ault Ground $24,963,021.86` total |
| 55–64 | Indirects | Total `($1,249,493.54)` — the **negative-Indirects** convention. Breakdown: Backbone, Clubhouse, Other, Pony Express, Water shares (Ault Water $702,262), etc. |
| 67–91 | Allocation — extended | Per-phase × lot_type Ext Sales Price, PRSV%, CRSV%, and ten Allocation columns. E1 Lennar 173 → 89.06% PRSV / 22.03% CRSV. |

### Phases included (PF Remaining)

| Phase | Lot Type | Lots | Status |
|---|---|---|---|
| D2 | SFR | 30 (Lennar) + 52 | Remaining; D2 Direct Base = "Actuals plus $500K per CM/BF/SH" |
| E1 | SFR | 173 (Lennar) + 25 | Remaining; **LD budget present** ($15.58M) |
| E2 | SFR | 76 | Remaining; estimated Direct Base $60K/lot |
| F | SFR | 61 | Remaining; estimated Direct Base $60K/lot |
| G1 | SFR | 63 | Remaining; estimated Direct Base $60K/lot |
| G1 | Comm | 1 | Remaining; estimated $60K + $300K commercial |
| G2 | SFR | 145 | Remaining; estimated Direct Base $60K/lot |
| H | SFR | 248 | Remaining; estimated Direct Base $60K/lot |

### Phases refused (PF Previous, historical / closed)

B2 SFR (72 + 51), D1 SFR (127 + 31), G1 Church (1).

### Tie-out verified

Penny-precision tie-out check on E1 SFR Lennar (173 lots):

| Cell | Per-lot | × Lots | CSV extended | Δ |
|---|---:|---:|---:|---:|
| Sales | $141,121.51 | 24,414,021.23 | $24,414,021.23 | $0.00 |
| Cost of land | $(31,781.78) | $(5,498,247.94) | $(5,498,248.54) | $0.60 (rounding) |
| Cost of direct dev | $(80,202.43) | $(13,875,020.39) | $(13,875,020.21) | $0.18 (rounding) |
| Total cost | $(110,393.41) | (sum of components) | matches | — |
| Margin | $30,728.10 | (Sales − Total cost) | matches | — |

The satellite is **fully self-contained and arithmetically consistent** for PF Remaining.

### Formulas derivable from the satellite

- `Ext_sales[phase,lot_type] = Lots × Sales_per_lot`
- `CRSV%[phase,lot_type] = Ext_sales[phase,lot_type] / Σ(Ext_sales in Remaining section)`
- `Cost_of_land_extended[phase,lot_type] = Community_Land_Pool × CRSV%[phase,lot_type]` (where Community Land Pool = $24,963,021.86)
- `Cost_of_indirects_extended[phase,lot_type] = Community_Indirects_Pool × CRSV%[phase,lot_type]` (where Community Indirects Pool = −$1,249,493.54)
- `Cost_of_direct_extended[phase,lot_type] = Phase_Direct_Base × (Lot_share within phase)`
- Per-lot views = extended / Lots

PR 5a does not need to **compute** these — the values are already in the Summary per lot section. PR 5a only needs to **read** them, plus emit caveats.

---

## 5. Option A vs Option B

| Axis | Option A — master engine | Option B — PF satellite replication |
|---|---|---|
| Tool name | `generate_per_lot_output` (reserved) | `replicate_pf_satellite_per_lot_output` |
| Scope | Any community / phase | PF only; refuses all others |
| Source | Flagship master workbook | PF satellite workbook CSV |
| Compute needed | Yes (sales-basis arithmetic) | No (read-through; values already in CSV) |
| Q23 ratification | Required | Workbook-observed caveat only — does not block read-through |
| Master pricing | Required (currently empty) | Not required |
| ClickUp lot-count pull | Required (MDA tie-out hard gate) | Not required for read-through; surfaces "tie-out not validated" caveat |
| Tie-out precision | Limited by master pricing | Penny-level today |
| Risk of overclaiming | High if pricing assumptions diverge from final ratification | Low — output is explicitly labelled "PF satellite replication" |
| Reversibility | High coupling to allocation_methods.calculation block | Local: tool reads the satellite file path and parses |
| Operator value today | None (cannot run) | Real — Finance/Land reviews of PF Remaining margins land today |
| Estimated implementation | 1–2 weeks after blockers close | 2–3 days, plus tests |

---

## 6. Data required (what to stage before each option ships)

### Option A — `generate_per_lot_output`

| Item | State | Path forward |
|---|---|---|
| Q23 source-owner ratification | Open | Finance/Streamline sign-off; update `allocation_methods_v1.json.land_at_mda.formula_status` to `source_owner_ratified` |
| Master pricing populated | Empty | Pricing team fills `Avg Projected Sales Price` in `Lot Mix & Pricing.csv` for at least every Remaining-section phase |
| Total Projected Sales recomputed | Auto-derives from pricing × lot-count | After pricing |
| ClickUp lot-count pull | Not staged | Streamline pulls; lands in `data/raw/datarails/clickup/api-upload.csv` (already present, but `default_status_today: "needs_clickup_pull"` for the live counts) |
| MDA Day three-way tie | Currently `unknown` for every phase | Function of ClickUp + workbook + MDA doc counts agreeing |
| PF Indirects sign-convention sign-off | Open | Finance sign-off on the negative-pool convention |

### Option B — `replicate_pf_satellite_per_lot_output`

| Item | State | Notes |
|---|---|---|
| PF satellite CSV | **Present** | `Parkway Allocation 2025.10.xlsx - PF.csv` is fully populated, last_modified 2026-04-10 |
| JCSList (optional) | Present | Used for context only, not for replication |
| AAJ (optional) | Present | Used for reconciliation, not for replication |
| Formula audit | **Complete** | CSV tie-out verified to penny precision in §4 of this doc |

---

## 7. Risks of Option B (PF satellite replication)

| Risk | Mitigation |
|---|---|
| Operator mistakes replication output for authoritative compute | Tool name explicitly says "replicate_pf_satellite"; output header reads "**PF satellite replication — not authoritative compute**"; provenance block carries `source: PF satellite workbook (Parkway Allocation 2025.10), as-of 2025-10-31` |
| Caveats get lost in tool output | Per-row `confidence: workbook_replicated`; per-row caveats for estimated Direct Base; community-level caveat for negative-Indirects sign |
| Tool drifts when satellite refreshes | `last_modified` on the CSV surfaces via `check_source_freshness`; new tool also surfaces it in its provenance block |
| Tie-out breaks when satellite formulas change | Tests assert PF E1 Lennar values to penny precision; regression catches any drift |
| Warranty omitted from satellite is misinterpreted as $0 | `warranty_per_lot` field is **refused** with reason `warranty_rate_unratified` + `not_in_pf_satellite`, identical to spec tool behaviour |
| Previous-section phases get re-allocated | Tool refuses by phase whitelist + by section header parsing; tests guard both refusal paths |
| Q23 not ratified — operator infers ratification from replication | Caveat header explicitly states "Sales-basis weighting is workbook-observed; Q23 source-owner ratification still pending" |
| Range-row request reaches PR 5a | Range rows are not in PF, so the tool refuses unmapped phase + cites EXC-007 |

---

## 8. Recommended path

**Ship PR 5a (Option B) now. Hold PR 5 (Option A) until blockers close.**

Rationale:
1. The PF satellite is the only data set in this repo that currently supports a faithful, tie-out-checkable per-lot allocation table.
2. Option B is a **read-through** — no formula derivation, no weighting choice, no fabricated values. The risk surface is the file-parse + caveat-rendering layer, not compute.
3. PR 4.5's `check_allocation_readiness` and `generate_per_lot_output_spec` already cover the master-engine spec/blocker conversation; PR 5a adds the only operationally useful follow-on we can build today.
4. PR 5a does **not preempt** Option A. The canonical `generate_per_lot_output` name stays reserved; Option A can land later, will subsume PR 5a (or keep it as a reconciliation tool).

---

## 9. Proposed tool contract — `replicate_pf_satellite_per_lot_output`

### Signature

```python
class ReplicatePfSatellitePerLotOutputTool(Tool):
    name = "replicate_pf_satellite_per_lot_output"
    description = (
        "[BCP Dev v0.2 — forward-looking accounting process] "
        "**PF SATELLITE REPLICATION — not authoritative compute.** "
        "For Parkway Fields Remaining Sales/Allocations phases (D2, E1, E2, "
        "F, G1 SFR + Comm, G2, H), read per-lot values directly from the PF "
        "satellite workbook (Parkway Allocation 2025.10) and emit a per-lot "
        "table. Refuses Previous-section phases (B2, D1, G1 Church), all "
        "non-PF communities, and any cell whose value is not present in "
        "the satellite (warranty). Preserves PR 4.5 caveats: "
        "sales-basis weighting workbook-observed but source-owner "
        "ratification still pending (Q23); negative-Indirects sign "
        "convention; estimated Direct Base for E2/F/G1/G2/H; MDA Day "
        "three-way tie not validated."
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "phase": {
                    "type": "string",
                    "description": (
                        "Optional phase identifier (D2, E1, E2, F, G1 SFR, "
                        "G1 Comm, G2, H). Default: all Remaining phases."
                    ),
                }
            },
            "required": [],
        }

    def run(self, phase: str = "", **kwargs) -> str: ...
```

### Output shape (markdown)

1. Header: `# PF Satellite Replication — Per-Lot Output (NOT authoritative compute)`
2. Scope caveat block:
   - source = PF satellite workbook
   - as_of = 2025-10-31
   - sales-basis weighting workbook-observed; Q23 pending
   - negative Indirects sign convention flag
   - warranty not in this satellite — refused per cell
3. Per-phase × lot_type table:
   - Columns: `Phase`, `Lot Type`, `Lots`, `Sales/lot`, `Cost of land/lot`, `Cost of direct dev/lot`, `Cost of water/lot`, `Cost of indirects/lot`, `Total cost/lot`, `Margin/lot`, `Margin %`, `Direct Base note`, `Confidence`
   - Confidence: `workbook_replicated` (taken directly from PF satellite Summary section) or `derived` (Margin / Lot, Margin %) or `inferred-unknown` (warranty, refused)
4. Per-phase Direct Base annotation:
   - D2: "Actuals plus $500K per CM/BF/SH"
   - E1: "LD budget present ($15,579,985.58)"
   - E2/F/G1 SFR/G2/H: "Est. $60K/lot"
   - G1 Comm: "Est. $60K + $300K commercial"
5. Refusal block listing what's excluded:
   - Previous-section phases (B2, D1, G1 Church)
   - Non-PF communities (point at `generate_per_lot_output_spec` for spec-only output)
   - Warranty cells (Q5 + UNRES-07)
   - Range rows (EXC-007)
6. Provenance block:
   - PF satellite path + last_modified
   - allocation_methods_v1.json verification_status + formula_status
   - exception_rules cross-references

### Refusal posture

- `phase` not in `{D2, E1, E2, F, G1 SFR, G1 Comm, G2, H}` → refuse with reason (Previous-section or unknown phase).
- Any value not present in the satellite Summary section → refuse for that cell, not the whole row.
- Warranty field always refused with `warranty_rate_unratified` reason.
- No fabricated chart codes, no estimated default values not already in the satellite.

---

## 10. Tests required for PR 5a

| # | Test | Expectation |
|---|---|---|
| 1 | `replicate_pf_satellite_per_lot_output()` returns 9 Remaining rows | D2 (×2), E1 (×2), E2, F, G1 SFR, G1 Comm, G2, H |
| 2 | `replicate_pf_satellite_per_lot_output(phase="E1")` returns 2 rows (Lennar 173 + non-Lennar 25) | — |
| 3 | E1 SFR Lennar 173: `Sales/lot = $141,121.51`, `Total cost/lot = $110,393.41`, `Margin/lot = $30,728.10` | Penny-precision tie-out |
| 4 | E1 SFR non-Lennar 25: `Sales/lot = $120,000.00`, `Margin % = 21.77%` | — |
| 5 | E2 SFR: surfaces "Est. $60K/lot" caveat | — |
| 6 | G1 Comm: `Sales/lot = $1,565,160`, surfaces "$60K + $300K commercial" caveat | — |
| 7 | D2 SFR Lennar 30: surfaces "Actuals plus $500K per CM/BF/SH" caveat | — |
| 8 | `replicate_pf_satellite_per_lot_output(phase="B2")` → refuses with `Previous-section refused` reason | — |
| 9 | `replicate_pf_satellite_per_lot_output(phase="D1")` → refuses Previous | — |
| 10 | `replicate_pf_satellite_per_lot_output(phase="G1 Church")` → refuses Previous | — |
| 11 | Negative-Indirects sign convention surfaces in the header caveat block | — |
| 12 | Warranty cells refused per row with `warranty_rate_unratified` | — |
| 13 | Sales-basis pending caveat (Q23) surfaces in provenance | — |
| 14 | Source `as_of` from PF CSV last_modified surfaces in provenance | — |
| 15 | Tool refuses to be called for non-PF communities (e.g., by absence of a `community` parameter and by the description) | Description carries explicit "PF only" routing |
| 16 | Output contains "NOT authoritative compute" guard phrase | Regression: prevents operators from mistaking replication for authoritative compute |
| 17 | Existing PR 1–4.5 tests still pass; no regression to range-row, warranty, LH, Eagle Vista refusals; protected files unchanged | — |

---

## 11. Decision summary

| Item | Recommendation |
|---|---|
| Proceed with PR 5? | Yes, **as PR 5a** (PF satellite replication only) |
| Tool name | `replicate_pf_satellite_per_lot_output` (reserves `generate_per_lot_output` for the canonical Option A tool) |
| When to start PR 5 (Option A)? | After Q23 closes, master pricing is staged, and ClickUp lot-counts are pulled. None of those is on the engine team's critical path. |
| Additional Flagship data needed for PR 5a? | **None.** PF satellite CSV is self-contained and present in repo. |
| Risk of shipping PR 5a | Low. Read-through, no compute, all PR 4.5 caveats preserved. |
| What PR 5a unblocks | Finance/Land per-lot review of PF Remaining margins, today. |
| What PR 5a does **not** unblock | Org-wide allocation, master pricing, ratified land formula, ClickUp tie-out. |

---

## 12. Open questions for the user before PR 5a starts

1. **Naming approval.** Confirm `replicate_pf_satellite_per_lot_output` is the preferred name, or pick from the alternatives:
   - `replicate_pf_satellite_per_lot_output` (recommended)
   - `generate_pf_satellite_per_lot_output`
   - `generate_per_lot_output(community="Parkway Fields", source_mode="pf_satellite_replication")` (not recommended — generic name implies broader scope)
2. **Output scope.** Default to all PF Remaining phases? Or require explicit `phase=`?
3. **Allocation columns.** PF satellite has 10 `Allocation 1–10` columns where present. Render these in the output, or surface only the Summary-per-lot view? (Recommendation: Summary-per-lot is enough for the operator question; Allocation columns can land in a follow-on if needed.)
4. **Warranty handling.** Refuse the cell with a caveat (recommended) or omit the column entirely? (Recommended: refuse the cell so operators see the gap.)

These are non-blocking — defaults are noted above. PR 5a can proceed with the recommendations unless overridden.
