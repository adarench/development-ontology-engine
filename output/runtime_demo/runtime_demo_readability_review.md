# Runtime Demo Readability Review

_Reviewer pass on the six BCPD workflow outputs under `output/runtime_demo/`._
_Audience perspective: a finance / land / ops reader who knows the business
but not the engineering stack. The question on every output: "is this a usable
deliverable, or an engineering artifact?"_

## Summary

| Output | Verdict | Strongest | Weakest |
|---|---|---|---|
| `project_brief_parkway_fields.md` | **ready / light polish** | AultF $4.0M story up-front, inferred caveat explicit | "VF lot grain", "VF SR-suffix" jargon undefined |
| `margin_readiness_bcpd.md` | **ready / light polish** | "missing = unknown, not $0" as the hard rule | "Full-triangle join coverage 37.2%" needs gloss |
| `false_precision_bcpd.md` | **ready** | Numbered six risks with dollar magnitudes per risk | Slight repetition vs change_impact (acceptable) |
| `change_impact_v2_1.md` | **light polish** | Headline table with rows / dollars / confidence per correction | Evidence cites `scratch/vf_decoder_*` files that aren't in the repo |
| `finance_land_review_prep.md` | **ready** | 30-min agenda shape: why → dollar gates → asks by team → decisions | "Standing item" framing for ClickUp is fine but could be sharper |
| `owner_update_bcpd.md` | **ready / light polish** | Honest scope, real bottleneck named, dollars front-and-center | "`is_queryable` gates (only 3/125 phases pass)" — technical phrase a reader may miss |

**Five of six demos are publishable today**, one (`change_impact_v2_1.md`) needs a small evidence-citation fix because it references internal `scratch/` files that aren't in the repo (broken hyperlinks for any reader trying to verify the claims).

## Per-output review

### 1. `project_brief_parkway_fields.md` — **ready / light polish**

**Would finance / land understand it?** Yes. The Identity table is clean (canonical project, entity, phase/lot counts). The cost-basis table is structured. The AultF B-suffix → B1 correction is the headline correction, exactly what a Parkway-Fields-aware reader would want to see.

**Is it too technical?** Mostly no. Two terms a non-engineer might trip over:
- "VF lot grain (2018–2025)" — VF = Vertical Financials, but the reader has to know that.
- "VF SR-suffix (inferred-unknown)" — what does the suffix mean?

**Caveats clear but not overwhelming?** Yes — three bullet caveats, each one operational.

**"Unknown, not zero"?** Not directly tested in this brief (project has cost). The structure could not lie about it.

**Org-wide v2 readiness?** Correctly stated as NOT available in the scope header.

**Inferred clarity?** Strong — `inferred (v1 decoder)` is called out on the cost-basis table heading AND in the caveats.

**Source/evidence?** Four chunks listed at the bottom — sufficient, not overwhelming.

**Reads like a usable deliverable?** Yes — this is the kind of brief a finance lead could put into a phase review packet.

**Recommended copy changes (light)**:
- Expand "VF" to "Vertical Financials (VF)" on first use in the cost-basis table header.
- Add a one-line gloss next to "SR-suffix" the first time it appears: "_SR-suffix = special-rate lots; canonical phase still pending source-owner sign-off._"

**Guardrail risk**: None observed. Inferred caveat lands; org-wide refusal is explicit.

### 2. `margin_readiness_bcpd.md` — **ready / light polish**

**Would accounting understand it?** Yes. The "Hard rule" framing of "missing cost is *unknown*, not $0" is exactly the discipline an accountant needs at the top.

**Is it too technical?** One term needs a gloss: "Full-triangle join coverage 37.2%" — what's a full triangle? (Answer: inventory ↔ GL ↔ ClickUp three-way match.) Without that gloss, the percentage reads as ambient noise.

**Caveats?** Four caveats under "Include WITH caveats" — clear, operational, and each one names a specific guardrail.

