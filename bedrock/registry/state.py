"""StateRegistry — loads canonical operating state into typed CanonicalEntity instances.

Phase 1 only ingests output/operating_state_v2_1_bcpd.json. Future phases will add
incremental refresh, lineage hashing, and external source loaders.

CLI:
    python -m bedrock.registry.state --count
    python -m bedrock.registry.state --entity-type lot --limit 5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from bedrock.contracts import CanonicalEntity, Edge, Lineage


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = REPO_ROOT / "output" / "operating_state_v2_1_bcpd.json"


def _clean(value: Any) -> Any:
    """Replace NaN/Inf with None recursively. v2.1 JSON includes 2,374 NaN tokens."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _entity_id(entity_type: str, *parts: str) -> str:
    safe_parts = [p for p in parts if p is not None and p != ""]
    return entity_type + ":" + "::".join(str(p) for p in safe_parts)


def _project_to_entity(proj: dict, lineage: Lineage) -> CanonicalEntity:
    cleaned = _clean(proj)
    fields = {
        k: v
        for k, v in cleaned.items()
        if k not in ("phases",)  # don't denormalize the children
    }
    confidence = "high"
    rels: List[Edge] = []
    for phase in proj.get("phases") or []:
        phase_name = phase.get("canonical_phase")
        if phase_name is None:
            continue
        rels.append(
            Edge(
                relationship_type="contains_phase",
                target_entity_id=_entity_id(
                    "phase", proj.get("canonical_project"), phase_name
                ),
                target_entity_type="phase",
                cardinality="many",
            )
        )
    return CanonicalEntity(
        entity_id=_entity_id("project", proj.get("canonical_project")),
        entity_type="project",
        fields=fields,
        relationships=rels,
        lineage=lineage,
        confidence=confidence,
        state_version=lineage.state_version or "v2.1",
    )


def _phase_to_entity(phase: dict, project_name: str, lineage: Lineage) -> CanonicalEntity:
    cleaned = _clean(phase)
    fields = {k: v for k, v in cleaned.items() if k != "lots"}
    fields["canonical_project"] = project_name
    confidence_raw = (phase.get("phase_confidence") or "").lower()
    if "high" in confidence_raw:
        confidence = "high"
    elif "medium" in confidence_raw:
        confidence = "medium"
    elif "low" in confidence_raw:
        confidence = "low"
    elif "inferred" in confidence_raw:
        confidence = "inferred"
    else:
        confidence = "unknown"
    rels: List[Edge] = [
        Edge(
            relationship_type="belongs_to_project",
            target_entity_id=_entity_id("project", project_name),
            target_entity_type="project",
            cardinality="one",
        )
    ]
    for lot in phase.get("lots") or []:
        lot_num = lot.get("canonical_lot_number")
        if lot_num is None:
            continue
        rels.append(
            Edge(
                relationship_type="contains_lot",
                target_entity_id=_entity_id(
                    "lot", project_name, phase.get("canonical_phase"), lot_num
                ),
                target_entity_type="lot",
                cardinality="many",
            )
        )
    return CanonicalEntity(
        entity_id=_entity_id("phase", project_name, phase.get("canonical_phase")),
        entity_type="phase",
        fields=fields,
        relationships=rels,
        lineage=lineage,
        confidence=confidence,
        state_version=lineage.state_version or "v2.1",
    )


def _lot_to_entity(
    lot: dict, project_name: str, phase_name: str, lineage: Lineage
) -> CanonicalEntity:
    cleaned = _clean(lot)
    fields = dict(cleaned)
    fields["canonical_project"] = project_name
    fields["canonical_phase"] = phase_name

    src_conf = (lot.get("source_confidence") or "").lower()
    if src_conf in ("high", "medium", "low", "unknown"):
        confidence = src_conf  # type: ignore[assignment]
    else:
        confidence = "unknown"

    rels: List[Edge] = [
        Edge(
            relationship_type="belongs_to_phase",
            target_entity_id=_entity_id("phase", project_name, phase_name),
            target_entity_type="phase",
            cardinality="one",
        ),
        Edge(
            relationship_type="belongs_to_project",
            target_entity_id=_entity_id("project", project_name),
            target_entity_type="project",
            cardinality="one",
        ),
    ]
    return CanonicalEntity(
        entity_id=_entity_id(
            "lot", project_name, phase_name, lot.get("canonical_lot_number")
        ),
        entity_type="lot",
        fields=fields,
        relationships=rels,
        lineage=lineage,
        confidence=confidence,  # type: ignore[arg-type]
        state_version=lineage.state_version or "v2.1",
    )


