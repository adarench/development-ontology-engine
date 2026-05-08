"""W5 — Generate `output/agent_chunks_v2_bcpd/`.

Source-backed context chunks for future RAG / free-form LLM usage. Every chunk
is derived from existing v2.1 artifacts; no chunk invents facts. Every chunk
ships with frontmatter (chunk_id, chunk_type, title, project, source_files,
state_version, confidence, last_generated, allowed_uses, caveats) and the
required body sections (Plain-English summary, Key facts, Evidence/source
files, Confidence, Caveats, Safe questions, Questions to refuse or caveat).

Outputs (deterministic; regenerate at will):
  output/agent_chunks_v2_bcpd/index.json
  output/agent_chunks_v2_bcpd/README.md
  output/agent_chunks_v2_bcpd/chunk_quality_report.md
  output/agent_chunks_v2_bcpd/projects/*.md
  output/agent_chunks_v2_bcpd/coverage/*.md
  output/agent_chunks_v2_bcpd/cost_sources/*.md
  output/agent_chunks_v2_bcpd/guardrails/*.md
  output/agent_chunks_v2_bcpd/sources/*.md

Hard rules (per the plan + user instructions):
- Chunks are derived artifacts only. v2.1 outputs not modified.
- Confidence labels in chunks reflect what's in the source; never promoted.
- Missing cost is reported as `unknown`, never `$0`.
- Org-wide is not presented as available.
- Range/shell rows are never allocated to lots.
- HarmCo commercial parcels are not modeled as residential lots.
- SctLot dollars belong to 'Scattered Lots', not Scarlet Ridge.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
import json
import re

REPO = Path(__file__).resolve().parent.parent
STATE_JSON = REPO / "output/operating_state_v2_1_bcpd.json"
OUT = REPO / "output/agent_chunks_v2_bcpd"
LAST_GEN = "2026-05-04"
STATE_VERSION = "v2.1"


def _usd(n) -> str:
    if n is None: return "unknown (not zero)"
    if not isinstance(n, (int, float)): return str(n)
    return f"${n:,.0f}"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _frontmatter(*, chunk_id: str, chunk_type: str, title: str,
                  project: str | None, source_files: list[str],
                  confidence: str, allowed_uses: list[str],
                  caveats: list[str]) -> str:
    """Render frontmatter consistent with the user's required schema."""
    lines = [
        "---",
        f"chunk_id: {chunk_id}",
        f"chunk_type: {chunk_type}",
        f"title: {title}",
        f"project: {project if project else 'n/a'}",
        "source_files:",
    ]
    lines += [f"  - {s}" for s in source_files]
    lines.append(f"state_version: {STATE_VERSION}")
    lines.append(f"confidence: {confidence}")
    lines.append(f"last_generated: {LAST_GEN}")
    lines.append("allowed_uses:")
    lines += [f"  - {u}" for u in allowed_uses]
    lines.append("caveats:")
    lines += [f"  - {c}" for c in caveats]
    lines.append("---")
    return "\n".join(lines) + "\n"


def _body(*, summary: str, facts: list[str], sources: list[str],
           confidence_para: str, caveats_list: list[str],
           safe_questions: list[str], refuse_or_caveat: list[str]) -> str:
    parts = []
    parts.append("\n## Plain-English summary\n\n" + summary + "\n")
    parts.append("\n## Key facts\n\n" + "\n".join(f"- {f}" for f in facts) + "\n")
    parts.append("\n## Evidence / source files\n\n" + "\n".join(f"- `{s}`" for s in sources) + "\n")
    parts.append("\n## Confidence\n\n" + confidence_para + "\n")
    parts.append("\n## Caveats\n\n" + "\n".join(f"- {c}" for c in caveats_list) + "\n")
    parts.append("\n## Safe questions this chunk grounds\n\n" + "\n".join(f"- {q}" for q in safe_questions) + "\n")
    parts.append("\n## Questions to refuse or caveat\n\n" + "\n".join(f"- {q}" for q in refuse_or_caveat) + "\n")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Project chunks
# ---------------------------------------------------------------------------

PROJECT_NOTES = {
    # canonical_project: (kind, free-text addition)
    "Harmony": ("decoder",
                "VF code Harm3 (9,234 rows) routes to Harmony phases via lot-range decoding "
                "(B1, B2, B3, A4.1, A7-A10, ADB13/14, MF1). HarmCo splits into MF2 residential "
                "(169 rows) and X-X commercial parcels (205 rows; non-lot). HarmTo townhomes "
                "(1,587 single-lot rows + 568 range rows). Joins MUST use the (project, phase, lot) "
                "3-tuple — flat (project, lot) doublecounts $6.75M because MF1 lot 101 ≠ B1 lot 101."),
    "Parkway Fields": ("decoder",
                       "VF codes split: PWFS2 4-digit (D1/D2/G1/G2) + 5-digit B-suffix (B2). PWFT1 "
                       "4-digit (C1/C2). AultF 5-digit suffix routing — A → A1/A2.x, **B → B1** "
                       "(corrected in v2.1; v2.0 routed to B2 wrong by $4.0M / 1,499 rows). "
                       "AultF SR-suffix (0139SR/0140SR; 401 rows / ~$1.2M) inferred-unknown."),
    "Lomond Heights": ("decoder",
                       "LomHS1 (SFR 101-171) + LomHT1 (TH 172-215). Single phase 2A; product-type "
                       "split lives at lot grain via Lot Data ProdType. Allocation workbook: LH 2025.10."),
    "Arrowhead Springs": ("decoder", "VF codes ArroS1/ArroT1 routed to phases 123 / 456 by lot range."),
    "Scarlet Ridge": ("decoder",
                       "VF code ScaRdg routed to phases 1/2/3 by lot range. SctLot is **NOT** Scarlet "
                       "Ridge — moved to canonical project 'Scattered Lots' in v2.1 (was silently "
                       "inflating Scarlet Ridge by $6.55M in v2.0)."),
    "Salem Fields": ("clean",
                     "VF codes SalemS / SaleTR / SaleTT — already at 100% inventory match in v0; no "
                     "decoder needed. Range rows: ~776 across SaleTR + SaleTT."),
    "Willowcreek": ("clean",
                    "VF code WilCrk — already at 100% inventory match in v0. Range rows: 82."),
    "Lewis Estates": ("no_gl",
                      "Structural gap: 34 BCPD lots in inventory + 2025Status + Lot Data; no GL VF or "
                      "DR rows; no Collateral Report row; no allocation workbook. Cost is unknown."),
    "Meadow Creek": ("collateral_only",
                     "VF code MCreek (7,418 rows / $50.3M) but no row in 2025Status — collateral-only "
                     "project. Range rows: 1,416 / $14.96M (largest range-row project)."),
    "Ammon": ("no_gl", "16 active 2025Status lots; no GL coverage. Cost unknown."),
    "Cedar Glen": ("no_gl", "10 active 2025Status lots; no GL coverage. Cost unknown."),
    "Eagle Vista": ("no_gl", "5 active 2025Status lots; no GL coverage. Cost unknown."),
    "Eastbridge": ("no_gl", "6 active 2025Status lots; no GL coverage. Cost unknown."),
    "Erda": ("no_gl", "14 active 2025Status lots; no GL coverage. Cost unknown."),
    "Ironton": ("no_gl", "12 active 2025Status lots; no GL coverage. Cost unknown."),
    "Santaquin Estates": ("no_gl", "2 active 2025Status lots; no GL coverage. Cost unknown."),
    "Westbridge": ("no_gl", "6 active 2025Status lots; no GL coverage. Cost unknown."),
    "Scattered Lots": ("scattered",
                       "v2.1 NEW canonical project. Carries SctLot rows previously misattributed to "
                       "Scarlet Ridge in v2.0. Project-grain only — no lot-level inventory feed exists "
                       "for these scattered/custom lots. Confidence: inferred-unknown (canonical name "
                       "'Scattered Lots' is a working name pending source-owner confirmation)."),
}


