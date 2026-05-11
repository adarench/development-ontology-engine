"""Pydantic v2 models for the ontology runtime IR.

YAML specs under ontology/{entities,relationships,metrics}/ load into these
models. Markdown views under ontology/generated/ are produced from them.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


FieldType = Literal[
    "string",
    "integer",
    "decimal",
    "boolean",
    "date",
    "datetime",
    "enum",
    "list",
    "map",
]


class SemanticAlias(BaseModel):
    """A user-facing synonym or business term that resolves to a canonical name."""

    alias: str
    resolves_to: str
    note: Optional[str] = None


class FieldDefinition(BaseModel):
    name: str
    type: FieldType
    nullable: bool = False
    description: str
    source_columns: List[str] = Field(default_factory=list)
    enum_values: Optional[List[str]] = None
    derived: bool = False
    derivation_note: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)


class Relationship(BaseModel):
    """Inline relationship summary on an entity. Full edges live in ontology/relationships/."""

    name: str
    target_entity: str
    cardinality: Literal["one", "many"]
    description: str
    via_field: Optional[str] = None


class JoinPath(BaseModel):
    """An approved join the retrieval layer can rely on."""

    name: str
    target_entity: str
    join_keys: List[str]
    cardinality: Literal["one", "many"]
    note: Optional[str] = None


class ConfidenceRule(BaseModel):
    field: str
    confidence: Literal[
        "validated", "inferred", "static", "high", "medium", "low", "unknown"
    ]
    reason: str


class ValidationRule(BaseModel):
    name: str
    rule: str
    severity: Literal["error", "warning", "info"] = "warning"


class SemanticWarning(BaseModel):
    """A warning the retrieval layer must surface when this entity or field is referenced."""

    name: str
    applies_to: str
    message: str


class EmbeddingPayloadSpec(BaseModel):
    """How to render this entity into the text chunk that will be embedded."""

    template: str
    fields_to_include: List[str] = Field(default_factory=list)
    aliases_in_text: bool = True
    retrieval_tags_in_text: bool = True


class EntitySpec(BaseModel):
    """The 14-field runtime ontology object from the master prompt."""

    entity_type: str
    canonical_name: str
    business_description: str
    field_definitions: List[FieldDefinition]
    semantic_aliases: List[SemanticAlias] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    approved_join_paths: List[JoinPath] = Field(default_factory=list)
    source_lineage: List[str] = Field(default_factory=list)
    retrieval_tags: List[str] = Field(default_factory=list)
    example_queries: List[str] = Field(default_factory=list)
    embedding_payload: EmbeddingPayloadSpec
    confidence_rules: List[ConfidenceRule] = Field(default_factory=list)
    validation_rules: List[ValidationRule] = Field(default_factory=list)
    historical_behavior: Optional[str] = None
    semantic_warnings: List[SemanticWarning] = Field(default_factory=list)
    vertical: str = "construction"
    schema_version: str = "v1"

    @model_validator(mode="after")
    def _check_field_names_unique(self) -> "EntitySpec":
        names = [f.name for f in self.field_definitions]
        if len(names) != len(set(names)):
            dupes = [n for n in names if names.count(n) > 1]
            raise ValueError(
                f"Duplicate field names in {self.entity_type}: {sorted(set(dupes))}"
            )
        return self


class RelationshipSpec(BaseModel):
    """A typed edge between two entity types — lives in ontology/relationships/."""

    name: str
    source_entity: str
    target_entity: str
    cardinality: Literal["one_to_one", "one_to_many", "many_to_many"]
    join_keys: List[str]
    description: str
    confidence: Literal["validated", "inferred", "static"] = "static"
    semantic_warnings: List[SemanticWarning] = Field(default_factory=list)


class MetricSpec(BaseModel):
    """A canonical metric definition — lives in ontology/metrics/."""

    name: str
    description: str
    unit: str
    formula: str
    inputs: List[str]
    confidence: Literal["validated", "inferred", "static"] = "static"
    source_definition: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    notes: Dict[str, Any] = Field(default_factory=dict)
