"""BCPD workflow tools — operational deliverables composed from real v2.1 state.

Six named tools that emit the same kinds of artifacts the workflow A/B eval
demonstrated (output/llm_eval/workflow_value_demo_cards.md), but **deterministically**:
- generate_project_brief
- review_margin_report_readiness
- find_false_precision_risks
- summarize_change_impact
- prepare_finance_land_review
- draft_owner_update

Design notes:
  - Tools subclass core.tools.base.Tool — they integrate with ToolRegistry +
    LLMAgent without modification.
  - Each tool combines (a) structured facts pulled directly from
    output/operating_state_v2_1_bcpd.json with (b) narrative chunks retrieved
    via the bedrock HybridOrchestrator (chunk + routed sources). No LLM in
    the composition loop — the orchestrator surfaces evidence; the tool's
    deterministic recipe assembles the deliverable.
  - Hard read-only. No mutation of v2.1 artifacts, no data writes outside
    output/runtime_demo/.
  - Guardrails honored: missing cost = unknown (not $0); inferred decoder
    stays inferred; range/shell rows stay project+phase grain; Harmony uses
    3-tuple; SctLot → Scattered Lots; HarmCo X-X commercial isolated;
    org-wide v2 is not claimed ready; VF is cost-basis / asset-side.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.connectors.base import Connector
from core.connectors.file import FileConnector
from core.tools.base import Tool


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = REPO_ROOT / "output" / "operating_state_v2_1_bcpd.json"


# ---------------------------------------------------------------------------
# BcpdContext — shared loader + retrieval orchestration for all 6 tools
# ---------------------------------------------------------------------------


class BcpdContext:
    """Caches the v2.1 state + a chunk/routed orchestrator across tool calls.

    The orchestrator uses only ChunkSource + RoutedSource — the entity-grain
    vector index is not required for these workflows, so this avoids the
    parquet-build dependency. EntitySource can be wired in via the optional
    `add_entity_source` flag if a caller has already built the index.
    """

    def __init__(
        self,
        state_path: Path = DEFAULT_STATE_PATH,
        add_entity_source: bool = False,
    ) -> None:
        self.state_path = Path(state_path)
        self.add_entity_source = add_entity_source
        self._state: Optional[Dict[str, Any]] = None
        self._orchestrator = None  # lazy

    @property
    def state(self) -> Dict[str, Any]:
        if self._state is None:
            self._state = FileConnector(self.state_path).fetch()
            if not isinstance(self._state, dict):
                raise RuntimeError(
                    f"FileConnector returned {type(self._state).__name__}; "
                    f"expected dict from {self.state_path}"
                )
        return self._state

    def orchestrator(self):
        if self._orchestrator is None:
            # Lazy import — keeps core/ -> bedrock/ coupling explicit.
            from bedrock.retrieval.orchestration import HybridOrchestrator, RRFFuser
            from bedrock.retrieval.retrievers.chunk_source import ChunkSource
            from bedrock.retrieval.retrievers.routed_source import RoutedSource

            retrievers = [ChunkSource(), RoutedSource()]
            if self.add_entity_source:
                # EntitySource depends on bedrock/embeddings/ + the entity
                # parquet at output/bedrock/entity_index.parquet. The BCPD
                # Skill v0.1 package ships neither (audit:
                # docs/embedding_retrieval_audit_bcpd_v0_1.md §9, weakness
                # 7.10). Raising a clear error here is preferable to the
                # silent ModuleNotFoundError the import would otherwise
                # produce inside the package.
                try:
                    from bedrock.retrieval.retrievers.entity_source import EntitySource
                    from bedrock.retrieval.services.entity_retriever import default_retriever
                except ImportError as e:
                    raise RuntimeError(
                        "EntitySource is not bundled in BCPD Skill v0.1; "
                        "use ChunkSource + RoutedSource (the default), or "
                        "rebuild the package with the entity retrieval stack "
                        "(bedrock/embeddings/, bedrock/retrieval/services/, "
                        "and output/bedrock/entity_index.parquet)."
                    ) from e
                try:
                    retrievers.append(EntitySource(default_retriever()))
                except FileNotFoundError as e:
                    raise RuntimeError(
                        "EntitySource is not bundled in BCPD Skill v0.1; "
                        "use ChunkSource + RoutedSource (the default), or "
                        "rebuild the package with the entity retrieval stack "
                        "(bedrock/embeddings/, bedrock/retrieval/services/, "
                        "and output/bedrock/entity_index.parquet)."
                    ) from e
            self._orchestrator = HybridOrchestrator(
                retrievers=retrievers,
                fuser=RRFFuser(),
            )
        return self._orchestrator

    def retrieve(
        self, query: str, top_k: int = 12
    ) -> List["RetrievalHit"]:  # type: ignore[name-defined]
        return self.orchestrator().retrieve(query=query, top_k=top_k).hits

    # ------------------------------------------------------------------
    # Structured fact accessors — every workflow tool calls these.
    # ------------------------------------------------------------------

    def change_summary(self) -> Dict[str, Any]:
        return self.state.get("v2_1_changes_summary", {}) or {}

    def data_quality(self) -> Dict[str, Any]:
        return self.state.get("data_quality", {}) or {}

    def metadata(self) -> Dict[str, Any]:
        return self.state.get("metadata", {}) or {}

    def caveats(self) -> List[Any]:
        return self.state.get("caveats", []) or []

    def open_questions(self) -> List[str]:
        return self.state.get("source_owner_questions_open", []) or []

    def projects(self) -> List[Dict[str, Any]]:
        return self.state.get("projects", []) or []

    def find_project(self, name: str) -> Optional[Dict[str, Any]]:
        target = name.strip().lower()
        for p in self.projects():
            if (p.get("canonical_project") or "").strip().lower() == target:
                return p
        # Tolerant fuzzy match — drop hyphens/spaces
        norm = target.replace(" ", "").replace("-", "")
        for p in self.projects():
            cand = (p.get("canonical_project") or "").lower().replace(" ", "").replace("-", "")
            if cand == norm:
                return p
        return None


# ---------------------------------------------------------------------------
# Shared rendering helpers — keep tools focused on content, not formatting.
# ---------------------------------------------------------------------------


def _money(n: Any) -> str:
    if n is None:
        return "unknown"
    try:
        f = float(n)
    except (TypeError, ValueError):
        return str(n)
    return f"${f:,.0f}"


def _evidence_block(hits: List[Any], limit: int = 6) -> str:
    """Render the retrieval hits as a compact evidence list with source paths."""
    if not hits:
        return "_(no retrieval evidence surfaced)_\n"
    lines: List[str] = []
    seen_files: set = set()
    for h in hits[:limit]:
        label = h.title or h.chunk_id or h.entity_id or "?"
        src = h.source_files[0] if h.source_files else "?"
        if src in seen_files:
            continue
        seen_files.add(src)
        lines.append(f"- **{label}** — `{src}`")
    return "\n".join(lines) + "\n"


def _scope_clause(scope: Optional[str]) -> str:
    if scope and scope.lower() == "bcpd":
        return "**Scope: BCPD only** (entities BCPD/BCPBL/ASD/BCPI). Hillcrest and Flagship Belmont are out of scope; their GL coverage ends 2017-02 — org-wide v2 is NOT available."
    return "**Scope: BCPD only** by design."


# Evidence-reference cleanup — the v2.1 JSON's evidence fields cite
# scratch/vf_decoder_*.md review files that are NOT in the repo. Publishable
# outputs should not link to dangling paths. This transform rewrites them
# to plain wording while preserving the audit reference.
_SCRATCH_PREFIX_RE = re.compile(
    r"^scratch/(vf_decoder|harm|parkway|ault)[^\s]*\.md\s*(Q\d+(?:\+Q?\d+)?)?\s*$",
    re.IGNORECASE,
)


def _humanize_evidence(ev: Optional[str]) -> str:
    """Rewrite scratch/vf_decoder_* references into publishable wording.

    Inputs like 'scratch/vf_decoder_gl_finance_review.md Q2' become
    'internal VF decoder review notes (Q2)'. Other paths pass through.
    """
    if not ev:
        return ""
    s = str(ev).strip()
    m = _SCRATCH_PREFIX_RE.match(s)
    if m:
        q = m.group(2)
        return (
            f"internal VF decoder review notes ({q})" if q
            else "internal VF decoder review notes"
        )
    # Other scratch/* paths get neutralized but keep the question marker if any.
    if s.startswith("scratch/"):
        return s.replace("scratch/", "internal review notes — ", 1)
    return s


def _confidence_boundary_section(fields: List[Dict[str, str]]) -> str:
    """Render a structured 'Confidence boundaries' table.

    Each `fields` entry is a dict with keys: grain, confidence, source.
    All values are derived from real v2.1 confidence labels — we don't invent
    levels that aren't in the source data (`source_confidence`,
    `vf_actual_cost_confidence`, `phase_confidence`, decoder confidence in
    v2_1_changes_summary, and the documented project+phase grain rule for
    range/shell rows).

    Purpose: give readers a single block that maps each fact in the
    deliverable to the confidence tier it carries — so a finance reader
    can see at a glance which numbers can be cited as-is and which need a
    caveat clause.
    """
    if not fields:
        return ""
    out: List[str] = [
        "## Confidence boundaries\n\n",
        "_Each row maps a fact in this brief to the confidence label it "
        "actually carries in v2.1 state. Cite accordingly._\n\n",
        "| Grain / Fact | Confidence | Source |\n",
        "|---|---|---|\n",
    ]
    for f in fields:
        out.append(
            f"| {f.get('grain', '')} | {f.get('confidence', '')} | "
            f"{f.get('source', '')} |\n"
        )
    return "".join(out) + "\n"


# ---------------------------------------------------------------------------
# Confidence-row catalogs — declared here so the same row text reads
# identically across tools that touch the same grain. No magic; no LLM.
# ---------------------------------------------------------------------------


_CONF_ROW_PROJECT_TOTALS = {
    "grain": "Project-level totals (rows, USD sums)",
    "confidence": "higher — exact aggregates of (inferred) per-lot rows",
    "source": "`operating_state_v2_1_bcpd.json` → `projects[].actuals.*`",
}

_CONF_ROW_PER_LOT_DECODER = {
    "grain": "Per-lot VF cost (`vf_actual_cost_3tuple_usd`)",
    "confidence": "**inferred** (v1 decoder; not source-owner-validated)",
    "source": "`vf_lot_code_decoder_v1` rule set; per-lot field `vf_actual_cost_confidence`",
}

_CONF_ROW_RANGE_SHELL = {
    "grain": "Range / shell GL rows (`'3001-06'`, `'0009-12'`, etc.)",
    "confidence": "**project+phase grain only** — allocation method pending source-owner sign-off",
    "source": "`v2_1_changes_summary.range_rows_at_project_phase_grain` ($45.75M / 4,020 rows)",
}

_CONF_ROW_SR_SUFFIX = {
    "grain": "AultF SR-suffix lots (`0139SR`, `0140SR`)",
    "confidence": "**inferred-unknown** — canonical phase pending source-owner sign-off",
    "source": "`v2_1_changes_summary.aultf_sr_isolated` (401 rows / $1.18M)",
}

_CONF_ROW_AULTF_B = {
    "grain": "AultF B-suffix routing (B1 in v2.1, was B2 in v2.0)",
    "confidence": "**inferred (high-evidence)** — empirically derived; awaiting source-owner sign-off",
    "source": "`v2_1_changes_summary.aultf_b_to_b1_correction` (1,499 rows / $4.0M)",
}

_CONF_ROW_NO_GL_UNKNOWN = {
    "grain": "Projects with no GL coverage (lot-level cost)",
    "confidence": "**unknown** — show as null / 'unknown', NEVER $0",
    "source": "absence in `vf_2018_2025_sum_usd` AND `dr_2016_2017_sum_usd_dedup`",
}

_CONF_ROW_COMMERCIAL = {
    "grain": "HarmCo X-X commercial parcels",
    "confidence": "**commercial / non-residential** — exclude from residential lot rollups",
    "source": "`v2_1_changes_summary.harmco_split.commercial_rows` (205 rows)",
}

_CONF_ROW_HARMONY_3TUPLE = {
    "grain": "Harmony lot cost (when joined)",
    "confidence": "valid only at **3-tuple** `(project, phase, lot)` — flat 2-tuple double-counts by $6.75M",
    "source": "`v2_1_changes_summary.harmony_3tuple_join_required`",
}

_CONF_ROW_PHASE_QUERYABLE = {
    "grain": "Phase variance / margin (`expected_total_cost` vs `actual_cost_total`)",
    "confidence": "**queryable on 3/125 phases only** — the rest lack complete expected_cost",
    "source": "`phase_state.is_queryable` gate (v2.1)",
}

_CONF_ROW_PHASE_CONFIDENCE = {
    "grain": "Per-phase aggregations",
    "confidence": "inherits per-phase `phase_confidence` label (high / medium / low)",
    "source": "`projects[].phases[].phase_confidence`",
}

_CONF_ROW_DR_38COL = {
    "grain": "DataRails 38-col GL (2016–2017)",
    "confidence": "valid after 2.16× row-multiplication dedup (handled in pipeline)",
    "source": "`data_quality.datarails_38col_dedup_applied`",
}

_CONF_ROW_QB_REGISTER = {
    "grain": "QuickBooks Register (12-col)",
    "confidence": "**tie-out only** — excluded from primary rollups",
    "source": "`data_quality.qb_register_12col_treatment`",
}


# ===========================================================================
# 1. generate_project_brief
# ===========================================================================


class GenerateProjectBriefTool(Tool):
    """Finance-ready project brief composed from v2.1 state + routed chunks.

    Hardwired to the Parkway Fields demo path of the workflow eval (which
    surfaces the AultF B-suffix correction story), but accepts any canonical
    project name — the tool falls back to a structured project sketch if the
    project is in v2.1 but not in the routed-rule narrative.
    """

    output_format = "markdown"
    name = "generate_project_brief"
    description = (
        "Compose a finance-ready brief for one BCPD v2.1 project. Surfaces "
        "phase composition, decoder-derived cost basis with inferred caveat, "
        "v2.1 correction story (e.g., AultF B-suffix for Parkway Fields), and "
        "the source-owner items blocking promotion to validated."
    )

    def __init__(self, context: Optional[BcpdContext] = None, **kwargs):
        super().__init__(**kwargs)
        self.context = context or BcpdContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Canonical BCPD project name (e.g. 'Parkway Fields').",
                }
            },
            "required": ["project"],
        }

    def run(self, data=None, project: str = "", **kwargs) -> str:
        if isinstance(data, dict) and "project" in data:
            project = data["project"]
        project = (project or kwargs.get("project") or "").strip()
        if not project:
            return "**ERROR**: project name required."

        ctx = self.context
        proj = ctx.find_project(project)
        changes = ctx.change_summary()
        hits = ctx.retrieve(
            f"{project} cost basis VF decoder phases inferred AultF correction",
            top_k=10,
        )

        out: List[str] = []
        out.append(f"# Project Brief — {project}\n")
        out.append(_scope_clause("bcpd") + "\n\n")

        # Identity + composition
        out.append("## Identity\n\n")
        if proj is None:
            out.append(
                f"`{project}` was not found as a canonical project in v2.1. "
                f"Confirm the name via `data/staged/canonical_project.csv`.\n\n"
            )
        else:
            out.append(f"- Canonical project: `{proj.get('canonical_project')}`\n")
            out.append(f"- Canonical entity: `{proj.get('canonical_entity')}`\n")
            out.append(f"- Phase count: {proj.get('phase_count')}\n")
            out.append(f"- Lot count: {proj.get('lot_count')}\n")
            out.append(
                f"- Active lots (2025Status): {proj.get('lot_count_active_2025status')}\n\n"
            )
            actuals = proj.get("actuals") or {}
            out.append(
                "## Cost basis (v2.1, inferred via Vertical Financials decoder v1)\n\n"
            )
            out.append(
                "_VF = Vertical Financials (primary 2018–2025 GL); "
                "DR = DataRails (legacy 2016–2017 GL, deduped); "
                "SR-suffix = special-rate lots (`0139SR`, `0140SR`) held inferred-unknown._\n\n"
            )
            out.append("| Bucket | Rows | USD |\n|---|---|---|\n")
            for label, rows_k, usd_k in (
                ("Vertical Financials (VF) lot grain (2018–2025)", "vf_lot_grain_rows", "vf_lot_grain_sum_usd"),
                ("VF range / shell grain", "vf_range_grain_rows", "vf_range_grain_sum_usd"),
                ("VF commercial parcels", "vf_commercial_grain_rows", "vf_commercial_grain_sum_usd"),
                ("VF SR-suffix (inferred-unknown)", "vf_sr_inferred_unknown_rows", "vf_sr_inferred_unknown_sum_usd"),
                ("DataRails (DR) 38-col 2016–2017 (deduped)", "dr_2016_2017_rows_dedup", "dr_2016_2017_sum_usd_dedup"),
            ):
                out.append(
                    f"| {label} | {actuals.get(rows_k, '—')} | {_money(actuals.get(usd_k))} |\n"
                )
            out.append("\n")

        # v2.1 correction story (especially material for Parkway Fields)
        is_parkway = project.lower().replace(" ", "") in {"parkwayfields"}
        if is_parkway:
            aultf = changes.get("aultf_b_to_b1_correction") or {}
            harmco = changes.get("harmco_split") or {}
            sr = changes.get("aultf_sr_isolated") or {}
            out.append("## v2.1 corrections affecting this project\n\n")
            out.append(
                f"- **AultF B-suffix → B1 correction**: {aultf.get('rows', '—'):,} rows "
                f"/ {_money(aultf.get('dollars'))}. Previously misrouted to B2 in v2.0. "
                f"_{aultf.get('description', '')}_ Confidence: `{aultf.get('confidence', 'inferred')}`.\n"
            )
            out.append(
                f"- **AultF SR-suffix isolated** (inferred-unknown): {sr.get('rows', '—'):,} rows / "
                f"{_money(sr.get('dollars'))}. Held separately — canonical phase still pending source-owner sign-off.\n"
            )
            if harmco:
                out.append(
                    f"- (HarmCo split context, also relevant if Parkway↔HarmCo decoder questions surface): "
                    f"{harmco.get('residential_rows', '—'):,} residential + "
                    f"{harmco.get('commercial_rows', '—'):,} commercial. Commercial parcels are non-residential.\n"
                )
            out.append("\n")

        # Inferred-decoder caveat — surface every time
        out.append("## Caveats (do not promote without source-owner sign-off)\n\n")
        out.append(
            "- All per-lot VF cost is **inferred (v1 decoder)** — not source-owner-validated. "
            "Do not promote to 'validated' for external reporting or transactions.\n"
        )
        out.append(
            "- Range/shell rows live at project+phase grain only — do not allocate to specific lots without a sign-off allocation method.\n"
        )
        out.append(
            "- For Harmony queries (not this project, but worth noting in cross-project work): "
            "always use the (project, phase, lot) 3-tuple — flat 2-tuple joins double-count by ~$6.75M.\n\n"
        )

        # Field-level confidence boundaries — distinguish project-level totals
        # (higher confidence) from per-lot decoder cost (inferred) etc.
        conf_rows = [
            _CONF_ROW_PROJECT_TOTALS,
            _CONF_ROW_PER_LOT_DECODER,
            _CONF_ROW_RANGE_SHELL,
        ]
        if is_parkway:
            conf_rows.append(_CONF_ROW_AULTF_B)
            conf_rows.append(_CONF_ROW_SR_SUFFIX)
        conf_rows.append(_CONF_ROW_PHASE_CONFIDENCE)
        out.append(_confidence_boundary_section(conf_rows))

        # Retrieval evidence
        out.append("## Retrieval evidence (auto-surfaced chunks)\n\n")
        out.append(_evidence_block(hits, limit=6))
        out.append("\n")

        return "".join(out) + self._provenance_section()


# ===========================================================================
# 2. review_margin_report_readiness
# ===========================================================================


class ReviewMarginReportReadinessTool(Tool):
    output_format = "markdown"
    name = "review_margin_report_readiness"
    description = (
        "List BCPD projects safe vs unsafe for lot-level margin reporting. "
        "Surfaces: projects with no GL coverage (unknown != $0), range/shell "
        "rows at project+phase grain, decoder-inferred per-lot cost. Output "
        "is a 'do not include' / 'include with caveat' checklist."
    )

    def __init__(self, context: Optional[BcpdContext] = None, **kwargs):
        super().__init__(**kwargs)
        self.context = context or BcpdContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": "Reporting scope (default 'bcpd').",
                    "default": "bcpd",
                }
            },
        }

    def run(self, data=None, scope: str = "bcpd", **kwargs) -> str:
        if isinstance(data, dict) and "scope" in data:
            scope = data["scope"]

        ctx = self.context
        changes = ctx.change_summary()
        dq = ctx.data_quality()
        range_info = changes.get("range_rows_at_project_phase_grain") or {}

        # Identify no-GL projects
        no_gl: List[str] = []
        for p in ctx.projects():
            actuals = p.get("actuals") or {}
            vf_total = float(actuals.get("vf_2018_2025_sum_usd") or 0)
            dr_total = float(actuals.get("dr_2016_2017_sum_usd_dedup") or 0)
            if vf_total == 0 and dr_total == 0:
                no_gl.append(p.get("canonical_project") or "?")

        hits = ctx.retrieve(
            "lot-level margin report missing cost unknown range shell rows inferred decoder",
            top_k=8,
        )

        out: List[str] = []
        out.append("# Lot-Level Margin Report — Readiness Review\n")
        out.append(_scope_clause(scope) + "\n\n")

        out.append("## Hard rule\n\n")
        out.append(
            "**Missing cost is *unknown*, not $0.** Reporting $0 for a project without GL "
            "coverage misstates margin and inflates apparent performance. Use a null / "
            "blank cell or an explicit 'unknown' marker.\n\n"
        )

        out.append("## Do NOT include at lot grain\n\n")
        if no_gl:
            out.append(
                f"### Projects with no GL coverage (cost = unknown for all lots) — {len(no_gl)} projects\n\n"
            )
            for n in no_gl:
                out.append(f"- `{n}` — unknown lot-level cost; show as **unknown**, never $0.\n")
            out.append("\n")
        else:
            out.append("_(All canonical projects have some GL coverage.)_\n\n")

        if range_info:
            out.append("### Range / shell GL rows — project+phase grain only\n\n")
            out.append(
                f"- {range_info.get('rows', '—'):,} GL rows / "
                f"{_money(range_info.get('dollars'))} in range/shell form "
                f"(e.g. `'3001-06'`, `'0009-12'`). **Not safe at lot grain.**\n"
            )
            out.append(
                "- Allocation method (equal split, sales-weighted, fixed proportional) "
                "is **pending source-owner sign-off** and does not yet exist in v2.1.\n\n"
            )

        out.append("## Include WITH caveats (inferred-decoder cost)\n\n")
        out.append(
            "- Per-lot VF cost is **inferred via the v1 decoder** — not source-owner-validated. "
            "Margin figures inherit that inferred confidence.\n"
        )
        out.append(
            "- Harmony lots: require the 3-tuple `(project, phase, lot)` to avoid the v2.0 "
            "$6.75M double-count. v2.1 enforces `vf_actual_cost_3tuple_usd`.\n"
        )
        out.append(
            "- SctLot lots roll up under **Scattered Lots**, NOT Scarlet Ridge "
            "($6.55M un-inflated in v2.1).\n"
        )
        out.append(
            "- HarmCo X-X parcels are commercial / non-residential — exclude from per-lot "
            "residential margin reports.\n\n"
        )

        out.append("## Coverage snapshot (v2.1)\n\n")
        out.append(
            "_'Full triangle' = a lot that appears in all three feeds: "
            "inventory + GL (general ledger / Vertical Financials) + ClickUp tasks._\n\n"
        )
        out.append("| Metric | Value |\n|---|---|\n")
        out.append(f"| Lots in canonical | {dq.get('lots_total_in_canonical')} |\n")
        out.append(f"| High-confidence lots | {dq.get('lots_high_confidence')} |\n")
        out.append(
            f"| Full-triangle join coverage (lot in inventory + GL + ClickUp) "
            f"| {dq.get('join_coverage_pct_triangle')}% |\n"
        )
        out.append(f"| GL join coverage | {dq.get('join_coverage_pct_gl')}% |\n\n")

        # Field-level confidence boundaries — distinguish the four tiers that
        # an accountant has to keep separate when building a margin report.
        out.append(
            _confidence_boundary_section(
                [
                    _CONF_ROW_NO_GL_UNKNOWN,
                    _CONF_ROW_PER_LOT_DECODER,
                    _CONF_ROW_RANGE_SHELL,
                    _CONF_ROW_HARMONY_3TUPLE,
                    _CONF_ROW_COMMERCIAL,
                    _CONF_ROW_PHASE_QUERYABLE,
                ]
            )
        )

        out.append("## Retrieval evidence\n\n")
        out.append(_evidence_block(hits, limit=4))

        return "".join(out) + self._provenance_section()


# ===========================================================================
# 3. find_false_precision_risks
# ===========================================================================


class FindFalsePrecisionRisksTool(Tool):
    output_format = "markdown"
    name = "find_false_precision_risks"
    description = (
        "Enumerate where current BCPD reports may give false precision: "
        "$45.75M range/shell rows kept at project+phase grain (not lot-level), "
        "inferred decoder rules treated as validated, 3-tuple Harmony joins, "
        "SctLot vs Scarlet Ridge attribution, HarmCo X-X commercial isolation."
    )

    def __init__(self, context: Optional[BcpdContext] = None, **kwargs):
        super().__init__(**kwargs)
        self.context = context or BcpdContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "default": "bcpd"},
            },
        }

    def run(self, data=None, scope: str = "bcpd", **kwargs) -> str:
        if isinstance(data, dict) and "scope" in data:
            scope = data["scope"]
        ctx = self.context
        c = ctx.change_summary()

        rng = c.get("range_rows_at_project_phase_grain") or {}
        harmony = c.get("harmony_3tuple_join_required") or {}
        sct = c.get("sctlot_to_scattered_lots") or {}
        harmco = c.get("harmco_split") or {}
        aultf = c.get("aultf_b_to_b1_correction") or {}

        hits = ctx.retrieve(
            "false precision range shell rows lot grain inferred decoder Harmony 3-tuple SctLot",
            top_k=10,
        )

        out: List[str] = []
        out.append("# False Precision Risks — BCPD Reports\n")
        out.append(_scope_clause(scope) + "\n\n")

        out.append(
            "## 1. Range / shell GL rows shown at lot grain (highest-dollar risk)\n\n"
        )
        out.append(
            f"- **{rng.get('rows', '—'):,} GL rows / {_money(rng.get('dollars'))}** "
            f"sit in range form (e.g. `'3001-06'`, `'0009-12'`) and are safe **only at project+phase grain**.\n"
        )
        out.append(
            "- Lot-grain rollups that include these dollars manufacture per-lot precision that "
            "does not exist in the source data.\n"
        )
        out.append(
            "- Allocation method is **pending source-owner sign-off** — no method has been ratified.\n\n"
        )

        out.append("## 2. Decoder-derived per-lot cost treated as validated\n\n")
        out.append(
            "- Per-lot `vf_actual_cost_3tuple_usd` is computed by the **v1 VF decoder** — "
            "heuristic, not source-owner-validated.\n"
        )
        out.append(
            "- Any margin / variance figure inherits this inferred confidence. Reports that "
            "cite per-lot cost without the inferred caveat give false precision.\n\n"
        )

        out.append("## 3. Harmony 3-tuple discipline\n\n")
        out.append(
            f"- Flat `(project, lot)` joins for Harmony double-count by **{_money(harmony.get('double_count_prevented'))}** "
            f"(MF1 lot 101 vs B1 lot 101 are different physical assets).\n"
        )
        out.append(
            "- v2.1 requires `(project, phase, lot)` — any v2.0-era report using flat joins is wrong.\n\n"
        )

        out.append("## 4. SctLot vs Scarlet Ridge attribution\n\n")
        out.append(
            f"- **{sct.get('rows_moved', '—'):,} rows / "
            f"{_money(sct.get('dollars_moved_off_scarlet_ridge'))}** were silently bucketed into Scarlet Ridge in v2.0.\n"
        )
        out.append(
            "- v2.1: SctLot → **Scattered Lots** (separate canonical project). "
            "Reports citing 'Scarlet Ridge total' from v2.0 inflate by ~$6.55M.\n\n"
        )

        out.append("## 5. HarmCo X-X commercial parcels in residential rollups\n\n")
        out.append(
            f"- **{harmco.get('commercial_rows', '—'):,} HarmCo X-X rows** are commercial parcels — non-residential.\n"
        )
        out.append(
            "- Including them in per-lot residential margin reports overstates residential cost basis.\n\n"
        )

        out.append("## 6. AultF B-suffix routing (precision changed in v2.1)\n\n")
        out.append(
            f"- **{aultf.get('rows', '—'):,} rows / {_money(aultf.get('dollars'))}** "
            f"moved from B2 (v2.0) → B1 (v2.1). Any v2.0-based phase rollup for AultF is stale.\n\n"
        )

        # Confidence boundaries by grain — surfaces which numbers are which
        # tier of confident. Pure derived from existing v2.1 labels.
        out.append(
            _confidence_boundary_section(
                [
                    _CONF_ROW_PROJECT_TOTALS,
                    _CONF_ROW_PER_LOT_DECODER,
                    _CONF_ROW_PHASE_QUERYABLE,
                    _CONF_ROW_RANGE_SHELL,
                    _CONF_ROW_COMMERCIAL,
                    _CONF_ROW_HARMONY_3TUPLE,
                    _CONF_ROW_AULTF_B,
                    _CONF_ROW_SR_SUFFIX,
                ]
            )
        )

        out.append("## Retrieval evidence\n\n")
        out.append(_evidence_block(hits, limit=4))

        return "".join(out) + self._provenance_section()


# ===========================================================================
# 4. summarize_change_impact
# ===========================================================================


class SummarizeChangeImpactTool(Tool):
    output_format = "markdown"
    name = "summarize_change_impact"
    description = (
        "Summarize v2.0 → v2.1 correction deltas with dollar magnitudes "
        "(AultF $4.0M, Harmony $6.75M double-count avoided, SctLot $6.55M "
        "un-inflated, range/shell $45.75M surfaced explicitly, HarmCo split). "
        "Reads directly from operating_state_v2_1_bcpd.json's "
        "v2_1_changes_summary block."
    )

    def __init__(self, context: Optional[BcpdContext] = None, **kwargs):
        super().__init__(**kwargs)
        self.context = context or BcpdContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "from_version": {"type": "string", "default": "v2.0"},
                "to_version": {"type": "string", "default": "v2.1"},
            },
        }

    def run(
        self,
        data=None,
        from_version: str = "v2.0",
        to_version: str = "v2.1",
        **kwargs,
    ) -> str:
        if isinstance(data, dict):
            from_version = data.get("from_version", from_version)
            to_version = data.get("to_version", to_version)

        ctx = self.context
        c = ctx.change_summary()
        hits = ctx.retrieve(
            f"what changed {from_version} to {to_version} AultF Harmony SctLot range rows HarmCo",
            top_k=8,
        )

        aultf = c.get("aultf_b_to_b1_correction") or {}
        harmony = c.get("harmony_3tuple_join_required") or {}
        sct = c.get("sctlot_to_scattered_lots") or {}
        rng = c.get("range_rows_at_project_phase_grain") or {}
        harmco = c.get("harmco_split") or {}
        sr = c.get("aultf_sr_isolated") or {}

        out: List[str] = []
        out.append(f"# Change Impact — {from_version} → {to_version}\n\n")

        out.append("## Headline dollar impact\n\n")
        out.append("| Correction | Rows | Dollar magnitude | Confidence |\n")
        out.append("|---|---|---|---|\n")
        out.append(
            f"| AultF B-suffix → B1 (was B2 in v0) | {aultf.get('rows', '—'):,} | "
            f"{_money(aultf.get('dollars'))} re-attributed | `{aultf.get('confidence', 'inferred')}` |\n"
        )
        out.append(
            f"| Harmony 3-tuple join | — | "
            f"{_money(harmony.get('double_count_prevented'))} double-count avoided | "
            f"`{harmony.get('confidence', 'inferred')}` |\n"
        )
        out.append(
            f"| SctLot → Scattered Lots (off Scarlet Ridge) | {sct.get('rows_moved', '—'):,} | "
            f"{_money(sct.get('dollars_moved_off_scarlet_ridge'))} un-inflated | "
            f"`{sct.get('confidence', 'inferred-unknown')}` |\n"
        )
        out.append(
            f"| Range / shell rows at project+phase grain | {rng.get('rows', '—'):,} | "
            f"{_money(rng.get('dollars'))} surfaced explicitly | "
            f"`{rng.get('confidence', 'inferred')}` |\n"
        )
        if harmco:
            out.append(
                f"| HarmCo residential / commercial split | "
                f"{harmco.get('residential_rows', '—')} res + "
                f"{harmco.get('commercial_rows', '—')} com | "
                f"non-residential isolated | `{harmco.get('confidence', 'inferred')}` |\n"
            )
        if sr:
            out.append(
                f"| AultF SR-suffix isolated | {sr.get('rows', '—'):,} | "
                f"{_money(sr.get('dollars'))} held inferred-unknown | "
                f"`{sr.get('confidence', 'inferred-unknown')}` |\n"
            )
        out.append("\n")

        out.append("## Per-correction notes\n\n")
        for key, item in c.items():
            if not isinstance(item, dict):
                continue
            out.append(f"### `{key}`\n")
            out.append(f"{item.get('description', '')}\n\n")
            ev = item.get("evidence")
            humanized = _humanize_evidence(ev)
            if humanized:
                out.append(f"_Evidence:_ {humanized}\n\n")

        out.append("## What did NOT change\n\n")
        out.append(
            "- Org-wide v2 is still not available. Hillcrest and Flagship Belmont GL coverage ends 2017-02.\n"
        )
        out.append(
            "- Decoder rules remain **inferred** until source-owner sign-off.\n"
        )
        out.append(
            "- Range/shell allocation method is still **pending** — no per-lot expansion has been authorized.\n\n"
        )

        out.append("## Retrieval evidence\n\n")
        out.append(_evidence_block(hits, limit=6))

        return "".join(out) + self._provenance_section()


# ===========================================================================
# 5. prepare_finance_land_review
# ===========================================================================


class PrepareFinanceLandReviewTool(Tool):
    output_format = "markdown"
    name = "prepare_finance_land_review"
    description = (
        "Prepare a 30-minute review agenda for finance + land + ops on BCPD "
        "v2.1 source-owner validation. Groups open questions by team and "
        "ranks by dollar gate / decision impact."
    )

    # Heuristic team routing of open questions — string match on substrings.
    # No LLM in the loop; the rules are explicit.
    _FINANCE_KEYWORDS = (
        "gl",
        "datarails",
        "quickbooks",
        "dr ",
        "qb ",
        "vf ",
        "cost-basis",
        "tie-out",
        "validation",
        "validate",
        "tied",
        "balanced",
        "trial",
    )
    _LAND_KEYWORDS = (
        "plat",
        "lot",
        "phase",
        "range",
        "shell",
        "allocation",
        "decoder",
        "harm",
        "parkway",
        "sctlot",
        "scattered",
        "ault",
        "sr-suffix",
        "lewis",
    )
    _OPS_KEYWORDS = (
        "clickup",
        "tagging",
        "naming",
        "task",
        "stage",
        "lifecycle",
        "as-built",
    )

    def __init__(self, context: Optional[BcpdContext] = None, **kwargs):
        super().__init__(**kwargs)
        self.context = context or BcpdContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"scope": {"type": "string", "default": "bcpd"}},
        }

    def _route(self, q: str) -> str:
        lower = q.lower()
        if any(k in lower for k in self._FINANCE_KEYWORDS):
            return "finance"
        if any(k in lower for k in self._OPS_KEYWORDS):
            return "ops"
        if any(k in lower for k in self._LAND_KEYWORDS):
            return "land"
        return "land"  # default — land/development owns most decoder semantics

    def run(self, data=None, scope: str = "bcpd", **kwargs) -> str:
        if isinstance(data, dict) and "scope" in data:
            scope = data["scope"]

        ctx = self.context
        opens = ctx.open_questions()
        changes = ctx.change_summary()
        hits = ctx.retrieve(
            "source-owner validation queue meeting prep finance land ops decisions",
            top_k=10,
        )

        by_team: Dict[str, List[str]] = {"finance": [], "land": [], "ops": []}
        for q in opens:
            by_team[self._route(q)].append(q)

        out: List[str] = []
        out.append("# Finance / Land / Ops Review — 30-Minute Agenda\n")
        out.append(_scope_clause(scope) + "\n\n")

        out.append("## Why this meeting\n\n")
        out.append(
            "Promote `inferred` decoder cost to `validated` for v2.2, and decide the "
            "allocation method for range/shell rows. The bottleneck is **source-owner sign-off**, "
            "not engineering.\n\n"
        )

        out.append("## Dollar gates (anchor the meeting around these)\n\n")
        rng = changes.get("range_rows_at_project_phase_grain") or {}
        aultf = changes.get("aultf_b_to_b1_correction") or {}
        harmony = changes.get("harmony_3tuple_join_required") or {}
        sct = changes.get("sctlot_to_scattered_lots") or {}
        sr = changes.get("aultf_sr_isolated") or {}
        out.append(f"- Range / shell allocation: **{_money(rng.get('dollars'))}** pending method sign-off.\n")
        out.append(f"- AultF B-suffix routing: **{_money(aultf.get('dollars'))}** decoder rule to validate.\n")
        out.append(f"- Harmony 3-tuple discipline: **{_money(harmony.get('double_count_prevented'))}** double-count avoided.\n")
        out.append(f"- SctLot → Scattered Lots: **{_money(sct.get('dollars_moved_off_scarlet_ridge'))}** un-inflated; canonical name pending.\n")
        out.append(f"- AultF SR-suffix: **{_money(sr.get('dollars'))}** held inferred-unknown.\n\n")

        out.append("## Finance / GL — asks\n\n")
        if by_team["finance"]:
            for q in by_team["finance"]:
                out.append(f"- {q}\n")
        else:
            out.append("- _(no items routed to finance; review change_summary above)_\n")
        out.append("\n")

        out.append("## Land / Development — asks\n\n")
        if by_team["land"]:
            for q in by_team["land"]:
                out.append(f"- {q}\n")
        else:
            out.append("- _(no items routed to land)_\n")
        out.append("\n")

        out.append("## Ops / ClickUp — asks\n\n")
        if by_team["ops"]:
            for q in by_team["ops"]:
                out.append(f"- {q}\n")
        else:
            out.append(
                "- (Standing item) ClickUp lot tagging is sparse — only ~21% of active lots are tagged. "
                "Decide if better tagging is owned by ops or by the data team.\n"
            )
        out.append("\n")

        out.append("## Decisions needed by end of meeting\n\n")
        out.append(
            "1. Range/shell allocation method (equal split, sales-weighted, or fixed proportional) — finance + land.\n"
        )
        out.append(
            "2. Canonical name for SctLot ('Scattered Lots' or other) — land.\n"
        )
        out.append(
            "3. AultF B-suffix decoder validation — finance / GL.\n"
        )
        out.append(
            "4. HarmCo commercial parcels: kept isolated as commercial entity or rolled into a separate commercial state? — land.\n\n"
        )

        out.append("## Retrieval evidence\n\n")
        out.append(_evidence_block(hits, limit=6))

        return "".join(out) + self._provenance_section()


# ===========================================================================
# 6. draft_owner_update
# ===========================================================================


class DraftOwnerUpdateTool(Tool):
    output_format = "markdown"
    name = "draft_owner_update"
    description = (
        "Draft a concise owner / executive update on BCPD v2.1 state. Honest "
        "about scope (BCPD only — Hillcrest / Flagship Belmont not available), "
        "the real bottleneck (source-owner validation, not engineering), and "
        "the dollar magnitudes of v2.1 corrections. Does NOT claim org-wide "
        "v2 is ready."
    )

    def __init__(self, context: Optional[BcpdContext] = None, **kwargs):
        super().__init__(**kwargs)
        self.context = context or BcpdContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"scope": {"type": "string", "default": "bcpd"}},
        }

    def run(self, data=None, scope: str = "bcpd", **kwargs) -> str:
        if isinstance(data, dict) and "scope" in data:
            scope = data["scope"]

        ctx = self.context
        c = ctx.change_summary()
        dq = ctx.data_quality()
        hits = ctx.retrieve(
            "owner executive update BCPD scope source-owner validation next steps",
            top_k=8,
        )

        aultf = c.get("aultf_b_to_b1_correction") or {}
        harmony = c.get("harmony_3tuple_join_required") or {}
        sct = c.get("sctlot_to_scattered_lots") or {}
        rng = c.get("range_rows_at_project_phase_grain") or {}

        out: List[str] = []
        out.append("# Owner Update — BCPD Operating State (v2.1)\n\n")

        out.append("## Scope (honest)\n\n")
        out.append(
            "- v2.1 covers **BCPD entities only** (BCPD, BCPBL, ASD, BCPI). "
            "Hillcrest and Flagship Belmont GL data ends 2017-02 — those entities are NOT in v2.1.\n"
        )
        out.append(
            "- **Org-wide v2 is NOT ready.** It needs three new GL streams — "
            "Hillcrest, Flagship Belmont, and a back-fill of the 2017-03 → 2018-06 "
            "data gap — before any consolidated view is possible.\n"
        )
        out.append(
            f"- Within scope: {dq.get('lots_total_in_canonical')} canonical lots across "
            "26 projects, joined across inventory + GL + ClickUp.\n\n"
        )

        out.append("## What v2.1 fixed (dollar magnitudes)\n\n")
        out.append(
            f"- **{_money(harmony.get('double_count_prevented'))}** Harmony double-count avoided "
            "by enforcing the (project, phase, lot) 3-tuple join.\n"
        )
        out.append(
            f"- **{_money(sct.get('dollars_moved_off_scarlet_ridge'))}** un-inflated from Scarlet Ridge — "
            "SctLot rows now live under a separate canonical project (Scattered Lots).\n"
        )
        out.append(
            f"- **{_money(aultf.get('dollars'))}** AultF B-suffix rows re-routed to phase B1 "
            "(was B2 in v2.0).\n"
        )
        out.append(
            f"- **{_money(rng.get('dollars'))}** in range/shell GL rows surfaced explicitly at "
            "project+phase grain (no silent lot-level allocation).\n\n"
        )

        out.append("## The real bottleneck (and why eng can't unblock it)\n\n")
        out.append(
            "Per-lot decoder rules ship as **inferred**, not **validated**. Promotion to "
            "validated requires source-owner sign-off — not engineering work. Open items live "
            "in `output/bcpd_data_gap_audit_for_streamline_session.md`.\n\n"
        )

        out.append("## What can be answered today (honestly)\n\n")
        out.append(
            "- Per-lot cost basis at the (project, phase, lot) 3-tuple, with inferred caveat.\n"
        )
        out.append(
            "- Per-phase cost roll-ups, but only **3 of 125 phases currently have "
            "complete enough expected-cost data to support reliable variance / "
            "margin reporting**. The remaining 122 phases have partial or missing budgets.\n"
        )
        out.append(
            "- Range/shell totals at project+phase grain (not lot grain).\n\n"
        )

        out.append("## What CANNOT be answered today (refuse these)\n\n")
        out.append(
            "- Org-wide rollups across Hillcrest / Flagship Belmont.\n"
        )
        out.append(
            "- Lot-level allocation of range/shell rows (no method sign-off).\n"
        )
        out.append(
            "- 'Is the per-lot decoder cost validated?' — NO. It is inferred.\n\n"
        )

        out.append("## Retrieval evidence\n\n")
        out.append(_evidence_block(hits, limit=6))

        return "".join(out) + self._provenance_section()


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_bcpd_workflow_tools(
    registry,
    context: Optional[BcpdContext] = None,
):
    """Register all six BCPD workflow tools on a ToolRegistry.

    Returns the registry for chaining.
    """
    ctx = context or BcpdContext()
    registry.register(GenerateProjectBriefTool(context=ctx))
    registry.register(ReviewMarginReportReadinessTool(context=ctx))
    registry.register(FindFalsePrecisionRisksTool(context=ctx))
    registry.register(SummarizeChangeImpactTool(context=ctx))
    registry.register(PrepareFinanceLandReviewTool(context=ctx))
    registry.register(DraftOwnerUpdateTool(context=ctx))
    return registry


BCPD_WORKFLOW_TOOLS = (
    GenerateProjectBriefTool,
    ReviewMarginReportReadinessTool,
    FindFalsePrecisionRisksTool,
    SummarizeChangeImpactTool,
    PrepareFinanceLandReviewTool,
    DraftOwnerUpdateTool,
)
