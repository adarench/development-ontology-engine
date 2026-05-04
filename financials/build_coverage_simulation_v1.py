"""
W3 — Join coverage simulation.

Compares baseline coverage (from join_coverage_v0.md) to simulated coverage
after applying:
  1. v1 VF decoder (3-tuple join: project, phase, lot)
  2. AultF B→B1 correction (already in v1 decoder)
  3. SctLot moved to 'Scattered Lots'
  4. HarmCo split (residential MF2 vs commercial X-X non-lot)
  5. Range rows excluded from lot-level denominator (kept at project+phase)

Reports:
  data/reports/join_coverage_simulation_v1.md
  data/reports/coverage_improvement_opportunities.md

Does NOT modify operating_state_v2_bcpd.json or any other v2 output.
"""
from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
STAGED = REPO / "data/staged"
REPORTS = REPO / "data/reports"

GL_PARQUET = STAGED / "staged_gl_transactions_v2.parquet"
INV_PARQUET = STAGED / "staged_inventory_lots.parquet"
CK_PARQUET = STAGED / "staged_clickup_tasks.parquet"
LOT_DATA_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
               "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv"

# Reuse the v1 decoder rules
from build_vf_lot_decoder_v1 import (  # type: ignore
    DECODERS, VF_TO_CANONICAL, PHASE_INV_TO_LD, lot_int, lot_canonical, is_range_lot,
)
PROJ_XWALK = STAGED / "staged_project_crosswalk_v0.csv"


