# BCP Dev v0.2 — Sprint Summary

> **Period:** PR 9 through PR 15 (merged 2026-05-11/12)
> **Audience:** Adam / Bedrock internal; lightly editable for Flagship finance/land/ops with the caveats in §14
> **Status:** v0.2 MVP shipped. Canonical allocation compute deferred pending source-owner inputs.

---

## 1. Executive summary

Across seven merged PRs we extended the existing BCPD v2.1 operating-state engine with a forward-looking BCP Dev process and allocation layer. Seven new LLM-facing tools — six MCP-exposed Q&A / readiness / detection / spec tools plus one Parkway-Fields-only workbook replication tool — now run locally and through the same MCP stdio server the v2.1 BCPD tools use. The system can explain the BCP Dev process, route ClickUp status changes to the recommended GL entries, surface allocation readiness with separate "method eligible" / "inputs available today" axes, flag unresolved crosswalks and stale source files, emit the canonical Per-Lot Output spec with per-field blockers, and read-through the populated Parkway Fields satellite workbook for review.

**What the system can now do:** answer scoped process questions with rule-level citations and provenance; tell you whether allocation for a (community, phase) is runnable today and what's missing; surface what accounting events should fire for given ClickUp status changes; emit the Per-Lot Output shape and blockers for any community; replicate the Parkway Fields satellite workbook per-lot table to the penny.

**What it cannot do yet:** run canonical master-engine allocation compute. The master Flagship Allocation Workbook has no pricing populated (Sales Basis % = 0% on every row), Q23 (land_at_mda weighting) is workbook-observed but not formally source-owner ratified, and ClickUp lot-count pulls are not staged. The PF satellite replication tool is **not** canonical compute — it is a read-through of an existing workbook output.

**Main takeaway:** the substrate, tools, and MCP surface are done. What ships next is source-owner validation, not engine code.

---

## 2. What changed strategically

The roadmap shifted away from a generic BCPD cost Q&A surface focused on historical coverage (the v2.1 layer) and toward a **forward-looking BCP Dev process and allocation tooling family**. Five concrete pivots:

- **From historical Q&A to process truth.** The v2.1 tools answer "what did this BCPD project cost?" The v0.2 tools answer "what should happen when this lot moves to status X?", "can we run allocation for this phase today?", "which crosswalks are blocking my pipeline?".
- **From projects to lifecycle events.** ClickUp status transitions are now first-class. `detect_accounting_events` is the entry point for "the lot just changed status — what accounting event should fire and what GL entries are recommended?".
- **From "is the data there" to "is allocation runnable today."** `check_allocation_readiness` splits two axes: `method_status` (is the allocation path eligible for this community/phase?) and `run_readiness` (are required inputs actually available?). Operators no longer get hedged headlines.
- **From master-engine compute first to PF satellite replication first.** The master Flagship workbook has empty pricing, so canonical compute is structurally blocked. The PF satellite is fully populated and tie-out-checkable — we shipped a read-through tool there and reserved the canonical name for later.
- **From single-document briefing to versioned process state.** Six process rule files (status taxonomy, ClickUp→GL event map, account/prefix matrix, allocation methods, monthly review checks, exception rules) plus five BCP Dev state files (workbook schema, input requirements, per-lot output schema, source crosswalks, source file manifest) are now versioned JSON and validated by `BcpDevContext`.

---

## 3. Architecture summary

Additive extension of the existing BCPD operating-state architecture. Nothing in v2.1 was rewritten.

```
┌────────────────────────────────────────────────────────────────┐
│ Claude Desktop (MCP client over stdio)                         │
└─────────────────────────┬──────────────────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────────────────┐
│ bedrock/mcp/bcpd_server.py        — single FastMCP server      │
│   13 typed @mcp.tool() handlers (6 v2.1 BCPD + 7 v0.2 BCP Dev) │
└─────────────────────────┬──────────────────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────────────────┐
│ core/agent/registry.py            — ToolRegistry               │
│   name → Tool dispatch; deterministic; stateless wire layer    │
└─────────┬───────────────────────────────┬──────────────────────┘
          │                               │
┌─────────▼─────────────────┐   ┌─────────▼──────────────────────┐
│ core/tools/bcpd_workflows │   │ core/tools/bcp_dev_workflows   │
│ (v2.1, six tools)         │   │ (v0.2, seven tools)            │
└─────────┬─────────────────┘   └─────────┬──────────────────────┘
          │                               │
┌─────────▼─────────────────┐   ┌─────────▼──────────────────────┐
│ BcpdContext               │   │ BcpDevContext                  │
│ (v2.1 operating state)    │   │ (v0.2 lazy loader + validator) │
└─────────┬─────────────────┘   └─────────┬──────────────────────┘
          │                               │
          ▼                               ▼
┌──────────────────────────┐   ┌──────────────────────────────────┐
│ output/operating_state_  │   │ state/process_rules/*.json (6)   │
│ v2_1_bcpd.json (frozen)  │   │ state/bcp_dev/*.json       (5)   │
└──────────────────────────┘   └──────────────────────────────────┘
```

