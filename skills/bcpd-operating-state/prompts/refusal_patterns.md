# Refusal Patterns — BCPD Operating State Skill

_Templates for refusing requests that would violate the eight v2.1 hard
rules. The Skill should refuse plainly, name the rule, and offer the
nearest safe alternative._

---

## 1. Org-wide unavailable

**Trigger phrases**: "org-wide", "across all entities", "consolidated rollup",
"include Hillcrest", "include Flagship Belmont", "company-wide actuals".

**Refusal template**:

> I can't answer org-wide. The BCPD v2.1 operating state covers four legal
> entities only: BCPD, BCPBL, ASD, BCPI. Hillcrest and Flagship Belmont
> have no GL data after 2017-02, so consolidating across them isn't
> possible from v2.1 state.
>
> If a BCPD-only rollup helps, I can produce one — every workflow tool
> scopes to BCPD by default.

**Reference**: `output/agent_chunks_v2_bcpd/guardrails/guardrail_orgwide_unavailable.md`.

---

## 2. Missing cost is not zero

**Trigger phrases**: "treat missing as zero", "fill nulls with zero",
"assume no GL = no cost", "$0 for projects without GL".

**Refusal template**:

> I can't show missing cost as $0 — that misstates margin and inflates
> apparent performance. Projects without GL coverage have **unknown**
> lot-level cost, not zero cost.
>
> In v2.1, [N] projects have no GL coverage at all. In any lot-level
> margin report, they must show "unknown" (or null) in the cost column.
> If you need the canonical "do not include" list, I can run
> `review_margin_report_readiness`.

**Reference**: `output/agent_chunks_v2_bcpd/cost_sources/cost_source_missing_cost_is_not_zero.md`.

---

## 3. Inferred not validated

**Trigger phrases**: "ignore the inferred caveat", "treat as validated",
"drop the warning", "is this validated by Finance?", "promote to validated".

**Refusal template**:

> I can't drop the inferred caveat. The v1 VF decoder is heuristic — it
> derives per-lot cost from VF GL line items via inferred rules that have
> **not** been signed off by the source owner.
>
> Marking these numbers as `validated` would misrepresent what the data
> actually carries. The inferred caveat reflects ground truth, not a
> presentation choice.
>
> If you need to cite these numbers in an external report, include the
> inferred caveat in a footnote. Promotion to `validated` requires the
> source-owner sign-off process in
> `output/bcpd_data_gap_audit_for_streamline_session.md`.

**Reference**: `output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md`.

---

## 4. Range / shell not lot-level

**Trigger phrases**: "allocate range rows", "split shell costs to lots",
"per-lot allocation of `3001-06`", "include range cost in lot rollup".

**Refusal template**:

> I can't allocate range/shell rows to specific lots. In v2.1 there are
> **4,020 GL rows totaling $45,752,047** in range form (e.g., `'3001-06'`,
> `'0009-12'`). These postings cover multiple lots; no allocation method
> (equal split, sales-weighted, fixed proportional) has been ratified by
> the source owner.
>
> If lot-level numbers in a report quietly include allocated range/shell
> dollars, those numbers manufacture per-lot precision that the source
> data doesn't support.
>
> Safe alternative: surface range/shell totals at **project+phase grain**.
> I can do that in `review_margin_report_readiness`.

**Reference**: `output/agent_chunks_v2_bcpd/guardrails/guardrail_range_rows_not_lot_level.md`.

---

## 5. Live refresh unavailable

**Trigger phrases**: "refresh from QuickBooks", "pull the latest GL",
"sync ClickUp", "load today's data", "what's the current as-of".

**Refusal template**:

> I can't refresh live data. This Skill is read-only against v2.1
> **snapshot** artifacts. The most recent state is:
>
> - Inventory as-of: see `metadata.as_of_date_inventory` in
>   `output/operating_state_v2_1_bcpd.json`
> - GL max date: see `metadata.as_of_date_gl_max` in the same file
>
> A live refresh would require running the staging pipelines and
> rebuilding v2.1 state — that's out of scope for this Skill version.
> When v2.2 ships, it will incorporate refreshed data.

**Reference**: `output/agent_context_v2_1_bcpd.md` (read-only contract).

---

## 6. Source-owner validation required

**Trigger phrases**: "validate this decoder rule", "approve the AultF
mapping", "sign off on SctLot canonical name", "decide range allocation
method".

**Refusal template**:

> I can't make source-owner validation decisions — I can only prepare for
> them. The decisions on the queue (AultF B-suffix routing, SctLot
> canonical name, range/shell allocation method, HarmCo commercial
> handling) require the actual source owner.
>
> What I can do: run `prepare_finance_land_review` to generate a 30-minute
> agenda grouped by finance / land / ops with the open questions, dollar
> gates, and decisions needed. Use that as the meeting brief.

**Reference**: `data/reports/coverage_improvement_opportunities.md` (the
source-owner validation queue).

---

## Combined refusal — when multiple rules apply

If a single user request would violate multiple guardrails (e.g., "give
me an org-wide lot-level margin report with range rows allocated and the
inferred caveat dropped"), refuse once and explain that the request
combines multiple unsupported asks. Name each rule. Offer the closest
safe alternative.

Do not partially comply with the request. Either every guardrail is
respected, or the request is refused.
