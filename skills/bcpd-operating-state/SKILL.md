# SKILL.md — BCPD Operating State

## 1. Skill name

**BCPD Operating State**

Internal slug: `bcpd-operating-state`
Version: pinned to **BCPD v2.1**. A future v2.2 ships as a new Skill version (see §10).

## 2. One-line description

> Read-only workflow tools for briefing, pressure-testing, and explaining the BCPD v2.1 operating state.

## 3. Intended users

| Role | What they get out of it |
|---|---|
| **Finance / accounting** | "Do not include" lists for closing-week margin reports; AultF B-suffix attribution; false-precision audit. |
| **Land / development** | Project briefs with phase / lot / cost-basis tables; decoder validation queue; commercial-parcel isolation. |
| **Ops / data team** | Source-owner validation queue; finance / land / ops review prep; v2.0 → v2.1 change impact. |
| **Executive / owner** | Honest scope update; what v2.1 fixed (dollar magnitudes); what's still blocked. |

Out of scope (intentionally): generic real-estate Q&A, autonomous agent action, anything that mutates source/staged data, anything that requires fresh live-system reads.

## 4. What the Skill can do

1. **Generate Project Brief**
2. **Review Margin Report Readiness**
3. **Find False Precision Risks**
4. **Summarize Change Impact**
5. **Prepare Finance / Land Review**
6. **Draft Owner Update**

(Detailed capability blocks in §6.)

## 5. What the Skill cannot do

- Answer org-wide current actuals (Hillcrest, Flagship Belmont GL ends 2017-02).
- Validate inferred decoder rules (requires source-owner sign-off, not engineering).
- Allocate range/shell GL rows to specific lots (no allocation method ratified).
- Mutate source or staged data of any kind.
- Refresh live source systems (QuickBooks, ClickUp, GL connectors).
- Replace the finance / land review meeting — it can only prepare for it.
- Answer from generic memory when v2.1 BCPD state files are available — must read from state.

## 6. Capability blocks

### 6.1 Generate Project Brief

- **When to use**: a finance lead, land manager, or executive asks for a focused summary of one BCPD project (phases, lot count, cost basis, v2.1 corrections, caveats).
- **Underlying tool**: `core.tools.bcpd_workflows.GenerateProjectBriefTool` (registered as `generate_project_brief` in `ToolRegistry`).
- **CLI command**: `python -m bedrock.workflows.cli project-brief --project "<canonical project name>"`
- **Input arguments**:
  - `project` *(string, required)*: canonical project name (e.g., `"Parkway Fields"`, `"Harmony"`, `"Scattered Lots"`).
- **Sample questions**:
  - "Give me a finance-ready summary of Parkway Fields."
  - "What's the cost basis for Harmony, with caveats?"
  - "Brief me on Scattered Lots — what's the status?"
- **Expected output shape**: markdown with sections: Identity, Cost basis (table, v2.1 inferred), v2.1 corrections affecting this project, Caveats, Confidence boundaries, Retrieval evidence.
- **Caveats / guardrails surfaced**: inferred-decoder warning on per-lot cost, range/shell project+phase grain rule, Harmony 3-tuple discipline note.

### 6.2 Review Margin Report Readiness

- **When to use**: an accountant is preparing a lot-level margin report and needs a "do not include" / "include with caveat" checklist.
- **Underlying tool**: `core.tools.bcpd_workflows.ReviewMarginReportReadinessTool` (`review_margin_report_readiness`).
- **CLI command**: `python -m bedrock.workflows.cli margin-readiness --scope bcpd`
- **Input arguments**:
  - `scope` *(string, default `"bcpd"`)*: reporting scope.
- **Sample questions**:
  - "Which BCPD projects should I be careful including in a lot-level margin report this week?"
  - "Is the cost basis safe to put in a per-lot margin model?"
  - "What's the right way to handle the no-GL projects in this week's close?"
- **Expected output shape**: hard rule (missing = unknown, never $0), no-GL projects list, range/shell warning, include-with-caveats list, coverage snapshot, confidence boundaries table.
- **Caveats / guardrails surfaced**: missing-is-unknown-not-zero (hard rule), range/shell at project+phase grain only, inferred decoder, Harmony 3-tuple, SctLot → Scattered Lots, HarmCo X-X commercial isolation.

### 6.3 Find False Precision Risks

- **When to use**: a finance lead or executive asks where current BCPD reports may be giving false precision — i.e., where lot-level numbers manufacture certainty the source data doesn't support.
- **Underlying tool**: `core.tools.bcpd_workflows.FindFalsePrecisionRisksTool` (`find_false_precision_risks`).
- **CLI command**: `python -m bedrock.workflows.cli false-precision --scope bcpd`
- **Input arguments**:
  - `scope` *(string, default `"bcpd"`)*: scope of the audit.
- **Sample questions**:
  - "Where might our current reports be giving false precision?"
  - "What numbers are we citing too precisely?"
  - "Audit our lot-level cost basis for false precision."
