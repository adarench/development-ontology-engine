# BCP Dev v0.2 — MCP Desktop Trial Results

> **Date:** 2026-05-11
> **Server:** `bedrock/mcp/bcpd_server.py` (12 tools registered)
> **Transport:** stdio via Claude Desktop
> **Surface tested:** the six new BCP Dev v0.2 tools (the six existing BCPD v2.1 tools were exercised in their own trial; not re-tested here)
> **Status:** **PASS with hardening required.** All six tools registered and responded; product-behaviour issues were uncovered and are fixed in PR 4.5 (this PR).

---

## 1. Tools available

| Tool | Purpose | Status |
|---|---|---|
| `query_bcp_dev_process` | General process Q&A grounded in `state/process_rules/*.json` | OK |
| `explain_allocation_logic` | Method explanations by cost_type / event | Fix landed: formula ambiguity surfaces |
| `validate_crosswalk_readiness` | Crosswalk + manifest readiness report | OK |
| `check_allocation_readiness` | "Can we run allocation for X today?" | Fix landed: method_status vs run_readiness split |
| `detect_accounting_events` | ClickUp status-change → recommended AccountingEvents | OK; description tightened for routing |
| `generate_per_lot_output_spec` | Per-Lot Output shape, spec-only | OK |

`generate_per_lot_output` (PR 5) was intentionally not exposed.

---

## 2. Prompts tested

| # | Prompt | Tool invoked (actual) | Tool that should route (post-fix) | Pass / Fail | Notes |
|---|---|---|---|---|---|
| 1 | How is land allocated at MDA? | `explain_allocation_logic(cost_type="Land")` | same | **FAIL → fixed** | Confidently returned a single lot-count-weighted formula. Disagrees with the actual Flagship workbook formula (sales-basis). PR 4.5 marks the formula `pending_source_owner_confirmation` and surfaces both candidates. |
| 2 | Can we run allocation for Parkway Fields phase E1 today? | `check_allocation_readiness(community="Parkway Fields", phase="E1")` | same | **FAIL → fixed** | Returned `compute_ready` with hedging language ("technically compute_ready, but I wouldn't run it today"). PR 4.5 separates `method_status` (eligibility) from `run_readiness` (input availability). Top-line for PF E1 today is now `❌ No — not cleanly today`. |
| 3 | What is blocking Lomond Heights from allocation? | `check_allocation_readiness(community="Lomond Heights", phase="2A")` | same | **PASS** | Correctly returned `blocked: aaj_error_cascade` with the AAJ #ERROR cascade narrative. |
| 4 | Which crosswalks need maintenance right now? | `validate_crosswalk_readiness(scope="all")` | same | **PASS** | Returned UNRES-01..UNRES-08, null-canonical rows, stale-file warnings. |
| 5 | What should accounting do if a ClickUp lot moves to LND_RECORDED_SIH but FMV at Transfer is missing? | `query_bcp_dev_process(question=...)` | `detect_accounting_events(status_changes=[{status_to:"LND_RECORDED_SIH", fields:{FMV at Transfer:null}}])` | **FAIL → fixed** | Routing mismatch. The Q&A tool returned generic SIH rule text. The right tool is `detect_accounting_events`, which would surface the event, flag missing FMV as `missing_required_input_refusal`, and emit the sentinel credit-side caveat. PR 4.5 tightens descriptions on both tools — `detect_accounting_events` now explicitly advertises status-change / "what should accounting do" triggers; `query_bcp_dev_process` adds a "**Do NOT use** for this specific lot's status change" carve-out. |
| 6 | Show me the Per-Lot Output spec for Parkway Fields E1. | `generate_per_lot_output_spec(community="Parkway Fields", phase="E1")` | same | **PASS** | Spec emitted with PF Indirects negative-sign caveat, warranty refusal, no numeric values. |
| 7 | Allocate the range rows anyway. | `query_bcp_dev_process(question=...)` then `explain_allocation_logic(cost_type="shell_range_row")` | either; both should refuse | **PASS** | Both tools refused with `EXC-007` citation; no formula substitution. |

---

## 3. Issues found

### Issue A — Confusing readiness language (severity: medium)

`check_allocation_readiness` for Parkway Fields E1 collapsed two distinct concepts (path eligibility, input availability) into one `compute_ready` headline. Operators reading the result needed a hedge sentence to extract the truth.

**Root cause:** The tool reported only `BcpDevContext.compute_status_for()`'s `decision` field, which describes whether the method/path is eligible. It did not separately classify whether *today's* required inputs are present.

**Fix (PR 4.5):** Two named axes are now emitted at the top:
- `method_status` — `compute_ready | compute_ready_with_caveat | spec_only | blocked` (path eligibility, unchanged source from `compute_status_for`)
- `run_readiness` — `ready | partial | not_ready | blocked` (derived from `allocation_input_requirements_v1.json` against the (community, phase) scope)

Top-line headline now leads with a clear yes/no. PF E1 today returns:

> ❌ No — not cleanly today. The allocation method is **eligible** (`method_status: compute_ready`), but **required inputs are incomplete** (`run_readiness: not_ready`).

### Issue B — `land_at_mda` formula disagreement (severity: high)

The trial answer for "How is land allocated at MDA?" confidently described a lot-count-weighted formula. Two authoritative sources disagree on the weighting:

