"""Operational scenarios — real moments of confusion in a land development business.

Each scenario captures: who would ask this, what they'd say, what the
correct response includes / excludes, and which caveats matter. Scenarios
are NOT IR benchmarks — they pressure-test whether the retrieval+runtime
system reconstructs correct *operational* meaning from fragmented,
partially conflicting, lineage-aware business state.

Categories:
  - overlapping_names      Harmony lot 101 in MF1 vs B1 — different physical assets.
  - crosswalk              SctLot must canonicalize to Scattered Lots (NOT Scarlet Ridge).
  - allocation_ambiguity   Range/shell rows must NOT be allocated to specific lots.
  - inferred_caveat        Per-lot cost via VF decoder is inferred, not validated.
  - phase_ambiguity        'Phase A' alone is ambiguous across projects.
  - commercial_isolation   HarmCo X-X is commercial, not residential.
  - canonical_promotion    Inferred decoder rules must not be cited as validated.
  - source_conflict        DR vs VF vs QB Register have disjoint semantics.
  - margin_reconstruction  Composing cost + sale + close must include the inferred caveat.
  - org_wide_refusal       Hillcrest/Flagship are out of scope by design.
  - aultf_b_correction     v2.1 corrected B-suffix routing; lineage must show it.
  - lineage_integrity      Pack content hashes must verify against disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from bedrock.evaluation.operational.assertions import (
    Assertion,
    LineageHashesMustMatchDisk,
    MustDistinguishOverlappingNames,
    MustHaveLineageIncluding,
    MustNotPromoteInferredToValidated,
    MustNotReturnEntityIdMatching,
    MustResolveCrosswalk,
    MustReturnEntity,
    MustReturnGuardrailFile,
    MustSurfaceWarning,
)


@dataclass
class OperationalScenario:
    """A real moment of business confusion + the assertions a correct system would satisfy."""

    name: str
    category: str
    narrative: str  # who asks, why, what the wrong answer would do
    query: str
    assertions: List[Assertion] = field(default_factory=list)
    top_k: int = 12
    budget_tokens: int = 2400


SCENARIOS: List[OperationalScenario] = [
    # -----------------------------------------------------------------------
    # OVERLAPPING NAMES — the v2.1 3-tuple discipline
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="harmony_lot_101_distinct_in_mf1_vs_b1",
        category="overlapping_names",
        narrative=(
            "An accountant asks 'what is the cost picture for Harmony lot 101?'. "
            "There are TWO physical assets: lot 101 in MF1 (townhome) and lot 101 in B1 "
            "(single-family). v2.0 used a flat (project, lot) join and conflated $443K of "
            "spend onto the wrong inventory row. The retrieval system must surface BOTH "
            "lots distinctly so the accountant can see they are not the same asset."
        ),
        query="What is the cost picture for Harmony lot 101?",
        assertions=[
            MustDistinguishOverlappingNames(
                must_have_all_of=[
                    "lot:Harmony::MF1::101",
                    "lot:Harmony::B1::101",
                ]
            ),
            MustReturnGuardrailFile(filename_substring="guardrail_harmony_3tuple_join"),
            MustSurfaceWarning(pattern=r"inferred|do not promote"),
        ],
    ),
    # -----------------------------------------------------------------------
    # CROSSWALK — SctLot canonicalization
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="sctlot_resolves_to_scattered_lots_not_scarlet_ridge",
        category="crosswalk",
        narrative=(
            "A finance lead asks about 'SctLot cost'. In the raw VF GL, SctLot is a "
            "vendor-system label for the Scattered Lots program. v2.0 mistakenly bucketed "
            "$6.55M of SctLot spend into the Scarlet Ridge project, inflating Scarlet by "
            "~46%. The system must resolve SctLot to Scattered Lots and must NOT silently "
            "include Scarlet Ridge as the canonical answer."
        ),
        query="What is the actual cost on SctLot?",
        assertions=[
            MustResolveCrosswalk(
                source_value="SctLot",
                canonical_substring="Scattered Lots",
                wrong_canonical_substring=None,  # mention can co-occur in change-log chunks
            ),
            MustReturnGuardrailFile(filename_substring="guardrail_sctlot_scattered_lots"),
            MustNotReturnEntityIdMatching(pattern=r"^project:Scarlet Ridge$"),
            MustSurfaceWarning(pattern=r"inferred|Scattered Lots|do not promote"),
        ],
    ),
    # -----------------------------------------------------------------------
    # ALLOCATION AMBIGUITY — range/shell rows
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="range_row_cost_must_not_allocate_to_lots",
        category="allocation_ambiguity",
        narrative=(
            "A land manager asks 'allocate the range row cost to specific HarmCo lots'. "
            "$45.75M of GL postings (~4,020 rows, 8 VF codes) span multiple lots and live "
            "at project+phase grain only. They cannot be allocated to specific lots without "
            "source-owner method selection (equal split, sales-weighted, fixed proportional). "
            "The system must surface the range-row guardrail and refuse to fabricate per-lot "
            "allocations."
        ),
        query="Allocate the range row cost to specific HarmCo lots and show me per-lot totals",
        assertions=[
            MustReturnGuardrailFile(filename_substring="guardrail_range_rows_not_lot_level"),
            MustHaveLineageIncluding(
                source_file_substring="cost_source_range_shell_rows"
            ),
            MustSurfaceWarning(pattern=r"inferred|do not promote"),
        ],
    ),
    # -----------------------------------------------------------------------
    # INFERRED CAVEAT — VF decoder per-lot cost
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="per_lot_actual_cost_must_carry_inferred_caveat",
        category="inferred_caveat",
        narrative=(
            "A controller asks 'what's the actual cost on Harmony B1 lot 101?'. The "
            "vf_actual_cost_3tuple_usd field is computed by the v1 VF decoder, which is "
            "heuristic-driven and NOT source-owner-validated. The system must cite the "
            "inferred-decoder caveat and lineage the decoder report."
        ),
        query="What is the actual cost of Harmony B1 lot 101?",
        assertions=[
            MustReturnEntity(entity_id="lot:Harmony::B1::101"),
            MustSurfaceWarning(pattern=r"inferred|VF decoder|not source-owner"),
            MustReturnGuardrailFile(
                filename_substring="guardrail_inferred_decoder_rules"
            ),
            MustHaveLineageIncluding(
                source_file_substring="vf_lot_code_decoder_v1"
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # PHASE AMBIGUITY — same phase name across multiple projects
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="phase_a_ambiguous_across_projects",
        category="phase_ambiguity",
        narrative=(
            "A new analyst asks 'what is phase A?'. There are multiple projects with a "
            "phase 'A' (Salem Fields A, Eagle Vista A, etc.). The retrieval system must "
            "surface multiple project-scoped phase entities so the analyst sees the "
            "ambiguity, not a single arbitrary winner."
        ),
        query="What is phase A?",
        assertions=[
            # Both Salem Fields A and Eagle Vista A exist in v2.1 — system must surface both
            MustReturnEntity(entity_id="phase:Salem Fields::A"),
            MustReturnEntity(entity_id="phase:Eagle Vista::A"),
        ],
    ),
    # -----------------------------------------------------------------------
    # COMMERCIAL ISOLATION — HarmCo X-X
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="harmco_xx_commercial_isolated_from_residential_lots",
        category="commercial_isolation",
        narrative=(
            "A pricing analyst asks 'what's the total cost on HarmCo'. HarmCo X-X parcels "
            "(~$2.6M, 205 rows) are commercial parcels — NOT residential lots. The system "
            "must surface the commercial-not-residential guardrail so the analyst knows "
            "to exclude commercial when reporting per-lot costs."
        ),
        query="What is the total cost on HarmCo and per-lot averages?",
        assertions=[
            MustReturnGuardrailFile(
                filename_substring="guardrail_commercial_not_residential"
            ),
            MustHaveLineageIncluding(
                source_file_substring="cost_source_commercial_parcels"
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # CANONICAL PROMOTION — inferred must stay inferred
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="inferred_decoder_must_not_promote_to_validated",
        category="canonical_promotion",
        narrative=(
            "A reporting analyst asks 'is Harmony lot cost validated by Finance?'. The "
            "honest answer is NO — the v1 decoder is inferred until source-owner sign-off. "
            "If the system surfaces an entity with confidence='inferred' inside a section "
            "that uses 'validated' loosely, that's a quiet promotion bug. This assertion "
            "catches it."
        ),
        query="Is Harmony lot 101 cost validated, or inferred?",
        assertions=[
            MustNotPromoteInferredToValidated(),
            MustReturnGuardrailFile(
                filename_substring="guardrail_inferred_decoder_rules"
            ),
            MustSurfaceWarning(pattern=r"inferred|do not promote"),
        ],
    ),
    # -----------------------------------------------------------------------
    # SOURCE CONFLICT — DR vs VF vs QB
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="dr_and_vf_have_disjoint_semantics_no_silent_combine",
        category="source_conflict",
        narrative=(
            "A controller asks 'reconcile DataRails and Vertical Financials cost on "
            "Harmony for 2018-2025'. DataRails is legacy 2016-17 (with 2.16x row "
            "duplication), VF is the primary 2018-25 lot-cost source, and QB Register "
            "is 2025 vendor/cash on a different chart of accounts. They are NEVER "
            "combined raw. The system must surface the cost-source guardrails so the "
            "controller sees the semantic boundary."
        ),
        query="Reconcile DataRails and Vertical Financials cost on Harmony 2018-2025",
        assertions=[
            MustHaveLineageIncluding(
                source_file_substring="cost_source"
            ),
            # The change-log captures the DR dedup rule + VF/QB semantic split
            MustHaveLineageIncluding(source_file_substring="change_log"),
        ],
    ),
    # -----------------------------------------------------------------------
    # MARGIN RECONSTRUCTION — composition over inferred state
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="margin_reconstruction_must_inherit_inferred_caveat",
        category="margin_reconstruction",
        narrative=(
            "An asset manager asks 'what's the margin on Harmony B1 lot 101?'. To compute "
            "margin you need vf_actual_cost_3tuple_usd (inferred) + vert_close_date / "
            "sale_price. Even if the system surfaces all the inputs correctly, it must "
            "carry the inferred-cost caveat through — variance/margin inherits the "
            "weakest input's confidence."
        ),
        query="What is the margin on Harmony B1 lot 101?",
        assertions=[
            MustReturnEntity(entity_id="lot:Harmony::B1::101"),
            MustSurfaceWarning(pattern=r"inferred|do not promote"),
            MustReturnGuardrailFile(
                filename_substring="guardrail_inferred_decoder_rules"
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # ORG-WIDE REFUSAL — out of scope by design
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="org_wide_query_must_surface_refusal_guardrail",
        category="org_wide_refusal",
        narrative=(
            "A board member asks 'what are our org-wide actuals across all entities?'. "
            "Hillcrest and Flagship Belmont have GL data only through 2017-02 — frozen. "
            "Org-wide rollups are explicitly out of scope. The system must surface the "
            "org-wide-unavailable guardrail so the board member sees the data limit."
        ),
        query="What are our org-wide actuals across BCPD, Hillcrest, and Flagship Belmont?",
        assertions=[
            MustReturnGuardrailFile(filename_substring="guardrail_orgwide_unavailable"),
            MustHaveLineageIncluding(source_file_substring="agent_context_v2_1_bcpd"),
        ],
    ),
    # -----------------------------------------------------------------------
    # AULTF B-SUFFIX — v2.1 correction lineage
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="aultf_b_suffix_correction_visible_in_lineage",
        category="aultf_b_correction",
        narrative=(
            "An auditor asks 'what changed for AultF in v2.1?'. v2.1 corrected $4.0M / "
            "1,499 rows from B → B1. The change log carries the correction story. "
            "The system must lineage-cite the change_log so the auditor can verify the "
            "delta themselves."
        ),
        query="What changed for AultF in v2.1?",
        assertions=[
            MustHaveLineageIncluding(source_file_substring="change_log"),
            MustHaveLineageIncluding(source_file_substring="parkway_fields"),
        ],
    ),
    # -----------------------------------------------------------------------
    # LINEAGE INTEGRITY — content hashes must verify
    # -----------------------------------------------------------------------
    OperationalScenario(
        name="lineage_content_hashes_verify_against_disk",
        category="lineage_integrity",
        narrative=(
            "Any pack the system emits must be self-verifying: a downstream consumer "
            "must be able to confirm 'this fact came from a file that's still on disk "
            "and unchanged'. If a source file is mutated between pack-time and read-time, "
            "the lineage hash mismatch must catch it. This scenario asserts integrity on "
            "a normal query — verifying the framework works on current state."
        ),
        query="Harmony 3-tuple correction overview",
        assertions=[
            LineageHashesMustMatchDisk(),
        ],
    ),
]


def by_category() -> dict:
    """Return scenarios grouped by category for the report."""
    out: dict = {}
    for s in SCENARIOS:
        out.setdefault(s.category, []).append(s)
    return out
