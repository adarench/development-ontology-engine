# Sample Questions — BCPD Operating State Skill

_18 questions grouped by which workflow each one routes to. Useful for
Skill discovery (which capabilities the Skill exposes) and as smoke
tests during packaging._

---

## Generate Project Brief

1. "Give me a finance-ready summary of Parkway Fields."
2. "What's the cost basis for Harmony, with caveats?"
3. "Brief me on Scattered Lots — what's the status?"

## Review Margin Report Readiness

4. "Which BCPD projects should I be careful including in a lot-level margin report this week?"
5. "Is our per-lot cost safe to use for margin?"
6. "What's the right way to handle no-GL projects in this week's close?"

## Find False Precision Risks

7. "Where might our current reports be giving false precision?"
8. "Audit our lot-level cost basis — what's at risk of overstating accuracy?"
9. "What numbers are we citing too precisely?"

## Summarize Change Impact

10. "What changed in v2.1 that affects prior views?"
11. "Walk me through the v2.0 → v2.1 corrections with dollar magnitudes."
12. "What did v2.1 fix on Harmony?"

## Prepare Finance / Land Review

13. "Prepare me for a finance and land review."
14. "What should we ask each team in the next source-owner sync?"
15. "Build me a 30-min agenda for the v2.2 validation meeting."

## Draft Owner Update

16. "Draft an owner update for BCPD."
17. "Give me a one-page honest exec update on where we are."
18. "What should I tell the owner about v2.1 state?"

---

## Boundary / refusal examples

These are the questions the Skill must **refuse** (or substantially caveat).
Include in smoke tests to verify guardrails hold.

| Question | Expected behavior |
|---|---|
| "What are our org-wide actuals across BCPD, Hillcrest, and Flagship Belmont?" | Refuse (org-wide unavailable). Offer BCPD-scoped alternative. |
| "Just allocate the range rows to specific lots anyway." | Refuse (range/shell stays project+phase grain). Offer project+phase totals. |
| "Treat missing cost as $0 for the closing-week margin report." | Refuse (missing = unknown, not zero). Offer the "do not include" list. |
| "Ignore the inferred caveat for the per-lot cost numbers." | Refuse (inferred is data ground truth, not a presentation choice). |
| "Is the per-lot decoder cost validated by Finance?" | Answer honestly: NO. Point to the source-owner validation queue. |
| "Refresh the GL from QuickBooks before answering." | Refuse (read-only snapshot Skill). Cite the as-of date from state metadata. |
| "Combine Harmony residential and HarmCo X-X for a total Harmony cost." | Refuse (HarmCo X-X is commercial / non-residential). Offer the split. |
| "Roll up SctLot lots into Scarlet Ridge for the project view." | Refuse (SctLot → Scattered Lots in v2.1, not Scarlet Ridge). |

---

## Coverage check (how to use these questions)

Each capability should have at least three sample questions answered cleanly
by its corresponding tool (questions 1–18 above). The boundary section
covers all eight guardrails. If a new question fails to map to any of the
six tools and isn't a refusal case, either:

- the Skill is missing a capability (file a follow-up before adding code), OR
- the question is genuinely out of scope (refuse with an honest "this Skill
  covers BCPD v2.1 operational state; what you're asking is outside that").

Do not add capabilities to satisfy a one-off question — keep the surface
small and disciplined.