def chunk_project(project_dict: dict) -> tuple[str, str]:
    """Return (relative_path, markdown) for one project chunk."""
    name = project_dict["canonical_project"]
    actuals = project_dict.get("actuals") or {}
    phases = project_dict.get("phases") or []
    notes_kind, notes_text = PROJECT_NOTES.get(name, ("default", ""))

    # Lot count active vs canonical
    n_lots_active = project_dict.get("lot_count_active_2025status", 0) or 0
    n_lots_total = project_dict.get("lot_count", 0) or 0
    n_phases = project_dict.get("phase_count", 0) or 0

    # Cost partitions (only present in v2.1)
    vf_lot = actuals.get("vf_lot_grain_sum_usd")
    vf_range = actuals.get("vf_range_grain_sum_usd")
    vf_comm = actuals.get("vf_commercial_grain_sum_usd")
    vf_sr = actuals.get("vf_sr_inferred_unknown_sum_usd")
    vf_total = actuals.get("vf_2018_2025_sum_usd")
    dr_total = actuals.get("dr_2016_2017_sum_usd_dedup")

    # Collateral signal
    has_collateral = any((ph.get("collateral") is not None) for ph in phases)
    coll_phase_count = sum(1 for ph in phases if ph.get("collateral") is not None)

    # ClickUp signal
    has_ck = any(any(lot.get("in_clickup_lottagged") for lot in ph.get("lots") or [])
                  for ph in phases)

    # Build summary
    if notes_kind == "no_gl":
        summary = (
            f"{name} is an active BCPD project with inventory rows but **no GL coverage**. "
            f"There are {n_lots_active} active 2025Status lots; no Vertical Financials rows, "
            f"no DataRails 38-col rows after the canonical filter, and no Collateral Report row. "
            f"This is a structural gap, not a v2.1 defect — the cost is **unknown**, not zero. "
            f"{notes_text}"
        )
        confidence = "low"
    elif notes_kind == "collateral_only":
        summary = (
            f"{name} is collateral-only in v2.1 — present in Vertical Financials and the Collateral "
            f"Report but not enumerated in 2025Status. {notes_text}"
        )
        confidence = "medium"
    elif notes_kind == "scattered":
        summary = (
            f"{name} is a v2.1-introduced canonical project. {notes_text} "
            f"In v2.0 these rows silently inflated Scarlet Ridge."
        )
        confidence = "inferred"
    elif notes_kind == "decoder":
        summary = (
            f"{name} carries decoder-derived per-lot VF cost in v2.1. {notes_text} All decoder "
            f"rules ship `confidence='inferred'` and `validated_by_source_owner=False`."
        )
        confidence = "inferred"
    elif notes_kind == "clean":
        summary = (
            f"{name} reaches the v2.1 lot grain without needing the v1 decoder. {notes_text}"
        )
        confidence = "high"
    else:
        summary = f"{name} is in scope for BCPD v2.1."
        confidence = "medium"

    # Facts
    facts = [
        f"Active 2025Status lot count: {n_lots_active}.",
        f"Total canonical lots in body: {n_lots_total}.",
        f"Phase count in body: {n_phases}.",
    ]
    if vf_total is not None and vf_total > 0:
        facts.append(f"VF 2018-2025 cost total: {_usd(vf_total)} (lot-grain {_usd(vf_lot)}; "
                     f"range/shell {_usd(vf_range)}; commercial {_usd(vf_comm)}; SR-inferred-unknown "
                     f"{_usd(vf_sr)}).")
    if dr_total and abs(dr_total) > 1:
        facts.append(f"DR 38-col 2016-17 cost (post-dedup): {_usd(dr_total)}.")
    if has_collateral:
        facts.append(f"Collateral Report rows: {coll_phase_count} phase entries (as_of 2025-12-31).")
    if has_ck:
        facts.append(f"ClickUp lot-tagged tasks present for this project.")
    if notes_kind == "no_gl":
        facts.append("**Cost is unknown, not zero.** No GL row exists for this project; do not estimate.")
    if notes_kind == "decoder":
        facts.append("Per-lot VF cost is decoder-derived; cite `confidence='inferred'` when reporting.")

    # Sources
    sources = [
        "output/operating_state_v2_1_bcpd.json",
        "output/state_quality_report_v2_1_bcpd.md",
    ]
    if notes_kind == "decoder":
        sources.append("data/reports/vf_lot_code_decoder_v1_report.md")
        sources.append("data/staged/vf_lot_code_decoder_v1.csv")
    if notes_kind in ("decoder", "no_gl", "collateral_only"):
        sources.append("data/reports/join_coverage_v0.md")
        sources.append("data/reports/join_coverage_simulation_v1.md")
    if notes_kind == "scattered":
        sources.append("scratch/vf_decoder_gl_finance_review.md")
        sources.append("data/reports/v2_0_to_v2_1_change_log.md")
    if has_collateral:
        sources.append("data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv")

    # Confidence paragraph
    if confidence == "inferred":
        confidence_para = (
            "Decoder-derived per-lot cost ships with `confidence='inferred'` and "
            "`validated_by_source_owner=False`. The mapping rules are evidence-backed but not "
            "source-owner-validated. Per-project totals from VF and DR are high-confidence in their "
            "source schema; what's inferred is the decomposition into specific (phase, lot) triples."
        )
    elif confidence == "low":
        confidence_para = (
            "Confidence is low because no GL data exists. Inventory facts (lot count, status) are "
            "high-confidence; cost is **unknown**. Do not substitute zero for unknown cost."
        )
    elif confidence == "high":
        confidence_para = (
            "Project lot-grain join was already at 100% (or near) in v0 without the decoder; v2.1 "
            "changes do not affect this project's matching. Per-project totals are high-confidence."
        )
    else:
        confidence_para = (
            "Mixed confidence: some facts are high (lot counts, presence flags) while cost rollups "
            "carry `inferred` or `medium` labels per their source."
        )

    # Caveats
    caveats = []
    if notes_kind == "decoder":
        caveats.append("Per-lot cost is `inferred` (decoder-derived; not source-owner-validated).")
        caveats.append("Range / shell rows for this project, if any, are kept at project+phase grain "
                        "via `vf_unattributed_shell_dollars` — not allocated to specific lots.")
    if name == "Harmony":
        caveats.append("Harmony joins MUST use the 3-tuple (project, phase, lot). Flat (project, lot) "
                        "doublecounts $6.75M (MF1 lot 101 ≠ B1 lot 101).")
        caveats.append("HarmCo X-X commercial parcels are NOT residential lots; tracked under "
                        "`commercial_parcels_non_lot`.")
    if name == "Parkway Fields":
        caveats.append("AultF SR-suffix (0139SR / 0140SR; 401 rows) is inferred-unknown.")
        caveats.append("AultF B-suffix routes to B1 (corrected in v2.1; was B2 in v2.0).")
    if name == "Scarlet Ridge":
        caveats.append("Do NOT report SctLot rows under Scarlet Ridge — they live under 'Scattered Lots' in v2.1.")
    if notes_kind == "no_gl":
        caveats.append("Cost is unknown for this project; do not infer from sibling projects.")
    if name == "Scattered Lots":
        caveats.append("Project-grain only; no lot-level inventory feed exists.")
        caveats.append("Canonical name not source-owner-validated.")

    # Allowed uses
    allowed_uses = [
        "RAG retrieval for project-specific Q&A about BCPD scope",
        "Grounding facts for an LLM agent answering business questions",
    ]
    if notes_kind in ("decoder", "scattered"):
        allowed_uses.append("Citing per-project cost with explicit `inferred` confidence label")
    if notes_kind == "no_gl":
        allowed_uses.append("Refusing cost-estimation queries on this project")

    # Safe questions
    safe = [
        f"How many active lots does {name} have in inventory?",
        f"What is the v2.1 status of {name} (active / no GL / decoder-derived / etc.)?",
    ]
    if vf_total and vf_total > 0:
        safe.append(f"What is {name}'s VF cost basis 2018-2025?")
        safe.append(f"What share of {name}'s cost is at lot grain vs project+phase grain?")
    if has_collateral:
        safe.append(f"Does {name} have a Collateral Report row, and what's the as-of date?")
    if name == "Harmony":
        safe.append("Why must Harmony cost queries use the 3-tuple join key?")
    if name == "Parkway Fields":
        safe.append("What did the AultF B-suffix correction in v2.1 fix?")

    # Refuse or caveat
    refuse = []
    if notes_kind == "no_gl":
        refuse.append(f"What is {name}'s actual cost? — REFUSE: no GL data; cost is unknown, not zero.")
        refuse.append(f"What is the cost-per-lot for {name}? — REFUSE: cannot compute without GL.")
    if name == "Scarlet Ridge":
        refuse.append("What is Scarlet Ridge's total cost including SctLot? — CAVEAT: SctLot dollars belong to 'Scattered Lots' in v2.1, not Scarlet Ridge.")
    if notes_kind == "decoder":
        refuse.append(f"Is {name}'s decoder-derived per-lot cost source-owner-validated? — REFUSE: no, all rules ship `inferred`.")
    if name == "Scattered Lots":
        refuse.append("What is the per-lot cost for a Scattered Lots lot? — REFUSE: project-grain only; no lot-level inventory feed.")
    refuse.append(f"Provide org-wide cost including {name}? — REFUSE: org-wide v2 is blocked.")

    chunk_id = f"project_{_slug(name)}"
    title = f"Project: {name}"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="project", title=title,
        project=name, source_files=sources,
        confidence=confidence, allowed_uses=allowed_uses,
        caveats=caveats or ["See state_quality_report_v2_1_bcpd.md for project-specific quality notes."],
    )
    body = _body(
        summary=summary, facts=facts, sources=sources,
        confidence_para=confidence_para,
        caveats_list=caveats or ["No project-specific caveats beyond the BCPD-wide guardrail set."],
        safe_questions=safe, refuse_or_caveat=refuse,
    )
    return (f"projects/{chunk_id}.md", fm + body)


# ---------------------------------------------------------------------------
# Coverage chunks
# ---------------------------------------------------------------------------

def chunk_coverage_inventory_gl() -> tuple[str, str]:
    chunk_id = "coverage_gl_inventory"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="coverage",
        title="Coverage: GL ↔ inventory join",
        project=None,
        source_files=["data/reports/join_coverage_v0.md",
                       "data/reports/join_coverage_simulation_v1.md",
                       "output/state_quality_report_v2_1_bcpd.md"],
        confidence="high",
        allowed_uses=["RAG grounding for coverage / fill-rate questions"],
        caveats=["Coverage metric is binary (≥1 GL row per inventory lot); "
                 "does not imply cost completeness."],
    )
    summary = (
        "Of the 1,285 high-confidence BCPD inventory lots in v2.1, **864 (67.2%) have ≥1 GL row** "
        "(was 810 / 63.0% in v0). The +54 lift comes from the AultF B→B1 correction reaching 11 "
        "previously-missed Parkway B1 lots, plus HarmCo residential MF2 matches once alpha lots "
        "were preserved in the validation index."
    )
    facts = [
        "v0 baseline: 810 / 1,285 inventory lots had ≥1 GL row (63.0%).",
        "v2.1 simulated: 864 / 1,285 (67.2%) — delta +54 lots / +4.2pp.",
        "Per-project: Salem Fields 100%, Willowcreek 100%, Scarlet Ridge 90.9%, Parkway Fields 78.0% (was 61.5%), Arrowhead Springs 65.0%, Harmony 53.7%, Lomond Heights 43.9%, Lewis Estates 0%.",
        "8 BCPD projects have 0% GL coverage (Lewis Estates + 7 active no-GL projects).",
    ]
    safe = [
        "What fraction of BCPD inventory lots have GL coverage?",
        "Which projects are at 100% GL match? Which at 0%?",
        "Did the AultF B→B1 correction change GL coverage?",
    ]
    refuse = [
        "What is the GL coverage for Hillcrest? — REFUSE: org-wide v2 is blocked; Hillcrest not in scope.",
        "Does GL coverage = cost completeness? — CAVEAT: no, coverage is binary; missing-cost-not-zero rule still applies.",
    ]
    return (f"coverage/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["data/reports/join_coverage_v0.md",
                          "data/reports/join_coverage_simulation_v1.md",
                          "output/state_quality_report_v2_1_bcpd.md"],
                confidence_para="The coverage numbers are directly counted from staged data; high confidence. "
                                "Forward-looking projections are deferred to W3 outputs.",
                caveats_list=["Binary coverage metric; not cost completeness.",
                              "Lewis Estates and 7 active projects are structural 0% gaps."],
                safe_questions=safe, refuse_or_caveat=refuse))