Key properties:

- **One MCP server, two tool families.** No new server. Same Claude Desktop config that runs the v2.1 tools now sees all 13 tools.
- **Versioned state files.** Eleven JSON files describe the v0.2 substrate. Every tool reads them through `BcpDevContext`, which validates cross-file integrity at load time (event_id ↔ status_taxonomy, account codes ↔ posting/alloc matrix, method_id_ref ↔ allocation_methods, UNRES-* id format, etc.).
- **Deterministic tools.** Every BCP Dev tool's `run()` returns markdown. No probabilistic estimation in the tool layer; estimation lives in the source state files (e.g., satellite Direct-Base estimates) and is surfaced as a caveat.
- **Read-only contract.** Every dispatch is verified to leave the seven protected v2.1 artifacts byte-identical (smoke test hashes before/after each call).
- **Provenance everywhere.** Every successful response carries a `## Provenance` block listing the rule files, source artifacts, and verification status that produced the answer.

---

## 4. PR / milestone summary

### PR 9 — `bcp-dev-context-v0` (merged)

**Added:** `core/agent/bcp_dev_context.py` (`BcpDevContext` class), `scripts/validate_process_rules.py`, `tests/test_bcp_dev_context.py`, and the eleven v0.2 state JSON files (forced-in despite the bulk-data gitignore because the engine depends on them).

**Why it mattered:** without versioned, validated state files, every later tool would have re-parsed the same briefing extracts inconsistently. The integrity validator catches dangling event_ids, missing account codes, malformed UNRES- ids, etc. before any tool runs.

**Changed runtime behavior?** No — pure infrastructure.

**Unlocked:** all subsequent PRs.

### PR 10 — `bcp-dev-workflows-v0` (merged)

**Added:** `core/tools/bcp_dev_workflows.py` with `QueryBcpDevProcessTool` and `ExplainAllocationLogicTool`. Six-route keyword table mapping natural-language questions to the relevant rule file (status taxonomy / event map / account prefix / allocation methods / monthly review / exception rules).

**Why it mattered:** first LLM-facing tools that read the v0.2 substrate. Rule-grounded answers with explicit citations (e.g., `[ALLOC-001 from allocation_methods_v1.json]`) and a provenance block that surfaces each file's `verification_status`.

**Changed runtime behavior?** No — read-only, additive.

**Unlocked:** the Q&A and explanation surface that became the headline demo of v0.2.

### PR 11 / PR 12 — `bcp-dev-mcp-v0` + `bcp-dev-mcp-hardening-v0` (both merged)

**Added (PR 11):** `validate_crosswalk_readiness`, `check_allocation_readiness`, `detect_accounting_events`, `generate_per_lot_output_spec`. Exposed all six v0.2 BCP Dev tools alongside the six v2.1 BCPD tools in `bedrock/mcp/bcpd_server.py` (12 total at this point). Extended `scripts/smoke_test_bcpd_mcp.py` to exercise every new tool.

**Hardening (PR 12), based on Claude Desktop trial findings:**
- `check_allocation_readiness` split `method_status` (path eligibility) from `run_readiness` (input availability today). Top-line answers now lead with ✅/⚠️/❌. The trial-time bug ("technically compute_ready, but I wouldn't run it") was eliminated.
- `land_at_mda` marked `formula_status: pending_source_owner_confirmation` with both lot-count and sales-basis candidates surfaced. (Later narrowed in PR 13.)
- Tool descriptions tightened: `detect_accounting_events` now leads with "status change / what should accounting do" routing hints; `query_bcp_dev_process` adds a "**Do NOT use** for specific lot's status change" carve-out.
- New `docs/bcp_dev_v0_2_mcp_desktop_trial_results.md` documents the trial.

