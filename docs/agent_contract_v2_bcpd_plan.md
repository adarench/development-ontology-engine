# Agent Contract v2 (BCPD) — Plan

**Owner**: Terminal A
**Status**: planning, pre-implementation
**Parent**: `docs/bcpd_state_quality_pass_plan.md` W4
**Last updated**: 2026-05-01

## Goal

`output/agent_context_v2_bcpd.md` describes — in prose — what the BCPD v2 state can answer, what it cannot, how to cite, and what the hard limits are. That document is good for a human onboarding to the data, but it is not a **contract** an agent layer can be evaluated against.

This plan defines a formal contract — `output/agent_contract_v2_bcpd.md` — that:

- Categorizes every plausible question the agent will get into **allowed**, **caveated**, or **refused**.
- Specifies the exact citation format for each answer.
- Codifies the confidence rules (when to say `high`, when to qualify, when to refuse).
- Encodes the "missing is not zero" rule.
- Encodes the cost-source hierarchy rule (which source wins when two could answer the same question).
- Provides refusal templates so refusals are explicit, not evasive.

Treat this as the authoritative spec the agent layer must satisfy. `output/agent_context_v2_bcpd.md` becomes the human-facing version; `agent_contract_v2_bcpd.md` becomes the machine-checkable version.

## Hard guardrails

1. **Do not invent.** Every fact the agent emits is grounded in a source row.
2. **Missing is not zero.** Lots / projects / years with no data return `null` and a refusal explanation, never `0`.
3. **Citation is mandatory.** Every numerical claim in an agent answer carries a source-file citation per the rules below.
4. **Confidence is mandatory.** Every claim carries a confidence label inherited from the underlying canonical row's `source_confidence`.
5. **Refuse cleanly.** Refusal templates are explicit and reference the relevant gap by name.

## Question taxonomy

The contract divides agent questions into three categories. Examples below, not exhaustive.

### A. Allowed (high-confidence answer, normal citation)

Questions whose underlying data is `high` confidence and complete enough that the agent can answer directly. Each row pairs the question pattern with the source it must cite.

| question pattern | answerable from | citation requirement |
|---|---|---|
| BCPD lot inventory at 2026-04-29 by project / phase / status | `staged_inventory_lots.parquet` | cite `Inventory _ Closing Report (2).xlsx` and as_of date |
| BCPD project-level cost 2018–2025 by project / account | `staged_gl_transactions_v2.parquet` filtered to VF rows for BCPD | cite `Vertical Financials 46-col` and the project_code |
| BCPD project-level cost 2016-02 → 2017-02 by project | `staged_gl_transactions_v2.parquet` filtered to DR rows for BCPD, **post-dedup** | cite `DataRails 38-col post-dedup` and the project_code |
| BCPD lot lifecycle stage for the 2,797 BCPD-built lots | derived from `Lot Data` via v1 waterfall | cite `Collateral Dec2025 - Lot Data.csv` and the waterfall rule |
| BCPD CollateralSnapshot at 2025-12-31 (or 2025-06-30) | `Collateral Dec2025 - Collateral Report.csv` (and PriorCR for 2025-06-30) | cite the report file and as_of |
| BCPD allocation/budget for Lomond Heights or Parkway Fields phases | `LH Allocation 2025.10.xlsx` / `Parkway Allocation 2025.10.xlsx` | cite the workbook + sheet |

### B. Caveated (answer with required disclosure)

Questions the agent CAN answer, but the answer must include a specific disclosure in the same response. The disclosure is part of the contract, not a footnote.

| question pattern | required disclosure |
|---|---|
| BCPD lot-level cost for Harmony / Lomond Heights / Parkway Fields | "Lot match rate is 53.7% / 43.9% / 61.5%; some VF lot codes encode phase+lot together and have not been decoded in v0. The reported number reflects only matched lots." |
| Cross-era BCPD project rollup (2016-17 + 2018+) | "Per-project totals are reported separately for the two eras. There is a 15-month gap (2017-03 → 2018-06) with zero rows for any entity." |
| Per-lot cost using ClickUp data | "ClickUp lot tagging is sparse (~21% of all tasks). Returned values cover only the 1,091 distinct lot-tagged lots; coverage is 49.2% on active inventory." |
| 2025 BCPD vendor analysis | "Vendor data lives only in the QB register, which uses a different chart of accounts than DR/VF. Tie-out only; do not aggregate against VF." |
| Phase-level cost rollup | "Phase column is 0% filled in GL. Phase rollups derive from inventory + Lot Data + 2025Status + ClickUp; some phase IDs are inferred." |
| Project-level cost where a project has VF rows but inventory shows it as confidence=low | "This project's inventory rows are pre-2018 historical (low confidence). Cost is reported but should not be compared against active-project metrics." |

### C. Refused (no answer; explicit refusal with template)

Questions the agent must not answer because the data is structurally absent. Refusal templates ensure refusals are clear.