def chunk_coverage_inventory_clickup() -> tuple[str, str]:
    chunk_id = "coverage_clickup_inventory"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="coverage",
        title="Coverage: ClickUp lot-tagged ↔ inventory",
        project=None,
        source_files=["data/reports/join_coverage_v0.md",
                       "output/state_quality_report_v2_1_bcpd.md"],
        confidence="high",
        allowed_uses=["RAG grounding for ClickUp coverage and lot-tagging questions"],
        caveats=["Lot-tagging discipline is the upstream gate; only 21% of ClickUp tasks have both subdivision and lot_num."],
    )
    summary = (
        "ClickUp coverage is unchanged between v2.0 and v2.1: 1,177 lot-tagged tasks (filtered "
        "from 5,509 total), covering 1,091 distinct (project, lot) pairs across 9 BCPD communities. "
        "811 of 1,285 high-confidence inventory lots (63.1%) have ≥1 lot-tagged task."
    )
    facts = [
        "Total ClickUp tasks: 5,509. Lot-tagged subset (subdivision + lot_num both populated): 1,177.",
        "Distinct (project, lot) pairs in lot-tagged subset: 1,091.",
        "Inventory match: 811 / 1,285 high-confidence inventory lots (63.1%).",
        "Phase fill within lot-tagged subset: 92.86% (much higher than 19.86% across the full file).",
        "Subdivision typo crosswalk applied: Aarowhead → Arrowhead Springs, Scarlett Ridge → Scarlet Ridge, Park Way → Parkway Fields, etc.",
        "Arrowhead-173 outlier (75 tasks on one lot) flagged but not removed.",
    ]
    safe = [
        "How many ClickUp tasks are lot-tagged in BCPD scope?",
        "Which subdivisions are in scope for ClickUp lot-tagged matching?",
        "What's the ClickUp coverage of inventory lots?",
    ]
    refuse = [
        "What is the ClickUp progress for a lot not in the lot-tagged subset? — REFUSE: 79% of tasks are not lot-tagged; do not extrapolate.",
        "Does ClickUp coverage equal active-construction coverage? — CAVEAT: no; ClickUp is a per-lot signal where present.",
    ]
    return (f"coverage/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["data/reports/join_coverage_v0.md",
                          "output/state_quality_report_v2_1_bcpd.md",
                          "data/reports/staged_clickup_validation_report.md"],
                confidence_para="Counts derived directly from staged_clickup_tasks.parquet; high confidence on the "
                                "totals. The 21% lot-tagging rate is an operational/process gate, not a data defect.",
                caveats_list=["79% of ClickUp tasks lack subdivision/lot_num and are excluded from lot matching.",
                              "Arrowhead lot 173 has 75 tasks (likely template parent); flagged."],
                safe_questions=safe, refuse_or_caveat=refuse))


def chunk_coverage_full_triangle() -> tuple[str, str]:
    chunk_id = "coverage_full_triangle"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="coverage",
        title="Coverage: Full triangle (GL ∧ ClickUp ∧ inventory)",
        project=None,
        source_files=["data/reports/join_coverage_v0.md",
                       "data/reports/join_coverage_simulation_v1.md"],
        confidence="high",
        allowed_uses=["RAG grounding for full-triangle coverage questions"],
        caveats=["Triangle requires all three data sources; missing any one drops a lot from the count."],
    )
    summary = (
        "Full triangle = inventory lots that have ≥1 GL row AND ≥1 ClickUp lot-tagged task. "
        "v0 baseline: 476 / 1,285 (37.0%). v2.1: 478 / 1,285 (37.2%, +2 lots). On the active-only "
        "subset (n=965), triangle is 49.2% in v2.1."
    )
    facts = [
        "v0 baseline triangle: 476 lots (37.0%).",
        "v2.1 triangle: 478 lots (37.2%) — modest delta.",
        "Active-only subset triangle: ~49% (965 active lots).",
        "Per-project triangle: Willowcreek 100%, Salem Fields 87.8%, Scarlet Ridge 59.1%, Lomond Heights 43.0%, Harmony 35.0%, Parkway Fields 23.7%, Arrowhead Springs 9.7%.",
    ]
    safe = [
        "What is the BCPD full triangle coverage?",
        "Which projects have the highest full-triangle coverage?",
        "Why didn't v2.1's correctness fixes increase the triangle much?",
    ]
    refuse = [
        "Is full triangle coverage the right metric for cost completeness? — CAVEAT: no; binary triangle says nothing about cost amounts.",
    ]
    return (f"coverage/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["data/reports/join_coverage_v0.md", "data/reports/join_coverage_simulation_v1.md"],
                confidence_para="High confidence on the binary count; the modest v2.1 delta is honest — "
                                "v2.1's correctness wins are on dollars, not on lot-binary coverage.",
                caveats_list=["Lot-tagging discipline gates ClickUp side; structural no-GL gates the GL side."],
                safe_questions=safe, refuse_or_caveat=refuse))


def chunk_coverage_no_gl_projects() -> tuple[str, str]:
    chunk_id = "coverage_no_gl_projects"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="coverage",
        title="Coverage: BCPD projects with inventory but no GL",
        project=None,
        source_files=["output/state_quality_report_v2_1_bcpd.md",
                       "output/operating_state_v2_1_bcpd.json"],
        confidence="high",
        allowed_uses=["RAG grounding for missing-cost / structural-gap questions"],
        caveats=["Cost is unknown for these projects; do not substitute zero."],
    )
    summary = (
        "Eight BCPD-scope projects have inventory rows but **no GL coverage**. They appear in "
        "2025Status (and in some cases inventory + Lot Data) but have zero VF or DR rows after the "
        "BCPD canonical filter, and no Collateral Report row. Cost is unknown — not zero — for "
        "these projects. This is a structural gap that requires new data, not a v2.1 defect."
    )
    facts = [
        "Lewis Estates: 34 lots, no GL, no Collateral row, no allocation workbook.",
        "Ammon: 16 lots, no GL.",
        "Erda: 14 lots, no GL.",
        "Ironton: 12 lots, no GL.",
        "Cedar Glen: 10 lots, no GL.",
        "Eastbridge: 6 lots, no GL.",
        "Westbridge: 6 lots, no GL.",
        "Eagle Vista: 5 lots, no GL.",
        "Santaquin Estates: 2 lots, no GL.",
    ]
    safe = [
        "Which BCPD projects have no GL coverage?",
        "Why is Lewis Estates' cost unknown?",
        "What does it take to fix the no-GL gap?",
    ]
    refuse = [
        "What is Ammon's actual cost? — REFUSE: cost is unknown, not zero.",
        "Estimate Lewis Estates' cost from sibling projects? — REFUSE: do not infer; structural gap.",
    ]
    return (f"coverage/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["output/state_quality_report_v2_1_bcpd.md",
                          "output/operating_state_v2_1_bcpd.json",
                          "data/reports/coverage_improvement_opportunities.md"],
                confidence_para="High confidence that these projects have zero GL coverage; this is observed "
                                "directly from staged_gl_transactions_v2.parquet. The fix requires new source data.",
                caveats_list=["Cost = unknown; never substitute zero.",
                              "Ammon, Erda may also appear in DR-era IA Breakdown but project-grain only."],
                safe_questions=safe, refuse_or_caveat=refuse))


def chunk_coverage_validation_queue() -> tuple[str, str]:
    chunk_id = "coverage_source_owner_validation_queue"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="coverage",
        title="Coverage: Source-owner validation queue",
        project=None,
        source_files=["output/operating_state_v2_1_bcpd.json",
                       "scratch/vf_decoder_gl_finance_review.md",
                       "scratch/vf_decoder_ops_allocation_review.md"],
        confidence="high",
        allowed_uses=["RAG grounding for 'what's still inferred' questions"],
        caveats=["Items here gate confidence promotion from `inferred` to higher."],
    )
    summary = (
        "v2.1 ships with 8 open source-owner questions. Each gates promotion of a corresponding "
        "decoder/mapping rule from `confidence='inferred'` to higher. v2.1 is internally "
        "consistent without any of them being resolved; promotion to 'high' / 'validated' "
        "requires sign-off."
    )
    facts = [
        "Q1 — Harm3 lot-range routing: confirm phase is recoverable only via lot range.",
        "Q2 — AultF SR-suffix meaning (0139SR, 0140SR; 401 rows / 2 lots).",
        "Q3 — AultF B-suffix range: confirm B1 max lot = 211.",
        "Q4 — MF1 vs B1 overlap 101-116: sample audit for SFR/B1 leakage.",
        "Q5 — SctLot canonical name and program identity ('Scattered Lots' is working name).",
        "Q6 — Range-entry allocation method (equal split / sales-weighted / unit-fixed).",
        "Q7 — HarmCo X-X commercial parcels: ontology entity and allocation source.",
        "Q8 — DR 38-col phase recovery: any source-system attribute we missed?",
    ]
    safe = [
        "What still needs source-owner validation in v2.1?",
        "When can the v1 VF decoder rules be promoted from inferred?",
        "What's blocking v2.2's range-row per-lot expansion?",
    ]
    refuse = [
        "Promote a rule to source-owner-validated without sign-off? — REFUSE: explicit human sign-off required.",
    ]
    return (f"coverage/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["output/operating_state_v2_1_bcpd.json",
                          "scratch/vf_decoder_gl_finance_review.md",
                          "scratch/vf_decoder_ops_allocation_review.md"],
                confidence_para="High confidence that these are the open items; the JSON's "
                                "`source_owner_questions_open` array is the canonical list.",
                caveats_list=["Until each is resolved, the corresponding rule stays `inferred`."],
                safe_questions=safe, refuse_or_caveat=refuse))


# ---------------------------------------------------------------------------
# Cost-source hierarchy chunks
# ---------------------------------------------------------------------------

def chunk_cost_source_vf() -> tuple[str, str]:
    chunk_id = "cost_source_vertical_financials"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="cost_source",
        title="Cost source: Vertical Financials (BCPD 2018-2025 primary)",
        project=None,
        source_files=["scratch/gl_financials_findings.md",
                       "data/reports/guardrail_check_v0.md",
                       "output/state_quality_report_v2_1_bcpd.md"],
        confidence="high",
        allowed_uses=["RAG grounding for any BCPD 2018-2025 cost question"],
        caveats=["VF is one-sided; not a balanced trial balance."],
    )
    summary = (
        "Vertical Financials 46-col is the **primary** BCPD cost source for 2018-2025. It carries "
        "100% project + lot fill across 83,433 rows and ~$346.5M of one-sided capitalized cost. "
        "Each row records the asset-side debit of an entry that capitalized construction cost into "
        "the lot/project. The credit-side (cash, AP, accrued) lives in a different feed not "
        "included here."
    )
    facts = [
        "Rows: 83,433 (BCPD only, 2018-2025).",
        "Account codes: 1535 (Permits & Fees), 1540 (Direct Construction), 1547 (Direct Construction-Lot).",
        "Total $346.5M one-sided.",
        "Project + lot fill: 100% (1,306 distinct (project, lot) pairs).",
        "Phase fill: 0% — phase is NOT in VF; derive from inventory + Lot Data + decoder.",
        "Use the 3-tuple (project, phase, lot) join key for any per-lot cost rollup.",
    ]
    safe = [
        "Where does BCPD's 2018-2025 cost basis come from?",
        "Why is VF described as 'one-sided'?",
        "What account codes does VF cover?",
    ]
    refuse = [
        "What is the VF debit-credit balance? — REFUSE: VF is one-sided by design; not a trial balance.",
        "Aggregate VF and QB register together for 2025 BCPD? — REFUSE: zero account-code overlap; would double-count.",
    ]
    return (f"cost_sources/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["scratch/gl_financials_findings.md",
                          "data/reports/guardrail_check_v0.md",
                          "output/state_quality_report_v2_1_bcpd.md"],
                confidence_para="High confidence on both the row counts and the one-sided structural "
                                "interpretation. VF is the canonical lot-level cost basis for BCPD 2018-2025.",
                caveats_list=["One-sided: do not expect debit = credit.",
                              "Phase column is empty — must come from inventory or decoder."],
                safe_questions=safe, refuse_or_caveat=refuse))