**Why it mattered:** the readiness/detection/spec surface that lets operators answer real workflow questions; the hardening prevented operator-misleading headlines.

**Changed runtime behavior?** Yes — added the read-only event-detection and readiness surfaces.

**Unlocked:** the Claude Desktop trial; full v0.2 MVP surface.

### PR 13 — `bcp-dev-land-sales-basis-v0` (merged)

**Added:** Narrowing of `land_at_mda` in `allocation_methods_v1.json` after CSV inspection of the Flagship Allocation Workbook v3. `current_workbook_method: "sales_basis_weighted"`, `formula_status: "workbook_observed_pending_source_owner_ratification"`. The lot-count form is preserved as a control/tie-out interpretation only, NOT the workbook formula. Tool rendering updated to surface the new structure.

**Why it mattered:** the earlier framing presented two formulas as equally weighted candidates. CSV evidence (Instructions tab + Allocation Engine columns) confirmed sales-basis is the observed workbook method. The fix avoids overclaiming source-owner ratification while removing false symmetry.

**Changed runtime behavior?** Output for `explain_allocation_logic(cost_type="Land")` and `query_bcp_dev_process(...)` now leads with sales-basis as the current workbook method and demotes lot-count to a control interpretation.

**Unlocked:** narrowed Q23 from "either of two" to "sales-basis observed, sign-off pending."

### PR 14 — `bcp-dev-pr5-feasibility` (merged)

**Added:** `docs/bcp_dev_pr5_compute_feasibility.md` — strategy-only document weighing **Option A (canonical master-engine compute)** against **Option B (PF satellite workbook replication)**. Recommends Option B as PR 5a, reserves the canonical `generate_per_lot_output` name for Option A, lists exact source files, risks, tool contract, and 17 required tests. No code in this PR.

**Why it mattered:** Option A is structurally blocked (master has no pricing). Option B is fully feasible today and a Finance/Land review surface, but only if scoped and named correctly to avoid being mistaken for canonical compute.

**Changed runtime behavior?** No.

**Unlocked:** PR 15.

### PR 15 — `bcp-dev-pr5a-pf-replication` (merged)

**Added:** `ReplicatePfSatellitePerLotOutputTool` — read-through of `Parkway Allocation 2025.10.xlsx - PF.csv`. 13th MCP tool. State-machine CSV parser over the four satellite sections (Summary per lot / Budgeting / Allocation). Emits per-(phase, lot_type, lots) rows with all nine required caveats. Refuses Previous-section phases (B2, D1, G1 Church), all non-PF communities, warranty cells, and range rows. Penny-precision tie-out verified for E1 SFR Lennar 173 lots (Sales/lot $141,121.51, Margin/lot $30,728.10). PF satellite CSV force-added (same pattern as PR 9 state files).

**Why it mattered:** delivers a real operator-visible per-lot table today, without bypassing the source-owner ratification blockers and without claiming canonical compute.

**Changed runtime behavior?** Yes — added the 13th MCP tool with explicit "NOT authoritative compute" header on every response.

**Unlocked:** Finance/Land review of PF Remaining margins today; demonstrates the read-through pattern that future replication tools could extend.

---

## 5. Current tool capabilities

### BCP Dev v0.2 tool family (seven tools, all MCP-exposed)

| Tool | What it does |
|---|---|
| `query_bcp_dev_process` | General process Q&A over the six rule files (statuses, events, accounts, methods, monthly checks, exception rules). Cites rule IDs and surfaces `verification_status` caveats. |
| `explain_allocation_logic` | Explain the allocation method for a cost_type or accounting event. Surfaces trigger, required inputs, formula, GL accounts, and any "formula pending source-owner ratification" caveat (notably for `land_at_mda`). |
| `validate_crosswalk_readiness` | Enumerate the 13 crosswalk tables: resolved counts, unresolved-in-table rows (`canonical_value: null`), UNRES-* mappings, stale source files, monitored-field drift alerts. Optional scope filter. |
| `check_allocation_readiness` | Given (community, phase?), report **both** `method_status` (path eligibility) and `run_readiness` (input availability today). Top-line ✅/⚠️/❌ headline. Per-input checklist with present/partial/missing classification. MDA Day tie status. |
| `detect_accounting_events` | Given a list of ClickUp status changes (or a CSV path), surface the recommended AccountingEvents. **Detection only — never posts.** Flags missing required fields, MDA Day partial-tie, SIH/3RDY sentinel credit codes (Q17/Q18 pending), and unresolved subdivision/phase crosswalks. |
| `generate_per_lot_output_spec` | Spec-only Per-Lot Output for any (community, phase). Per-field `compute_status` and blocker list. **Never emits numeric dollar values.** Cites refusal patterns from `per_lot_output_schema_v1.json`. PF surfaces negative-Indirects sign caveat; LH cites AAJ #ERROR cascade; Eagle Vista cites not-in-workbook; range rows cite EXC-007. |
| `replicate_pf_satellite_per_lot_output` | Read-through replication of the Parkway Allocation 2025.10 satellite workbook for PF Remaining phases (D2, E1, E2, F, G1 SFR, G1 Comm, G2, H). **NOT authoritative compute.** Penny-precision tie-out to the workbook. Refuses Previous-section phases, non-PF communities, warranty cells, range rows. |

