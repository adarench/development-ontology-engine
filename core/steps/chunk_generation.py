from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.steps.base import DeterministicToolStep


@dataclass
class Chunk:
    chunk_id: str
    chunk_type: str        # "project_summary" | "cost_source" | "guardrail" | "scope"
    title: str
    project: str           # canonical project name or "all"
    source_files: list[str]
    state_version: str
    confidence: str        # "high" | "medium" | "low" | "inferred" | "estimated"
    allowed_uses: list[str]
    caveats: list[str]
    body: str
    last_generated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChunkGenerationStep(DeterministicToolStep):
    """Generates structured RAG chunks from an operating state dict.

    Input:  state dict (as produced by package_operating_state / OperatingStateTool)
    Output: list of Chunk objects

    Each chunk is self-contained: frontmatter (metadata) + body (markdown).
    Guardrail chunks are always generated regardless of state content.

    Args:
        state_version: schema_version string to embed in each chunk
    """

    GUARDRAIL_CHUNKS = [
        {
            "chunk_id":    "guardrail_missing_cost_not_zero",
            "chunk_type":  "guardrail",
            "title":       "Missing cost is not zero",
            "confidence":  "high",
            "allowed_uses": ["cost interpretation"],
            "caveats":     [],
            "body": (
                "When a project or lot has no GL data, its cost is **unknown**, not $0. "
                "Never report $0 for a project that is absent from the GL. "
                "Say 'no GL coverage' or 'cost unknown' instead."
            ),
        },
        {
            "chunk_id":    "guardrail_phase_ids_estimated",
            "chunk_type":  "guardrail",
            "title":       "Phase IDs are estimated",
            "confidence":  "high",
            "allowed_uses": ["phase interpretation"],
            "caveats":     ["phase_id_estimated derived from lot_number proximity, not a plat reference"],
            "body": (
                "All `phase_id_estimated` values are derived from gap-based lot_number clustering, "
                "not from a real plat reference. They may change if the clustering threshold is retuned. "
                "Always qualify phases as 'estimated' when citing them."
            ),
        },
    ]

    def __init__(self, state_version: str = "operating_state_v1"):
        self.state_version = state_version

    def run(self, data: dict) -> list[Chunk]:
        chunks: list[Chunk] = []

        # Scope chunk.
        projects = data.get("projects", [])
        chunks.append(Chunk(
            chunk_id="scope_overview",
            chunk_type="scope",
            title="Operating state scope",
            project="all",
            source_files=["operating_state_v1.json"],
            state_version=self.state_version,
            confidence="high",
            allowed_uses=["scope queries", "project listing"],
            caveats=[],
            body=self._scope_body(data),
        ))

        # Per-project chunks.
        for proj in projects:
            code = proj.get("project_code", "unknown")
            chunks.append(Chunk(
                chunk_id=f"project_{code.lower().replace(' ', '_')}",
                chunk_type="project_summary",
                title=f"Project: {code}",
                project=code,
                source_files=["operating_state_v1.json"],
                state_version=self.state_version,
                confidence="medium",
                allowed_uses=["project status queries", "lot counts", "stage distribution"],
                caveats=["phase_id_estimated is heuristic"],
                body=self._project_body(proj),
            ))

        # Fixed guardrail chunks.
        for g in self.GUARDRAIL_CHUNKS:
            chunks.append(Chunk(
                chunk_id=g["chunk_id"],
                chunk_type=g["chunk_type"],
                title=g["title"],
                project="all",
                source_files=[],
                state_version=self.state_version,
                confidence=g["confidence"],
                allowed_uses=g["allowed_uses"],
                caveats=g["caveats"],
                body=g["body"],
            ))

        return chunks

    def _scope_body(self, state: dict) -> str:
        projects = state.get("projects", [])
        dq = state.get("data_quality", {})
        lines = [
            f"**Schema version**: {state.get('schema_version', self.state_version)}",
            f"**Generated**: {state.get('generated_at', 'unknown')}",
            f"**Projects in scope**: {', '.join(p.get('project_code', '?') for p in projects)}",
            f"**Total lots**: {dq.get('lots_total', '?')}",
        ]
        return "\n".join(lines)

    def _project_body(self, proj: dict) -> str:
        code = proj.get("project_code", "?")
        fin  = proj.get("financials", {})
        lines = [
            f"**{code}** — {proj.get('lots_total', '?')} lots, "
            f"avg completion {proj.get('avg_completion_pct', 0) * 100:.1f}%",
            f"Stage distribution: `{proj.get('stage_distribution', 'n/a')}`",
            f"Cost: {fin.get('project_total_cost', 'unknown')} "
            f"(confidence: {fin.get('financial_confidence', 'unknown')})",
        ]
        return "\n".join(lines)
