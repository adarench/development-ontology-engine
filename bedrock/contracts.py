"""Stable seam between Adam-owned semantic modules and Jakob-owned infra modules.

Any change here requires both reviewers (gated by CODEOWNERS).
Adam never imports from bedrock.vector_store or bedrock.embeddings.{voyage,local,cache,provider}.
Jakob never imports from bedrock.ontology, bedrock.registry, or bedrock.retrieval.services.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


ConfidenceLabel = Literal[
    "validated", "inferred", "static", "high", "medium", "low", "unknown"
]
SourceKind = Literal["chunk", "entity", "metric", "canonical"]
RetrievalMode = Literal["lexical", "vector", "hybrid"]


class Lineage(BaseModel):
    """Provenance for a fact or entity. Source files + content hashes + derivation note."""

    source_files: List[str] = Field(default_factory=list)
    content_hashes: Dict[str, str] = Field(default_factory=dict)
    derivation: Optional[str] = None
    decoder_version: Optional[str] = None
    state_version: Optional[str] = None


class Edge(BaseModel):
    """Typed directional relationship between entities."""

    relationship_type: str
    target_entity_id: str
    target_entity_type: str
    cardinality: Literal["one", "many"] = "many"


class CanonicalEntity(BaseModel):
    """Authoritative representation of a domain object after canonicalization.

    The Layer 1 (Canonical State Registry) emits these. Everything above
    consumes them through this single shape.
    """

    entity_id: str
    entity_type: str
    vertical: str = "construction"
    fields: Dict[str, Any] = Field(default_factory=dict)
    relationships: List[Edge] = Field(default_factory=list)
    lineage: Lineage = Field(default_factory=Lineage)
    confidence: ConfidenceLabel = "static"
    state_version: str
    schema_version: str = "v1"


class EmbeddingPayload(BaseModel):
    """Adam-authored: what gets embedded for a given source object."""

    payload_id: str
    payload_version: str
    source_kind: SourceKind
    text: str
    structured_facets: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str


class VectorRow(BaseModel):
    """Jakob-stored: one row of the vector index. Schema is portable across stores."""

    id: str
    entity_id: Optional[str] = None
    entity_type: str
    vertical: str = "construction"
    confidence: str
    state_version: str
    retrieval_tags: List[str] = Field(default_factory=list)
    source_files: List[str] = Field(default_factory=list)
    text_to_embed: str
    vector: List[float]
    content_hash: str
    created_at: datetime


class MetadataFilter(BaseModel):
    """Typed filter for vector queries — never raw SQL."""

    entity_types: Optional[List[str]] = None
    verticals: Optional[List[str]] = None
    confidences: Optional[List[str]] = None
    state_versions: Optional[List[str]] = None
    retrieval_tags_any: Optional[List[str]] = None
    retrieval_tags_all: Optional[List[str]] = None


class VectorHit(BaseModel):
    row: VectorRow
    score: float
    matched_filters: List[str] = Field(default_factory=list)


class RetrievalHit(BaseModel):
    """Unified hit shape across routed/lexical/vector sources."""

    source: str
    entity_id: Optional[str] = None
    chunk_id: Optional[str] = None
    title: Optional[str] = None
    text: str
    score: float
    score_components: Dict[str, float] = Field(default_factory=dict)
    matched_aliases: List[str] = Field(default_factory=list)
    source_files: List[str] = Field(default_factory=list)
    confidence: str = "unknown"


class LineageRef(BaseModel):
    source_file: str
    content_hash: Optional[str] = None
    cited_by_facts: List[str] = Field(default_factory=list)


class ContextSection(BaseModel):
    section_kind: Literal["guardrail", "routed", "evidence"]
    title: str
    text: str
    hit: Optional[RetrievalHit] = None
    token_count: int


class ContextPack(BaseModel):
    """Operational context pack handed to an LLM. Deterministic, lineage-stamped."""

    pack_id: str
    query: str
    sections: List[ContextSection] = Field(default_factory=list)
    lineage: List[LineageRef] = Field(default_factory=list)
    semantic_warnings: List[str] = Field(default_factory=list)
    confidence_summary: Dict[str, int] = Field(default_factory=dict)
    token_count: int = 0
    truncated: bool = False


# ---------------------------------------------------------------------------
# Protocols that infra implements and semantics consumes.
# ---------------------------------------------------------------------------


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Pluggable embedding model. Implementations live under bedrock/embeddings/."""

    model_id: str
    dim: int

    def embed(self, texts: List[str]) -> List[List[float]]: ...


@runtime_checkable
class VectorStore(Protocol):
    """Pluggable vector store. Implementations live under bedrock/vector_store/."""

    def upsert(self, rows: List[VectorRow]) -> None: ...

    def query(
        self,
        embedding: List[float],
        filters: Optional[MetadataFilter],
        k: int,
    ) -> List[VectorHit]: ...

    def delete(self, ids: List[str]) -> None: ...

    def count(self) -> int: ...
