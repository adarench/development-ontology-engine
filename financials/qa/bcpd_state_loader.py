"""Read-only loader for the BCPD v2.1 operating state and companion context."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json

REPO = Path(__file__).resolve().parent.parent.parent

# Required v2.1 state file
STATE_JSON = REPO / "output/operating_state_v2_1_bcpd.json"

# Companion text context (read as raw markdown / csv)
AGENT_CONTEXT = REPO / "output/agent_context_v2_1_bcpd.md"
QUALITY_REPORT = REPO / "output/state_quality_report_v2_1_bcpd.md"
QUERY_EXAMPLES = REPO / "output/state_query_examples_v2_1_bcpd.md"
CHANGE_LOG = REPO / "data/reports/v2_0_to_v2_1_change_log.md"
JOIN_COVERAGE = REPO / "data/reports/join_coverage_v0.md"
COVERAGE_OPS = REPO / "data/reports/coverage_improvement_opportunities.md"
DECODER_REPORT = REPO / "data/reports/vf_lot_code_decoder_v1_report.md"
ONTOLOGY = REPO / "docs/ontology_v0.md"
FIELD_MAP = REPO / "docs/field_map_v0.csv"
SOURCE_MAP = REPO / "docs/source_to_field_map.md"

# v2.0 state — referenced ONLY to detect accidental loading; never read by default.
V20_STATE_JSON = REPO / "output/operating_state_v2_bcpd.json"

EXPECTED_SCHEMA = "operating_state_v2_1_bcpd"


@dataclass(frozen=True)
class BCPDState:
    """Bundle of v2.1 state + companion context, all read-only."""
    state: dict
    agent_context: str
    quality_report: str
    query_examples: str
    change_log: str
    join_coverage: str
    coverage_ops: str
    decoder_report: str
    ontology: str
    field_map: str
    source_map: str

    @property
    def schema_version(self) -> str:
        return self.state["schema_version"]

    @property
    def projects(self) -> list[dict]:
        return self.state["projects"]

    @property
    def caveats(self) -> list[str]:
        return self.state.get("caveats", [])

    @property
    def open_questions(self) -> list[str]:
        return self.state.get("source_owner_questions_open", [])

    @property
    def data_quality(self) -> dict:
        return self.state.get("data_quality", {})

    @property
    def metadata(self) -> dict:
        return self.state.get("metadata", {})

    @property
    def v2_1_changes(self) -> dict:
        return self.state.get("v2_1_changes_summary", {})

    def all_text_blob(self) -> str:
        """Concatenated companion-text blob (markdown only) for keyword retrieval."""
        return "\n\n".join([
            self.agent_context, self.quality_report, self.query_examples,
            self.change_log, self.join_coverage, self.coverage_ops,
            self.decoder_report, self.ontology, self.source_map,
        ])

    def find_project(self, name: str) -> dict | None:
        """Case-sensitive lookup of a canonical project by name."""
        for p in self.projects:
            if p.get("canonical_project") == name:
                return p
        return None


class StateLoadError(Exception):
    pass


def _read_text(p: Path) -> str:
    if not p.exists():
        raise StateLoadError(f"required companion file missing: {p}")
    return p.read_text()


def load_state() -> BCPDState:
    """Load v2.1 state + companion context. Fails loudly if v2.0 is loaded by mistake."""
    if not STATE_JSON.exists():
        raise StateLoadError(
            f"BCPD v2.1 state not found at {STATE_JSON}. "
            f"Run financials/build_operating_state_v2_1_bcpd.py to generate it."
        )

    raw = STATE_JSON.read_text()
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as e:
        raise StateLoadError(f"v2.1 state JSON failed to parse: {e}") from e

    schema = state.get("schema_version", "")
    if schema != EXPECTED_SCHEMA:
        # Hard fail if the v2.0 file (or any other version) was placed at v2.1's path.
        if schema == "operating_state_v2_bcpd":
            raise StateLoadError(
                f"v2.0 state was loaded ({schema}) but v2.1 is required. "
                f"The harness defaults to v2.1 — do not point it at v2.0."
            )
        raise StateLoadError(
            f"unexpected schema_version '{schema}'; expected '{EXPECTED_SCHEMA}'."
        )

    return BCPDState(
        state=state,
        agent_context=_read_text(AGENT_CONTEXT),
        quality_report=_read_text(QUALITY_REPORT),
        query_examples=_read_text(QUERY_EXAMPLES),
        change_log=_read_text(CHANGE_LOG),
        join_coverage=_read_text(JOIN_COVERAGE),
        coverage_ops=_read_text(COVERAGE_OPS),
        decoder_report=_read_text(DECODER_REPORT),
        ontology=_read_text(ONTOLOGY),
        field_map=_read_text(FIELD_MAP),
        source_map=_read_text(SOURCE_MAP),
    )


# All read-only file paths the harness depends on. Used by the test fixture
# to verify they are not touched.
PROTECTED_PATHS = (
    STATE_JSON, AGENT_CONTEXT, QUALITY_REPORT, QUERY_EXAMPLES,
    CHANGE_LOG, JOIN_COVERAGE, COVERAGE_OPS, DECODER_REPORT,
    ONTOLOGY, FIELD_MAP, SOURCE_MAP,
)