| question pattern | refusal template |
|---|---|
| Org-wide actuals across BCPD + Hillcrest + Flagship Belmont | "Org-wide v2 is blocked: Hillcrest Road at Saratoga LLC and Flagship Belmont Phase two LLC have GL data only through 2017-02. A fresh GL pull covering 2017-03 onward for those entities is required. v0 is BCPD-only by design." |
| BCPD spend in 2017-03 → 2018-06 | "This is a documented GL gap: zero rows exist for any entity between 2017-03-01 and 2018-06-25. The gap cannot be reconstructed from current data; a fresh GL pull covering this window is needed." |
| Per-lot cost for Ammon / Cedar Glen / Eagle Vista / Eastbridge / Erda / Ironton / Santaquin Estates / Westbridge / Lewis Estates | "[Project] has no GL coverage in the current dump. Lot inventory is known but cost is unknown. Do not estimate — see `data/reports/join_coverage_v0.md` and `output/state_quality_report_v2_bcpd.md`." |
| Vendor / cash / AP analysis outside 2025 BCPD | "Vendor data lives only in the QB register, which covers BCPD 2025 only. Pre-2025 vendor analysis is not supported by current data." |
| Per-lot allocation/budget for projects other than Lomond Heights or Parkway Fields | "Budget data is populated only for Lomond Heights and Parkway Fields. Flagship Allocation Workbook v3 has the framework for other projects but the cells are mostly empty. Do not estimate." |
| Anything based on confidence=`unmapped` rows | "This row's source vocabulary did not resolve to a canonical entity (`unmapped`). The original source value is preserved for traceability but cannot be aggregated. See `data/reports/crosswalk_quality_audit_v1.md` (when available)." |

## Citation rules (mandatory in every answer)

Every numerical claim in an agent answer must include:

1. **Source schema or file** — e.g. `Vertical Financials 46-col`, `staged_inventory_lots.parquet`, `Collateral Dec2025 - Lot Data.csv`.
2. **Confidence label** — `high` / `medium` / `low` / `inferred`.
3. **Scope qualifier** — entity (BCPD), period (2018-2025), and any filter applied (e.g. "post-dedup", "lot-tagged subset only").
4. **Row count or coverage qualifier** — e.g. "across 26,258 rows" or "covers 60% of inventory lots for this project".

Example correct citation:

> **Per Vertical Financials 46-col (high confidence)**, BCPD 2018–2025 cost basis for Parkway Fields is **$147.2M** across **43,254 rows**. Lot-match rate to inventory is 61.5% (some VF lot codes are phase-encoded and undecoded in v0).

Example INCORRECT citation (would violate the contract):

> Parkway Fields cost is $147.2M.

## Confidence rules

Confidence labels in the answer must come from the underlying canonical row's `source_confidence` (worst-link semantics). If the answer aggregates multiple rows, the answer's confidence is the **min** across contributing rows.

| canonical row confidence | how to phrase |
|---|---|
| `high` | "Per [source] (high confidence), …" |
| `medium` | "Per [source] (medium confidence — single-source / typo correction / partial coverage), …" |
| `low` | "Per [source] (low confidence — historical only / pre-2018 / unmapped subdivision), …" |
| `inferred` | "Inferred via [rule], not source-owner-validated. Treat as estimate, not fact." |
| `unmapped` | Refuse per the unmapped-row template above. |

## "Missing is not zero" rule

When a query asks for a numeric quantity (cost, lots, value) and the underlying data has no rows, the agent returns `null` (or "no data") and explains why. It must NOT return `0`.

Examples:

- "What was BCPD spend in May 2017?" → "No data — this falls in the documented 2017-03 → 2018-06 gap."
- "What is Lewis Estates' actual cost?" → "Unknown — Lewis Estates has 0 GL rows in current data; estimating would be misleading."
- "How many BCPD vendors paid in 2018?" → "Unknown — vendor data lives only in QB register, which covers 2025 only."

The contract enforces this by requiring every numeric answer to also report the source row count. A row count of 0 plus a non-zero numeric is an automatic contract violation.

## Cost-source hierarchy rule

When two GL sources could answer the same cost question, the contract specifies which wins.

| period | scope | preferred source | fallback | never |
|---|---|---|---|---|
| 2016-02 → 2017-02 | BCPD project-level cost | DataRails 38-col **post-dedup** | — | DR raw (would be 2.16× multiplied) |
| 2017-03 → 2018-06 | any | (refuse) | — | any source — gap |
| 2018-06 → 2025-12 | BCPD project-level cost | Vertical Financials 46-col | — | QB register (different chart) |
| 2025 (BCPD only) | vendor / cash / AP | QB register | — | VF (no vendor field) |
| 2025 (BCPD only) | project / account-level cost | Vertical Financials 46-col | — | QB register (would double-count if combined) |

When the agent reports a cross-era number (e.g. all-time Parkway Fields cost), it must report the two eras separately and explicitly note the gap.

## Refusal mechanics

Refusals are explicit messages, not silent failures. Each refusal includes:

1. **What was asked**, restated briefly.
2. **Why it cannot be answered**, citing the relevant artifact (`join_coverage_v0.md`, `state_quality_report_v2_bcpd.md`, `guardrail_check_v0.md`).
3. **What would unblock it**, if anything (e.g. "fresh GL pull for entity_code=2000 from 2017-03-01 onward").
4. **Optionally**, a related question the agent CAN answer (e.g. "I can report 2018-2025 Parkway Fields cost from VF.")

## Outputs (post-approval)

`output/agent_contract_v2_bcpd.md` — a single document with:

1. Question taxonomy (Allowed / Caveated / Refused tables).
2. Citation rules.
3. Confidence rules.
4. Missing-is-not-zero rule.
5. Cost-source hierarchy.
6. Refusal templates.
7. A 5-minute test suite: 10–15 example questions, the expected category, the required citation, and an example correct answer.

This document does NOT replace `output/agent_context_v2_bcpd.md` — both ship. The context doc is the prose introduction; the contract doc is the spec.

## Validation requirements

- Every Allowed question pattern must be answerable from a named existing artifact.
- Every Caveated question pattern's required disclosure must reference a specific gap or limitation in the existing artifacts.
- Every Refused question pattern's refusal template must name the unblocking condition.
- The 5-minute test suite must include at least one example from each of the three categories.

## Out of scope

- Building the agent layer itself. This is the contract; not the implementation.
- Modifying `output/agent_context_v2_bcpd.md`. The contract is additive.
- Defining the embedding / retrieval scheme for chunks (that's W5).
