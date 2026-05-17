# Types of Human Involvement

A classification of how humans participate in the system, plus what each type requires the system to support.

## Type 1 — Inline approval during a run
**What:** Mid-run, the system pauses and asks "is this assumption okay?"
**Example:** "I'm going to estimate phase IDs from lot-number gaps. Proceed?"

**System needs**
- Tools can pause and resume.
- A standard prompt format: assumption, default, options.
- Remember "always allow this" per user.
- Whatever the user picks is recorded with the answer.

## Type 2 — Providing data the system can't infer
**What:** A human types in a number the system has no way to know.
**Example:** Projected sales price, warranty budget, official lot count from the land team.

**System needs**
- A clear input surface, separate from automated extracts.
- Versioned values with dates and a named owner.
- Treat manual inputs as a source with provenance, just like a file.
- Default to refusing until the input exists — never substitute a zero.

## Type 3 — Source-owner sign-off
**What:** A named expert confirms an inferred rule is correct → confidence is promoted.
**Example:** "Yes, Harm3 lot 1034 really means Phase A10 Lot 44."

**System needs**
- A queue of open rules with evidence and dollar impact.
- Every rule tracks who validated it and when.
- If the underlying data changes, validation expires.
- Promotion regenerates affected outputs.

## Type 4 — Picking a policy
**What:** Multiple valid answers exist; a human picks one for everyone.
**Example:** How to spread $45.75M of shell costs — equal split? sales-weighted?

**System needs**
- A separate policy registry (not crosswalks, not rules).
- Easy to change; outputs say which policy version produced them.
- Big-money policy changes show a before/after diff before they apply.

## Type 5 — Disambiguating new or unclear values
**What:** A new source value appears; the system asks "which canonical does this map to?"
**Example:** A new ClickUp subdivision name, a new GL project code, a new lot suffix.

**System needs**
- Pipeline flags new unmatched values automatically.
- Suggests top candidate mappings with reasoning.
- "Leave unmapped for now" is a valid choice.
- Decisions become new crosswalk rows.

## Type 6 — Overriding a refusal
**What:** A user with authority says "produce it anyway, with labels."
**Example:** Org-wide rollup that mixes 2017 and 2025 data, knowingly.

**System needs**
- Refusal is the default; override requires permission.
- Overrides log who, when, and stamp the output with a stronger caveat.
- Some refusals are *not* overridable (e.g., flat Harmony join — it's wrong, not just risky).

## Type 7 — Monthly review and signoff
**What:** A scheduled cycle: someone prepares a report, someone reviews, someone signs off.
**Example:** Monthly cost-by-phase report for accounting.

**System needs**
- Roles: preparer, reviewer, approver.
- Report has a state: draft → in review → approved → published.
- Built-in diff vs last month so the reviewer knows what to look at.
- Signoff is immutable; reruns produce a new version.

## Type 8 — Feedback after publishing
**What:** A user says "this number looks wrong" after the fact.
**Example:** "Lewis Estates Q2 cost is off."

**System needs**
- Feedback is captured as data, not as a direct edit to tools.
- Each item links to the output, the tool, and the source rows.
- Triage queue: who handles it, by when.
- If feedback becomes a rule change, it flows through Type 3.

## Type 9 — Naming owners
**What:** Every tool, rule, source, and input has a named human who owns it.
**Example:** Corey owns warranty; finance owns the GL re-export.

**System needs**
- A registry of who owns what.
- Items without an owner are flagged.
- Routing for Types 3–6 uses this registry to find the right person.

## Type 10 — Access control
**What:** Decide who can use which tools and see which outputs.
**Example:** Accounting lead gets the allocation tool; external lender sees a redacted collateral view.

**System needs**
- Tools and outputs are visible per-user, not always to everyone.
- Sensitive fields can be redacted.
- Access is logged.
- Real identities — this only matters once hosting is shared.

---

## What this adds up to across the system

A few capabilities show up over and over:

1. **A queue/inbox subsystem.** Types 3, 5, 6, 7, 8 are all "things waiting for a human."
2. **Human decisions as provenance.** Every approval, override, and signoff is recorded the same way file sources are.
3. **No silent confidence boosts.** Promotion always points to a person and a timestamp.
4. **Auto-regenerate on decisions.** When a human changes something upstream, dependent outputs rebuild or get marked stale.
5. **Two kinds of refusal.** Policy refusals (overridable) vs correctness refusals (not).
6. **Real identity.** Required the moment more than one person uses the system.
7. **Diffs for big decisions.** Anything that moves dollars shows before/after first.
8. **A schedule engine.** Monthly cycles need to fire on their own.

Priority order if you're building these: **queue + human-decision provenance + identity** first. Everything else sits on top.
