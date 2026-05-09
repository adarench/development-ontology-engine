"""Load ontology YAML specs into typed Pydantic objects.

CLI:
    python -m bedrock.ontology.runtime.loader --validate ontology/
    python -m bedrock.ontology.runtime.loader --root ontology/ --dump
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import ValidationError

from bedrock.ontology.runtime.schema import (
    EntitySpec,
    MetricSpec,
    RelationshipSpec,
)


@dataclass
class OntologyRegistry:
    """In-memory registry of all entity, relationship, and metric specs."""

    entities: Dict[str, EntitySpec] = field(default_factory=dict)
    relationships: Dict[str, RelationshipSpec] = field(default_factory=dict)
    metrics: Dict[str, MetricSpec] = field(default_factory=dict)
    root: Optional[Path] = None

    @classmethod
    def load(cls, root: Path) -> "OntologyRegistry":
        root = Path(root)
        reg = cls(root=root)
        entities_dir = root / "entities"
        relationships_dir = root / "relationships"
        metrics_dir = root / "metrics"

        if entities_dir.exists():
            for path in sorted(entities_dir.glob("*.yaml")):
                spec = _load_yaml_as(EntitySpec, path)
                if spec.entity_type in reg.entities:
                    raise ValueError(
                        f"Duplicate entity_type {spec.entity_type!r} in {path}"
                    )
                reg.entities[spec.entity_type] = spec

        if relationships_dir.exists():
            for path in sorted(relationships_dir.glob("*.yaml")):
                spec = _load_yaml_as(RelationshipSpec, path)
                if spec.name in reg.relationships:
                    raise ValueError(
                        f"Duplicate relationship name {spec.name!r} in {path}"
                    )
                reg.relationships[spec.name] = spec

        if metrics_dir.exists():
            for path in sorted(metrics_dir.glob("*.yaml")):
                spec = _load_yaml_as(MetricSpec, path)
                if spec.name in reg.metrics:
                    raise ValueError(f"Duplicate metric name {spec.name!r} in {path}")
                reg.metrics[spec.name] = spec

        reg._validate_cross_references()
        return reg

    def _validate_cross_references(self) -> None:
        """Catch dangling references between entities, relationships, and metrics."""
        entity_types = set(self.entities)
        for rel in self.relationships.values():
            for side, et in [("source", rel.source_entity), ("target", rel.target_entity)]:
                if et not in entity_types:
                    raise ValueError(
                        f"Relationship {rel.name!r} {side}_entity {et!r} is not a known entity_type"
                    )
        for ent in self.entities.values():
            for r in ent.relationships:
                if r.target_entity not in entity_types:
                    raise ValueError(
                        f"Entity {ent.entity_type!r} relationship {r.name!r} -> "
                        f"unknown target_entity {r.target_entity!r}"
                    )
            for jp in ent.approved_join_paths:
                if jp.target_entity not in entity_types:
                    raise ValueError(
                        f"Entity {ent.entity_type!r} join_path {jp.name!r} -> "
                        f"unknown target_entity {jp.target_entity!r}"
                    )

    def to_jsonable(self) -> dict:
        return {
            "entities": {k: v.model_dump(mode="json") for k, v in self.entities.items()},
            "relationships": {
                k: v.model_dump(mode="json") for k, v in self.relationships.items()
            },
            "metrics": {k: v.model_dump(mode="json") for k, v in self.metrics.items()},
        }

    def summary(self) -> List[str]:
        lines = [
            f"OntologyRegistry(root={self.root})",
            f"  entities: {len(self.entities)}",
        ]
        for k, v in sorted(self.entities.items()):
            lines.append(
                f"    - {k}: {len(v.field_definitions)} fields, "
                f"{len(v.semantic_aliases)} aliases, "
                f"{len(v.relationships)} relationships, "
                f"{len(v.semantic_warnings)} warnings"
            )
        lines.append(f"  relationships: {len(self.relationships)}")
        for k in sorted(self.relationships):
            lines.append(f"    - {k}")
        lines.append(f"  metrics: {len(self.metrics)}")
        for k in sorted(self.metrics):
            lines.append(f"    - {k}")
        return lines


def _load_yaml_as(model, path: Path):
    with path.open() as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raise ValueError(f"{path} is empty")
    try:
        return model.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"{path} failed schema validation: {e}") from e


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate / dump the ontology registry.")
    parser.add_argument(
        "--root", type=Path, default=Path("ontology"), help="Ontology root directory"
    )
    parser.add_argument(
        "--validate",
        nargs="?",
        const=True,
        default=False,
        help="Validate only; print summary and exit 0/1.",
    )
    parser.add_argument(
        "--dump", action="store_true", help="Print full registry as JSON to stdout."
    )
    args = parser.parse_args(argv)

    root = Path(args.validate) if args.validate not in (False, True) else args.root

    try:
        reg = OntologyRegistry.load(root)
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    for line in reg.summary():
        print(line)

    if args.dump:
        print(json.dumps(reg.to_jsonable(), indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