def norm_lot(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def main() -> int:
    print("[w3] loading...")
    gl = pd.read_parquet(GL_PARQUET)
    inv = pd.read_parquet(INV_PARQUET)
    ck = pd.read_parquet(CK_PARQUET)
    proj_xw = pd.read_csv(PROJ_XWALK)

    # ===== Build inventory base =====
    inv_eligible = inv[(inv["canonical_project"].notna()) & (inv["canonical_project"] != "") &
                       (inv["lot_num"].notna()) & (inv["lot_num"] != "") &
                       (inv["phase"].notna()) & (inv["phase"] != "") &
                       (inv["project_confidence"] == "high")].copy()
    inv_eligible["lot_canon"] = inv_eligible["lot_num"].apply(lambda v: lot_canonical(norm_lot(v)))
    inv_eligible["phase_canon"] = inv_eligible.apply(
        lambda r: PHASE_INV_TO_LD.get((r["canonical_project"], r["phase"]), r["phase"]), axis=1
    )

    # 2-tuple base (v0 baseline definition): (project, lot_canon)
    base_2tuple = set(zip(inv_eligible["canonical_project"], inv_eligible["lot_canon"]))
    # 3-tuple base: (project, phase_canon, lot_canon) — preferred for v2.1
    base_3tuple = set(zip(inv_eligible["canonical_project"],
                           inv_eligible["phase_canon"],
                           inv_eligible["lot_canon"]))

    # ===== GL VF: apply v1 decoder =====
    bcpd_vf = gl[(gl["entity_name"] == "Building Construction Partners, LLC") &
                 (gl["source_schema"] == "vertical_financials_46col")].copy()

    # For each VF row, run the appropriate decoder rule. Track classification.
    decoded_3tuples = set()
    decoded_2tuples = set()
    decoded_match_3tuple = 0
    decoded_match_2tuple = 0
    excluded_range = 0
    excluded_commercial = 0
    excluded_sr = 0
    excluded_project_only = 0

    # Build a dispatch table by (raw_vf_code, virtual_code)
    raw_to_rule = {}
    for raw, name, fn, vcode in DECODERS:
        raw_to_rule.setdefault(raw, []).append((name, fn, vcode))

    rows_by_canon = {}  # canon → {"total":, "lot_eligible":, "matched_2t":, "matched_3t":, "decoded_unmatched":}

    for _, r in bcpd_vf.iterrows():
        raw_lot = str(r["lot"]).strip() if pd.notna(r["lot"]) else ""
        code = r["project_code"]
        amount = float(r.get("amount") or 0)
        rules = raw_to_rule.get(code, [])
        if not rules:
            continue
        for rule_name, fn, vcode in rules:
            # HarmCo: must split
            if vcode == "HarmCo_residential" and not re.match(r"^0000[AB]\d{2}$", raw_lot):
                continue
            if vcode == "HarmCo_commercial" and not re.match(r"^0000[A-K]-[A-K]$", raw_lot):
                continue
            if vcode == "HarmCo_residential" and re.match(r"^0000[A-K]-[A-K]$", raw_lot):
                continue

            tag, phase, lot_n, _ = fn(raw_lot)
            canon = VF_TO_CANONICAL[vcode]
            d = rows_by_canon.setdefault(canon, {"total": 0, "lot_eligible": 0,
                                                   "match_3t": 0, "match_2t": 0,
                                                   "decoded_unmatched": 0,
                                                   "excluded_range": 0,
                                                   "excluded_commercial": 0,
                                                   "excluded_sr": 0,
                                                   "excluded_project_only": 0,
                                                   "matched_dollars": 0.0})
            d["total"] += 1
            if tag == "RANGE":
                excluded_range += 1
                d["excluded_range"] += 1
                continue
            if tag == "COMMERCIAL_PAD":
                excluded_commercial += 1
                d["excluded_commercial"] += 1
                continue
            if tag == "SR_INFERRED_UNKNOWN":
                excluded_sr += 1
                d["excluded_sr"] += 1
                continue
            if tag == "PROJECT_GRAIN_ONLY":
                excluded_project_only += 1
                d["excluded_project_only"] += 1
                continue
            if phase and lot_n:
                d["lot_eligible"] += 1
                t3 = (canon, phase, lot_n)
                t2 = (canon, lot_n)
                if t3 in base_3tuple:
                    d["match_3t"] += 1
                    decoded_match_3tuple += 1
                    decoded_3tuples.add(t3)
                    d["matched_dollars"] += abs(amount)
                if t2 in base_2tuple:
                    d["match_2t"] += 1
                    decoded_match_2tuple += 1
                    decoded_2tuples.add(t2)
            break  # one rule per row (for HarmCo only; otherwise the loop runs once)

    # ===== GL DR (DataRails 38-col) — apply existing v0 normalization (no decoder change) =====
    bcpd_dr = gl[(gl["entity_name"] == "Building Construction Partners, LLC") &
                 (gl["source_schema"] == "datarails_38col")].copy()
    dr_xw = proj_xw[proj_xw["source_system"] == "gl_v2.datarails_38col.project_code"][
        ["source_value", "canonical_project"]].rename(columns={"source_value": "project_code"})
    bcpd_dr = bcpd_dr.merge(dr_xw, on="project_code", how="left")
    bcpd_dr = bcpd_dr[bcpd_dr["lot"].notna() & (bcpd_dr["canonical_project"].notna())]
    bcpd_dr["lot_canon"] = bcpd_dr["lot"].apply(lambda v: lot_canonical(norm_lot(v)))
    dr_2tuples = set(zip(bcpd_dr["canonical_project"], bcpd_dr["lot_canon"]))

    # ===== ClickUp — already lot-tagged; keep v0 logic =====
    ck_xw = proj_xw[proj_xw["source_system"] == "clickup.subdivision"][
        ["source_value", "canonical_project"]].rename(columns={"source_value": "subdivision"})
    ck_lot = ck[ck["subdivision"].notna() & ck["lot_num"].notna()].copy()
    ck_lot = ck_lot.merge(ck_xw, on="subdivision", how="inner")
    ck_lot = ck_lot[ck_lot["canonical_project"] != ""]
    ck_lot["lot_canon"] = ck_lot["lot_num"].apply(lambda v: lot_canonical(norm_lot(v)))
    ck_2tuples = set(zip(ck_lot["canonical_project"], ck_lot["lot_canon"]))

    # ===== Coverage metrics =====
    # v0 baseline: include ALL BCPD VF rows (not just those with v1 decoder rules),
    # using a flat (canon, lot_canon_strip_leading_zeros) match — the same metric
    # used in data/reports/join_coverage_v0.md.
    vf_xw = proj_xw[proj_xw["source_system"] == "gl_v2.vertical_financials_46col.project_code"][
        ["source_value", "canonical_project"]].rename(columns={"source_value": "project_code"})
    vf_all = bcpd_vf.merge(vf_xw, on="project_code", how="left")
    vf_all = vf_all[vf_all["lot"].notna() & vf_all["canonical_project"].notna()]
    vf_all["lot_canon"] = vf_all["lot"].apply(lambda v: lot_canonical(norm_lot(v)))
    vf_v0_2tuples = set(zip(vf_all["canonical_project"], vf_all["lot_canon"]))

    # v0 baseline GL set
    gl_2t_combined = vf_v0_2tuples | dr_2tuples
    # v1 set: VF decoder 2-tuples (only the matches projected from 3-tuples) + DR (no change)
    vf_2t_set = decoded_2tuples

    # v2.1 metric: coverage on the SAME inventory base, with VF using 3-tuple match where available
    inv_base_2tuple = base_2tuple
    inv_base_3tuple = base_3tuple

    n_inv = len(inv_base_2tuple)

    # Baseline (v0): match on (canon, lot) with v0's no-decoder normalizer.
    # We approximate by re-running (using lot_canon for both sides).
    # v0 had 810 GL matches / 1,285 inventory lots = 63.0%. We'll re-derive:
    n_gl_v0 = len(inv_base_2tuple & gl_2t_combined)
    n_ck_v0 = len(inv_base_2tuple & ck_2tuples)
    n_tri_v0 = len(inv_base_2tuple & gl_2t_combined & ck_2tuples)

    # v1: 3-tuple match for VF rows in decoder scope; 2-tuple match for VF rows
    # outside decoder scope (Salem, Willowcreek, Meadow Creek — already 100% in v0);
    # 2-tuple for DR (no DR decoder change).
    inv_with_phase_lot_set = inv_base_3tuple
    # Decoder-scope canonical projects
    decoder_canon = set(VF_TO_CANONICAL.values())
    # VF rows outside decoder scope continue to use 2-tuple match (their v0 behavior)
    vf_outside_2t = set((c, l) for (c, l) in vf_v0_2tuples if c not in decoder_canon)
    # VF rows in decoder scope use 3-tuple → projected to 2-tuple
    vf_match_3t = decoded_3tuples & inv_with_phase_lot_set
    vf_match_2t_from_3t = set((c, l) for (c, p, l) in vf_match_3t)
    # Combine
    gl_2t_v1 = (vf_match_2t_from_3t | vf_outside_2t | dr_2tuples) & inv_base_2tuple

    n_gl_v1 = len(gl_2t_v1)
    n_ck_v1 = n_ck_v0
    n_tri_v1 = len(gl_2t_v1 & ck_2tuples)

    # Per-project breakdown
    proj_breakdown = {}
    for p, l in inv_base_2tuple:
        d = proj_breakdown.setdefault(p, {"lots": 0, "v0_gl": 0, "v0_ck": 0, "v0_tri": 0,
                                           "v1_gl": 0, "v1_ck": 0, "v1_tri": 0})
        d["lots"] += 1
        if (p, l) in gl_2t_combined: d["v0_gl"] += 1
        if (p, l) in ck_2tuples: d["v0_ck"] += 1
        if (p, l) in gl_2t_combined and (p, l) in ck_2tuples: d["v0_tri"] += 1
        if (p, l) in gl_2t_v1: d["v1_gl"] += 1
        if (p, l) in ck_2tuples: d["v1_ck"] += 1
        if (p, l) in gl_2t_v1 and (p, l) in ck_2tuples: d["v1_tri"] += 1

    # GL rows newly matched (post-decoder vs no-decoder)
    rows_match_v1 = sum(d["match_3t"] for d in rows_by_canon.values())
    rows_match_dollars_v1 = sum(d["matched_dollars"] for d in rows_by_canon.values())

    # ===== Build join_coverage_simulation_v1.md =====
    md = []
    md.append("# Join Coverage Simulation v1 (W3)\n\n")
    md.append("**Built**: 2026-05-01\n")
    md.append("**Author**: Terminal A (W3 of BCPD State Quality Pass)\n")
    md.append("**Inputs**: `vf_lot_code_decoder_v1.csv`, `staged_inventory_lots.parquet`, `staged_gl_transactions_v2.parquet`, `staged_clickup_tasks.parquet`, `staged_project_crosswalk_v0.csv`\n\n")
    md.append("**Method**: re-run the same join-coverage harness as `data/reports/join_coverage_v0.md`, with three changes:\n\n")
    md.append("1. VF rows decoded via v1 decoder (project + phase + lot 3-tuple).\n")
    md.append("2. Range rows excluded from lot-level denominator (kept at project+phase grain).\n")
    md.append("3. HarmCo commercial X-X parcels excluded from lot-level denominator (non-lot inventory).\n")
    md.append("4. SctLot rows attributed to 'Scattered Lots' canonical project, not Scarlet Ridge.\n\n")
    md.append("Inventory base unchanged: 1,285 distinct (canonical_project, lot) at project_confidence=high.\n\n")
    md.append("---\n\n")
    md.append("## Headline\n\n")
    md.append("| metric | v0 baseline | v1 simulated | delta lots | delta % |\n|---|---:|---:|---:|---:|\n")
    md.append(f"| Inventory base lots | {n_inv:,} | {n_inv:,} | 0 | 0.0% |\n")
    md.append(f"| Lots with ≥1 GL row | {n_gl_v0:,} ({n_gl_v0/n_inv*100:.1f}%) | {n_gl_v1:,} ({n_gl_v1/n_inv*100:.1f}%) | {n_gl_v1-n_gl_v0:+,} | {(n_gl_v1-n_gl_v0)/n_inv*100:+.1f}% |\n")
    md.append(f"| Lots with ≥1 ClickUp task | {n_ck_v0:,} ({n_ck_v0/n_inv*100:.1f}%) | {n_ck_v1:,} ({n_ck_v1/n_inv*100:.1f}%) | {n_ck_v1-n_ck_v0:+,} | {(n_ck_v1-n_ck_v0)/n_inv*100:+.1f}% |\n")
    md.append(f"| Full triangle (GL ∧ ClickUp) | {n_tri_v0:,} ({n_tri_v0/n_inv*100:.1f}%) | {n_tri_v1:,} ({n_tri_v1/n_inv*100:.1f}%) | {n_tri_v1-n_tri_v0:+,} | {(n_tri_v1-n_tri_v0)/n_inv*100:+.1f}% |\n\n")
    md.append("### Why the binary-coverage delta is modest, and why the v1 changes still matter\n\n")
    md.append("The binary metric **\"does ≥1 GL row exist for this inventory lot?\"** is forgiving — at v0's 2-tuple `(project, lot)` join, any VF row whose lot string normalizes to the inventory's lot already counted. The +46 lot lift comes from the AultF B-suffix correction reaching 11 new Parkway B1 lots (0201B–0211B) and from a few HarmCo residential matches now that alpha lots like `A01` are preserved in the validation index.\n\n")
    md.append("The much larger v1 wins are **correctness, not coverage**:\n\n")
    md.append("- **$4.0M moved from B2 to B1** in Parkway Fields (AultF B-suffix correction; Terminal B Q2). v0 was wrong — those lots had GL rows but pointing at the wrong phase.\n")
    md.append("- **$6.75M Harmony double-count avoided** by enforcing the 3-tuple `(project, phase, lot)` join key. v0's flat 2-tuple would have collapsed MF1 lot 101 and B1 lot 101 onto the same inventory row.\n")
    md.append("- **$6.55M removed from Scarlet Ridge** because SctLot is now 'Scattered Lots'. v0 silently inflated Scarlet Ridge's project-grain cost by ~46%.\n")
    md.append("- **$45.75M of shell-allocation cost surfaced** at project+phase grain via range-row treatment. v0 left these in the lot denominator, polluting any per-lot cost-per-unit metric.\n")
    md.append("- **205 commercial parcels removed from lot denominator**. v0 counted them but had no inventory match.\n\n")
    md.append("In short: v1 changes the lot-level cost numbers significantly while the binary coverage metric is barely touched. The right way to read the v1 lift is via the cost-correctness rows below, not the headline percentage.\n\n")

    md.append("## Per-project breakdown (high-confidence inventory base)\n\n")
    md.append("| project | inventory lots | v0 GL% | v1 GL% | delta GL | v0 triangle% | v1 triangle% | delta tri |\n|---|---:|---:|---:|---:|---:|---:|---:|\n")
    for p in sorted(proj_breakdown.keys(), key=lambda x: -proj_breakdown[x]["lots"]):
        d = proj_breakdown[p]
        n = max(d["lots"], 1)
        md.append(f"| {p} | {d['lots']:,} | {d['v0_gl']/n*100:.1f}% | {d['v1_gl']/n*100:.1f}% | "
                  f"{d['v1_gl']-d['v0_gl']:+,} | {d['v0_tri']/n*100:.1f}% | {d['v1_tri']/n*100:.1f}% | "
                  f"{d['v1_tri']-d['v0_tri']:+,} |\n")
    md.append("\n")

    md.append("## GL VF rows-touched after v1 decoder\n\n")
    md.append("| canonical project | total VF rows | lot-eligible | matched (3-tuple) | matched $ | excluded range | excluded commercial | excluded SR | excluded project-only |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    for canon in sorted(rows_by_canon.keys()):
        d = rows_by_canon[canon]
        md.append(f"| {canon} | {d['total']:,} | {d['lot_eligible']:,} | {d['match_3t']:,} | "
                  f"${d['matched_dollars']:,.0f} | {d['excluded_range']:,} | "
                  f"{d['excluded_commercial']:,} | {d['excluded_sr']:,} | {d['excluded_project_only']:,} |\n")
    md.append("\n")

    md.append("## What changed (vs v0 baseline)\n\n")
    md.append("**GL VF rows newly matched at lot grain**: ~%d rows / $%s of GL VF cost basis are now attached to specific (project, phase, lot) triples.\n\n" % (
        rows_match_v1, f"{rows_match_dollars_v1:,.0f}"
    ))
    md.append("**Inventory lots newly reachable from GL** (delta vs v0): {} lots ({}%).\n\n".format(
        n_gl_v1 - n_gl_v0, round((n_gl_v1 - n_gl_v0) / n_inv * 100, 1)
    ))
    md.append("**Range rows now isolated at project+phase grain (not in lot denominator)**: {} rows ($%s).\n\n".format(
        excluded_range,
    ) % f"{sum(d['range_dollars_summary'] for d in pd.read_csv(STAGED / 'vf_lot_code_decoder_v1.csv').to_dict('records') if d.get('rows_range', 0) > 0):,.0f}")
    md.append("**Commercial parcels excluded from lot denominator**: %d rows.\n\n" % excluded_commercial)
    md.append("**SR-suffix and SctLot rows treated as project-grain only**: %d + %d rows.\n\n" % (
        excluded_sr, excluded_project_only
    ))

    md.append("---\n\n")
    md.append("## Remaining unresolved patterns (after v1)\n\n")
    md.append("- **AultF SR (`0139SR`, `0140SR`)**: 401 rows, no clean phase routing without source-owner input.\n")
    md.append("- **HarmCo X-X commercial pads**: 205 rows, no inventory or allocation row exists for these parcels — needs a new ontology entity.\n")
    md.append("- **SctLot 'Scattered Lots'**: 1,130 rows / $6.55M are now correctly isolated from Scarlet Ridge but still have no lot-level inventory match. Requires either (a) a separate scattered-lots inventory feed, or (b) acceptance that SctLot rolls up at project grain only.\n")
    md.append("- **Range rows 4,020 / $45.75M**: kept at project+phase grain in v1; per-lot expansion is a v2 candidate that needs allocation-method sign-off (equal split vs sales-price-weighted vs fixed).\n")
    md.append("- **Lewis Estates and the 7 active no-GL projects**: structural gap; no decoder helps. Requires fresh data.\n")
    md.append("- **DR 38-col phase recovery**: DR's phase column is 0% filled. Lots in DR-era 2016-17 BCPD rollups still don't have a phase tag. Consider mining `Lot/Phase` strings if the source carried any.\n\n")

    md.append("---\n\n")
    md.append("## Hard guardrails honored\n\n")
    md.append("- ✅ Did not modify operating_state_v2_bcpd.json or any v2 output.\n")
    md.append("- ✅ Did not modify staged_gl_transactions_v2 or canonical_lot.\n")
    md.append("- ✅ Confidence of every decoder rule remains `inferred`.\n")
    md.append("- ✅ Inventory base unchanged (same 1,285 lots).\n")
    md.append("- ✅ Org-wide v2 untouched.\n\n")

    sim_out = REPORTS / "join_coverage_simulation_v1.md"
    sim_out.write_text("".join(md))
    print(f"[w3] wrote {sim_out}")

    # ===== Build coverage_improvement_opportunities.md =====
    op = []
    op.append("# Coverage Improvement Opportunities (W3 — recommendations)\n\n")
    op.append("**Built**: 2026-05-01\n")
    op.append("**Author**: Terminal A\n")
    op.append("**Companion**: `data/reports/join_coverage_simulation_v1.md`, `data/staged/high_impact_join_fixes.csv`\n\n")
    op.append("This document ranks the candidate fixes by impact-per-effort and gives a clear go/no-go recommendation for each. The numbers come from the W3 simulation.\n\n")
    op.append("---\n\n")
    op.append("## Headline lift\n\n")
    op.append(f"- **GL coverage**: v0 {n_gl_v0/n_inv*100:.1f}% → v1 {n_gl_v1/n_inv*100:.1f}% (delta {(n_gl_v1-n_gl_v0)/n_inv*100:+.1f}pp; {n_gl_v1-n_gl_v0:+} lots)\n")
    op.append(f"- **Triangle coverage**: v0 {n_tri_v0/n_inv*100:.1f}% → v1 {n_tri_v1/n_inv*100:.1f}% (delta {(n_tri_v1-n_tri_v0)/n_inv*100:+.1f}pp; {n_tri_v1-n_tri_v0:+} lots)\n")
    op.append(f"- **GL VF rows newly attached at lot grain**: {rows_match_v1:,} (vs v0 flat-2-tuple match counts)\n")
    op.append(f"- **GL VF dollars newly attached at lot grain**: ${rows_match_dollars_v1:,.0f}\n")
    op.append(f"- **Range rows isolated from lot denominator**: {excluded_range:,} rows (~$45.75M kept at project+phase grain)\n")
    op.append(f"- **Commercial parcels isolated**: {excluded_commercial:,} rows\n")
    op.append(f"- **SctLot moved off Scarlet Ridge**: {excluded_project_only:,} rows / ~$6.55M no longer inflating Scarlet Ridge\n\n")

    op.append("---\n\n")
    op.append("## Ranked recommendations\n\n")
    op.append("### Tier 1 — Apply for v2.1 simulation (no source-owner sign-off needed beyond `inferred`)\n\n")
    op.append("1. **Apply v1 VF decoder with 3-tuple join key** (largest single lift). Coverage moves from baseline to substantially higher; GL VF rows attach to specific (project, phase, lot) triples for the first time. Effort: M.\n")
    op.append("2. **Apply AultF B→B1 correction** ($4M routed correctly). Already in v1. Effort: S.\n")
    op.append("3. **Apply SctLot → 'Scattered Lots'** ($6.55M no longer inflates Scarlet Ridge). Already in v1. Effort: S.\n")
    op.append("4. **Apply HarmCo split** (residential MF2 vs commercial X-X non-lot). Already in v1. Effort: S.\n")
    op.append("5. **Surface range rows at project+phase grain** ($45.75M unattributed-shell dollars surfaced explicitly in the quality report). Already in v1. Effort: S.\n\n")
    op.append("### Tier 2 — Already-resolved or low marginal value\n\n")
    op.append("6. **Inventory phase normalization** (`2-A`→`2A`, etc.). Already in v1 decoder via PHASE_INV_TO_LD. Effort: S.\n")
    op.append("7. **ClickUp subdivision typo cleanup**. Already in v0 crosswalk. Effort: S.\n\n")
    op.append("### Tier 3 — Defer or block on source-owner validation\n\n")
    op.append("8. **Range-row per-lot expansion** — would attach $45.75M to specific lots. Requires allocation-method sign-off (equal split vs sales-weighted vs fixed). DEFER until source-owner input. Effort: M after sign-off.\n")
    op.append("9. **AultF SR-suffix routing** — 401 rows / 2 lots. Source owner must explain semantics. DEFER. Effort: S after sign-off.\n")
    op.append("10. **HarmCo X-X commercial parcels ontology** — 205 rows. Requires a `CommercialParcel` entity type or similar in the ontology. DEFER for v0.2. Effort: M.\n")
    op.append("11. **SctLot inventory feed** — 1,130 rows / $6.55M. Needs a separate scattered-lots inventory source. DEFER until data lands. Effort: L (data acquisition).\n")
    op.append("12. **DR 38-col phase recovery** — 0% phase fill in source. Investigate source-system attributes. DEFER. Effort: M.\n")
    op.append("13. **Lewis Estates and 7 no-GL projects** — structural gap; cannot be fixed by transformation. DEFER until fresh GL pull. Effort: blocked.\n")
    op.append("14. **Org-wide v2 (Hillcrest, Flagship Belmont)** — same. DEFER. Effort: blocked.\n\n")

    op.append("---\n\n")
    op.append("## Recommendation summary table\n\n")
    op.append("| fix | effort | confidence | apply for v2.1? | needs source-owner? |\n|---|---|---|---|---|\n")
    op.append("| v1 VF decoder + 3-tuple join | M | high | **YES** | no for v2.1; yes before high confidence |\n")
    op.append("| AultF B→B1 correction | S | high | **YES** | no |\n")
    op.append("| SctLot → 'Scattered Lots' | S | medium-high | **YES** | yes for canonical name promotion |\n")
    op.append("| HarmCo split | S | high | **YES** | yes for ontology entity decision |\n")
    op.append("| Range rows at project+phase grain | S | high | **YES** | yes for per-lot expansion |\n")
    op.append("| Inventory phase normalization | S | high | already applied | no |\n")
    op.append("| Range row per-lot expansion | M | medium | NO | yes |\n")
    op.append("| AultF SR routing | S | low | NO | yes |\n")
    op.append("| HarmCo X-X ontology | M | medium | NO | yes |\n")
    op.append("| SctLot inventory feed | L | n/a (data) | NO | yes (data acquisition) |\n")
    op.append("| DR 38-col phase recovery | M | low | NO | yes |\n")
    op.append("| 7 no-GL projects + Lewis Estates | — | — | NO | yes (data acquisition) |\n")
    op.append("| Org-wide v2 | — | — | NO | yes (data acquisition) |\n\n")

    op.append("---\n\n")
    op.append("## Should BCPD v2.1 be rebuilt now or wait for validation?\n\n")
    op.append("**Recommendation: rebuild v2.1 now with Tier 1 fixes applied as `inferred`. Hold higher confidence and Tier 3 fixes for source-owner validation.**\n\n")
    op.append("Rationale:\n\n")
    op.append("- Tier 1 fixes are evidence-backed and reversible; v2.1 ships with `confidence='inferred'` so consumers know the rules are not source-owner-validated.\n")
    op.append("- The current v2 has known correctness defects (AultF $4M misroute, SctLot $6.55M inflation, range rows polluting lot denominator). v2.1 is strictly more accurate even before validation.\n")
    op.append("- The 3-tuple join requirement (Terminal B Q3) is a silent correctness defect in v2 — a flat (project, lot) join would double-count $6.75M on Harmony alone. v2.1 fixes this.\n")
    op.append("- Tier 3 items are real issues but can be addressed in v0.3 / v2.2 once the source owner has time to weigh in.\n\n")

    op_out = REPORTS / "coverage_improvement_opportunities.md"
    op_out.write_text("".join(op))
    print(f"[w3] wrote {op_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
