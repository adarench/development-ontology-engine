from __future__ import annotations
from dataclasses import dataclass, field

import pandas as pd

from core.steps.base import DeterministicToolStep


@dataclass
class EntityResolver:
    """Lookup object built from crosswalk tables.

    Injected as a constructor dependency into ToolSteps that need entity
    resolution, rather than being sequenced in a pipeline.
    """

    _lookup: dict[tuple[str, str], str] = field(default_factory=dict)
    _lot_lookup: dict[tuple[str, str, str], str] = field(default_factory=dict)

    def resolve(self, source_system: str, source_value: str) -> str | None:
        return self._lookup.get((source_system, str(source_value).strip()))

    def resolve_lot(self, project: str, phase: str, lot: str) -> str | None:
        return self._lot_lookup.get((project, phase, str(lot).strip()))

    def add_mapping(self, source_system: str, source_value: str, canonical_value: str) -> None:
        self._lookup[(source_system, str(source_value).strip())] = canonical_value

    def add_lot_mapping(self, project: str, phase: str, lot: str, canonical_lot_id: str) -> None:
        self._lot_lookup[(project, phase, str(lot).strip())] = canonical_lot_id

    def __len__(self) -> int:
        return len(self._lookup) + len(self._lot_lookup)


class EntityResolutionStep(DeterministicToolStep):
    """Builds an EntityResolver from crosswalk CSV/parquet files.

    Input:  optional — if None, fetches from connector provided at construction
    Output: EntityResolver

    The crosswalk file(s) must have columns:
        source_system, source_value, canonical_value
    Optionally also: canonical_entity, confidence

    Args:
        connector:    Connector to fetch crosswalk data from (required if data
                      is not passed directly to run())
        lot_connector: optional separate connector for lot-grain crosswalk
    """

    def __init__(self, connector=None, lot_connector=None):
        self.connector     = connector
        self.lot_connector = lot_connector

    def run(self, data: pd.DataFrame | None = None) -> EntityResolver:
        resolver = EntityResolver()

        xwalk = data if data is not None else (
            self.connector.fetch() if self.connector else pd.DataFrame()
        )
        if not xwalk.empty:
            self._load_crosswalk(xwalk, resolver)

        if self.lot_connector is not None:
            lot_xwalk = self.lot_connector.fetch()
            self._load_lot_crosswalk(lot_xwalk, resolver)

        return resolver

    def _load_crosswalk(self, df: pd.DataFrame, resolver: EntityResolver) -> None:
        required = {"source_system", "source_value", "canonical_value"}
        if not required.issubset(set(df.columns)):
            raise ValueError(
                f"EntityResolutionStep: crosswalk must have columns {required}, "
                f"got {set(df.columns)}"
            )
        for _, row in df.iterrows():
            if pd.notna(row["source_value"]) and pd.notna(row["canonical_value"]):
                resolver.add_mapping(
                    str(row["source_system"]),
                    str(row["source_value"]),
                    str(row["canonical_value"]),
                )

    def _load_lot_crosswalk(self, df: pd.DataFrame, resolver: EntityResolver) -> None:
        required = {"canonical_project", "canonical_phase", "lot_number", "canonical_lot_id"}
        if not required.issubset(set(df.columns)):
            return
        for _, row in df.iterrows():
            if all(pd.notna(row[c]) for c in required):
                resolver.add_lot_mapping(
                    str(row["canonical_project"]),
                    str(row["canonical_phase"]),
                    str(row["lot_number"]),
                    str(row["canonical_lot_id"]),
                )