- **Expected output shape**: six numbered risks ranked by dollar magnitude (range/shell $45.75M, decoder inferred, Harmony 3-tuple $6.75M, SctLot $6.55M, HarmCo X-X, AultF B-suffix $4.0M), confidence boundaries table.
- **Caveats / guardrails surfaced**: all of the v2.1 hard rules, in one place.

### 6.4 Summarize Change Impact

- **When to use**: an auditor, reviewer, or new team member asks what changed between v2.0 and v2.1, and what dollar magnitudes attach to each correction.
- **Underlying tool**: `core.tools.bcpd_workflows.SummarizeChangeImpactTool` (`summarize_change_impact`).
- **CLI command**: `python -m bedrock.workflows.cli change-impact`
- **Input arguments**:
  - `from_version` *(string, default `"v2.0"`)*
  - `to_version` *(string, default `"v2.1"`)*
- **Sample questions**:
  - "What changed in v2.1 that affects prior views?"
  - "Walk me through the v2.0 → v2.1 corrections with dollar magnitudes."
  - "What did v2.1 fix?"
- **Expected output shape**: headline table (correction, rows, dollars, confidence), per-correction notes (with humanized evidence citations), "what did NOT change" section.
- **Caveats / guardrails surfaced**: corrections remain inferred until source-owner sign-off; org-wide v2 still unavailable; range/shell allocation still pending.

### 6.5 Prepare Finance / Land Review

- **When to use**: an ops or data lead needs an agenda for a 30-minute review with finance, land/development, and ops to drive source-owner validation forward.
- **Underlying tool**: `core.tools.bcpd_workflows.PrepareFinanceLandReviewTool` (`prepare_finance_land_review`).
- **CLI command**: `python -m bedrock.workflows.cli meeting-prep --scope bcpd`
- **Input arguments**:
  - `scope` *(string, default `"bcpd"`)*.
- **Sample questions**:
  - "Prepare me for a finance and land review."
  - "What should we ask each team in the next source-owner sync?"
  - "Build me a 30-min agenda for the v2.2 validation meeting."
- **Expected output shape**: why-this-meeting section, dollar gates (anchors), finance / land / ops grouped asks, decisions needed by end of meeting, retrieval evidence.
- **Caveats / guardrails surfaced**: source-owner sign-off is the bottleneck (not engineering); range/shell allocation method pending; SctLot canonical name pending.

### 6.6 Draft Owner Update

- **When to use**: an exec or owner asks for a concise honest update on BCPD operating state — what's working, what's blocked, and what's NOT yet available.
- **Underlying tool**: `core.tools.bcpd_workflows.DraftOwnerUpdateTool` (`draft_owner_update`).
- **CLI command**: `python -m bedrock.workflows.cli owner-update --scope bcpd`
- **Input arguments**:
  - `scope` *(string, default `"bcpd"`)*.
- **Sample questions**:
  - "Draft an owner update for BCPD."
  - "Give me a one-page honest exec update on where we are."
  - "What should I tell the owner about v2.1 state?"
- **Expected output shape**: scope (honest), what v2.1 fixed (dollar magnitudes), the real bottleneck, what can / cannot be answered today.
- **Caveats / guardrails surfaced**: explicitly states org-wide v2 is NOT ready; names what cannot be answered (org-wide rollups, range/shell lot allocation, "is this validated"); points to data-gap audit for open items.

## 7. Guardrails (must be enforced)

All eight v2.1 hard rules. The Skill is required to respect every one of these in every response, regardless of user phrasing:

1. **Missing cost is unknown, never zero.** Projects without GL coverage have unknown lot-level cost; reports must show "unknown" or null, never $0.
2. **Inferred decoder mappings remain inferred** until source-owner validation. The v1 VF decoder is heuristic; per-lot cost it produces is `inferred (high-evidence)` at best.
3. **Range / shell rows stay project+phase grain** unless an allocation method has been approved. $45,752,047 / 4,020 GL rows live in range form (`'3001-06'`, `'0009-12'`); no allocation method has been ratified.
4. **Harmony joins require the 3-tuple** `(canonical_project, canonical_phase, canonical_lot_number)`. Flat `(project, lot)` joins double-count by ~$6.75M.
5. **SctLot is Scattered Lots, not Scarlet Ridge.** v2.0 silently inflated Scarlet Ridge by $6,553,893; v2.1 separates SctLot as its own canonical project.
6. **HarmCo X-X is commercial / non-residential.** 205 rows of HarmCo X-X parcels are commercial pads; exclude from per-lot residential rollups.
7. **Org-wide v2 is unavailable.** BCPD, BCPBL, ASD, BCPI are in scope. Hillcrest and Flagship Belmont have no GL after 2017-02; org-wide rollups are not possible.
8. **VF is cost-basis / asset-side**, not a balanced trial balance. Never present as TB.

Plus the meta-rule: **Read-only only.** No writes to source or staged data. The seven protected v2.1 files (state JSON, agent context, state quality report, change log, coverage opportunities, crosswalk audit, decoder report) must be byte-identical before and after any Skill invocation. Verified by `tests/test_bcpd_workflows.py::test_workflow_tools_did_not_modify_protected_files`.