def chunk_cost_source_dr_dedup() -> tuple[str, str]:
    chunk_id = "cost_source_datarails_38col_dedup"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="cost_source",
        title="Cost source: DataRails 38-col (BCPD 2016-17 — dedup mandatory)",
        project=None,
        source_files=["scratch/gl_financials_findings.md",
                       "data/staged/staged_gl_transactions_v2_validation_report.md"],
        confidence="high",
        allowed_uses=["RAG grounding for BCPD 2016-17 cost questions"],
        caveats=["Raw DR sums are wrong by ~2x without dedup."],
    )
    summary = (
        "DataRails 38-col is the BCPD cost source for 2016-02 through 2017-02. **DR is 2.16× "
        "row-multiplied at the source** — every posting line appears 2-3 times consecutively with "
        "identical financial fields and slightly different metadata bits. Any naive sum is wrong by "
        "~2×. The build pipeline deduplicates on a 9-field canonical key before any cost rollup."
    )
    facts = [
        "Raw rows (BCPD): 111,497 across 14 monthly extracts.",
        "Post-dedup rows: 51,694 (multiplicity 2.16×).",
        "Dedup key: (entity_name, posting_date, account_code, amount, project_code, lot, memo_1, description, batch_description).",
        "Pick canonical row preferring most non-null metadata (account_name + account_type both populated).",
        "Post-dedup balance: debit ≈ credit ≈ $330.9M (within 0.15%).",
        "Lot fill in DR (BCPD): 49.5% (vs 100% in VF).",
        "Phase fill in DR: 0% (project-grain only for cost rollups).",
    ]
    safe = [
        "Why does DataRails 38-col need deduplication?",
        "What's the dedup key for DR 38-col?",
        "What's BCPD's 2016-17 cost from DR after dedup?",
    ]
    refuse = [
        "Sum DR amounts directly from raw v2.parquet? — REFUSE: 2.16× off without dedup.",
        "Roll DR cost up to phase grain? — REFUSE: phase is 0% filled in DR.",
    ]
    return (f"cost_sources/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["scratch/gl_financials_findings.md",
                          "data/staged/staged_gl_transactions_v2_validation_report.md"],
                confidence_para="High confidence that dedup is required and that the 9-field key recovers a "
                                "balanced two-sided journal. The build pipeline applies this automatically.",
                caveats_list=["Raw v2 parquet is preserved unchanged; dedup happens at query time.",
                              "DR has no Harmony, Parkway Fields, or other post-2018 projects."],
                safe_questions=safe, refuse_or_caveat=refuse))


def chunk_cost_source_qb_tieout() -> tuple[str, str]:
    chunk_id = "cost_source_qb_register_tieout_only"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="cost_source",
        title="Cost source: QB Register (tie-out only)",
        project=None,
        source_files=["scratch/gl_financials_findings.md",
                       "output/state_quality_report_v2_1_bcpd.md"],
        confidence="high",
        allowed_uses=["RAG grounding for BCPD vendor / cash / AP queries on 2025"],
        caveats=["Different chart of accounts; never aggregate against VF/DR."],
    )
    summary = (
        "QB Register 12-col carries 2,922 rows for BCPD 2025. It uses a different chart of accounts "
        "(177 codes, e.g. 132-XXX, 510-XXX) with **zero account_code overlap to VF or DR**. It is "
        "**tie-out only** — never aggregate against VF or DR; would double-count. Use exclusively "
        "for 2025 BCPD vendor / cash / AP queries."
    )
    facts = [
        "Rows: 2,922 (BCPD 2025 only).",
        "Account codes: 177 distinct, e.g. 132-XXX (Inventory Asset), 510-XXX, 210-100 (AP).",
        "Project / lot fill: 0% (no project_code, no lot field).",
        "Vendor fill: 95.7% (161 distinct vendors); only place vendor lives.",
        "Account-code overlap with VF/DR: zero.",
        "Sum: balanced (debit = credit ≈ $215.25M to ten decimal places).",
    ]
    safe = [
        "What is QB Register used for in v2.1?",
        "Why can't we aggregate QB against VF?",
        "Where do BCPD vendor names come from?",
    ]
    refuse = [
        "Sum QB + VF for 2025 BCPD? — REFUSE: double-counts; different charts.",
        "Provide vendor analysis for 2024 BCPD? — REFUSE: QB is 2025-only.",
        "Provide per-lot cost from QB? — REFUSE: no lot field in QB.",
    ]
    return (f"cost_sources/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["scratch/gl_financials_findings.md",
                          "output/state_quality_report_v2_1_bcpd.md"],
                confidence_para="High confidence on the chart-of-accounts disjointness and the tie-out-only directive.",
                caveats_list=["No project / lot tagging; cannot join to inventory.",
                              "2025-only; do not extrapolate."],
                safe_questions=safe, refuse_or_caveat=refuse))


def chunk_cost_source_range_shell() -> tuple[str, str]:
    chunk_id = "cost_source_range_shell_rows"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="cost_source",
        title="Cost source: Range / shell rows (project+phase grain)",
        project=None,
        source_files=["data/reports/vf_lot_code_decoder_v1_report.md",
                       "scratch/vf_decoder_gl_finance_review.md",
                       "output/operating_state_v2_1_bcpd.json"],
        confidence="inferred",
        allowed_uses=["RAG grounding for shared-shell / shared-infrastructure cost questions"],
        caveats=["Range rows are NEVER allocated to specific lots in v2.1."],
    )
    summary = (
        "Range-form GL rows (lot strings like '3001-06', '0009-12', '0172-175') are summary "
        "postings that span multiple lots — typically shared-shell or shared-infrastructure costs. "
        "v2.1 keeps them at the **project+phase grain** via `vf_unattributed_shell_dollars` per "
        "phase, totaling **4,020 rows / $45,752,047** across 8 VF codes. They are NOT allocated "
        "to specific lots."
    )
    facts = [
        "Range rows total: 4,020 across 8 VF codes (HarmTo, LomHT1, PWFT1, ArroT1, MCreek, SaleTT, SaleTR, WilCrk).",
        "Range dollars total: $45,752,047 (~13% of BCPD VF cost basis).",
        "Largest contributor: MCreek (1,416 rows / $14.96M) followed by PWFT1 (1,114 / $15.19M).",
        "Memo evidence: 'shell allocation', design/engineering vendors, shared-infra accounts.",
        "Per-row dollar magnitude: median $3,304, mean $11,381 — real cost line items.",
        "v2.2 candidate: per-lot expansion (equal split / sales-weighted / unit-fixed) — needs source-owner sign-off.",
    ]
    safe = [
        "How are range-form GL rows treated in v2.1?",
        "What is `vf_unattributed_shell_dollars`?",
        "Why aren't range rows expanded to per-lot in v2.1?",
    ]
    refuse = [
        "Allocate the $45.75M of range cost to specific lots? — REFUSE: requires allocation-method sign-off.",
        "Drop range rows entirely? — REFUSE: they are real cost; project+phase rollup needs them.",
        "Add range dollars to per-lot vf_actual_cost_3tuple_usd? — REFUSE: explicitly excluded by design.",
    ]
    return (f"cost_sources/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["data/reports/vf_lot_code_decoder_v1_report.md",
                          "scratch/vf_decoder_gl_finance_review.md",
                          "output/operating_state_v2_1_bcpd.json"],
                confidence_para="High confidence on the interpretation (memo + magnitude evidence). Inferred on the "
                                "specific allocation method for any future per-lot expansion.",
                caveats_list=["$45.75M not at lot grain in v2.1.",
                              "Per-lot expansion deferred until source-owner sign-off."],
                safe_questions=safe, refuse_or_caveat=refuse))


def chunk_cost_source_commercial_parcels() -> tuple[str, str]:
    chunk_id = "cost_source_commercial_parcels"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="cost_source",
        title="Cost source: HarmCo commercial parcels (non-lot inventory)",
        project="Harmony",
        source_files=["scratch/vf_decoder_ops_allocation_review.md",
                       "data/reports/vf_lot_code_decoder_v1_report.md",
                       "output/operating_state_v2_1_bcpd.json"],
        confidence="inferred",
        allowed_uses=["RAG grounding for Harmony commercial-parcel questions"],
        caveats=["Commercial parcels are NOT residential lots; not in LotState."],
    )
    summary = (
        "HarmCo carries 31 distinct lot strings. v2.1 splits them: 20 residential lots `0000A01`–"
        "`0000B10` map to Harmony phase MF2 at the lot grain (169 rows). The remaining 11 commercial "
        "parcels `0000A-A` through `0000K-K` are **non-lot inventory** — they have no row in Lot Data, "
        "2025Status, inventory closing report, or any allocation workbook. v2.1 tracks them under "
        "`commercial_parcels_non_lot` per project. They are NOT modeled as residential LotState."
    )
    facts = [
        "Commercial parcels: 11 X-X strings (A-A through K-K), 205 rows total.",
        "Dollar volume: ~$2.6M across all commercial parcels in HarmCo.",
        "Concentration: pads A-A (106 rows) and B-B (80 rows) dominate; pads C-K are 1-3 rows each.",
        "Account distribution: 88.5% Direct Construction (real building activity, not just allocation).",
        "Not in any allocation workbook (Flagship Allocation Workbook v3 has no Harmony Commercial entry).",
        "Future ontology entity (`CommercialParcel`?) deferred to v0.2.",
    ]
    safe = [
        "What are the HarmCo X-X parcels?",
        "Why aren't commercial parcels in Harmony's LotState?",
        "How much commercial parcel cost is in Harmony?",
    ]
    refuse = [
        "Add HarmCo commercial dollars to Harmony's residential lot rollup? — REFUSE: violates non-lot inventory rule.",
        "Show Harmony residential cost including commercial pads? — REFUSE: commercial pads are not residential.",
    ]
    return (f"cost_sources/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["scratch/vf_decoder_ops_allocation_review.md",
                          "data/reports/vf_lot_code_decoder_v1_report.md",
                          "output/operating_state_v2_1_bcpd.json"],
                confidence_para="Inferred (decoder-derived split). Strong evidence the X-X parcels are commercial: "
                                "VF code name, no residential Lot Data match, A-K letter sequencing.",
                caveats_list=["205 rows kept out of residential LotState by design.",
                              "Ontology decision pending."],
                safe_questions=safe, refuse_or_caveat=refuse))