@dataclass
class StateRegistry:
    """In-memory registry of CanonicalEntity instances loaded from a state file."""

    entities: Dict[str, CanonicalEntity] = field(default_factory=dict)
    state_version: str = "v2.1"
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_path: Optional[Path] = None

    @classmethod
    def from_v2_1_json(cls, path: Path = DEFAULT_STATE_PATH) -> "StateRegistry":
        path = Path(path)
        with path.open() as f:
            raw = json.load(f)

        state_version = raw.get("schema_version", "operating_state_v2_1_bcpd")
        # Normalize "operating_state_v2_1_bcpd" -> "v2.1" for the registry version label.
        version_label = "v2.1" if "v2_1" in state_version else state_version

        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        lineage = Lineage(
            source_files=[str(path.relative_to(REPO_ROOT))],
            content_hashes={str(path.relative_to(REPO_ROOT)): content_hash},
            decoder_version=raw.get("metadata", {}).get("decoder_version"),
            state_version=version_label,
            derivation="loaded from output/operating_state_v2_1_bcpd.json",
        )

        reg = cls(
            state_version=version_label,
            metadata=raw.get("metadata", {}),
            source_path=path,
        )

        for proj in raw.get("projects", []):
            project_name = proj.get("canonical_project")
            if not project_name:
                continue
            proj_entity = _project_to_entity(proj, lineage)
            reg.entities[proj_entity.entity_id] = proj_entity

            for phase in proj.get("phases") or []:
                phase_name = phase.get("canonical_phase")
                if not phase_name:
                    continue
                phase_entity = _phase_to_entity(phase, project_name, lineage)
                reg.entities[phase_entity.entity_id] = phase_entity

                for lot in phase.get("lots") or []:
                    lot_num = lot.get("canonical_lot_number")
                    if lot_num is None:
                        continue
                    lot_entity = _lot_to_entity(lot, project_name, phase_name, lineage)
                    # If the same canonical id reappears, last-write-wins (rare).
                    reg.entities[lot_entity.entity_id] = lot_entity

        return reg

    # ------------------------------------------------------------------
    # query helpers
    # ------------------------------------------------------------------

    def by_type(self, entity_type: str) -> List[CanonicalEntity]:
        return [e for e in self.entities.values() if e.entity_type == entity_type]

    def get(self, entity_id: str) -> Optional[CanonicalEntity]:
        return self.entities.get(entity_id)

    def iter_entities(
        self, entity_type: Optional[str] = None
    ) -> Iterator[CanonicalEntity]:
        for e in self.entities.values():
            if entity_type is None or e.entity_type == entity_type:
                yield e

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for e in self.entities.values():
            out[e.entity_type] = out.get(e.entity_type, 0) + 1
        return out

    def confidence_distribution(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for e in self.entities.values():
            bucket = out.setdefault(e.entity_type, {})
            bucket[e.confidence] = bucket.get(e.confidence, 0) + 1
        return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the v2.1 StateRegistry.")
    parser.add_argument(
        "--state-path",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Path to operating_state_v2_1_bcpd.json",
    )
    parser.add_argument(
        "--count", action="store_true", help="Print entity counts and exit."
    )
    parser.add_argument(
        "--entity-type",
        type=str,
        default=None,
        help="Filter listing to one entity_type (project|phase|lot).",
    )
    parser.add_argument(
        "--limit", type=int, default=5, help="Max entities to show when listing."
    )
    parser.add_argument(
        "--confidence",
        action="store_true",
        help="Print confidence distribution per entity_type.",
    )
    args = parser.parse_args(argv)

    if not args.state_path.exists():
        print(f"ERROR: state file not found at {args.state_path}", file=sys.stderr)
        return 1

    reg = StateRegistry.from_v2_1_json(args.state_path)

    counts = reg.counts()
    print(f"StateRegistry(state_version={reg.state_version})")
    print(f"  source: {reg.source_path}")
    print(f"  decoder_version: {reg.metadata.get('decoder_version')}")
    print(f"  total entities: {len(reg.entities)}")
    for k in sorted(counts):
        print(f"    {k}: {counts[k]}")

    if args.confidence:
        print("\nConfidence distribution:")
        for et, dist in sorted(reg.confidence_distribution().items()):
            print(f"  {et}: {dict(sorted(dist.items()))}")

    if args.count:
        return 0

    if args.entity_type:
        items = list(reg.iter_entities(args.entity_type))[: args.limit]
        print(f"\nFirst {len(items)} {args.entity_type} entities:")
        for e in items:
            print(f"  {e.entity_id} [{e.confidence}] -> {len(e.relationships)} edges")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
