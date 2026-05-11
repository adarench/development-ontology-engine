"""Answer-rule guardrails for the BCPD v2.1 Q&A harness.

A guardrail fires when the QUESTION is asking about a topic the rule covers
(question-intent, not stray keywords). When fired, the answer must contain at
least one phrase from each `must_include_one_of` group, and must NOT contain
any phrase in `forbid`.

Returning a non-empty list from `check_answer(question, answer)` means
guardrail violations were detected.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Guardrail:
    name: str
    rule: str
    description: str
    # If ANY of these phrases appears in the question (case-insensitive), the guardrail fires.
    question_triggers: tuple[str, ...]
    # When fired, the answer must include at least ONE phrase from each tuple in this list.
    # (i.e. outer = AND, inner = OR.)
    must_include_one_of: tuple[tuple[str, ...], ...] = ()
    # When fired, the answer must NOT include any of these.
    forbid: tuple[str, ...] = ()


GUARDRAILS: tuple[Guardrail, ...] = (
    Guardrail(
        name="missing_cost_is_not_zero",
        rule="Missing cost is missing, not zero.",
        description="Lots/projects without GL data must report cost as 'unknown' or 'no GL', not $0.",
        question_triggers=("missing cost", "no gl", "no coverage", "unknown cost",
                            "what does missing"),
        must_include_one_of=(
            ("unknown", "missing", "not zero", "no GL", "not in"),
        ),
        forbid=("$0 cost", "= 0 dollars", "is zero dollars"),
    ),
    Guardrail(
        name="org_wide_unavailable",
        rule="Org-wide v2 is unavailable.",
        description="Hillcrest, Flagship Belmont have GL only through 2017-02. Org-wide rollups are out of scope.",
        question_triggers=("org-wide", "org wide", "all entities", "company-wide",
                            "across entities", "consolidated"),
        must_include_one_of=(
            ("blocked", "out of scope", "BCPD-only", "cannot be answered", "BCPD only"),
            ("hillcrest", "flagship belmont", "non-BCPD"),
        ),
    ),
    Guardrail(
        name="decoder_inferred",
        rule="Decoder-derived mappings are inferred unless source-owner-validated.",
        description="Per-lot VF cost via the v1 decoder ships with confidence='inferred'.",
        question_triggers=("safe at lot", "lot grain", "per-lot cost",
                            "vf cost for", "decoder", "lot-level cost"),
        must_include_one_of=(
            ("inferred", "decoder-derived", "not source-owner-validated"),
        ),
    ),
    Guardrail(
        name="range_not_lot_level",
        rule="Range rows / shell allocations are not lot-level costs.",
        description="$45.75M of range/shell rows are kept at project+phase grain via vf_unattributed_shell_dollars.",
        question_triggers=("range", "range row", "range-row", "shell allocation",
                            "shared shell", "unattributed shell"),
        must_include_one_of=(
            ("project+phase", "project + phase", "not allocated to specific lots",
             "not lot-level", "not at lot grain", "kept at project"),
        ),
    ),
    Guardrail(
        name="harmco_commercial_not_residential",
        rule="HarmCo commercial parcels are not residential lots.",
        description="The 11 X-X parcels are non-lot inventory; do not roll into residential LotState.",
        question_triggers=("harmco", "commercial parcel", "x-x", "harmony commercial"),
        must_include_one_of=(
            ("non-lot", "not residential", "commercial parcel", "do not roll"),
        ),
    ),
    Guardrail(
        name="harmony_3tuple_required",
        rule="Harmony joins require project + phase + lot.",
        description="Flat (project, lot) double-counts $6.75M because MF1 lot 101 and B1 lot 101 are different physical lots.",
        question_triggers=("mf1 vs b1", "harmony mf1", "harmony b1", "harmony cost",
                            "harmony lot", "issue with harmony"),
        must_include_one_of=(
            ("3-tuple", "project + phase", "phase + lot",
             "(canonical_project, canonical_phase, canonical_lot",
             "double-count"),
        ),
    ),
    Guardrail(
        name="sctlot_is_scattered_lots",
        rule="SctLot is Scattered Lots, not Scarlet Ridge.",
        description="v2.0 silently inflated Scarlet Ridge by $6.55M via SctLot rows.",
        question_triggers=("sctlot", "scattered lots", "interpretation of sctlot"),
        must_include_one_of=(
            ("Scattered Lots",),
            ("not Scarlet Ridge", "separate", "isolated", "off Scarlet"),
        ),
    ),
    Guardrail(
        name="qb_register_tieout_only",
        rule="QB register is tie-out only unless explicitly supported.",
        description="Different chart of accounts; zero overlap with VF/DR.",
        question_triggers=("qb register", "quickbooks", "vendor analysis"),
        must_include_one_of=(
            ("tie-out", "exclude from primary", "not aggregate against VF",
             "different chart"),
        ),
    ),
    Guardrail(
        name="vf_is_one_sided",
        rule="Vertical Financials is cost-basis / asset-side, not full trial balance.",
        description="VF carries only asset-side debits (3 account codes).",
        question_triggers=("trial balance", "vf totals", "vertical financials totals",
                            "346.5m", "346m"),
        must_include_one_of=(
            ("one-sided", "asset-side", "not a balanced", "cost-basis"),
        ),
    ),
    Guardrail(
        name="datarails_dedup_required",
        rule="DataRails 38-col raw sums are unsafe unless deduped.",
        description="DR 38-col is 2.16x row-multiplied at source.",
        question_triggers=("datarails 38", "dr 38-col", "pre-2018 cost",
                            "2016 cost", "2016-17 cost"),
        must_include_one_of=(
            ("dedup", "deduplicate", "row-multipl"),
        ),
    ),
)


def _q_fires(question: str, g: Guardrail) -> bool:
    q = question.lower()
    return any(t.lower() in q for t in g.question_triggers)


def check_answer(question: str, answer: str) -> list[dict]:
    """Return guardrail-violation records.

    A guardrail FIRES based on the question's intent (its trigger phrases).
    Once fired, every group in `must_include_one_of` must have at least one
    member appearing in the answer; and no `forbid` phrase may appear.
    """
    a_lower = answer.lower()
    violations = []
    for g in GUARDRAILS:
        if not _q_fires(question, g):
            continue
        missing_groups = []
        for group in g.must_include_one_of:
            if not any(phrase.lower() in a_lower for phrase in group):
                missing_groups.append(list(group))
        forbidden = [f for f in g.forbid if f.lower() in a_lower]
        if missing_groups or forbidden:
            violations.append({
                "guardrail": g.name,
                "rule": g.rule,
                "missing_required_phrases_any_of_each_group": missing_groups,
                "forbidden_phrases_present": forbidden,
            })
    return violations


def applicable_guardrails(question: str) -> list[str]:
    """Names of guardrails that apply to a given question."""
    return [g.name for g in GUARDRAILS if _q_fires(question, g)]


def all_rules_brief() -> list[dict]:
    return [{"name": g.name, "rule": g.rule} for g in GUARDRAILS]