def chunk_cost_source_missing_not_zero() -> tuple[str, str]:
    chunk_id = "cost_source_missing_cost_is_not_zero"
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="cost_source",
        title="Cost source: Missing cost is missing, not zero",
        project=None,
        source_files=["output/agent_context_v2_1_bcpd.md",
                       "output/state_quality_report_v2_1_bcpd.md"],
        confidence="high",
        allowed_uses=["RAG grounding for refusal of cost-estimation queries on no-GL projects"],
        caveats=["Hard rule; never violated."],
    )
    summary = (
        "A project or lot with no GL row has cost = **unknown** (null in the JSON), never $0. "
        "Reporting $0 would falsely imply the project incurred no cost when in reality the cost "
        "is simply not in the available source. v2.1 enforces this rule across all rollups: 8 "
        "BCPD projects (Lewis Estates + 7 active no-GL projects) carry inventory but have null "
        "cost fields, not zero."
    )
    facts = [
        "Affected projects: Lewis Estates, Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge.",
        "Total unknown-cost lots: ~105 across these 9 projects.",
        "DR 38-col gap (2017-03 → 2018-06): 15 months of zero rows for any entity — also 'unknown', not zero.",
        "Hillcrest + Flagship Belmont post-2017-02: blocked org-wide; cost unknown for v2.1 scope.",
    ]
    safe = [
        "What does 'missing cost' mean in v2.1?",
        "How does v2.1 distinguish unknown from zero?",
        "Which BCPD projects have unknown cost?",
    ]
    refuse = [
        "Substitute $0 for missing cost? — REFUSE: violates the missing-cost-is-not-zero rule.",
        "Estimate Lewis Estates' cost from sibling projects? — REFUSE: structural gap; do not infer.",
    ]
    return (f"cost_sources/{chunk_id}.md",
            fm + _body(
                summary=summary, facts=facts,
                sources=["output/agent_context_v2_1_bcpd.md",
                          "output/state_quality_report_v2_1_bcpd.md"],
                confidence_para="High confidence; hard rule enforced at the agent layer.",
                caveats_list=["Never substitute zero; never infer from siblings."],
                safe_questions=safe, refuse_or_caveat=refuse))


# ---------------------------------------------------------------------------
# Guardrail chunks
# ---------------------------------------------------------------------------

def _guardrail_chunk(chunk_id: str, title: str, summary: str, facts: list[str],
                     safe: list[str], refuse: list[str], sources: list[str],
                     confidence_para: str, caveats_list: list[str]) -> tuple[str, str]:
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="guardrail",
        title=title, project=None,
        source_files=sources, confidence="high",
        allowed_uses=["RAG grounding for refusal / caveat decisions",
                       "Anchor for any answer that touches this guardrail's scope"],
        caveats=caveats_list,
    )
    return (f"guardrails/{chunk_id}.md",
            fm + _body(summary=summary, facts=facts, sources=sources,
                        confidence_para=confidence_para,
                        caveats_list=caveats_list,
                        safe_questions=safe, refuse_or_caveat=refuse))


def chunk_guardrail_bcpd_only():
    return _guardrail_chunk(
        chunk_id="guardrail_bcpd_only",
        title="Guardrail: BCPD-only scope",
        summary="v2.1 covers BCPD (Building Construction Partners) and its horizontal-developer "
                 "affiliates BCPBL, ASD, BCPI. It does NOT cover Hillcrest, Flagship Belmont, "
                 "Lennar, or external customers. Org-wide is explicitly out of scope.",
        facts=[
            "In scope: BCPD, BCPBL (Ben Lomond), ASD (Arrowhead Springs Developer), BCPI (BCP Investor).",
            "Out of scope: Hillcrest Road at Saratoga LLC, Flagship Belmont Phase two LLC, Lennar, EXT/EXT-Comm/Church.",
            "GL filter: entity_name = 'Building Construction Partners, LLC'.",
            "2025Status / Lot Data filter: HorzCustomer = 'BCP'.",
        ],
        safe=["What does BCPD include in v2.1?",
               "Are the horizontal developers in scope?",
               "Is Lennar in BCPD's scope?"],
        refuse=["Provide cost for Hillcrest? — REFUSE: out of v2.1 scope.",
                 "Aggregate across all entities? — REFUSE: not org-wide."],
        sources=["output/agent_context_v2_1_bcpd.md", "output/operating_state_v2_1_bcpd.json"],
        confidence_para="High confidence; BCPD-only is the canonical scope of v2.1.",
        caveats_list=["Track B (org-wide) is a roadmap item; not v2.1."],
    )


def chunk_guardrail_orgwide_blocked():
    return _guardrail_chunk(
        chunk_id="guardrail_orgwide_unavailable",
        title="Guardrail: Org-wide v2 is unavailable",
        summary="Hillcrest Road at Saratoga LLC and Flagship Belmont Phase two LLC have GL rows "
                 "only through 2017-02. Publishing an org-wide rollup today would mix 2024-2025 "
                 "BCPD activity against 2017-frozen non-BCPD entities — misleading regardless of "
                 "labeling. The unblocking artifact is a fresh GL pull for those entities covering "
                 "2017-03 onward.",
        facts=[
            "Hillcrest GL rows: 12,093 (all in 2016-01 → 2017-02).",
            "Flagship Belmont GL rows: 495 (all in 2016-04 → 2017-02).",
            "Dump-wide gap 2017-03 → 2018-06: zero rows for any entity (~15 months).",
            "v2.1 refuses org-wide questions explicitly via Q7 in the Q&A harness.",
        ],
        safe=["Why is org-wide v2 blocked?",
               "What would unblock org-wide v2?",
               "Does Hillcrest have any post-2017-02 GL?"],
        refuse=["Roll up actuals across BCPD + Hillcrest + Flagship Belmont? — REFUSE: blocked.",
                 "Estimate non-BCPD post-2017 cost? — REFUSE: do not infer."],
        sources=["scratch/bcpd_financial_readiness.md",
                  "data/reports/guardrail_check_v0.md",
                  "output/agent_context_v2_1_bcpd.md"],
        confidence_para="High confidence on the structural gap. Refusal is the right default until fresh data lands.",
        caveats_list=["Track B remains a roadmap track."],
    )


def chunk_guardrail_inferred_decoder():
    return _guardrail_chunk(
        chunk_id="guardrail_inferred_decoder_rules",
        title="Guardrail: Decoder-derived mappings are inferred",
        summary="Every rule in the v1 VF lot-code decoder ships `confidence='inferred'` and "
                 "`validated_by_source_owner=False`. v2.1 is strictly more accurate than v2.0 even "
                 "at inferred confidence — the rules are evidence-backed, not blessed. Promotion "
                 "requires explicit source-owner sign-off.",
        facts=[
            "Decoder rules cover: Harm3, HarmCo (split), HarmTo, LomHS1, LomHT1, PWFS2, PWFT1, AultF, ArroS1, ArroT1, ScaRdg, SctLot.",
            "Match rate against Lot Data: 93.9% across 65,958 in-scope VF rows.",
            "Confidence label: 'inferred' for all 12 rules.",
            "Source-owner questions open: 8 (see source_owner_validation_queue chunk).",
        ],
        safe=["Are v2.1's decoder rules source-owner-validated?",
               "What confidence level do decoder-derived per-lot costs carry?",
               "Why is per-lot cost labeled inferred?"],
        refuse=["Promote a decoder rule from inferred without sign-off? — REFUSE.",
                 "Cite per-lot cost without the inferred label? — CAVEAT: always include the confidence."],
        sources=["data/reports/vf_lot_code_decoder_v1_report.md",
                  "data/staged/vf_lot_code_decoder_v1.csv",
                  "output/agent_context_v2_1_bcpd.md"],
        confidence_para="High confidence on the rule itself; inferred on the mapping outputs.",
        caveats_list=["Inferred ≠ low quality; just unvalidated."],
    )


def chunk_guardrail_harmony_3tuple():
    return _guardrail_chunk(
        chunk_id="guardrail_harmony_3tuple_join",
        title="Guardrail: Harmony joins require project + phase + lot",
        summary="In Harmony, lot numbers 101–116 exist in two distinct phases — MF1 (multi-family) "
                 "and B1 (single-family). They are different physical assets. A flat (project, lot) "
                 "join collapses them onto one inventory row, producing a $6.75M attribution error. "
                 "v2.1 enforces the 3-tuple (canonical_project, canonical_phase, canonical_lot_number).",
        facts=[
            "Harmony MF1 lots 101-116 are townhomes; B1 lots 101-116 are single-family.",
            "VF Harm3 (rows for 0101-0116): 1,733 rows / $5.35M (correctly B1 via lot-range routing).",
            "VF HarmTo (rows for 0001-0116): 53 rows / $1.40M for lots 101-116 (correctly MF1).",
            "Flat-join error: $443K wrongly attributed to one inventory row, $99K dropped.",
            "Project-wide error if flat-join: ~$6.75M.",
            "v2.1 implementation: every lot's vf_actual_cost_3tuple_usd is computed at the 3-tuple.",
        ],
        safe=["Why does Harmony need the 3-tuple join?",
               "What's the double-count risk on a flat (project, lot) join?",
               "Does the 3-tuple rule apply only to Harmony?"],
        refuse=["Use a flat (project, lot) join for Harmony cost? — REFUSE: $6.75M error risk.",
                 "Roll Harmony cost without phase? — REFUSE: phase is part of the canonical key."],
        sources=["scratch/vf_decoder_gl_finance_review.md",
                  "data/reports/v2_0_to_v2_1_change_log.md",
                  "docs/bcpd_operating_state_architecture.md"],
        confidence_para="High confidence on the data evidence; both Harm3 and HarmTo carry rows for the same lot strings.",
        caveats_list=["Rule applies project-wide; Harmony is the visible case."],
    )


def chunk_guardrail_sctlot_scattered():
    return _guardrail_chunk(
        chunk_id="guardrail_sctlot_scattered_lots",
        title="Guardrail: SctLot is Scattered Lots, not Scarlet Ridge",
        summary="In v2.0, 1,130 SctLot rows / $6.55M were silently attributed to Scarlet Ridge "
                 "(inflating Scarlet Ridge's project-grain cost by ~46%). v2.1 introduces a separate "
                 "canonical project 'Scattered Lots' to hold these rows. Confidence stays "
                 "inferred-unknown (canonical name pending source-owner confirmation).",
        facts=[
            "SctLot rows: 1,130 across 6 distinct lot strings (0001, 0002, 0003, 0008, 0029, 0639).",
            "SctLot dollars: $6,553,893 — moved off Scarlet Ridge in v2.1.",
            "Evidence: zero lot-number overlap with ScaRdg (101-152); 'SctLot' appears as accounting bucket in invoice IDs.",
            "Vendor mix: custom-build / scattered-construction trades (Bob Craghead Plumbing, etc.).",
            "v2.1 canonical_project: 'Scattered Lots' (working name).",
            "Project-grain only — no lot-level inventory feed exists.",
        ],
        safe=["What is SctLot in v2.1?",
               "Why is SctLot not Scarlet Ridge?",
               "What was the v2.0 misattribution?"],
        refuse=["Report SctLot dollars under Scarlet Ridge in v2.1? — REFUSE: violates v2.1 separation.",
                 "Provide lot-level cost for Scattered Lots? — REFUSE: project-grain only."],
        sources=["scratch/vf_decoder_gl_finance_review.md",
                  "data/reports/v2_0_to_v2_1_change_log.md",
                  "output/operating_state_v2_1_bcpd.json"],
        confidence_para="Medium-high confidence on disjointness from Scarlet Ridge. "
                          "Inferred-unknown on the canonical name.",
        caveats_list=["Canonical name not source-owner-validated.",
                       "Lot 0639 is an outlier; specifically inferred-unknown."],
    )


