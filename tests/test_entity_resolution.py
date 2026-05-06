"""Tests for EntityResolutionStep and EntityResolver."""
from pathlib import Path

import pandas as pd
import pytest

from core.connectors.file import FileConnector
from core.steps.entity_resolution import EntityResolutionStep, EntityResolver

FIXTURES = Path(__file__).parent / "fixtures"


class TestEntityResolver:
    def test_add_and_resolve_mapping(self):
        r = EntityResolver()
        r.add_mapping("clickup_subdivision", "H", "Park")
        assert r.resolve("clickup_subdivision", "H") == "Park"

    def test_resolve_returns_none_for_unknown(self):
        r = EntityResolver()
        assert r.resolve("clickup_subdivision", "UNKNOWN") is None

    def test_add_and_resolve_lot_mapping(self):
        r = EntityResolver()
        r.add_lot_mapping("Park", "Phase 1", "1", "lot-abc123")
        assert r.resolve_lot("Park", "Phase 1", "1") == "lot-abc123"

    def test_len_reflects_total_mappings(self):
        r = EntityResolver()
        r.add_mapping("sys", "a", "b")
        r.add_lot_mapping("P", "Ph", "1", "lid")
        assert len(r) == 2

    def test_strips_whitespace_on_lookup(self):
        r = EntityResolver()
        r.add_mapping("clickup_subdivision", "H", "Park")
        assert r.resolve("clickup_subdivision", " H ") == "Park"


class TestEntityResolutionStep:
    def test_builds_resolver_from_crosswalk(self):
        connector = FileConnector(FIXTURES / "mock_crosswalk.csv")
        step = EntityResolutionStep(connector=connector)
        resolver = step.run()
        assert isinstance(resolver, EntityResolver)
        assert len(resolver) > 0

    def test_resolves_known_mapping(self):
        connector = FileConnector(FIXTURES / "mock_crosswalk.csv")
        resolver = EntityResolutionStep(connector=connector).run()
        assert resolver.resolve("clickup_subdivision", "H") == "Park"
        assert resolver.resolve("clickup_subdivision", "LE") == "Anderson Geneva"

    def test_accepts_data_directly(self):
        df = pd.DataFrame({
            "source_system":   ["test_sys"],
            "source_value":    ["raw_val"],
            "canonical_value": ["canon_val"],
        })
        resolver = EntityResolutionStep().run(data=df)
        assert resolver.resolve("test_sys", "raw_val") == "canon_val"

    def test_raises_on_missing_required_columns(self):
        df = pd.DataFrame({"col1": ["a"], "col2": ["b"]})
        with pytest.raises(ValueError, match="crosswalk must have columns"):
            EntityResolutionStep().run(data=df)

    def test_skips_null_rows(self):
        df = pd.DataFrame({
            "source_system":   ["sys", None],
            "source_value":    ["val", "other"],
            "canonical_value": ["canon", None],
        })
        resolver = EntityResolutionStep().run(data=df)
        assert resolver.resolve("sys", "val") == "canon"
        assert resolver.resolve(None, "other") is None