| Source | Weighting | Formula |
|---|---|---|
| `docs/bcp_dev_process_ontology_v1.md:160`; `docs/bcp_dev_allocation_accounting_tool_family_plan.md:238`; briefing extract (Agent C) | **lot-count** | `raw_land_basis_per_property * (lot_count_in_phase / lot_count_total_property)` |
| `state/bcp_dev/allocation_workbook_schema_v1.json:121` (Agent B, reading the actual Flagship Allocation Workbook v3 formula) | **sales-basis** | `community_land_pool * sales_basis_pct_per_phase` |

**Root cause:** Agent C authored `allocation_methods_v1.json` from the briefing extract, which described lot-count weighting. Agent B's workbook schema, captured from the actual `.xlsx` formula in the Allocation Engine sheet, uses sales-basis weighting. Both can't be canonical.

**Fix (PR 4.5):**
- `allocation_methods_v1.json#land_at_mda` now carries `formula_status: "pending_source_owner_confirmation"` and `verification_status: "pending_source_doc_review"`.
- `calculation` block is restructured into `candidate_a_lot_count_weighted` + `candidate_b_sales_basis_weighted` + `conflict_note`. The `ratified: true` flag is retained because the method *concept* is ratified (land does get allocated at MDA); only the weighting is disputed.
- A new open question Q23 was added to `allocation_methods_v1.json.open_questions`.
- `explain_allocation_logic` and `query_bcp_dev_process` now detect `formula_status == "pending_source_owner_confirmation"` and surface both candidates with sources. Tests assert that neither tool confidently emits a single weighting.

### Issue C — Routing miss on status-change questions (severity: medium)

Prompt 5 ("what should accounting do if a lot moves to LND_RECORDED_SIH but FMV at Transfer is missing?") was answered by `query_bcp_dev_process`, returning generic process text. The user-correct tool is `detect_accounting_events`, which can surface the event, flag the missing FMV blocker, and emit the sentinel credit caveat.

**Root cause:** Tool descriptions did not signal the routing axis. `detect_accounting_events` advertised itself as "given a list of status changes or CSV path" — passive framing that doesn't match natural-language phrasings like "what should accounting do when …". `query_bcp_dev_process` advertised "process questions" broadly, so it claimed the route.

**Fix (PR 4.5):**
- `detect_accounting_events` description now leads with **"Use this tool for ClickUp status changes and 'what should accounting do' questions"** and lists trigger phrasings ("a lot moves to status X", "this lot just changed status", "what accounting event should fire when …").
- `query_bcp_dev_process` description now adds an explicit "**Do NOT use** for 'what should accounting do given this specific lot's status change' — that is `detect_accounting_events`" carve-out.
- A test asserts that both descriptions contain the routing hints (`status change`, `moves to`, `accounting event`, `missing required field`).

### Non-issues observed

- **Refusals held.** Range-row prompt (7) and LH AAJ prompt (3) refused with the right citations.
- **No numeric leakage.** `generate_per_lot_output_spec` did not emit dollar values for any community.
- **Provenance present.** Every routed response included the `## Provenance` block.
- **Protected files byte-identical.** The smoke test verified the seven v2.1 protected artifacts unchanged across every dispatch.

---

## 4. Recommended fixes (status)

| Fix | Landed in | Status |
|---|---|---|
| `check_allocation_readiness`: split `method_status` / `run_readiness` axes; top-line ready/partial/not_ready/blocked | PR 4.5 | ✅ |
| `land_at_mda`: mark `formula_status: pending_source_owner_confirmation`; surface both candidates | PR 4.5 | ✅ |
| Open Q23 added to `allocation_methods_v1.json.open_questions` | PR 4.5 | ✅ |
| `detect_accounting_events` description: lead with status-change routing hints | PR 4.5 | ✅ |
| `query_bcp_dev_process` description: add "do NOT use for status changes" carve-out | PR 4.5 | ✅ |
| Tighten descriptions on remaining four tools with use-case hints | PR 4.5 | ✅ |
| Tests: PF E1 readiness no longer answers as if it can run today | PR 4.5 | ✅ |
| Tests: `explain_allocation_logic(cost_type="Land")` does not confidently state a single formula | PR 4.5 | ✅ |
| Tests: tool descriptions contain routing hints | PR 4.5 | ✅ |
| Source-owner ratification of `land_at_mda` weighting (Q23) | external | open — awaits Finance / Streamline |

---

## 5. Is PR 5 compute ready?

**No — still blocked.** PR 5 (`generate_per_lot_output` for PF Remaining) requires the `land_at_mda` weighting question (Q23) to close before any per-lot land allocation can be computed with confidence. Sales-basis weighting depends on `avg_projected_sales_price`, which is populated only in the PF satellite tab; lot-count weighting works against `clickup_phase_task.lot_count`, which currently needs a ClickUp pull. The two routes have different upstream dependencies.

Recommended path forward:

1. Close Q23 via source-owner ratification.
2. Pull current ClickUp lot counts for PF Remaining phases.
3. Re-snapshot the PF satellite `Avg Projected Sales Price` values.
4. Re-run `check_allocation_readiness("Parkway Fields", "E1")`; the top-line should flip to `ready` or `partial`.
5. Only then start PR 5 implementation with the canonical formula wired in.
