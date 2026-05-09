"""Phase 1 acceptance tests: ontology runtime, markdown round-trip, StateRegistry counts.

Run from the repo root:
    python3 -m pytest tests/test_ontology_runtime.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from bedrock.contracts import CanonicalEntity, EmbeddingProvider, VectorStore
from bedrock.ontology.runtime import (
    EntitySpec,
    MetricSpec,
    OntologyRegistry,
)
from bedrock.ontology.runtime.render_markdown import (
    check_drift,
    render_all,
)
from bedrock.ontology.runtime.schema import (
    EmbeddingPayloadSpec,
    FieldDefinition,
    RelationshipSpec,
)
from bedrock.registry import StateRegistry
from bedrock.registry.state import DEFAULT_STATE_PATH


# ---------------------------------------------------------------------------
# Ontology runtime — YAML loads, schema validates, semantics are intact.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def registry() -> OntologyRegistry:
    return OntologyRegistry.load(REPO / "ontology")


def test_registry_loads_three_entities(registry: OntologyRegistry) -> None:
    assert set(registry.entities) == {"lot", "phase", "project"}


def test_registry_loads_two_relationships(registry: OntologyRegistry) -> None:
    assert set(registry.relationships) == {
        "lot_belongs_to_phase",
        "phase_belongs_to_project",
    }


def test_registry_loads_three_metrics(registry: OntologyRegistry) -> None:
    assert set(registry.metrics) == {
        "cost_to_date",
        "lot_state_waterfall",
        "variance_total",
    }


def test_lot_entity_has_required_shape(registry: OntologyRegistry) -> None:
    lot = registry.entities["lot"]
    assert lot.canonical_name == "LotState"
    assert lot.vertical == "construction"
    # field_definitions exists and is non-trivial
    assert len(lot.field_definitions) >= 30
    # the canonical id must be present
    field_names = {f.name for f in lot.field_definitions}
    assert "canonical_lot_id" in field_names
    assert "lot_state" in field_names
    assert "cost_to_date" in field_names
    # semantic warnings include the inferred-cost surface
    warning_names = {w.name for w in lot.semantic_warnings}
    assert "cost_is_inferred" in warning_names
    assert "missing_is_not_zero" in warning_names


def test_phase_entity_has_required_shape(registry: OntologyRegistry) -> None:
    phase = registry.entities["phase"]
    field_names = {f.name for f in phase.field_definitions}
    assert "variance_total" in field_names
    assert "phase_state" in field_names
    assert "is_queryable" in field_names


def test_project_entity_has_required_shape(registry: OntologyRegistry) -> None:
    project = registry.entities["project"]
    field_names = {f.name for f in project.field_definitions}
    assert "canonical_project" in field_names
    assert "canonical_entity" in field_names
    # validation rules enforce the BCPD-only scope
    rule_names = {r.name for r in project.validation_rules}
    assert "bcpd_only_scope" in rule_names
    assert "sctlot_not_scarlet" in rule_names


def test_relationship_cross_references_resolve(registry: OntologyRegistry) -> None:
    # The cross-reference validator already ran in OntologyRegistry.load.
    # Sanity-check the lot-phase relationship semantics here.
    rel = registry.relationships["lot_belongs_to_phase"]
    assert rel.source_entity == "lot"
    assert rel.target_entity == "phase"
    assert "canonical_project" in rel.join_keys


def test_duplicate_field_validator_fires() -> None:
    with pytest.raises(ValueError, match="Duplicate field names"):
        EntitySpec(
            entity_type="x",
            canonical_name="X",
            business_description="y",
            field_definitions=[
                FieldDefinition(name="a", type="string", description="d"),
                FieldDefinition(name="a", type="integer", description="d"),
            ],
            embedding_payload=EmbeddingPayloadSpec(template="t"),
        )


# ---------------------------------------------------------------------------
# Markdown renderer — generated MD must round-trip cleanly.
# ---------------------------------------------------------------------------


def test_generated_markdown_matches_yaml(registry: OntologyRegistry) -> None:
    """If this fails, run `python -m bedrock.ontology.runtime.render_markdown` and commit."""
    diffs = check_drift(registry, REPO / "ontology" / "generated")
    assert diffs == [], (
        "Generated markdown drifted from YAML. "
        "Run `python3 -m bedrock.ontology.runtime.render_markdown` and commit."
        "\n\n" + "\n".join(diffs)
    )


def test_render_all_produces_eight_files(registry: OntologyRegistry, tmp_path) -> None:
    written = render_all(registry, tmp_path)
    # 3 entities + 2 relationships + 3 metrics = 8
    assert len(written) == 8
    assert (tmp_path / "entities" / "lot.md").exists()
    assert (tmp_path / "relationships" / "lot_belongs_to_phase.md").exists()
    assert (tmp_path / "metrics" / "cost_to_date.md").exists()


# ---------------------------------------------------------------------------
# StateRegistry — v2.1 JSON loads into typed entities at the expected counts.
# ---------------------------------------------------------------------------

EXPECTED_LOT_COUNT = 5366
EXPECTED_PHASE_COUNT = 184
EXPECTED_PROJECT_COUNT = 26


@pytest.fixture(scope="module")
def state_registry() -> StateRegistry:
    if not DEFAULT_STATE_PATH.exists():
        pytest.skip(f"v2.1 state file missing: {DEFAULT_STATE_PATH}")
    return StateRegistry.from_v2_1_json(DEFAULT_STATE_PATH)


def test_state_registry_counts(state_registry: StateRegistry) -> None:
    counts = state_registry.counts()
    assert counts["lot"] == EXPECTED_LOT_COUNT
    assert counts["phase"] == EXPECTED_PHASE_COUNT
    assert counts["project"] == EXPECTED_PROJECT_COUNT


def test_state_registry_state_version(state_registry: StateRegistry) -> None:
    assert state_registry.state_version == "v2.1"


def test_every_entity_carries_lineage(state_registry: StateRegistry) -> None:
    sample = list(state_registry.entities.values())[:50]
    for e in sample:
        assert e.lineage.source_files, f"{e.entity_id} missing source_files"
        assert e.lineage.state_version == "v2.1"
        assert e.lineage.decoder_version  # carries decoder version


def test_lot_entity_has_known_fields(state_registry: StateRegistry) -> None:
    a_lot = next(state_registry.iter_entities("lot"))
    # The fields dict must mirror what v2.1 JSON puts on each lot row
    for required in (
        "canonical_lot_id",
        "canonical_lot_number",
        "current_stage",
        "vf_actual_cost_3tuple_usd",
        "vf_actual_cost_confidence",
        "source_confidence",
    ):
        assert required in a_lot.fields, f"missing {required} in lot.fields"


def test_lot_relationships_link_to_phase_and_project(state_registry: StateRegistry) -> None:
    a_lot = next(state_registry.iter_entities("lot"))
    rel_types = {r.relationship_type for r in a_lot.relationships}
    assert "belongs_to_phase" in rel_types
    assert "belongs_to_project" in rel_types


def test_no_nan_leaks_into_fields(state_registry: StateRegistry) -> None:
    """v2.1 JSON contains 2,374 NaN tokens. _clean must replace them with None."""
    import math

    for e in list(state_registry.entities.values())[:500]:
        for k, v in e.fields.items():
            if isinstance(v, float):
                assert not math.isnan(v), f"NaN leaked at {e.entity_id}.{k}"


# ---------------------------------------------------------------------------
# Contracts — Protocols are runtime-checkable, types are importable.
# ---------------------------------------------------------------------------


def test_canonical_entity_round_trip() -> None:
    e = CanonicalEntity(
        entity_id="lot:test::p::1",
        entity_type="lot",
        state_version="v2.1",
        confidence="high",
    )
    dumped = e.model_dump(mode="json")
    rebuilt = CanonicalEntity.model_validate(dumped)
    assert rebuilt == e


def test_protocol_imports() -> None:
    # If these import without errors, the protocols are well-formed.
    assert EmbeddingProvider is not None
    assert VectorStore is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
