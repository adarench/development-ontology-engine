"""The 15 fixed test questions for the BCPD v2.1 Q&A harness.

These are the questions the harness is evaluated against. They are deliberately
ordered from descriptive (state metadata) → analytical (cost rollups) →
self-aware (what the state cannot answer).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionSpec:
    qid: int
    question: str
    category: str
    expected_kind: str   # 'descriptive' | 'analytical' | 'refusal' | 'self-aware'
    notes: str = ""


QUESTIONS: tuple[QuestionSpec, ...] = (
    QuestionSpec(
        qid=1,
        question="What is the current BCPD operating state scope?",
        category="metadata",
        expected_kind="descriptive",
        notes="entities in scope, time horizon, source families",
    ),
    QuestionSpec(
        qid=2,
        question="Which projects have strong GL coverage?",
        category="coverage",
        expected_kind="analytical",
        notes="Salem Fields and Willowcreek at 100%; Scarlet Ridge 90.9%; etc.",
    ),
    QuestionSpec(
        qid=3,
        question="Which projects have inventory but no GL coverage?",
        category="coverage",
        expected_kind="analytical",
        notes="Lewis Estates + 7 active no-GL projects",
    ),
    QuestionSpec(
        qid=4,
        question="What changed from v2.0 to v2.1?",
        category="change-log",
        expected_kind="descriptive",
        notes="6 changes: AultF B→B1, Harmony 3-tuple, HarmCo split, SctLot, range, SR",
    ),
    QuestionSpec(
        qid=5,
        question="Why should v2.1 replace v2.0?",
        category="recommendation",
        expected_kind="descriptive",
        notes="correctness fixes outweigh modest binary-coverage delta",
    ),
    QuestionSpec(
        qid=6,
        question="What does missing cost mean?",
        category="semantics",
        expected_kind="self-aware",
        notes="missing != 0; explicit 'unknown' for projects with no GL",
    ),
    QuestionSpec(
        qid=7,
        question="Can we answer org-wide actuals?",
        category="refusal",
        expected_kind="refusal",
        notes="Hillcrest + Flagship Belmont blocked; v2.1 is BCPD-only",
    ),
    QuestionSpec(
        qid=8,
        question="Which costs are safe at lot grain?",
        category="trust",
        expected_kind="analytical",
        notes="VF in decoder scope (with 3-tuple) ; DR project-grain only",
    ),
    QuestionSpec(
        qid=9,
        question="Which costs are only safe at project/phase grain?",
        category="trust",
        expected_kind="analytical",
        notes="range rows, commercial parcels, SctLot, DR (no phase)",
    ),
    QuestionSpec(
        qid=10,
        question="What are the open source-owner validation questions?",
        category="self-aware",
        expected_kind="descriptive",
        notes="8 open: Harm3 routing, AultF SR, B-suffix range, MF1/B1 leakage, SctLot name, range allocation method, HarmCo X-X ontology, DR phase recovery",
    ),
    QuestionSpec(
        qid=11,
        question="What is the safest interpretation of SctLot?",
        category="semantics",
        expected_kind="self-aware",
        notes="Scattered Lots project-grain only; not Scarlet Ridge; canonical name pending",
    ),
    QuestionSpec(
        qid=12,
        question="What is the issue with Harmony MF1 vs B1?",
        category="semantics",
        expected_kind="analytical",
        notes="lot 101 collision; 3-tuple required; $6.75M double-count if flat",
    ),
    QuestionSpec(
        qid=13,
        question="What does the range-row treatment mean?",
        category="semantics",
        expected_kind="analytical",
        notes="$45.75M shell at project+phase grain; not allocated; v2.2 candidate",
    ),
    QuestionSpec(
        qid=14,
        question="What can we say about ClickUp coverage?",
        category="coverage",
        expected_kind="analytical",
        notes="1,177 lot-tagged of 5,509; 63.1% inventory match",
    ),
    QuestionSpec(
        qid=15,
        question="What data would most improve the next version?",
        category="roadmap",
        expected_kind="self-aware",
        notes="fresh GL for non-BCPD; 2017-03→2018-06 gap fill; populated Flagship workbook; range allocation method",
    ),
)