### Existing BCPD v2.1 tool family (six tools, unchanged)

`generate_project_brief`, `review_margin_report_readiness`, `find_false_precision_risks`, `summarize_change_impact`, `prepare_finance_land_review`, `draft_owner_update`. None of these were modified during the sprint; their behaviour, tests, and outputs are identical to pre-sprint.

---

## 6. What the system can answer today

Concrete prompts that work end-to-end through MCP / Claude Desktop:

- **"How is land allocated at MDA?"** → `explain_allocation_logic(cost_type="Land")`. Returns the workbook-observed sales-basis formula (`community_land_pool × sales_basis_pct_per_phase`), the lot-count control interpretation, the Q23 pending caveat, and the reconciliation note that lot counts are still required for MDA tie-out and the per-lot denominator.
- **"Can we run allocation for Parkway Fields E1 today?"** → `check_allocation_readiness(community="Parkway Fields", phase="E1")`. Returns `method_status: compute_ready`, `run_readiness: not_ready`, top-line "❌ No — not cleanly today", and the input checklist showing what's missing.
- **"What is blocking Lomond Heights from allocation?"** → `check_allocation_readiness(community="Lomond Heights", phase="2A")`. Returns `blocked: aaj_error_cascade` with explanation that the AAJ Capitalized Interest #ERROR cascades through Indirects.
- **"Which crosswalks need maintenance?"** → `validate_crosswalk_readiness(scope="all")`. Returns resolved counts per CW table, all UNRES-* mappings, and any stale source files.
- **"What should accounting do when a lot moves to RECORDED - SIH but FMV at Transfer is missing?"** → `detect_accounting_events(status_changes=[{...status_to: "LND_RECORDED_SIH", fields: {FMV at Transfer: null}}])`. Returns the `lot_sale_sih` event with a blocker citing `missing_required_input_refusal` and a `pending_source_doc_review` caveat on the SIH sentinel credit code (Q17).
- **"Show me the Per-Lot Output spec for Parkway Fields E1."** → `generate_per_lot_output_spec(community="Parkway Fields", phase="E1")`. Returns the canonical Per-Lot Output shape with per-field `compute_status`, PF Indirects negative-sign caveat, warranty refusal, and no numeric values.
- **"Replicate the PF satellite output for E1."** → `replicate_pf_satellite_per_lot_output(phase="E1")`. Returns the Lennar 173-lot row + non-Lennar 25-lot row directly from the satellite workbook, with all nine required caveats and an explicit "NOT authoritative compute" header.

---

## 7. What the system refuses / should not do

Refusal posture is consistent across all seven tools and is verified by tests:

