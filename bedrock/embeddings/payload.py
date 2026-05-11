"""Render a CanonicalEntity into an EmbeddingPayload — the text + facets that go into the index.

Design intent:
  - Payload text must make *individual* entities discoverable. A query like
    "Harmony B1 lot 101 cost" should hit that specific lot, not just the
    LotState entity-type template. So we lead with an instance label that
    surfaces the entity's identifying values.
  - Aliases and retrieval_tags from the EntitySpec are inlined verbatim so
    semantic-equivalent queries score against the same payload.
  - Structured facets carry every field a metadata filter might want to test
    (project, phase, lot_state, confidence, etc.) — never required to parse
    out of the text at query time.
  - content_hash is sha256(text + sorted_facets) so equivalent entities cache-hit.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from bedrock.contracts import CanonicalEntity, EmbeddingPayload
from bedrock.ontology.runtime.schema import EntitySpec


# Fields that go into structured_facets for every entity (used by metadata filters).
_FACET_FIELDS_BY_TYPE: Dict[str, List[str]] = {
    "lot": [
        "canonical_project",
        "canonical_phase",
        "canonical_lot_number",
        "canonical_lot_id",
        "current_stage",
        "vf_actual_cost_3tuple_usd",
        "vf_actual_cost_confidence",
        "source_confidence",
        "in_2025status",
        "in_inventory",
        "in_clickup_lottagged",
    ],
    "phase": [
        "canonical_project",
        "canonical_phase",
        "lot_count_observed",
        "phase_confidence",
        "vf_unattributed_shell_dollars",
        "in_inventory",
        "in_lot_data",
        "in_2025status",
    ],
    "project": [
        "canonical_project",
        "canonical_entity",
        "phase_count",
        "lot_count",
        "lot_count_active_2025status",
    ],
}


def _format_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        # money-ish field gets dollar formatting
        if abs(v) >= 1000:
            return f"${v:,.0f}"
        return f"{v:.4g}"
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v if x is not None)
    if isinstance(v, dict):
        return json.dumps(v, sort_keys=True, default=str)
    return str(v).strip()


def _instance_label(entity: CanonicalEntity) -> str:
    """Entity-instance line — the part of the payload that distinguishes one row from another."""
    f = entity.fields
    et = entity.entity_type

    if et == "lot":
        proj = f.get("canonical_project") or ""
        phase = f.get("canonical_phase") or ""
        lot = f.get("canonical_lot_number") or ""
        stage = f.get("current_stage") or "UNKNOWN"
        cost = f.get("vf_actual_cost_3tuple_usd")
        cost_part = f" cost={_format_value(cost)}" if cost not in (None, 0, 0.0) else ""
        c_of_o = f.get("actual_c_of_o")
        co_part = f" c_of_o={_format_value(c_of_o)}" if c_of_o else ""
        return f"Lot {proj}::{phase}::{lot} stage={stage}{cost_part}{co_part}"

    if et == "phase":
        proj = f.get("canonical_project") or ""
        phase = f.get("canonical_phase") or ""
        n_lots = f.get("lot_count_observed")
        n_part = f" lots={n_lots}" if n_lots is not None else ""
        shell = f.get("vf_unattributed_shell_dollars")
        shell_part = (
            f" range_row_shell={_format_value(shell)}"
            if shell not in (None, 0, 0.0)
            else ""
        )
        return f"Phase {proj}::{phase}{n_part}{shell_part}"

    if et == "project":
        proj = f.get("canonical_project") or ""
        ent = f.get("canonical_entity") or ""
        n_phases = f.get("phase_count")
        n_lots = f.get("lot_count")
        bits = [f"Project {proj}"]
        if ent:
            bits.append(f"entity={ent}")
        if n_phases is not None:
            bits.append(f"phases={n_phases}")
        if n_lots is not None:
            bits.append(f"lots={n_lots}")
        return " ".join(bits)

    return f"{et} {entity.entity_id}"


def _render_template(spec: EntitySpec, entity: CanonicalEntity) -> str:
    template = spec.embedding_payload.template

    aliases_str = ", ".join(a.alias for a in spec.semantic_aliases)
    tags_str = " ".join(spec.retrieval_tags)

    fields_for_template: Dict[str, str] = {
        "canonical_name": spec.canonical_name,
        "business_description": spec.business_description.strip(),
        "aliases": aliases_str,
        "retrieval_tags": tags_str,
        "entity_type": spec.entity_type,
    }
    for name in spec.embedding_payload.fields_to_include:
        fields_for_template[name] = _format_value(entity.fields.get(name))

    # Substitute {placeholders}; tolerate missing keys instead of KeyError.
    def repl(match: "re.Match[str]") -> str:
        key = match.group(1)
        return fields_for_template.get(key, match.group(0))

    return re.sub(r"\{(\w+)\}", repl, template)


def build_payload(
    entity: CanonicalEntity,
    spec: Optional[EntitySpec],
    payload_version: str = "v1",
) -> EmbeddingPayload:
    """Render a CanonicalEntity into a deterministic EmbeddingPayload."""

    # Instance label — always present, even if no spec available.
    instance = _instance_label(entity)

    # Spec-driven block — adds canonical_name, description, aliases, tags.
    spec_block = _render_template(spec, entity) if spec is not None else ""

    # Confidence + lineage — surface inline so retrieval can cite without a join.
    conf_line = f"Confidence: {entity.confidence}; state_version: {entity.state_version}"
    if entity.lineage.decoder_version:
        conf_line += f"; decoder: {entity.lineage.decoder_version}"

    source_line = ""
    if entity.lineage.source_files:
        source_line = "Sources: " + ", ".join(entity.lineage.source_files)

    text_lines = [instance]
    if spec_block:
        text_lines.append(spec_block.strip())
    text_lines.append(conf_line)
    if source_line:
        text_lines.append(source_line)
    text = "\n".join(text_lines).strip()

    # Structured facets — what filters operate on.
    facets: Dict[str, Any] = {
        "entity_type": entity.entity_type,
        "vertical": entity.vertical,
        "confidence": entity.confidence,
        "state_version": entity.state_version,
        "source_files": list(entity.lineage.source_files),
    }
    if spec is not None:
        facets["retrieval_tags"] = list(spec.retrieval_tags)
        facets["aliases"] = [a.alias for a in spec.semantic_aliases]
    else:
        facets["retrieval_tags"] = []
        facets["aliases"] = []

    for fname in _FACET_FIELDS_BY_TYPE.get(entity.entity_type, []):
        if fname in entity.fields:
            facets[fname] = entity.fields[fname]

    facets_for_hash = json.dumps(facets, sort_keys=True, default=str)
    content_hash = hashlib.sha256((text + "||" + facets_for_hash).encode("utf-8")).hexdigest()[
        :16
    ]

    return EmbeddingPayload(
        payload_id=entity.entity_id,
        payload_version=payload_version,
        source_kind="entity",
        text=text,
        structured_facets=facets,
        content_hash=content_hash,
    )
