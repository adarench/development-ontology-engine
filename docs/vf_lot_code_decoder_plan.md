# VF Lot-Code Decoder — Plan

**Owner**: Terminal A (or designated worker)
**Status**: planning, pre-implementation
**Parent**: `docs/bcpd_state_quality_pass_plan.md` W1
**Last updated**: 2026-05-01

## Goal

Vertical Financials (VF) `lot` values for some BCPD projects encode **phase + lot** in a single string, while inventory carries phase and lot in separate columns. The v0 normalizer (`measure_join_coverage_v0._norm_lot`) only strips whitespace, trailing `.0`, and leading zeros — it does not decode phase prefixes. Result: lot-match rates are 44–62% for affected projects (Harmony, Lomond Heights, Parkway Fields).

This plan investigates whether VF lot codes encode phase + lot under a project-specific rule, and produces a decoder rule set that can lift those match rates substantially.

## Hypothesis (to test, not assume)

For some VF project codes, the `lot` field is a 4-digit string of the form `PXLL` where `PX` encodes phase (1–9) and `LL` is the 2-digit lot number within phase. Example from the review memo:

> Harmony VF lot `1034` likely = Harmony Phase 3 Lot 34 (inventory has Phase A7 / Lot 34).

This is **one specific candidate pattern**. Other candidates per project:

- 4-digit `PXXX` where `P` is phase and `XXX` is lot (no zero padding).
- 4-digit numeric where 1st digit = phase, last 3 = lot.
- 5-digit `PPLLL` where the first 1–2 chars are phase and the remainder is lot.
- Alpha prefix (`A1`, `A7`, `B2`) where the alpha part is phase.
- VF project_code suffix already carries the phase (`Harm3` = Phase 3); in that case the lot field IS already just the lot, but the inventory uses a different phase identifier (e.g. inventory `Phase A7` = VF `Harm3`).

**The hypothesis is project-specific.** Do not assume a single rule applies globally. Profile each affected VF project independently.

## Scope

### In scope (BCPD VF projects with sub-100% match rates per `data/reports/join_coverage_v0.md`)
- Harmony (53.7%) — VF codes Harm3 / HarmCo / HarmTo
- Lomond Heights (43.9%) — VF codes LomHS1 / LomHT1
- Parkway Fields (61.5%) — VF codes AultF / PWFS2 / PWFT1
- Arrowhead Springs (65.0%) — VF codes ArroS1 / ArroT1
- Scarlet Ridge (90.9%) — VF codes ScaRdg / SctLot — already high; investigate only the missing 9.1%
- Salem Fields (100%) — already complete; **out of scope**
- Willowcreek (100%) — already complete; **out of scope**

### Out of scope (structural gaps — no decoder will help)
- Lewis Estates (0% — no GL data at all)
- The 7 active BCPD projects with no GL coverage (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge)
- DataRails 38-col `Lot/Phase` field (combined lot/phase, but already accounted for in v0 — separate decoder concern, not VF-specific)
- Hillcrest and Flagship Belmont (org-wide blocked)

## Investigation methodology

### Step 1 — Per-VF-project profiling
For each VF project_code in scope, produce a profile:

- Distinct lot values, their lengths (4-digit / 5-digit / alpha prefix?), and frequency.
- Min/max numeric value if numeric.
- Distinct **inventory** phases for the same canonical_project (e.g. Harmony inventory phases: A6, A7, B1, …).
- Cross-tabulate VF lot prefix vs inventory phase — does a clean mapping appear?

### Step 2 — Pattern hypothesis per project
For each VF project, propose 1–3 candidate decoder rules. Examples:

- **Harmony / Harm3**: hypothesis: VF `1034` = lot `34` in inventory phase that maps to VF code `Harm3`. Decoder: `(VF code, VF lot) → (canonical_project, canonical_phase, canonical_lot_number)`.
- **Lomond Heights / LomHS1**: similar, where `S1` in the project_code already denotes Phase S1 (SFR), and the lot field is the lot within S1.
- **Parkway Fields / PWFS2**: `S2` denotes Phase 2 SFR; lot field is lot within Phase 2.

### Step 3 — Validation per rule
For each candidate decoder rule, validate against inventory:

- Apply the rule to every VF lot for that project.
- Count how many decoded `(project, phase, lot)` triples match an inventory row.
- Compare to baseline (no decoder).
- Compute confidence:
  - **`high`** if ≥90% of decoded rows match inventory rows AND the rule is unambiguous.
  - **`medium`** if 60–90% match.
  - **`low`** if <60% — rule is wrong or covers only a sub-pattern.
  - **`inferred`** is the default label; promote only after source-owner validation.

### Step 4 — Per-project decoder rule selection
Pick the best rule per project. If two rules tie, prefer the simpler one. If no rule clears 60%, document as "no clean decoder; coverage stays at baseline".

### Step 5 — Edge cases
- Lots in VF that have no matching inventory phase even after decoding — flag as VF-only.
- Lots in VF whose decoded value still doesn't match any inventory row — flag as "decoded but unmatched"; could be VF lot codes that don't follow the rule.
- Lots with non-numeric components (e.g. `1034A`) — handle alpha suffix preservation.

## Decoder rule format

The decoder is a small lookup table, not a regex tower. Per row:

| field | type | meaning |
|---|---|---|
| `vf_project_code` | string | Source VF project_code (e.g. `Harm3`, `LomHS1`). |
| `decoder_rule_name` | string | Short identifier (e.g. `harmony_4digit_phase_prefix`). |
| `decoder_pattern` | string | Plain-language description of the rule. |
| `parsed_phase_canonical` | string | The canonical phase in inventory that this VF code maps to. |
| `lot_extraction` | string | How to extract the lot number from the VF lot field (e.g. "last 2 digits", "drop first digit"). |
| `confidence` | enum | `inferred` / `medium` / `high` |
| `evidence_match_rate` | float | % of VF rows for this code that produce an inventory match after decode. |
| `rows_matched` | int | Absolute count of matched VF rows. |
| `rows_total` | int | Total VF rows for this code. |
| `validated_by_source_owner` | bool | Default false; flips true only with explicit human sign-off. |
| `notes` | string | Edge cases, ambiguities, etc. |

## Outputs (post-approval)

- `data/staged/vf_lot_code_decoder_v0.csv` — the decoder rule table above.
- `data/reports/vf_lot_code_decoder_report.md` — narrative covering:
  - Per-project profile (Step 1).
  - Per-project hypothesis + candidate rules (Step 2).
  - Per-rule validation (Step 3) with match rates.
  - Selected rules (Step 4).
  - Edge cases and decoded-but-unmatched lots (Step 5).
  - Coverage delta if these rules were applied to the join (forwarded to W3).

The decoder is a **lookup**, not pipeline code, in v0. If approved, a future v0.1 can wire it into the canonical lot crosswalk; this plan does not include that step.

## Validation requirements

- Every decoder rule must show its match-rate evidence (`rows_matched` / `rows_total`).
- Every rule ships with `confidence='inferred'` unless the human marks `validated_by_source_owner=true`.
- The report must explicitly state which VF rows decoded successfully, which decoded but failed to match, and which were untouched.
- The report must NOT modify `data/reports/join_coverage_v0.md` or `output/state_quality_report_v2_bcpd.md` — those baselines are sacred. New numbers go in W3 / W6 outputs.

## Hard guardrails

- **Do not assume globally.** Profile per project; do not extrapolate one project's rule to another without evidence.
- **Do not silently upgrade confidence.** All rules ship `inferred`. Promotion requires source-owner sign-off documented in `validated_by_source_owner`.
- **Do not modify staged_gl_transactions_v2.** This is read-only investigation.
- **Do not apply the decoder to the canonical lot crosswalk in v0.** That's a v0.1 step requiring a separate plan.

## Risks

1. **The pattern is not consistent within a project.** E.g., Harmony might have phase encoding for some VF rows and not others (older vs newer entries). The decoder may need a temporal split.
2. **VF code suffix already encodes phase, but inventory uses different phase IDs.** E.g., VF `Harm3` is Phase 3, but inventory shows Phase A7. The decoder must produce inventory-compatible phase IDs, which may need a per-project phase-name crosswalk.
3. **Source-owner validation may take time.** If we ship `inferred` rules, downstream consumers must respect that label.

## Definition of done

- A profile, a hypothesis, and a candidate rule for each in-scope VF project_code.
- A validation match-rate per candidate rule.
- A selected rule per project (or an explicit "no decoder" verdict).
- The report and the lookup table written.
- W3 has the inputs it needs to simulate the coverage lift.