- **Range-row allocation** — `allocation_methods.range_row_unratified` is `ratified: false`. Tools cite `EXC-007` (unratified method refusal) and never approximate it with a ratified method.
- **Missing values as zero** — `EXC-002` (missing required input refusal). `detect_accounting_events` surfaces events but flags them blocked when blocking-required fields are missing (e.g., FMV at Transfer for SIH, Sale Price for 3RDY). `generate_per_lot_output_spec` never emits $0 — every field is either present-with-confidence, blocked, refused, or input_required.
- **Warranty computation** — Q5 (rate) and UNRES-07 (pool source) are both open. Every tool that touches warranty surfaces it as `warranty_rate_unratified` and refuses to compute or substitute a numeric default.
- **Canonical master-engine compute** — `generate_per_lot_output` (canonical, Option A) is intentionally not implemented; the master workbook has no pricing, Q23 is not formally ratified, and ClickUp lot-counts are not staged.
- **Non-PF communities through `replicate_pf_satellite_per_lot_output`** — refused by name and scope; the tool points operators at `generate_per_lot_output_spec` for the spec-only view.
- **Re-emitting historical/closed PF phases** — B2, D1, G1 Church are Previous-section in the PF satellite. `replicate_pf_satellite_per_lot_output` refuses with "historical/closed; re-replaying would corrupt the closed allocation record."
- **Claiming source-owner ratification where only workbook-observed evidence exists** — `land_at_mda.formula_status: workbook_observed_pending_source_owner_ratification` is the canonical phrase. Tools surface "Q23 ratification still pending" on every relevant response.
- **Sentinel chart codes for SIH/3RDY revenue** — `intercompany_revenue_or_transfer_clearing` and `land_sale_revenue` are flagged `pending_source_doc_review` (Q17/Q18); tools never fabricate a real chart code.

---

## 8. What "PF satellite replication" means

A short, explicit definition so we don't drift on it:

- **It reads values directly** from the already-populated Parkway Fields satellite workbook (`Parkway Allocation 2025.10.xlsx - PF.csv`). Every cell in the output is a verbatim copy of a cell from that workbook.
- **It is not canonical allocation compute.** It does not derive allocations from raw ClickUp / QBD / pricing source truth. It does not validate the workbook's internal arithmetic against any external source.
- **It does not recompute.** No formula evaluation happens in the tool; the workbook already did the math, and the satellite tab is the snapshot of that math at 2025-10-31.
- **It is useful as a bridge / demo / reporting surface.** Finance and Land can see the per-lot Sales / Cost / Margin breakdown for PF Remaining phases today, with the exact values the satellite produces, plus structured caveats.
- **It must be labelled "NOT authoritative compute."** Every response leads with this guard phrase; a regression test asserts the phrase is present.
- **It preserves workbook sign conventions and caveats.** Negative Indirects pool (−$1.25M) shows through as the workbook records it. Estimated Direct Base annotations ($60K/lot, Actuals plus $500K, LD budget authoritative) are surfaced per row.

What it is **not**: a substitute for `generate_per_lot_output` (canonical). When Q23 closes and master pricing is staged, the canonical tool will be the source of truth; PR 5a's replication tool will remain as a tie-out / reconciliation surface.

---

## 9. Actual allocation blockers

Canonical compute is blocked by external dependencies, not engine code:

1. **Master Flagship workbook pricing.** `Avg Projected Sales Price` is `$0` for every PF row in `Flagship Allocation Workbook v3.xlsx - Lot Mix & Pricing.csv`. Without pricing, Sales Basis % = 0% and every allocation cell resolves to $0.
2. **ClickUp lot-count pull.** The MDA Day three-way tie requires `clickup_lot_count == mda_lot_count == workbook_lot_count`. Today only the LandDev workbook and satellite counts are available — the ClickUp side is `needs_clickup_pull`. The hard gate cannot be evaluated.
3. **MDA Day three-way tie cannot fully run.** Consequence of (2). `check_allocation_readiness(...)` correctly returns `mda_day_check: unknown` for every PF phase.
4. **Q23 source-owner ratification.** Workbook CSV inspection narrowed the answer to sales-basis weighting, but that's evidence, not sign-off. Until a Flagship source owner formally ratifies, `formula_status` remains `workbook_observed_pending_source_owner_ratification` and tools refuse canonical compute.
5. **Warranty rate / pool source.** Q5 (rate value) and UNRES-07 (pool source) are both open. Warranty cells refuse on every tool until both close.
6. **Unresolved crosswalks.** Eight UNRES-* entries remain (e.g., UNRES-03 QBD job-prefix attribution, UNRES-07 warranty pool, UNRES-08 Salem Fields letter-vs-number phase naming). Some communities/phases have `inferred-unknown` resolution paths today.
7. **Spec-only or blocked communities.** Hillcrest / Flagship Belmont are out of v0.2 scope. Lomond Heights is blocked by AAJ #ERROR. Eagle Vista is not present in the master Allocation Engine. Communities other than PF in the master engine are spec-only because of (1).

---

## 10. Data / decisions needed from Flagship