def chunk_guardrail_range_not_lot_level():
    return _guardrail_chunk(
        chunk_id="guardrail_range_rows_not_lot_level",
        title="Guardrail: Range / shell rows are not lot-level cost",
        summary="$45.75M / 4,020 rows of range-form GL postings (e.g. '3001-06') are kept at "
                 "project+phase grain via vf_unattributed_shell_dollars per phase. They are "
                 "shared-shell or shared-infrastructure costs that genuinely span multiple lots and "
                 "have not been allocated. Per-lot expansion is a v2.2 candidate that requires "
                 "source-owner sign-off on the allocation method.",
        facts=[
            "Range rows: 4,020 / $45.75M across 8 VF codes.",
            "Surfaced per-phase as `vf_unattributed_shell_dollars` and `vf_unattributed_shell_rows`.",
            "Most affected: PWFT1 ($15.19M), MCreek ($14.96M), HarmTo ($5.51M).",
            "Memo evidence: 'shell allocation' is the most common memo on these rows.",
            "v2.1 explicitly does NOT allocate to specific lots.",
        ],
        safe=["How are range / shell rows treated in v2.1?",
               "Why are they not allocated to specific lots?",
               "What allocation methods are candidates for v2.2?"],
        refuse=["Allocate range dollars to specific lots in v2.1? — REFUSE: pending allocation-method sign-off.",
                 "Add range dollars to per-lot vf_actual_cost_3tuple_usd? — REFUSE: explicitly excluded."],
        sources=["data/reports/vf_lot_code_decoder_v1_report.md",
                  "scratch/vf_decoder_gl_finance_review.md",
                  "output/operating_state_v2_1_bcpd.json"],
        confidence_para="High confidence on the interpretation; inferred on per-lot allocation method (deferred to v2.2).",
        caveats_list=["$45.75M is ~13% of BCPD VF cost basis; surface separately in any total."],
    )


def chunk_guardrail_commercial_not_residential():
    return _guardrail_chunk(
        chunk_id="guardrail_commercial_not_residential",
        title="Guardrail: Commercial parcels are not residential lots",
        summary="The 11 HarmCo X-X parcels (`0000A-A` through `0000K-K`, 205 rows / ~$2.6M) are "
                 "commercial parcels in the Harmony master plan. They have no row in inventory, "
                 "Lot Data, 2025Status, or any allocation workbook. v2.1 tracks them under "
                 "`commercial_parcels_non_lot` per project. They are NOT modeled as residential "
                 "LotState and must NOT be rolled into residential lot totals.",
        facts=[
            "Commercial parcels: 11 X-X strings (A-A, B-B, …, K-K).",
            "Total rows: 205 (~55% of HarmCo's 374 rows).",
            "Pads A-A and B-B dominate (active vertical construction); C-K are placeholder.",
            "Account distribution: 88.5% Direct Construction.",
            "Future ontology: needs a `CommercialParcel` entity (deferred to v0.2).",
        ],
        safe=["Where do HarmCo X-X commercial parcels live in v2.1?",
               "Why aren't they in residential LotState?",
               "What ontology decision is pending?"],
        refuse=["Roll commercial parcel cost into Harmony residential lot totals? — REFUSE.",
                 "Treat HarmCo X-X as Harmony LotState rows? — REFUSE."],
        sources=["scratch/vf_decoder_ops_allocation_review.md",
                  "data/reports/vf_lot_code_decoder_v1_report.md",
                  "output/operating_state_v2_1_bcpd.json"],
        confidence_para="High confidence on the non-lot treatment; ontology decision (CommercialParcel?) is deferred.",
        caveats_list=["Tracked separately so they're visible but not double-counted into residential."],
    )


def chunk_guardrail_readonly_qa():
    return _guardrail_chunk(
        chunk_id="guardrail_read_only_qa",
        title="Guardrail: Read-only Q&A rules",
        summary="The Q&A layer (`financials/qa/`) is strictly read-only against the v2.1 state and "
                 "all source / staged / report files. It writes ONLY to three allowed paths: "
                 "`output/bcpd_state_qa_results.json`, `output/bcpd_state_qa_examples.md`, "
                 "`output/bcpd_state_qa_eval.md`. A test (`tests/test_bcpd_state_qa_readonly.py`) "
                 "verifies this contract every run.",
        facts=[
            "Protected paths: 11 (state JSON + companion docs + reports + ontology + field map + source map).",
            "Allowed writes: 3 (results JSON, examples MD, eval MD).",
            "Default mode: deterministic, no API calls, 15 fixed handlers.",
            "Optional LLM mode: gated on ANTHROPIC_API_KEY env var; never hardcoded.",
            "Test verifies sha256 + size of every protected path before/after run.",
        ],
        safe=["What does the read-only Q&A harness write?",
               "How is the read-only contract enforced?",
               "Can the harness call an external LLM API?"],
        refuse=["Modify the v2.1 state JSON via the Q&A harness? — REFUSE.",
                 "Write to source / staged / canonical files from the QA layer? — REFUSE."],
        sources=["financials/qa/__init__.py",
                  "financials/qa/bcpd_state_qa.py",
                  "tests/test_bcpd_state_qa_readonly.py"],
        confidence_para="High confidence; enforced by code + test.",
        caveats_list=["Optional LLM mode requires explicit API key in env; default is deterministic."],
    )


# ---------------------------------------------------------------------------
# Source-family chunks
# ---------------------------------------------------------------------------

def _source_chunk(chunk_id: str, title: str, summary: str, facts: list[str],
                   safe: list[str], refuse: list[str], sources: list[str],
                   confidence: str = "high",
                   caveats: list[str] | None = None) -> tuple[str, str]:
    fm = _frontmatter(
        chunk_id=chunk_id, chunk_type="source_family",
        title=title, project=None,
        source_files=sources, confidence=confidence,
        allowed_uses=["RAG grounding for source-system questions",
                       "Anchor for any answer that cites this source family"],
        caveats=caveats or ["See state_quality_report_v2_1_bcpd.md for per-field detail."],
    )
    return (f"sources/{chunk_id}.md",
            fm + _body(summary=summary, facts=facts, sources=sources,
                        confidence_para=f"Confidence: {confidence}. "
                                          "Counts and field profiles are derived directly from staged data.",
                        caveats_list=caveats or [],
                        safe_questions=safe, refuse_or_caveat=refuse))


def chunk_source_inventory():
    return _source_chunk(
        chunk_id="source_inventory_closing_report",
        title="Source family: Inventory Closing Report",
        summary="Excel workbook (`Inventory _ Closing Report (2).xlsx`) carrying per-lot inventory "
                 "snapshots. Two main sheets: `INVENTORY` (header=0; 978 active lots) and `CLOSED ` "
                 "(header=1; 2,894 closed/projected lots). v2.1 uses workbook (2) deliberately — "
                 "freshest static data; lane doc claim that (4) is canonical was contradicted by "
                 "the data.",
        facts=[
            "Total staged rows: 3,872 (978 ACTIVE + 1,760 CLOSED + 1,134 ACTIVE_PROJECTED).",
            "as_of_date: 2026-04-29 (data-derived from max INVENTORY.SALE DATE).",
            "9 high-confidence active subdivs + ~25 historical communities (CLOSED tab).",
            "Forward-fill required for vertically-merged subdiv labels.",
            "Volatile `=TODAY()-SaleDate` columns dropped at stage time.",
        ],
        safe=["What's the as-of date of v2.1 inventory?",
               "How many active vs closed lots are in inventory?",
               "Why was workbook (2) chosen over (4)?"],
        refuse=["Provide inventory state as of a different as_of_date? — REFUSE: stage is fixed at 2026-04-29.",
                 "Treat ACTIVE_PROJECTED as actually CLOSED? — REFUSE: forward-projected dates only."],
        sources=["data/staged/staged_inventory_lots.parquet",
                  "data/reports/staged_inventory_lots_validation_report.md",
                  "scratch/ops_inventory_collateral_allocation_findings.md"],
    )


def chunk_source_vf():
    return _source_chunk(
        chunk_id="source_gl_vertical_financials",
        title="Source family: Vertical Financials (GL VF 46-col)",
        summary="BCPD lot-level cost basis 2018-2025. Filtered to a 3-account-code asset-side slice "
                 "(1535/1540/1547). One-sided — NOT a balanced trial-balance.",
        facts=[
            "Rows: 83,433 BCPD-only.",
            "Cost basis total: $346.5M (one-sided).",
            "Project + lot fill: 100%; phase fill: 0% (no phase column).",
            "1,306 distinct (project, lot) pairs.",
            "Source schema in v2: source_schema='vertical_financials_46col'.",
        ],
        safe=["What does VF cover?", "What account codes are in VF?", "Is VF balanced?"],
        refuse=["Treat VF as a balanced trial balance? — REFUSE.",
                 "Aggregate VF + QB Register? — REFUSE: zero account-code overlap."],
        sources=["scratch/gl_financials_findings.md",
                  "data/reports/staged_gl_validation_report.md",
                  "data/staged/staged_gl_transactions_v2_validation_report.md"],
    )


def chunk_source_dr():
    return _source_chunk(
        chunk_id="source_gl_datarails_38col",
        title="Source family: DataRails 38-col (GL DR 38-col)",
        summary="BCPD GL extracts for 2016-02 → 2017-02 across 14 monthly CSV files. **2.16× row-"
                 "multiplied at source** — every posting line appears 2-3 times consecutively. Build "
                 "pipeline deduplicates before any cost rollup; raw v2 parquet preserved unchanged.",
        facts=[
            "Raw rows (BCPD): 111,497.",
            "Post-dedup: 51,694 (multiplicity 2.16×).",
            "Lot fill (BCPD): 49.5%; phase fill: 0%.",
            "Dedup key: 9 financial+narrative fields; canonical row picks max non-null metadata.",
            "Source schema in v2: source_schema='datarails_38col'.",
        ],
        safe=["Why is DR 38-col deduplicated?", "What's DR's coverage window?",
               "Can we get phase from DR?"],
        refuse=["Sum DR amounts directly from raw parquet? — REFUSE: 2.16× off.",
                 "Get Harmony cost from DR? — REFUSE: Harmony is post-2018; not in DR."],
        sources=["scratch/gl_financials_findings.md",
                  "data/staged/staged_gl_transactions_v2_validation_report.md"],
    )


