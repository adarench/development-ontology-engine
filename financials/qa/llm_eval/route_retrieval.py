"""Question-category retrieval routing for Mode B.

The original Mode B used pure lexical top-k retrieval. That left two real
holes:
  - Q1 ("scope of BCPD") never surfaced agent_context_v2_1_bcpd.md, so the
    model invented "Blue Cedar Property Development" as an expansion.
  - Q4 ("what changed v2.0 → v2.1") and Q9 ("what data would improve the
    next version") only matched the QA-examples question header, not the
    change-log or coverage-improvement bodies, so the model safely refused
    when it should have answered.

This module adds a thin routing layer:
  1. Match the question against rule triggers.
  2. For each matched rule, pull the highest-overlap chunk(s) from each
     required file in the index.
  3. Prepend those routed chunks before the lexical top-k.
  4. Dedupe by (file, section_title); cap total at MAX_TOTAL_CHUNKS.

No protected files are read; the index already covers the BCPD v2.1 corpus.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re

from financials.qa.rag_eval.retrieval_index import (
    Index, Chunk, RetrievalHit, retrieve, tokenize,
)

REPO = Path(__file__).resolve().parent.parent.parent.parent

# Cap routed chunks (per category match) to avoid overloading context, and
# cap total prompt chunks. Lexical top-k is appended to fill remaining slots.
MAX_ROUTED_CHUNKS = 6
MAX_TOTAL_CHUNKS = 9


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoutingRule:
    name: str
    triggers: tuple[str, ...]
    required_files: tuple[str, ...]
    # Optional: per-file substring patterns for section_title to prefer.
    # If set, chunks whose section_title contains any pattern (case-
    # insensitive) get a ranking boost; if no chunk matches a pattern,
    # we fall back to overlap-best.
    preferred_sections: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # Optional: per-file count of chunks to pull (default 1).
    n_per_file: dict[str, int] = field(default_factory=dict)


RULES: tuple[RoutingRule, ...] = (
    RoutingRule(
        name="scope_definition",
        triggers=(
            "scope", "what is bcpd", "bcpd meaning",
            "current state of bcpd", "entities in scope",
            "in scope", "out of scope", "current scope",
        ),
        required_files=(
            "output/agent_context_v2_1_bcpd.md",
            "output/operating_state_v2_1_bcpd.json",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_bcpd_only.md",
        ),
        preferred_sections={
            "output/agent_context_v2_1_bcpd.md": (
                "BCPD Agent Context",  # the preamble — has BCPD = Building Construction Partners
                "Hard limits",
            ),
            "output/operating_state_v2_1_bcpd.json": ("metadata",),
        },
        n_per_file={"output/agent_context_v2_1_bcpd.md": 2},
    ),
    RoutingRule(
        # AultF / Parkway B-suffix and SR-suffix corrections — placed BEFORE
        # version_change so it takes first priority on routed-chunk budget for
        # AultF-specific queries. Surfaces the parkway_fields chunk + the
        # AultF sections of the v2.0→v2.1 change log + the decoder report.
        name="aultf_correction",
        triggers=(
            # B-suffix / SR-suffix specifics
            "aultf b-suffix", "aultf b suffix", "ault f b-suffix", "ault-f b-suffix",
            "aultf sr-suffix", "aultf sr suffix", "ault f sr-suffix", "ault-f sr-suffix",
            "0139sr", "0140sr",
            "0127b", "0211b",
            # Phrasings from the workflow / change-impact eval queries
            "what changed for aultf", "what changed in aultf",
            "aultf correction", "ault farms correction",
            "b-suffix correction", "b suffix correction",
            "sr-suffix correction", "sr suffix correction",
            # Full-name variants the existing project_parkway_fields rule misses
            "ault farms", "ault-farms",
            # Parkway VF code variants the existing project rule misses
            "pwft1", "pwft 1",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/projects/project_parkway_fields.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
            "data/reports/vf_lot_code_decoder_v1_report.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md",
        ),
        preferred_sections={
            "data/reports/v2_0_to_v2_1_change_log.md": (
                "AultF B-suffix", "1. AultF",
                "AultF SR-suffix", "6. AultF",
            ),
            "data/reports/vf_lot_code_decoder_v1_report.md": (
                "AultF", "B-suffix", "SR-suffix",
            ),
        },
        n_per_file={
            "data/reports/v2_0_to_v2_1_change_log.md": 2,
            "output/agent_chunks_v2_bcpd/projects/project_parkway_fields.md": 2,
        },
    ),
    RoutingRule(
        name="version_change",
        triggers=(
            "what changed", "what change",
            "v2.0 to v2.1", "v2_0 to v2_1", "from v2.0", "from v2_0",
            "v2.0 → v2.1", "v2_0 → v2_1",
            "correctness fix", "delta", "change log", "changelog",
            "replaces v2.0", "replace v2.0",
        ),
        required_files=(
            "data/reports/v2_0_to_v2_1_change_log.md",
            "output/state_quality_report_v2_1_bcpd.md",
            "output/operating_state_v2_1_bcpd.json",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_sctlot_scattered_lots.md",
        ),
        preferred_sections={
            "output/operating_state_v2_1_bcpd.json": ("v2_1_changes_summary",),
            "output/state_quality_report_v2_1_bcpd.md": (
                "v2.0 → v2.1 high-level deltas", "deltas",
            ),
        },
        n_per_file={
            "data/reports/v2_0_to_v2_1_change_log.md": 3,  # multiple correction sections
        },
    ),
    RoutingRule(
        name="coverage_gaps_next_version",
        triggers=(
            "data would improve", "improve the next", "next version",
            "gaps", "source-owner validation", "source owner validation",
            "coverage", "no gl", "no coverage", "missing gl",
            "what data would", "improvements",
            # Phrasings used by the business eval:
            "no matched gl", "no matched cost",
            "inventory activity", "inventory but no",
            "better source data", "improve decision",
            "decision quality",
        ),
        required_files=(
            "data/reports/coverage_improvement_opportunities.md",
            "data/reports/crosswalk_quality_audit_v1.md",
            "output/state_quality_report_v2_1_bcpd.md",
            "output/agent_chunks_v2_bcpd/coverage/coverage_no_gl_projects.md",
            "output/agent_chunks_v2_bcpd/coverage/coverage_source_owner_validation_queue.md",
            "output/agent_chunks_v2_bcpd/cost_sources/cost_source_missing_cost_is_not_zero.md",
        ),
        preferred_sections={
            "output/state_quality_report_v2_1_bcpd.md": (
                "Source-owner questions", "Per-project coverage", "Decoder-rule",
            ),
        },
        n_per_file={
            "data/reports/coverage_improvement_opportunities.md": 2,
        },
    ),
    RoutingRule(
        name="org_wide",
        triggers=(
            "org-wide", "org wide", "orgwide", "all entities",
            "company-wide", "company wide", "across entities",
            "consolidated",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_orgwide_unavailable.md",
            "output/agent_context_v2_1_bcpd.md",
            "output/operating_state_v2_1_bcpd.json",
        ),
        preferred_sections={
            "output/agent_context_v2_1_bcpd.md": (
                "Cannot answer", "Hard limits",
            ),
            "output/operating_state_v2_1_bcpd.json": (
                "metadata", "data_quality",
            ),
        },
    ),
    RoutingRule(
        name="cost_grain",
        triggers=(
            "safe at lot grain", "lot grain", "lot-grain",
            "per-lot cost", "per lot cost", "range row", "range-row",
            "range rows", "range/shell", "range-shell", "shell row",
            "shell allocation", "missing cost", "what does missing",
            "cost grain",
            # Phrasings used by the business eval:
            "cost by lot", "total cost by lot",
            "trusting per-lot", "trust per-lot",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_range_rows_not_lot_level.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md",
            "output/agent_chunks_v2_bcpd/cost_sources/cost_source_range_shell_rows.md",
            "output/agent_chunks_v2_bcpd/cost_sources/cost_source_missing_cost_is_not_zero.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
        ),
        preferred_sections={
            "data/reports/v2_0_to_v2_1_change_log.md": (
                "Range-row treatment", "5. Range",
            ),
        },
    ),
    RoutingRule(
        name="harmony_3tuple",
        triggers=(
            "harmony", "3-tuple", "three-tuple", "three tuple",
            "project + phase + lot", "project, phase, lot",
            "project + phase", "phase + lot",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md",
            "output/agent_chunks_v2_bcpd/projects/project_harmony.md",
            "data/reports/vf_lot_code_decoder_v1_report.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
        ),
        preferred_sections={
            "data/reports/v2_0_to_v2_1_change_log.md": (
                "Harmony 3-tuple", "2. Harmony",
            ),
        },
    ),
    RoutingRule(
        # HarmCo X-X commercial parcels — non-residential, isolated from
        # Harmony LotState. The existing harmony_3tuple rule covers Harmony
        # residential; this rule covers the commercial side that the v2.1
        # split surfaced.
        name="harmco_commercial",
        triggers=(
            "harmco", "harm co", "harm-co",
            "harmony commercial", "harmony comm",
            "commercial parcel", "commercial parcels",
            "commercial pad", "commercial pads",
            "non-residential", "non residential",
            "harmco x-x", "harmco xx", "harm co x-x",
            "x-x", "x x parcel",
            # HarmCo total / cost queries the workflow eval surfaced
            "harmco total", "harmco cost", "harmco per-lot",
            "total cost on harmco", "harmony total cost",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_commercial_not_residential.md",
            "output/agent_chunks_v2_bcpd/cost_sources/cost_source_commercial_parcels.md",
            "output/agent_chunks_v2_bcpd/projects/project_harmony.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
            "output/state_quality_report_v2_1_bcpd.md",
        ),
        preferred_sections={
            "data/reports/v2_0_to_v2_1_change_log.md": (
                "HarmCo", "3. HarmCo", "Commercial", "X-X",
            ),
            "output/state_quality_report_v2_1_bcpd.md": (
                "HarmCo", "Commercial", "Per-project coverage",
            ),
        },
        n_per_file={
            "output/agent_chunks_v2_bcpd/projects/project_harmony.md": 2,
        },
    ),
    RoutingRule(
        name="sctlot_scattered",
        triggers=(
            "sctlot", "scattered lots", "scarlet ridge",
            "interpretation of sctlot",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_sctlot_scattered_lots.md",
            "output/agent_chunks_v2_bcpd/projects/project_scattered_lots.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
        ),
        preferred_sections={
            "data/reports/v2_0_to_v2_1_change_log.md": (
                "SctLot", "4. SctLot",
            ),
        },
    ),
    RoutingRule(
        name="readiness_for_chat",
        triggers=(
            "ready for", "free-form chat", "free form chat",
            "chat ui", "chat-ui", "production chat",
            "ready to ship", "ship it",
        ),
        required_files=(
            "output/bcpd_state_qa_eval.md",
            "output/rag_eval/bcpd_rag_eval_summary.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_read_only_qa.md",
            "output/agent_context_v2_1_bcpd.md",
        ),
        preferred_sections={
            "output/agent_context_v2_1_bcpd.md": (
                "Hard limits", "Quality artifacts",
            ),
        },
    ),
    RoutingRule(
        # Project-specific: Parkway Fields. The PWFS2 phase carries the
        # AultF B-suffix correction story from v2.1; the project chunk has
        # the cost-basis numbers and grain split (lot vs range/shell).
        name="project_parkway_fields",
        triggers=(
            "parkway fields", "parkway field",
            "pwfs", "pwfs2",
            "aultf", "ault f", "ault-f", "ault_f",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/projects/project_parkway_fields.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md",
            "output/agent_chunks_v2_bcpd/cost_sources/cost_source_range_shell_rows.md",
            "output/state_quality_report_v2_1_bcpd.md",
        ),
        preferred_sections={
            "data/reports/v2_0_to_v2_1_change_log.md": (
                "AultF B-suffix", "1. AultF",
                "AultF SR-suffix", "6. AultF",
            ),
            "output/state_quality_report_v2_1_bcpd.md": (
                "Per-project coverage", "Decoder-rule",
            ),
        },
        n_per_file={
            "output/agent_chunks_v2_bcpd/projects/project_parkway_fields.md": 2,
            "data/reports/v2_0_to_v2_1_change_log.md": 2,
        },
    ),
    RoutingRule(
        # Reporting readiness — "should I include X in this margin report",
        # "what should I caveat in a lot-level report", etc.
        name="reporting_readiness",
        triggers=(
            "lot-level margin", "lot level margin",
            "margin report", "include in a report",
            "include in this report", "include in the report",
            "careful including", "careful about including",
            "report this week", "report next week",
            "lot-level report", "lot level report",
            "what should i caveat", "what to caveat",
            "what should i exclude", "what to exclude",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_range_rows_not_lot_level.md",
            "output/agent_chunks_v2_bcpd/coverage/coverage_no_gl_projects.md",
            "output/agent_chunks_v2_bcpd/cost_sources/cost_source_missing_cost_is_not_zero.md",
            "output/agent_chunks_v2_bcpd/cost_sources/cost_source_range_shell_rows.md",
            "output/state_quality_report_v2_1_bcpd.md",
            "output/operating_state_v2_1_bcpd.json",
            "output/agent_chunks_v2_bcpd/coverage/coverage_full_triangle.md",
        ),
        preferred_sections={
            "output/state_quality_report_v2_1_bcpd.md": (
                "What's safe to put in agent answers",
                "What's not safe", "Per-project coverage",
            ),
        },
    ),
    RoutingRule(
        # False precision / grain risk — "where might our reports give false
        # precision" → grain mismatches, decoder inference, range/shell rows.
        name="false_precision",
        triggers=(
            "false precision", "false-precision",
            "misleading report", "misleading reports",
            "giving false precision", "may look precise",
            "looks precise", "appears precise",
            "precision risk", "grain risk",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_range_rows_not_lot_level.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_harmony_3tuple_join.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_sctlot_scattered_lots.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_commercial_not_residential.md",
            "output/agent_chunks_v2_bcpd/cost_sources/cost_source_range_shell_rows.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
        ),
    ),
    RoutingRule(
        # Review prioritization — "if I only have one hour…", "where should
        # I focus first" → validation queue + change log + biggest dollar risks.
        name="review_prioritization",
        triggers=(
            "one hour to review", "limited time to review",
            "prioritize review", "review prioritization",
            "where should i focus first", "where to focus first",
            "where should we focus first",
            "before a meeting", "before the meeting",
            "review bcpd cost", "review cost issues",
            "spend limited review", "limited review time",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/coverage/coverage_source_owner_validation_queue.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
            "data/reports/coverage_improvement_opportunities.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_range_rows_not_lot_level.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md",
            "output/agent_chunks_v2_bcpd/coverage/coverage_no_gl_projects.md",
            "output/state_quality_report_v2_1_bcpd.md",
        ),
        preferred_sections={
            "output/state_quality_report_v2_1_bcpd.md": (
                "Source-owner questions", "Decoder-rule",
            ),
        },
    ),
    RoutingRule(
        # Pricing / release support — land/development decisions on active
        # lots; needs coverage map + decoder caveats + range/shell.
        name="pricing_release_support",
        triggers=(
            "pricing or release", "pricing discussion",
            "release discussion", "support a pricing",
            "pricing decision", "release decision",
            "active lots", "lot pricing",
            "support a release", "release for active",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/coverage/coverage_full_triangle.md",
            "output/agent_chunks_v2_bcpd/coverage/coverage_no_gl_projects.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_inferred_decoder_rules.md",
            "output/agent_chunks_v2_bcpd/cost_sources/cost_source_range_shell_rows.md",
            "output/agent_chunks_v2_bcpd/coverage/coverage_clickup_inventory.md",
            "output/state_quality_report_v2_1_bcpd.md",
        ),
        preferred_sections={
            "output/state_quality_report_v2_1_bcpd.md": (
                "Per-project coverage", "What's safe to put",
            ),
        },
    ),
    RoutingRule(
        # Meeting prep — "prepare me for a 30-minute review", "what to ask
        # each team", "what decisions do we need".
        name="meeting_prep",
        triggers=(
            "prepare me for", "prepare for a", "prepare for the",
            "30-minute", "30 minute", "thirty minute",
            "what should i ask", "what to ask each",
            "ask each team", "review meeting",
            "meeting agenda", "agenda for",
            "decisions do we need",
        ),
        required_files=(
            "output/agent_chunks_v2_bcpd/coverage/coverage_source_owner_validation_queue.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
            "data/reports/coverage_improvement_opportunities.md",
            "output/agent_chunks_v2_bcpd/coverage/coverage_no_gl_projects.md",
            "output/agent_context_v2_1_bcpd.md",
            "output/state_quality_report_v2_1_bcpd.md",
            "output/operating_state_v2_1_bcpd.json",
        ),
        preferred_sections={
            "output/agent_context_v2_1_bcpd.md": (
                "Quality artifacts", "Hard limits",
            ),
            "output/state_quality_report_v2_1_bcpd.md": (
                "Source-owner questions",
            ),
        },
    ),
    RoutingRule(
        # Executive / owner update — concise leadership summary needs the
        # change log, agent_context preamble + Hard limits, and the validation
        # queue. Keep this rule tight so it doesn't fire on Q10's
        # 'free-form chat ready' question (which uses readiness_for_chat).
        name="executive_update",
        triggers=(
            "owner-level update", "owner level update",
            "owner update", "executive update",
            "leadership update", "concise update",
            "concise owner", "draft a concise",
            "draft an update", "draft an owner",
        ),
        required_files=(
            "output/agent_context_v2_1_bcpd.md",
            "data/reports/v2_0_to_v2_1_change_log.md",
            "output/state_quality_report_v2_1_bcpd.md",
            "output/agent_chunks_v2_bcpd/coverage/coverage_source_owner_validation_queue.md",
            "output/agent_chunks_v2_bcpd/guardrails/guardrail_orgwide_unavailable.md",
        ),
        preferred_sections={
            "output/agent_context_v2_1_bcpd.md": (
                "BCPD Agent Context", "Hard limits",
                "What changed",
            ),
            "data/reports/v2_0_to_v2_1_change_log.md": (
                "What did change", "Coverage delta",
            ),
        },
    ),
    RoutingRule(
        # "What can we ANSWER today?" — surface the worked-examples catalog
        # and the agent-context confidence-by-question rules so the model
        # can describe the operating-question surface area itself.
        name="operating_capabilities",
        triggers=(
            "useful operating question", "useful question this state",
            "most useful operating", "operating question this state",
            "operating questions this state", "what can this state answer",
            "what can the system answer", "what can we answer today",
            "answer today", "covered operating questions",
        ),
        required_files=(
            "output/bcpd_state_qa_examples.md",
            "output/bcpd_state_qa_eval.md",
            "output/agent_context_v2_1_bcpd.md",
            "output/state_quality_report_v2_1_bcpd.md",
        ),
        preferred_sections={
            "output/agent_context_v2_1_bcpd.md": (
                "Confidence by question", "High-confidence",
                "Inferred-but-high-evidence", "Cannot answer",
            ),
            "output/state_quality_report_v2_1_bcpd.md": (
                "What's safe to put in agent answers",
            ),
            "output/bcpd_state_qa_eval.md": (
                "Strongest answers", "Pass-rate",
            ),
        },
        n_per_file={
            "output/agent_context_v2_1_bcpd.md": 2,
            "output/bcpd_state_qa_examples.md": 2,
        },
    ),
)


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

def matched_rules(question: str) -> list[RoutingRule]:
    q = question.lower()
    out: list[RoutingRule] = []
    for r in RULES:
        if any(t in q for t in r.triggers):
            out.append(r)
    return out


def _chunks_in_file(idx: Index, file: str) -> list[Chunk]:
    return [c for c in idx.chunks if c.file == file]


def _score_chunk_against_query(c: Chunk, q_tokens: set[str]) -> int:
    if not q_tokens:
        return 0
    body_tokens = set(c.tokens)
    return sum(1 for t in q_tokens if t in body_tokens)


def _section_matches_pattern(section_title: str, patterns: tuple[str, ...]) -> bool:
    title = section_title.lower()
    return any(p.lower() in title for p in patterns)


def best_chunks_for_file(idx: Index, file: str, query: str,
                          preferred: tuple[str, ...] = (),
                          n: int = 1) -> list[Chunk]:
    """Pick up to n chunks from `file` ranked by query overlap.

    If preferred section patterns are set, chunks whose section_title contains
    any pattern get a +100 boost. If no chunk matches a pattern, fall back
    to plain overlap. If overlap is tied (or all zero), prefer the longest
    chunk so we surface meaningful content even when the query is short.
    """
    candidates = _chunks_in_file(idx, file)
    if not candidates:
        return []
    q_tokens = set(tokenize(query))

    scored: list[tuple[int, int, Chunk]] = []  # (score, body_len, chunk)
    for c in candidates:
        ovl = _score_chunk_against_query(c, q_tokens)
        boost = 100 if (preferred and _section_matches_pattern(c.section_title, preferred)) else 0
        scored.append((ovl + boost, len(c.body), c))

    # Sort: highest score first, then longer body (more informative) first
    scored.sort(key=lambda t: (-t[0], -t[1]))

    # If absolutely nothing scored AND no preferred matches, fall back to
    # the longest chunk in the file (best chance of carrying real content).
    if scored[0][0] == 0 and not preferred:
        scored.sort(key=lambda t: -t[1])

    return [c for _, _, c in scored[:n]]


# ---------------------------------------------------------------------------
# Routed evidence builder
# ---------------------------------------------------------------------------

@dataclass
class RoutedHit:
    """Mirrors RetrievalHit shape so the run_ab_eval prompt formatter can
    consume routed and lexical hits uniformly."""
    chunk: Chunk
    score: float
    matched_tokens: list[str]
    source: str  # "routed:<rule_name>" or "lexical"
    rule: str = ""


def build_routed_evidence(idx: Index, question: str,
                          lexical_top_k: int = 5,
                          max_total: int = MAX_TOTAL_CHUNKS,
                          max_routed: int = MAX_ROUTED_CHUNKS,
                          ) -> tuple[list[RoutedHit], list[str]]:
    """Routed + lexical hybrid retrieval.

    Returns (hits, matched_rule_names). Hits are ordered: routed first,
    then lexical (deduped by chunk identity). Total capped at `max_total`.
    """
    rules = matched_rules(question)
    rule_names = [r.name for r in rules]

    routed: list[RoutedHit] = []
    seen_keys: set[tuple[str, str]] = set()  # (file, section_title)

    # Pass 1 — routed required files in rule order.
    for rule in rules:
        for f in rule.required_files:
            n = rule.n_per_file.get(f, 1)
            preferred = rule.preferred_sections.get(f, ())
            for c in best_chunks_for_file(idx, f, question, preferred=preferred, n=n):
                key = (c.file, c.section_title)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                # Compute a display "score" so the trace ranks meaningfully.
                ovl = _score_chunk_against_query(c, set(tokenize(question)))
                routed.append(RoutedHit(
                    chunk=c,
                    score=float(1000 + ovl),  # always above lexical scores
                    matched_tokens=[t for t in tokenize(question) if t in set(c.tokens)],
                    source=f"routed:{rule.name}",
                    rule=rule.name,
                ))
                if len(routed) >= max_routed:
                    break
            if len(routed) >= max_routed:
                break
        if len(routed) >= max_routed:
            break

    # Pass 2 — lexical fill, up to lexical_top_k unique-from-routed entries.
    lex_hits: list[RetrievalHit] = retrieve(idx, question, top_k=lexical_top_k)
    for h in lex_hits:
        key = (h.chunk.file, h.chunk.section_title)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        routed.append(RoutedHit(
            chunk=h.chunk,
            score=float(h.score),
            matched_tokens=list(h.matched_tokens),
            source="lexical",
            rule="",
        ))
        if len(routed) >= max_total:
            break

    # Final cap (defensive)
    return routed[:max_total], rule_names