Targeted asks, in priority order:

1. **Q23 — confirm sales-basis weighting is canonical for `land_at_mda` / Land RSV allocation.** Workbook CSV inspection (Instructions tab + Allocation Engine columns) confirms sales-basis is the observed method. We need a finance source-owner to ratify this so we can drop `pending_source_owner_ratification` and ship canonical compute.
2. **Fresh ClickUp lot counts for Parkway Fields Remaining phases.** Required for the MDA Day three-way tie hard gate. Once pulled, `check_allocation_readiness("Parkway Fields", "E1")` should pivot from `unknown` to `pass` / `partial` / `fail`.
3. **Manual land-team tie-out counts.** `Lots (Manual Input)` column in `Lot Mix & Pricing.csv` is empty for every observed phase, which currently masks the tie-out check.
4. **Confirm / provide projected sales prices in the master workflow.** Master `Avg Projected Sales Price` is empty for every row. PF satellite has prices for B2/D1/D2/E1/E2/F/G1/G2/H; LH satellite has assumed prices ($150K SFR, $110K TH, $80K MF, $5.7M Comm). These should land in the master engine to unblock canonical compute beyond PF.
5. **Warranty rate and pool source.** Q5 (rate, scope: global / per-DevCo / per-community?) and UNRES-07 (pool source: separate workbook, or computed downstream?).
6. **QBD job-prefix attribution (UNRES-03).** Observed QBD job names ("Harmony B1", "Parkway Fields E-1") do not carry the LND/MPL/IND/DIR/WTR/CPI prefix. Need confirmation: prefix encoded in parent class hierarchy, or on the QBD job ID itself (not visible in our exports)?
7. **PF Indirects negative-sign convention.** Satellite shows Indirects pool as `−$1,249,493.54` (net credit balance). Confirm that the canonical reporting convention treats this as a credit, or whether canonical compute should flip the sign in downstream presentation.
8. **SIH / 3RDY revenue account codes (Q17 / Q18).** Today both are `pending_source_doc_review` sentinels in the event map. Need the actual chart codes for intercompany revenue (SIH) and land-sale revenue (3RDY).

---

## 11. Definition of done for this sprint

- **BCP Dev process rules are structured** — six process-rules files + five BCP Dev state files, all versioned, validated, and consumed via `BcpDevContext`.
- **`BcpDevContext` loads and validates** — lazy-loads all 11 JSON files, runs cross-file integrity checks (event_id ↔ status_taxonomy, accounts ↔ posting/alloc, method_id_ref ↔ allocation_methods, UNRES-* ids, etc.), raises `BcpDevContextIntegrityError` with structured issues on failure.
- **Tools run locally and through MCP** — seven BCP Dev tools registered alongside the six v2.1 BCPD tools; 13 total exposed through `bedrock/mcp/bcpd_server.py`.
- **Claude Desktop can invoke the BCP Dev tool family** — verified via in-process smoke (`scripts/smoke_test_bcpd_mcp.py`, 11 dispatches) and end-to-end MCP Desktop trial.
- **Readiness / event / spec / replication workflows work** — `check_allocation_readiness` returns the correct top-line for every test case (PF E1 not_ready, LH blocked, Eagle Vista blocked, range row refused, Harmony spec_only). `detect_accounting_events` correctly surfaces SIH/3RDY events with blockers. `generate_per_lot_output_spec` emits no numeric values. `replicate_pf_satellite_per_lot_output` ties out to the penny.
- **Protected BCPD v2.1 state remains unchanged** — `git diff HEAD --` against the seven protected artifacts returns empty; smoke test verifies byte-identity across every dispatch.
- **Unsupported compute is refused** — range-row, warranty rate, canonical master-engine, non-PF through the PF replication tool, Previous-section PF phases, missing required inputs.
- **Tests pass** — 77 BCP Dev workflow tests, 26 context tests, 31 v2.1 BCPD workflow tests, 11 MCP server tests, validate script PASS, smoke PASS.

---

## 12. Recommended next steps

### Immediate

- **Re-run Claude Desktop trial after PR 15 merge.** Confirm the replication tool routes cleanly for "show me the PF Remaining per-lot table" prompts and the seven existing v0.2 tools continue to route as expected.
- **Create a clean demo script.** A 10-prompt run that exercises every tool, with the expected response highlights, suitable for sharing with a Flagship stakeholder.
- **Prepare a team-facing explanation.** A short walkthrough (10 minutes) for Bedrock + Flagship: what the surface does, what it refuses, how to read a readiness response, where the caveats come from.
- **Ask Flagship the §10 targeted questions** in priority order (Q23, ClickUp counts, master pricing).