## 8. Refusal behavior

Examples of how the Skill should refuse or caveat. (Full refusal templates in `prompts/refusal_patterns.md`.)

| User says | Skill response pattern |
|---|---|
| "Give me org-wide actuals across BCPD and Hillcrest." | **Refuse.** State that org-wide v2 is unavailable because Hillcrest / Flagship Belmont GL ends 2017-02. Offer BCPD-scoped rollup instead. |
| "Just allocate range rows to lots anyway — pick an even split." | **Refuse.** Range/shell rows are project+phase grain; no allocation method is signed off. Offer to surface the totals at project+phase grain. |
| "Ignore the inferred caveat for this report." | **Refuse.** The inferred caveat reflects what's true about the data, not a presentation choice. Surface alternative: include cost with the caveat in a footnote. |
| "Treat missing costs as zero." | **Refuse.** Missing cost is unknown, not zero. Show as `unknown` / null. |
| "Is the per-lot decoder cost validated by Finance?" | **Answer honestly: NO.** Decoder rules ship as `inferred`. Validation is pending source-owner sign-off (see meeting-prep tool). |
| "Refresh the GL from QuickBooks." | **Refuse.** This Skill is read-only against v2.1 snapshot artifacts. Live refresh is out of scope for this Skill version. |

## 9. State / bundle requirements

The Skill is **read-only** — it operates on snapshot artifacts. The bundle answers the question "what does the Skill need to run?"

### Bundle (small, deterministic — required at runtime)

| Path | Approx size | Why bundle |
|---|---|---|
| `output/operating_state_v2_1_bcpd.json` | ~4.7 MB | Canonical v2.1 state — every tool reads it. |
| `output/agent_chunks_v2_bcpd/` (46 chunks) | ~250 KB total | Retrieval source for chunk + routed retrievers. |
| `output/agent_context_v2_1_bcpd.md` | ~10 KB | Hard rules + citation patterns. |
| `output/state_quality_report_v2_1_bcpd.md` | ~12 KB | Per-project coverage + open questions. |
| `data/reports/v2_0_to_v2_1_change_log.md` | ~16 KB | Change-impact tool reads this. |
| `data/reports/coverage_improvement_opportunities.md` | ~20 KB | Source-owner validation queue (meeting-prep). |
| `output/bcpd_data_gap_audit_for_streamline_session.md` | ~14 KB | Open-items framing (meeting-prep + owner-update). |

**Total bundle**: ~5 MB. Fits comfortably as a Skill archive payload.

### Excluded (do NOT bundle)

- Raw source CSVs (`Collateral Dec2025 01 Claude.xlsx - *.csv`, `LH Allocation 2025.10.xlsx - *.csv`, etc.) — bulk; raw; the v2.1 state was already built from them.
- `output/bedrock/entity_index.parquet`, `embeddings_cache.parquet` — regenerable; workflow tools do not use them.
- `data/staged/*.parquet` — pre-staged canonical tables; workflow tools read from `operating_state_v2_1_bcpd.json` instead.
- `data/raw/`, `data/_unzip_tmp/`, `data/processed/` — already gitignored.
- Any `.env` or credentials file.

The full state details are in `state/README.md`.

## 10. Versioning

This Skill is **pinned to BCPD v2.1**. The pin is enforced two ways:

1. The bundled `output/operating_state_v2_1_bcpd.json` carries `schema_version: "operating_state_v2_1_bcpd"`. Tools read this and would error on a mismatch.
2. The Skill's `state/README.md` and packaging checklist record the sha256 of every bundled file. A drift check at packaging time confirms the Skill ships the exact snapshot it claims to ship.

When **BCPD v2.2 ships** (after the source-owner validation queue clears):
- Ship as a **new Skill version** — `BCPD Operating State v2.2`. Do not silently upgrade the v2.1 Skill.
- v2.1 Skill remains available so prior reports / audits can be reproduced.
- The capability surface (6 tools) stays the same — only the state and version pin change.

## 11. Cross-references

- Runtime code: `core/tools/bcpd_workflows.py` (6 Tool subclasses)
- CLI: `bedrock/workflows/cli.py`
- Demos: `output/runtime_demo/*.md`
- Glossary: `output/runtime_demo/_glossary.md`
- Packaging plan (full design brief): `docs/bcpd_claude_skill_packaging_plan.md`
- Tests: `tests/test_bcpd_workflows.py` (31 content + read-only), `tests/test_route_retrieval.py` (45 routing)

## 12. What this manifest is NOT

- Not duplicated runtime code. The Skill loads / invokes the existing `core/tools/bcpd_workflows.py` rather than re-implementing tools.
- Not a separate agent loop. The existing `core/agent/registry.py` + `LLMAgent` is the dispatcher.
- Not a refresh / live-system surface. Snapshot-only.
- Not a write-capable interface. Read-only by construction; enforced by tests.