def chunk_source_qb():
    return _source_chunk(
        chunk_id="source_gl_qb_register",
        title="Source family: QuickBooks Register (GL QB 12-col)",
        summary="2,922 BCPD 2025 rows from QuickBooks. Different chart of accounts (177 codes) — "
                 "tie-out only. Vendor field is the only place vendor names live (95.7% fill, 161 "
                 "distinct vendors).",
        facts=[
            "Rows: 2,922 BCPD 2025-only.",
            "Account codes: 177 distinct (e.g. 132-XXX, 510-XXX, 210-100).",
            "Account-code overlap with VF/DR: zero.",
            "Vendor fill: 95.7%.",
            "Project / lot / phase fill: 0%.",
            "Treatment: tie-out only; never aggregate against VF/DR.",
        ],
        safe=["What is QB Register used for?", "Where do BCPD vendor names come from?"],
        refuse=["Per-lot cost from QB? — REFUSE: no lot field.",
                 "Aggregate QB + VF for 2025? — REFUSE: would double-count."],
        sources=["scratch/gl_financials_findings.md",
                  "data/staged/staged_gl_transactions_v2_validation_report.md"],
    )


def chunk_source_collateral():
    return _source_chunk(
        chunk_id="source_collateral_reports",
        title="Source family: Collateral Reports",
        summary="`Collateral Dec2025 - Collateral Report.csv` and `PriorCR.csv` — phase-level "
                 "borrowing-base snapshots. as_of 2025-12-31 (current) and 2025-06-30 (prior). "
                 "Covers 9 of 16 active BCPD projects (the actively-pledged universe).",
        facts=[
            "Rows: 41 phase entries per snapshot.",
            "Coverage: 9 BCPD projects (Arrowhead Springs, Dry Creek, Harmony, Lomond Heights, Meadow Creek, Parkway Fields, Salem Fields, Scarlet Ridge, Willowcreek).",
            "Missing from collateral: 7 active BCPD projects + Lewis Estates (not pledged).",
            "Fields: lot count, total lot value, advance %, loan $, total dev cost, remaining dev cost.",
            "Sibling files: 2025Status (per-lot status), Lot Data (lifecycle dates), IA Breakdown, RBA-TNW.",
        ],
        safe=["What does the Collateral Report cover?",
               "Which BCPD projects are pledged collateral?",
               "What's the 6-month delta between current and prior snapshots?"],
        refuse=["Provide collateral data for Lewis Estates? — REFUSE: not in pledged universe.",
                 "Trend collateral over time? — CAVEAT: only 2 snapshots available."],
        sources=["scratch/ops_inventory_collateral_allocation_findings.md",
                  "data/staged/ops_inventory_collateral_validation_report.md"],
    )


def chunk_source_allocation():
    return _source_chunk(
        chunk_id="source_allocation_workbooks",
        title="Source family: Allocation workbooks",
        summary="Per-project budget data. Lomond Heights (LH Allocation 2025.10) and Parkway Fields "
                 "(Parkway Allocation 2025.10) have populated per-phase × prod_type rows. The "
                 "Flagship Allocation Workbook v3 covers 8 communities but most cells are empty in "
                 "the current snapshot.",
        facts=[
            "Lomond Heights LH.csv: 12 phase × prod_type rows (already in v1).",
            "Parkway Fields PF.csv: 14 phase × prod_type rows (already in v1).",
            "Flagship Allocation Workbook v3: 67 (community, phase) pairs framework — most cells $0.",
            "Dehart Underwriting (Summary).csv: not stageable as-is; deferred.",
        ],
        safe=["Where do BCPD budgets come from?",
               "Which projects have populated allocation workbooks?",
               "What's the Flagship Allocation Workbook v3 status?"],
        refuse=["Provide budget for Harmony from allocation? — REFUSE: workbook framework exists but cells are empty.",
                 "Treat Dehart underwriting as a stageable allocation source? — REFUSE: not in scope."],
        sources=["scratch/ops_inventory_collateral_allocation_findings.md",
                  "data/staged/ops_inventory_collateral_validation_report.md"],
        confidence="medium",
        caveats=["Allocation expansion is gated on populating Flagship workbook or wiring OfferMaster fallback."],
    )