### Next engineering (after Flagship inputs land)

- **Output-formatting polish.** Negative-Indirects sign confuses operators in tabular output; consider a `display_mode` option (workbook signs vs finance-positive costs). Optional; not blocking.
- **Source-doc verification.** When the original `.docx` / `.pptx` files (UCH GL Structure Process Guide v4, Lifecycle Tracking Guide v2, Lifecycle Walkthrough v2) land in `data/raw/process_docs/`, re-walk the 78 rules and bump `verification_status` from `inferred_from_briefing` to `source_doc_extracted` where confirmed.
- **Hold canonical `generate_per_lot_output`** until Q23 closes, master pricing is staged, and ClickUp lot-counts are pulled. Implementation contract is in `docs/bcp_dev_pr5_compute_feasibility.md` for when the gates open.

### Later

- **ClickUp connector / live pulls.** v0.2 is file-based by design. v0.3 should add a real ClickUp connector so lifecycle events drive the engine without manual CSV pulls.
- **DataRails / QBD / Yardi source refresh path.** Today the satellite and DataRails CSVs are point-in-time. A refresh pipeline (monthly close cadence) would keep the engine current.
- **Canonical master-engine compute** (`generate_per_lot_output`). Lands once §9 blockers close.
- **Broader DevCo coverage beyond PF.** PR 5a is PF-only. Once master pricing is staged, the canonical tool should cover BCPD / BCPBL / ASD / BCPI in scope.

---

## 13. Risks / caveats

- **Source docs not fully re-anchored yet.** Most v0.2 process rules carry `verification_status: inferred_from_briefing` or `pending_source_doc_review`. Tools surface this on every response, but operators reading output should know the rules describe what we believe the process to be, not (yet) what an authoritative source doc confirms.
- **PF satellite is one workbook snapshot.** The 2025-10-31 satellite is what the replication tool reads. If a 2025-11 or 2026-Q1 satellite version arrives with different Direct-Base estimates or pricing, the replication tool will need a refresh and the hard-coded direct-base note table updated.
- **Workbook sign conventions may confuse users.** The PF satellite Summary section shows per-lot Indirects as positive ($1,590.80 for E1 Lennar) while the Allocation section shows the same value extended as negative ($-275,208.11). Both are workbook-correct; the replication tool surfaces both. An operator unfamiliar with the convention may read it as a contradiction.
- **Source-owner ratification still matters.** Workbook-observed evidence is strong but not authoritative. Until Flagship finance ratifies Q23, canonical compute stays gated.
- **Readiness ≠ compute.** `check_allocation_readiness` returning `method_status: compute_ready` does NOT mean the system will produce an allocation — it means the path is eligible. The `run_readiness` axis is the actual "can we run it" signal. The PR-4.5 hardening fixed this UX bug; future tools should preserve the split.
- **Replication ≠ canonical allocation.** PR 5a's tool is read-through. Operators (and Flagship reviewers) must not treat its output as authoritative compute. The "NOT authoritative compute" guard phrase is present on every response and asserted by a regression test, but the social risk of misinterpretation exists.

---

## 14. Final bottom line

We now have a working BCP Dev process / allocation MCP layer. It can query process truth (statuses, events, accounts, methods, monthly checks, exceptions), report readiness with separated method-eligibility and input-availability axes, validate crosswalk and source-file freshness, detect accounting events from ClickUp status changes with proper refusals, emit the canonical Per-Lot Output spec without ever fabricating values, and replicate the Parkway Fields satellite workbook to the penny — all through the same MCP stdio server the existing v2.1 BCPD tools already use, and without modifying any v2.1 state. It is not yet the canonical allocation engine, and we did not pretend it was. The next step is **targeted data and source-owner validation**, not broad rebuilding.

---

## Audience suitability

This summary is suitable for **internal Bedrock review as-is**. With light editing, it can also go to **Flagship finance / land / ops stakeholders** — the technical sections (§3 architecture, §11 definition of done) can be condensed or moved to an appendix, but §1, §2, §6, §7, §8, §9, §10, and §14 are already written for a stakeholder audience and should not need substantive changes.
