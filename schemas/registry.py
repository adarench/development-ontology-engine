from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal

SourceType = Literal["sql", "json", "xlsx", "csv"]

DEFAULT_REGISTRY_PATH = Path(__file__).parent / "datasource_schema.json"


@dataclass
class DatasourceField:
    id: str
    source_type: SourceType
    data_source: str
    field_name: str
    table_name: str | None = None
    field_path: str | None = None
    data_type: str | None = None
    nullable: bool | None = None
    sample_values: list[Any] = field(default_factory=list)
    raw_description: str | None = None
    description: str | None = None
    # Pre-formatted text optimized for vector embedding. Built by
    # `schemas.build_embedding_text` from the other fields. Refresh after
    # description/sample changes.
    embedding_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DatasourceField":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"Unknown fields in payload: {sorted(unknown)}")
        return cls(**payload)


class SchemaRegistry:
    """Loads, mutates, and persists the datasource schema JSON file.

    The on-disk shape is:
        {"version": 1, "datasources": [ {DatasourceField}, ... ]}
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str = DEFAULT_REGISTRY_PATH) -> None:
        self.path: Path = Path(path)
        self._fields: dict[str, DatasourceField] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        payload = json.loads(self.path.read_text())
        version = payload.get("version")
        if version != self.SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported registry version {version!r}; expected {self.SCHEMA_VERSION}"
            )
        for entry in payload.get("datasources", []):
            f = DatasourceField.from_dict(entry)
            self._fields[f.id] = f

    def save(self) -> None:
        payload = {
            "version":     self.SCHEMA_VERSION,
            "datasources": [f.to_dict() for f in self._fields.values()],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n")

    def add(self, entry: DatasourceField, *, overwrite: bool = False) -> None:
        if entry.id in self._fields and not overwrite:
            raise KeyError(f"Field id {entry.id!r} already registered; pass overwrite=True to replace")
        self._fields[entry.id] = entry

    def get(self, field_id: str) -> DatasourceField:
        return self._fields[field_id]

    def update_description(self, field_id: str, description: str) -> None:
        self._fields[field_id].description = description

    def remove(self, field_id: str) -> None:
        del self._fields[field_id]

    def purge_data_source(self, data_source: str) -> int:
        """Drop every field whose data_source equals this URI. Returns count removed."""
        to_remove = [fid for fid, f in self._fields.items() if f.data_source == data_source]
        for fid in to_remove:
            del self._fields[fid]
        return len(to_remove)

    def __iter__(self) -> Iterator[DatasourceField]:
        return iter(self._fields.values())

    def __len__(self) -> int:
        return len(self._fields)

    def __contains__(self, field_id: object) -> bool:
        return field_id in self._fields