**"Unknown, not zero"?** Frontloaded as the **hard rule** and repeated for each no-GL project. Strongest in the suite on this point.

**Org-wide v2 readiness?** Correctly stated as NOT available.

**Inferred clarity?** Yes — both the decoder caveat and the Harmony 3-tuple are surfaced.

**Source/evidence?** Six chunks — slightly too many (mostly per-project caveat chunks that don't add much over the no-GL list above). Could trim to 3-4.

**Reads like a usable deliverable?** Yes — this is the kind of "do not include" checklist an accountant would paste into a closing-week note.

**Recommended copy changes (light)**:
- Add gloss for "Full-triangle join coverage" in the Coverage snapshot table: "_full triangle = lot appears in inventory + GL + ClickUp_".
- Trim retrieval evidence to the top 3 unique-source chunks.

**Guardrail risk**: None. Hard rule states $0 ≠ unknown loudly.

### 3. `false_precision_bcpd.md` — **ready**

**Would finance / leadership understand it?** Yes — the structure is "six risks, ranked by dollar magnitude". A leadership reader scanning quickly gets: $45.75M range/shell at top, $6.75M Harmony, $6.55M SctLot, $4.0M AultF. The numbers tell the story.

**Too technical?** No. The technical detail (3-tuple, MF1 vs B1, decoder) is exactly what the false-precision conversation needs.

**Caveats?** Built into each numbered risk.

**"Unknown, not zero"?** Implicit in #1 (range/shell is not allocatable) and #2 (decoder is inferred).

**Org-wide v2 readiness?** Correctly stated NOT available.

**Inferred clarity?** Excellent — risk #2 is entirely "decoder treated as validated" which is the inferred caveat.

**Source/evidence?** Six chunks — including the SctLot guardrail, range_shell, and inferred decoder. Good coverage.

**Reads like a usable deliverable?** Yes — this is a leadership-grade "where might we be wrong?" memo.

**Recommended copy changes**: none — keep as-is.

**Guardrail risk**: None. Every guardrail surfaces.

### 4. `change_impact_v2_1.md` — **light polish** (one fix is load-bearing)

**Would the auditor or reviewer understand it?** Yes. The headline table is the strongest artifact in the suite — rows, dollar magnitude, confidence label per correction.

**Too technical?** Mostly no. The per-correction notes are short and dense.

**Caveats?** "What did NOT change" section is the right discipline at the end.

**"Unknown, not zero"?** Implicit in range/shell row treatment.

**Org-wide v2 readiness?** Correctly stated NOT available.

**Inferred clarity?** Headline table shows the confidence label for each correction — `inferred (high-evidence)`, `inferred-unknown`, etc. Strong.

**Source/evidence?** Mixed. The retrieval-evidence section at the bottom is fine. **The per-correction `_Evidence:_` lines cite `scratch/vf_decoder_gl_finance_review.md Q2`, `scratch/vf_decoder_ops_allocation_review.md Q1`, etc. — these are internal review files that are not in the repo.** A reader trying to verify a claim will hit a dead end.

**Reads like a usable deliverable?** Yes, with the evidence fix.

**Recommended copy changes**:
- Either include those `scratch/` files in the repo as committed audit notes, or change the cite-pattern to: `_Evidence:_ internal VF decoder review notes (Q2). Available on request from the data team._` That preserves the audit trail without dangling references.

**Guardrail risk**: None observed in content. The risk is *trust* — broken evidence citations weaken the whole report.

### 5. `finance_land_review_prep.md` — **ready**

**Would the three teams understand it?** Yes — each section is grouped by team with clear asks.

**Too technical?** No — the asks are phrased the way a teammate would ask them, not the way an engineer would log them.

**Caveats?** Built into the dollar-gate framing.

**"Unknown, not zero"?** Not directly applicable — this is a meeting agenda, not a report.

**Org-wide v2 readiness?** Correctly stated NOT available in the scope header.

**Inferred clarity?** Yes — "Why this meeting" frames the meeting around promoting inferred → validated.

**Source/evidence?** Five chunks — appropriate for a prep doc.

**Reads like a usable deliverable?** Yes — this is the kind of agenda someone would forward to a calendar invite as-is.

**Recommended copy changes**: none — keep as-is.

**Guardrail risk**: None.

### 6. `owner_update_bcpd.md` — **ready / light polish**

**Would an owner / executive understand it?** Mostly yes — the structure is "scope honest" → "what fixed" → "real bottleneck" → "can/cannot answer".

**Too technical?** Two phrases land slightly engineering-flavored:
- "`is_queryable` gates (only 3/125 phases pass — the rest have partial or missing expected_cost)" — a non-engineer reader sees "is_queryable" as code-shaped jargon.
- "the 2017-03→2018-06 gap-fill" — clear but reads as an internal task name.

**Caveats?** "What CANNOT be answered today" section is the right discipline — owner-grade honesty.

**"Unknown, not zero"?** Implicit in the bottleneck framing.

**Org-wide v2 readiness?** Explicitly stated NOT ready. **The strongest signal on this in the whole suite.**

**Inferred clarity?** Yes — second bullet of "real bottleneck" calls out inferred → validated promotion requirement.

**Source/evidence?** Four chunks — concise.

**Reads like a usable deliverable?** Yes — this is the kind of update an owner could read in 90 seconds and ask one follow-up.

**Recommended copy changes (light)**:
- Replace "`is_queryable` gates (only 3/125 phases pass)" with "_only 3 of 125 phases currently have complete enough expected-cost data to support reliable variance / margin reporting._"
- Replace "2017-03→2018-06 gap-fill" with "the 2017-2018 GL data gap that needs to be backfilled."

**Guardrail risk**: None — org-wide-NOT-ready is the strongest in the suite.

## Cross-cutting observations

1. **All six demos respect the hard guardrails.** Missing-as-unknown, inferred-stays-inferred, range/shell-at-phase-grain, Harmony 3-tuple, SctLot → Scattered Lots, HarmCo X-X commercial, org-wide v2 NOT ready — every guardrail lands somewhere in the suite, sometimes redundantly across docs (intentional: a finance reader who reads margin_readiness AND false_precision should see the same rules from two angles).

2. **The narrative voice is consistent.** "Inferred", "not source-owner-validated", "do not promote", "honest scope", "real bottleneck" — these phrases recur and form a stable operational vocabulary the reader can rely on.

3. **Retrieval-evidence sections are working as intended** but are sometimes longer than they need to be (margin_readiness has 6 entries, several of which duplicate the no-GL project list above). Capping evidence to 3-4 unique-source chunks would tighten the readability.

4. **No demo claims org-wide v2 is ready.** Verified across all six.

5. **Two opportunities for the next pass:**
   - **Glossary**: a one-page `output/runtime_demo/_glossary.md` would let each demo drop jargon glosses inline. Terms to define: VF (Vertical Financials), DR (DataRails), QB (QuickBooks Register), full-triangle, is_queryable, SR-suffix, 3-tuple, range/shell.
   - **Field-level confidence section**: each demo currently mixes project-level (high-confidence) and per-lot (inferred) facts. A small "Confidence boundary" block per demo would make the gradient explicit. (Addressed in the next hardening pass.)

## Verdict

- **Ready as-is**: 3 of 6 (`false_precision_bcpd`, `finance_land_review_prep`)
- **Ready with light polish**: 3 of 6 (`project_brief_parkway_fields`, `margin_readiness_bcpd`, `owner_update_bcpd`)
- **One load-bearing fix**: 1 of 6 (`change_impact_v2_1` — the `scratch/` evidence-file citations break audit trail).

The suite reads as a real deliverable set, not an engineering artifact. The remaining polish is copy work, not architecture.
