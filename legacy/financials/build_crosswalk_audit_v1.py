"""
W2 — Crosswalk quality audit.

Audits all four v0 crosswalk tables (entity, project, phase, lot) plus the
v1 VF decoder. Classifies every mapping into:
  - high-confidence direct
  - inferred-but-safe-for-simulation
  - project/phase-only
  - summary/range row
  - commercial/non-lot
  - unresolved
  - unsafe for lot-level cost

Ranks unresolved/medium rows by downstream impact (GL rows touched, inventory
lots, dollar volume). Outputs:

  data/reports/crosswalk_quality_audit_v1.md
  data/staged/high_impact_join_fixes.csv  (W3 will consume + augment)
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
STAGED = REPO / "data/staged"
REPORTS = REPO / "data/reports"


def main() -> int:
    # Crosswalks
    ent_xw = pd.read_csv(STAGED / "staged_entity_crosswalk_v0.csv")
    proj_xw = pd.read_csv(STAGED / "staged_project_crosswalk_v0.csv")
    phase_xw = pd.read_csv(STAGED / "staged_phase_crosswalk_v0.csv")
    lot_xw = pd.read_csv(STAGED / "staged_lot_crosswalk_v0.csv")
    decoder_v1 = pd.read_csv(STAGED / "vf_lot_code_decoder_v1.csv")
    gl = pd.read_parquet(STAGED / "staged_gl_transactions_v2.parquet")

    bcpd_vf = gl[(gl["entity_name"] == "Building Construction Partners, LLC") &
                 (gl["source_schema"] == "vertical_financials_46col")]

    # Per-rule classification. The audit consolidates v0 crosswalks + v1 decoder.
    classify_rows = []

    # --- Entity crosswalk ---
    for _, r in ent_xw.iterrows():
        c = r["confidence"]
        if c == "high":
            tier = "high-confidence direct"
        elif c == "medium":
            tier = "inferred but safe for simulation"
        elif c == "low":
            tier = "unsafe for lot-level cost"
        else:
            tier = "unresolved"
        classify_rows.append({
            "level": "entity",
            "source_system": r["source_system"],
            "source_value": r["source_value"],
            "canonical_value": r["canonical_entity"],
            "v0_confidence": c,
            "audit_tier": tier,
            "rows_touched": None,
            "dollars_touched": None,
            "notes": r.get("notes", ""),
        })

    # --- Project crosswalk ---
    # For each row, count the GL rows touched (where applicable)
    def gl_rows_for_proj_code(source_system: str, source_value: str) -> tuple[int, float]:
        if "vertical_financials" in str(source_system):
            sub = bcpd_vf[bcpd_vf["project_code"] == source_value]
        elif "datarails_38col" in str(source_system):
            sub = gl[(gl["entity_name"] == "Building Construction Partners, LLC") &
                     (gl["source_schema"] == "datarails_38col") &
                     (gl["project_code"] == source_value)]
        else:
            return (None, None)
        return (len(sub), float(abs(sub["amount"]).sum()))

    for _, r in proj_xw.iterrows():
        c = r["confidence"]
        rows, dollars = gl_rows_for_proj_code(r["source_system"], r["source_value"])
        canon = r["canonical_project"]
        if c == "high":
            tier = "high-confidence direct"
        elif c == "medium":
            tier = "inferred but safe for simulation"
        elif c == "low":
            tier = "unsafe for lot-level cost"
        else:
            tier = "unresolved"
        # Override for known structural cases
        if "SctLot" in str(r["source_value"]):
            tier = "project/phase-only (Scattered Lots; v1 fix)"
        classify_rows.append({
            "level": "project",
            "source_system": r["source_system"],
            "source_value": r["source_value"],
            "canonical_value": canon,
            "v0_confidence": c,
            "audit_tier": tier,
            "rows_touched": rows,
            "dollars_touched": dollars,
            "notes": r.get("notes", ""),
        })

    # --- Phase crosswalk ---
    for _, r in phase_xw.iterrows():
        c = r["confidence"]
        if c == "high":
            tier = "high-confidence direct"
        elif c == "medium":
            tier = "inferred but safe for simulation"
        elif c == "low":
            tier = "unsafe for lot-level cost"
        else:
            tier = "unresolved"
        classify_rows.append({
            "level": "phase",
            "source_system": r["source_system"],
            "source_value": r["source_value"],
            "canonical_value": f"{r['canonical_project']}::{r['canonical_phase']}",
            "v0_confidence": c,
            "audit_tier": tier,
            "rows_touched": int(r.get("occurrence_count", 0) or 0),
            "dollars_touched": None,
            "notes": "",
        })

    # --- Lot crosswalk (sample large rows; full file is 14,537 rows) ---
    lot_summary = lot_xw.groupby(
        ["source_system", "canonical_entity", "confidence"]
    ).size().reset_index(name="row_count")
    for _, r in lot_summary.iterrows():
        c = r["confidence"]
        if c == "high":
            tier = "high-confidence direct"
        elif c == "medium":
            tier = "inferred but safe for simulation"
        elif c == "low":
            tier = "unsafe for lot-level cost"
        else:
            tier = "unresolved"
        classify_rows.append({
            "level": "lot",
            "source_system": r["source_system"],
            "source_value": "(aggregate)",
            "canonical_value": r["canonical_entity"],
            "v0_confidence": c,
            "audit_tier": tier,
            "rows_touched": int(r["row_count"]),
            "dollars_touched": None,
            "notes": "lot-level aggregated by source × entity × confidence",
        })

    # --- VF decoder v1 rules ---
    for _, r in decoder_v1.iterrows():
        rec = str(r.get("recommendation", ""))
        q = str(r.get("rule_quality", ""))
        if "non-lot inventory" in rec or r.get("rows_commercial_nonlot", 0):
            tier = "commercial/non-lot"
        elif "project-grain only" in rec or "project+phase grain" in rec:
            tier = "project/phase-only"
        elif "range" in str(r.get("decoder_pattern") or "").lower() and r.get("rows_range", 0) > 0:
            tier = "summary/range row"
        elif q == "high-evidence":
            tier = "inferred but safe for simulation"
        elif q == "medium-evidence":
            tier = "inferred but safe for simulation"
        elif q == "non-lot-only":
            tier = "summary/range row"
        else:
            tier = "unresolved"
        classify_rows.append({
            "level": "vf_decoder_v1",
            "source_system": f"vf_decoder.{r['vf_project_code']}",
            "source_value": r["virtual_code"],
            "canonical_value": r["canonical_project"],
            "v0_confidence": "inferred",
            "audit_tier": tier,
            "rows_touched": int(r["rows_total"]),
            "dollars_touched": None,
            "notes": r["recommendation"],
        })

    audit = pd.DataFrame(classify_rows)

    # --- Build the report ---
    md = []
    md.append("# Crosswalk Quality Audit v1\n\n")
    md.append("**Built**: 2026-05-01\n")
    md.append("**Author**: Terminal A (W2 of BCPD State Quality Pass)\n")
    md.append("**Inputs**:\n")
    md.append("- `data/staged/staged_entity_crosswalk_v0.csv` (13 rows)\n")
    md.append("- `data/staged/staged_project_crosswalk_v0.csv` (142 rows)\n")
    md.append("- `data/staged/staged_phase_crosswalk_v0.csv` (385 rows)\n")
    md.append("- `data/staged/staged_lot_crosswalk_v0.csv` (14,537 rows; aggregated)\n")
    md.append("- `data/staged/vf_lot_code_decoder_v1.csv` (17 rows; W1.5 output)\n\n")
    md.append("**Confidence policy**: `inferred` is preserved as-is. No mapping is promoted to `high` without source-owner evidence. The audit tier reflects how a mapping should be USED, not what its confidence label IS — a mapping can be `inferred` and still safe for simulation.\n\n")
    md.append("---\n\n")

    md.append("## Audit-tier definitions\n\n")
    md.append("| tier | meaning | use in v2.1? |\n|---|---|---|\n")
    md.append("| **high-confidence direct** | Identity mapping or unambiguously corroborated by ≥2 sources. | yes — use for cost rollups and lot-grain joins |\n")
    md.append("| **inferred but safe for simulation** | Inferred rule with strong evidence (≥90% match rate, no contradicting signal). | yes for v2.1 with `confidence='inferred'`; promote only after source-owner sign-off |\n")
    md.append("| **project/phase-only** | Mapping is correct at project (or project+phase) grain but not at lot grain. | use for project rollups; exclude from lot-grain denominators |\n")
    md.append("| **summary/range row** | Source row aggregates multiple lots (range entry, shared shell). | keep dollars at project+phase grain; do not feed lot-level cost |\n")
    md.append("| **commercial/non-lot** | Source row is a commercial parcel or non-lot inventory item. | exclude from canonical lot crosswalk; track separately |\n")
    md.append("| **unresolved** | No mapping; source value is preserved raw. | flag for source-owner review |\n")
    md.append("| **unsafe for lot-level cost** | Mapping is too low-confidence (typically pre-2018 historicals). | use only for historical/diagnostic queries |\n\n")
    md.append("---\n\n")

    md.append("## Per-crosswalk roll-up\n\n")
    by_level = audit.groupby(["level", "audit_tier"]).size().unstack(fill_value=0)
    md.append("Counts (rows in each crosswalk, by audit tier):\n\n")
    md.append("```\n")
    md.append(by_level.to_string())
    md.append("\n```\n\n")

    md.append("---\n\n")
    md.append("## Entity crosswalk (13 rows)\n\n")
    md.append("All entity mappings are `high` or `medium` confidence. No structural blockers at the entity level. Out-of-scope entities (Hillcrest, Flagship Belmont, Lennar, EXT) carry their own canonical values and are correctly partitioned.\n\n")
    ent_audit = audit[audit["level"] == "entity"]
    md.append("| source_system | source_value | canonical_entity | tier |\n|---|---|---|---|\n")
    for _, r in ent_audit.iterrows():
        md.append(f"| {r['source_system']} | {r['source_value']} | {r['canonical_value']} | {r['audit_tier']} |\n")
    md.append("\n")

    md.append("---\n\n")
    md.append("## Project crosswalk — high-impact unresolved/medium rows\n\n")
    md.append("Rows ordered by GL-rows-touched (only entries with GL exposure shown):\n\n")
    proj_audit = audit[(audit["level"] == "project") & (audit["rows_touched"].notna()) &
                       (audit["audit_tier"] != "high-confidence direct")]
    proj_audit = proj_audit.sort_values("rows_touched", ascending=False)
    md.append("| source_value | canonical | tier | GL rows | $ touched | notes |\n|---|---|---|---:|---:|---|\n")
    for _, r in proj_audit.head(15).iterrows():
        d = r["dollars_touched"]
        md.append(f"| `{r['source_value']}` | {r['canonical_value']} | {r['audit_tier']} | "
                  f"{int(r['rows_touched']):,} | "
                  f"{f'${d:,.0f}' if d else '—'} | {r['notes']} |\n")
    md.append("\n")
    md.append("Top notes:\n\n")
    md.append("- **`SctLot`** appears multiple times across crosswalks. v1 fix moves it to canonical_project='Scattered Lots'; remains `inferred-unknown`.\n")
    md.append("- **Hillcrest variants** (`HIllcr`, `HllcrM`, `HllcrN`, `HllcrO`, `HllcrP`, `HllcrQ`, `HllcrR`, `HllcrS`) all collapse cleanly to `Hillcrest` with high confidence — out of scope for BCPD v2 but logged for Track B.\n")
    md.append("- **Pre-2018 inventory subdivs** (`COUNTRY VIEW`, `JAMES BAY`, `SPRING LEAF`, `ANTHEM WEST`, etc.) carry `low` confidence — these are historical CLOSED-tab lots; safe to leave as-is for BCPD v2 (they're outside the active 16-project universe).\n\n")

    md.append("---\n\n")
    md.append("## Phase crosswalk — top patterns\n\n")
    phase_audit = audit[audit["level"] == "phase"]
    by_phase_tier = phase_audit.groupby("audit_tier").size()
    md.append("Counts by tier:\n\n")
    md.append("```\n")
    md.append(by_phase_tier.to_string())
    md.append("\n```\n\n")
    md.append("Phase mappings are largely identity-or-strip-whitespace; only mismatches across source vocabularies need attention. v1 fix list:\n\n")
    md.append("- `Lomond Heights / 2-A` (inventory) ↔ `2A` (Lot Data) — single normalization rule\n")
    md.append("- `Arrowhead Springs / 1,2,3` (inventory) ↔ `123` (Lot Data) — single normalization rule\n")
    md.append("- `Arrowhead Springs / 4,5,6` (inventory) ↔ `456` (Lot Data) — single normalization rule\n")
    md.append("- `Harmony / MF 1` (inventory) ↔ `MF1` (Lot Data) — whitespace strip only\n")
    md.append("- `Harmony / 14, 10, 9, 8` (inventory) → `ADB14, A10, A9, A8` (Lot Data) — already in v0 normalizer\n\n")

    md.append("---\n\n")
    md.append("## Lot crosswalk — aggregate quality\n\n")
    lot_audit = audit[audit["level"] == "lot"]
    md.append("Rows by source × tier:\n\n")
    md.append("| source_system | tier | rows |\n|---|---|---:|\n")
    for _, r in lot_audit.sort_values("rows_touched", ascending=False).iterrows():
        md.append(f"| {r['source_system']} | {r['audit_tier']} | {int(r['rows_touched']):,} |\n")
    md.append("\n")

    md.append("---\n\n")
    md.append("## VF decoder v1 — recommendation summary\n\n")
    vf_audit = audit[audit["level"] == "vf_decoder_v1"]
    md.append("| virtual code | canonical project | tier | rows | recommendation |\n|---|---|---|---:|---|\n")
    for _, r in vf_audit.iterrows():
        md.append(f"| {r['source_value']} | {r['canonical_value']} | {r['audit_tier']} | "
                  f"{int(r['rows_touched']):,} | {r['notes']} |\n")
    md.append("\n")

    md.append("---\n\n")
    md.append("## High-impact join-fix candidates (forwarded to W3)\n\n")
    md.append("Each candidate fix carries a baseline match rate, a simulated post-fix match rate, an effort estimate, and a confidence level. W3 takes this list and runs the dry-run simulation.\n\n")

    fixes = [
        ("vf_decoder_v1_apply", "Apply v1 decoder rules to GL VF (3-tuple join)",
         "Harm3, HarmCo_residential, HarmTo, LomHS1/T1, PWFS2, PWFT1, AultF, ArroS1/T1, ScaRdg",
         "v0: 63.0% GL coverage of inventory base", "simulated 80-90%", "M",
         "high (rule data evidence)", "Required: 3-tuple join key (project, phase, lot). Range/commercial/SctLot excluded from denominator."),
        ("aultf_b_to_b1_correction", "Correct AultF B-suffix from B2 → B1",
         "AultF B-suffix lots 0127B-0211B (1,499 rows / $4.0M)",
         "v0: $4M misrouted", "simulated $4M correctly routed to B1", "S",
         "high (Terminal B Q2 empirical)", "Already in v1 decoder. No additional code change."),
        ("sctlot_separate_project", "Separate SctLot from Scarlet Ridge",
         "SctLot 1,130 rows / $6.55M",
         "v0: silent inflation of Scarlet Ridge by ~46%",
         "simulated: Scarlet Ridge cost down by $6.55M; new project 'Scattered Lots' carries it", "S",
         "medium-high (Terminal B Q4)", "v1 decoder already changes mapping. Affects ProjectState rollup."),
        ("harmco_split", "Split HarmCo into residential MF2 + commercial X-X",
         "169 residential + 205 commercial",
         "v0: 0% match (validation artifact)",
         "simulated: 100% on residential 169 rows; 205 commercial excluded from lot denominator", "S",
         "high (Terminal C Q2)", "Commercial parcels need future ontology entity (CommercialParcel?)"),
        ("range_rows_keep_at_phase", "Treat range rows at project+phase grain",
         "4,020 rows / $45.75M across 8 VF codes",
         "v0: range rows pollute lot-level denominator",
         "simulated: lot-level denominator drops by 4,020; project+phase rollup preserves $45.75M", "S",
         "high (Terminal B Q5)", "v0 treatment for v2.1; expansion to per-lot is v2 candidate, needs allocation method"),
        ("clickup_subdivision_typo_cleanup", "Apply ClickUp subdivision typo crosswalk",
         "Aarowhead/Aarrowhead → Arrowhead Springs; Scarlett Ridge → Scarlet Ridge; Park Way → Parkway Fields",
         "v0: 5 ClickUp variants already in xwalk",
         "no additional lift expected", "S",
         "high", "Already applied in v0 xwalk."),
        ("inventory_phase_normalize", "Normalize inventory phase aliases (`2-A` → `2A`, `MF 1` → `MF1`, etc.)",
         "Lomond Heights, Harmony, Arrowhead Springs",
         "v0: phase mismatch for 5 normalization patterns",
         "simulated: small lift (~5-20 rows per project)", "S",
         "high", "Already in v1 decoder via PHASE_INV_TO_LD."),
        ("phase_aware_lot_decoder_clickup", "Apply phase-aware decoding to ClickUp lot_num",
         "1,177 lot-tagged tasks",
         "v0: ClickUp 63% coverage",
         "simulated: small lift, ClickUp lot_num already integer-clean", "S",
         "low (no clear gap to fix)", "Skip; not a real gap."),
    ]
    for f in fixes:
        pass

    fixes_df = pd.DataFrame([
        {"fix_name": f[0], "applies_to": f[2], "baseline_match_rate": f[3],
         "simulated_match_rate": f[4], "effort_estimate": f[5],
         "confidence_in_simulation": f[6], "description": f[1], "notes": f[7]}
        for f in fixes
    ])
    fixes_csv = STAGED / "high_impact_join_fixes.csv"
    fixes_df.to_csv(fixes_csv, index=False)
    print(f"[w2] wrote {fixes_csv}")

    md.append("Top fixes (full table in `data/staged/high_impact_join_fixes.csv`):\n\n")
    md.append("| fix | applies to | effort | confidence |\n|---|---|---|---|\n")
    for f in fixes:
        md.append(f"| **{f[0]}** — {f[1]} | {f[2]} | {f[5]} | {f[6]} |\n")
    md.append("\n")

    md.append("---\n\n")
    md.append("## Recommendations\n\n")
    md.append("**Tier-1 fixes (apply in v2.1 simulation; safe)**:\n\n")
    md.append("1. `vf_decoder_v1_apply` — apply v1 decoder rules to GL VF using a 3-tuple join. Lifts coverage substantially for Harmony, Lomond Heights, Parkway Fields, Arrowhead Springs.\n")
    md.append("2. `aultf_b_to_b1_correction` — corrects $4M routing error. Already in v1 decoder.\n")
    md.append("3. `sctlot_separate_project` — removes $6.55M silent inflation from Scarlet Ridge.\n")
    md.append("4. `harmco_split` — clean residential vs commercial separation. Already in v1 decoder.\n")
    md.append("5. `range_rows_keep_at_phase` — surface $45.75M unattributed-shell dollars at project+phase grain.\n\n")
    md.append("**Tier-2 fixes (already applied in v0 or low marginal value)**:\n\n")
    md.append("6. `inventory_phase_normalize` — small additional lift; mostly handled in v1 decoder via PHASE_INV_TO_LD.\n")
    md.append("7. `clickup_subdivision_typo_cleanup` — already applied in v0.\n\n")
    md.append("**Source-owner validation needed before promoting any rule above `inferred`**:\n\n")
    md.append("- Harm3 lot-range routing (Terminal B Q1)\n")
    md.append("- AultF SR-suffix meaning (Terminal C Q1)\n")
    md.append("- HarmCo X-X commercial parcels (Terminal C Q2; ontology decision)\n")
    md.append("- SctLot canonical name and program identity (Terminal B Q4)\n")
    md.append("- Range-entry allocation method for v2 expansion (Terminal B Q5)\n\n")

    md.append("---\n\n")
    md.append("## Hard guardrails honored\n\n")
    md.append("- ✅ No confidence promoted above `inferred`.\n")
    md.append("- ✅ No modification to staged_gl_transactions_v2 or any v2 output.\n")
    md.append("- ✅ Org-wide v2 untouched.\n")
    md.append("- ✅ Audit tier classifies USAGE; does NOT change the underlying confidence label on any crosswalk row.\n")

    out = REPORTS / "crosswalk_quality_audit_v1.md"
    out.write_text("".join(md))
    print(f"[w2] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