def chunk_source_clickup():
    return _source_chunk(
        chunk_id="source_clickup_tasks",
        title="Source family: ClickUp Tasks",
        summary="`staged_clickup_tasks` — 5,509 total tasks; lot-tagged subset of 1,177. Used as a "
                 "per-lot signal (status, due_date, actual_c_of_o) where present. Phase fill within "
                 "the lot-tagged subset is 92.86% (vs 19.86% across the full file).",
        facts=[
            "Total rows: 5,509.",
            "Lot-tagged subset (subdivision + lot_num both populated): 1,177.",
            "Distinct (project, lot) in lot-tagged: 1,091.",
            "Subdivision crosswalk: 11 mappings including typos (Aarowhead, Aarrowhead, Scarlett Ridge).",
            "Date-field coverage uplift in lot-tagged vs full file: 3-5x (e.g., actual_c_of_o 22.77% vs 4.88%).",
            "Arrowhead-173 outlier (75 tasks on one lot) flagged.",
        ],
        safe=["What ClickUp data is in scope?",
               "What's the lot-tagging discipline?",
               "Which subdivision typos are crosswalked?"],
        refuse=["Extrapolate ClickUp signals to non-lot-tagged tasks? — REFUSE: 79% are not lot-tagged.",
                 "Use ClickUp as the canonical source for any cost? — REFUSE: progress only."],
        sources=["data/reports/staged_clickup_validation_report.md",
                  "scratch/ops_inventory_collateral_allocation_findings.md"],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for sub in ("projects", "coverage", "cost_sources", "guardrails", "sources"):
        (OUT / sub).mkdir(exist_ok=True)

    state = json.loads(STATE_JSON.read_text())
    chunks: list[tuple[str, str]] = []  # (relative_path, content)

    # Project chunks: enumerate state.projects but skip historicals (anything outside our PROJECT_NOTES)
    seen = set()
    for p in state["projects"]:
        name = p["canonical_project"]
        if name not in PROJECT_NOTES:
            continue  # skip historical / not-yet-cataloged
        if name in seen:
            continue
        seen.add(name)
        rp, md = chunk_project(p)
        chunks.append((rp, md))

    # Coverage chunks
    for fn in (chunk_coverage_inventory_gl, chunk_coverage_inventory_clickup,
                chunk_coverage_full_triangle, chunk_coverage_no_gl_projects,
                chunk_coverage_validation_queue):
        chunks.append(fn())

    # Cost-source chunks
    for fn in (chunk_cost_source_vf, chunk_cost_source_dr_dedup,
                chunk_cost_source_qb_tieout, chunk_cost_source_range_shell,
                chunk_cost_source_commercial_parcels, chunk_cost_source_missing_not_zero):
        chunks.append(fn())

    # Guardrail chunks
    for fn in (chunk_guardrail_bcpd_only, chunk_guardrail_orgwide_blocked,
                chunk_guardrail_inferred_decoder, chunk_guardrail_harmony_3tuple,
                chunk_guardrail_sctlot_scattered, chunk_guardrail_range_not_lot_level,
                chunk_guardrail_commercial_not_residential, chunk_guardrail_readonly_qa):
        chunks.append(fn())

    # Source-family chunks
    for fn in (chunk_source_inventory, chunk_source_vf, chunk_source_dr,
                chunk_source_qb, chunk_source_collateral, chunk_source_allocation,
                chunk_source_clickup):
        chunks.append(fn())

    # Write chunks
    counts_by_type: dict[str, int] = {}
    for rel, content in chunks:
        path = OUT / rel
        path.write_text(content)
        ct = rel.split("/")[0]
        counts_by_type[ct] = counts_by_type.get(ct, 0) + 1

    # Build index.json
    index_entries = []
    for rel, content in chunks:
        # Parse frontmatter
        if not content.startswith("---\n"):
            continue
        end = content.find("\n---\n", 4)
        fm_text = content[4:end]
        fm = {}
        cur_list_key = None
        for line in fm_text.splitlines():
            if line.startswith("  - ") and cur_list_key:
                fm[cur_list_key].append(line[4:].strip())
            elif ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if v == "":
                    fm[k] = []
                    cur_list_key = k
                else:
                    fm[k] = v
                    cur_list_key = None
        # Extract keywords from title + project + chunk_type
        keywords = set()
        for token in re.split(r"\W+", (fm.get("title", "") + " " + (fm.get("project") or "") + " " + fm.get("chunk_type", "")).lower()):
            if token and len(token) >= 3:
                keywords.add(token)
        # Safe-question-types heuristic
        safe_types = []
        body = content[end + 5:]
        body_lower = body.lower()
        if "cost" in body_lower:           safe_types.append("cost_questions")
        if "coverage" in body_lower:       safe_types.append("coverage_questions")
        if "lot" in body_lower:            safe_types.append("lot_grain_questions")
        if "phase" in body_lower:          safe_types.append("phase_grain_questions")
        if "decoder" in body_lower:        safe_types.append("decoder_questions")
        if "guardrail" in body_lower:      safe_types.append("guardrail_questions")
        if "scope" in body_lower:          safe_types.append("scope_questions")
        if "source" in body_lower:         safe_types.append("source_provenance_questions")
        # Caveat tags
        caveat_tags = list(fm.get("caveats", []))
        index_entries.append({
            "chunk_id": fm.get("chunk_id"),
            "path": rel,
            "title": fm.get("title"),
            "chunk_type": fm.get("chunk_type"),
            "project": fm.get("project") if fm.get("project") != "n/a" else None,
            "source_files": fm.get("source_files", []),
            "state_version": fm.get("state_version"),
            "confidence": fm.get("confidence"),
            "last_generated": fm.get("last_generated"),
            "keywords": sorted(keywords),
            "safe_question_types": sorted(safe_types),
            "caveat_tags": caveat_tags[:5],
            "allowed_uses": fm.get("allowed_uses", []),
        })

    index_path = OUT / "index.json"
    index_path.write_text(json.dumps({
        "state_version": STATE_VERSION,
        "generated_at": LAST_GEN,
        "chunk_count": len(index_entries),
        "counts_by_type": counts_by_type,
        "chunks": sorted(index_entries, key=lambda c: (c["chunk_type"], c["chunk_id"])),
    }, indent=2))

    # README.md
    readme = []
    readme.append("# BCPD v2.1 Agent Context Chunks\n\n")
    readme.append(f"_Generated: {LAST_GEN}_  |  _State version: {STATE_VERSION}_  |  _Total chunks: {len(chunks)}_\n\n")
    readme.append("Source-backed context chunks for retrieval-augmented agent answers. Each chunk is a "
                   "self-contained markdown file with frontmatter (chunk_id, type, source_files, "
                   "confidence, allowed_uses, caveats) and a fixed body shape (Plain-English summary, "
                   "Key facts, Evidence/source files, Confidence, Caveats, Safe questions, Questions "
                   "to refuse or caveat).\n\n")
    readme.append("Chunks are **derived artifacts**: they do not invent facts. Every claim is traceable "
                   "to a v2.1 source file. Confidence labels reflect what's in the source — never promoted.\n\n")
    readme.append("## Counts by type\n\n")
    readme.append("| chunk_type | count |\n|---|---:|\n")
    for k in sorted(counts_by_type):
        readme.append(f"| {k} | {counts_by_type[k]} |\n")
    readme.append(f"| **total** | **{sum(counts_by_type.values())}** |\n\n")
    readme.append("## Layout\n\n")
    readme.append("```\n")
    readme.append("output/agent_chunks_v2_bcpd/\n")
    readme.append("├── README.md                 (this file)\n")
    readme.append("├── index.json                (machine-readable manifest)\n")
    readme.append("├── chunk_quality_report.md   (audit + retrieval strategy)\n")
    readme.append("├── projects/                 (one chunk per BCPD project)\n")
    readme.append("├── coverage/                 (GL/ClickUp/triangle/no-GL/validation queue)\n")
    readme.append("├── cost_sources/             (VF, DR-dedup, QB tie-out, range, commercial, missing-not-zero)\n")
    readme.append("├── guardrails/               (BCPD-only, org-wide-blocked, inferred decoder, 3-tuple, etc.)\n")
    readme.append("└── sources/                  (Inventory, VF, DR, QB, Collateral, Allocation, ClickUp)\n")
    readme.append("```\n\n")
    readme.append("## How to use these chunks\n\n")
    readme.append("- **Retrieval pattern**: pull the project chunk relevant to the question, plus any guardrail and source/cost-source chunks the question implicates. Never answer cost/coverage questions from a project chunk alone.\n")
    readme.append("- **Confidence labels**: respect them. A chunk labeled `inferred` has not been source-owner-validated; cite that label in any answer that uses it.\n")
    readme.append("- **Refusals**: every chunk has a 'Questions to refuse or caveat' section. Use it.\n")
    readme.append("- **Regeneration**: `python3 financials/build_agent_chunks_v2_bcpd.py`. Idempotent if upstream artifacts haven't changed.\n\n")
    readme.append("See `chunk_quality_report.md` for the full audit + recommended retrieval strategy.\n")
    (OUT / "README.md").write_text("".join(readme))

    # chunk_quality_report.md
    qr = []
    qr.append("# Chunk Quality Report — agent_chunks_v2_bcpd\n\n")
    qr.append(f"_Generated: {LAST_GEN}_  |  _State version: {STATE_VERSION}_\n\n")
    qr.append(f"Total chunks: **{sum(counts_by_type.values())}**\n\n")
    qr.append("## Counts by type\n\n")
    qr.append("| chunk_type | count |\n|---|---:|\n")
    for k in sorted(counts_by_type):
        qr.append(f"| {k} | {counts_by_type[k]} |\n")
    qr.append("\n")

    project_chunks = [c for c in index_entries if c["chunk_type"] == "project"]
    project_names = sorted([c["project"] for c in project_chunks if c["project"]])
    qr.append("## Projects covered\n\n")
    qr.append(f"{len(project_names)} BCPD projects, including the new 'Scattered Lots' canonical project introduced in v2.1.\n\n")
    for n in project_names:
        qr.append(f"- {n}\n")
    qr.append("\n")
    qr.append("**Not chunked** (deliberate): pre-2018 historical communities (Cascade, Silver Lake, Westbrook, Hamptons, etc.) live in the JSON state but are out of v2.1 active-project scope. They can be referenced via the operating_state JSON when needed; chunking them would inflate the chunk set without analytical value.\n\n")

    src_chunks = [c for c in index_entries if c["chunk_type"] == "source_family"]
    qr.append("## Source families covered\n\n")
    qr.append("- ✅ Inventory Closing Report\n")
    qr.append("- ✅ Vertical Financials (VF 46-col)\n")
    qr.append("- ✅ DataRails 38-col (DR)\n")
    qr.append("- ✅ QuickBooks Register (QB 12-col)\n")
    qr.append("- ✅ Collateral Reports + PriorCR + 2025Status + Lot Data\n")
    qr.append("- ✅ Allocation Workbooks (LH, Parkway, Flagship v3)\n")
    qr.append("- ✅ ClickUp Tasks\n\n")

    grd_chunks = [c for c in index_entries if c["chunk_type"] == "guardrail"]
    qr.append(f"## Guardrails covered ({len(grd_chunks)})\n\n")
    for c in sorted(grd_chunks, key=lambda x: x["chunk_id"]):
        qr.append(f"- `{c['chunk_id']}` — {c['title']}\n")
    qr.append("\n")

    cs_chunks = [c for c in index_entries if c["chunk_type"] == "cost_source"]
    qr.append(f"## Cost-source treatments covered ({len(cs_chunks)})\n\n")
    for c in sorted(cs_chunks, key=lambda x: x["chunk_id"]):
        qr.append(f"- `{c['chunk_id']}` — {c['title']}\n")
    qr.append("\n")

    cov_chunks = [c for c in index_entries if c["chunk_type"] == "coverage"]
    qr.append(f"## Coverage chunks ({len(cov_chunks)})\n\n")
    for c in sorted(cov_chunks, key=lambda x: x["chunk_id"]):
        qr.append(f"- `{c['chunk_id']}` — {c['title']}\n")
    qr.append("\n")

    qr.append("## Known omissions\n\n")
    qr.append("- **Historical pre-2018 projects** — Cascade, Silver Lake, Westbrook, Hamptons, Bridgeport, Beck Pines, etc. Not chunked as individual projects (they are present in the JSON state but out of active v2.1 scope).\n")
    qr.append("- **Per-lot chunks** — too granular for v0; revisit if the agent layer demands lot-level retrieval.\n")
    qr.append("- **Crosswalk-table chunks** — the lot-level crosswalk is 14,537 rows; chunking it would not be useful. Reference the source files instead.\n")
    qr.append("- **Org-wide / non-BCPD entities** — out of scope (Track B). Hillcrest / Flagship Belmont / Lennar / EXT have no chunks.\n")
    qr.append("- **Dehart Underwriting** — single-project underwriting model; not stageable; not chunked.\n\n")

    qr.append("## Are chunks ready for RAG?\n\n")
    qr.append("**Yes, with the retrieval strategy below.** Every chunk:\n\n")
    qr.append("- Has frontmatter parseable by retrieval engines (chunk_id, type, source_files, confidence, allowed_uses, caveats).\n")
    qr.append("- Carries source-file citations on every claim.\n")
    qr.append("- Declares its safe questions explicitly so retrieval can match question-intent to chunk.\n")
    qr.append("- Lists refused/caveated questions explicitly so retrieval can NOT-route those.\n")
    qr.append("- Stays within the W5 plan's 800-word cap (most chunks are 250-500 words).\n\n")

    qr.append("## Recommended retrieval strategy\n\n")
    qr.append("For an LLM or RAG layer using these chunks:\n\n")
    qr.append("**1. Always retrieve a guardrail chunk first** for any question that mentions:\n")
    qr.append("- 'all entities' / 'org-wide' / 'company-wide' → `guardrail_orgwide_unavailable`\n")
    qr.append("- 'cost' or 'dollars' on a project → `guardrail_inferred_decoder_rules` + the relevant cost_source chunk\n")
    qr.append("- 'Harmony' + 'cost' → `guardrail_harmony_3tuple_join`\n")
    qr.append("- 'SctLot' or 'Scarlet Ridge cost' → `guardrail_sctlot_scattered_lots`\n")
    qr.append("- 'shell' / 'range' / 'shared' → `guardrail_range_rows_not_lot_level`\n")
    qr.append("- 'commercial' → `guardrail_commercial_not_residential`\n\n")
    qr.append("**2. Retrieve project chunk + relevant source/guardrail chunk + quality/caveat chunk.** Never answer from a project chunk alone if the question asks about cost, coverage, org-wide rollup, or source confidence.\n\n")
    qr.append("**3. For cost questions specifically, retrieve at minimum:**\n")
    qr.append("- The relevant project chunk\n")
    qr.append("- The relevant cost-source chunk (VF / DR-dedup / QB tie-out / range / commercial / missing-not-zero)\n")
    qr.append("- The `guardrail_inferred_decoder_rules` chunk\n")
    qr.append("- The `coverage_no_gl_projects` chunk if the project might be in the no-GL set\n\n")
    qr.append("**4. For coverage questions, retrieve at minimum:**\n")
    qr.append("- The relevant coverage chunk (`coverage_gl_inventory`, `coverage_clickup_inventory`, `coverage_full_triangle`)\n")
    qr.append("- The relevant project chunk if scoped to one project\n")
    qr.append("- `coverage_source_owner_validation_queue` if the question asks about confidence promotion\n\n")
    qr.append("**5. Always include guardrail chunks for unsupported/ambiguous questions.** When the question mentions org-wide, missing cost, or anything in scope of a guardrail, the guardrail chunk's 'Questions to refuse or caveat' section drives the answer.\n\n")
    qr.append("**6. Cite source files in every answer.** Each chunk's `source_files` frontmatter lists the upstream artifacts; an answer that cites those is auditable.\n\n")
    qr.append("**7. Respect confidence labels.** A chunk labeled `inferred` requires the answer to include the confidence; a chunk labeled `low` (e.g. no-GL projects) should drive a refusal on cost questions.\n\n")
    qr.append("## Chunk index integrity\n\n")
    qr.append("All chunks listed in `index.json` exist as files under the directory. The index "
                "should be regenerated whenever a chunk is added or modified. Tests "
                "(`tests/test_agent_chunks_v2_bcpd.py`) verify:\n")
    qr.append("- Every indexed chunk has a corresponding file.\n")
    qr.append("- Every chunk has the required frontmatter fields.\n")
    qr.append("- Guardrail chunks include `missing_cost_is_not_zero` (in `cost_sources/`) and `org_wide_unavailable` (in `guardrails/`).\n")
    qr.append("- No chunk claims `validated_by_source_owner=True` for inferred decoder rules.\n")
    qr.append("- v2.1 protected files are not modified by chunk regeneration.\n")

    (OUT / "chunk_quality_report.md").write_text("".join(qr))

    print(f"[chunks] wrote {sum(counts_by_type.values())} chunks across {len(counts_by_type)} types")
    print(f"[chunks] counts: {counts_by_type}")
    print(f"[chunks] index: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
