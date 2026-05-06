"""Tests for all Connector implementations."""
import json
from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# FileConnector
# ---------------------------------------------------------------------------

from core.connectors.file import FileConnector


class TestFileConnector:
    def test_reads_csv(self):
        fc = FileConnector(FIXTURES / "mock_quickbooks.csv")
        df = fc.fetch()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_reads_json(self):
        fc = FileConnector(FIXTURES / "mock_operating_state_v1.json")
        data = fc.fetch()
        assert isinstance(data, dict)
        assert data["schema_version"] == "operating_state_v1"

    def test_validate_returns_true_for_existing_csv(self):
        assert FileConnector(FIXTURES / "mock_quickbooks.csv").validate()

    def test_validate_returns_false_for_missing_file(self):
        assert not FileConnector(FIXTURES / "does_not_exist.csv").validate()

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            FileConnector(FIXTURES / "no_such_file.csv").fetch()


# ---------------------------------------------------------------------------
# QuickBooksConnector
# ---------------------------------------------------------------------------

from core.connectors.quickbooks import QuickBooksConnector


class TestQuickBooksConnector:
    def test_reads_csv(self):
        qb = QuickBooksConnector(FIXTURES / "mock_quickbooks.csv")
        df = qb.fetch()
        assert isinstance(df, pd.DataFrame)
        assert "Data Type" in df.columns
        assert "Entity" in df.columns
        assert "Amount" in df.columns

    def test_validates_required_columns(self):
        qb = QuickBooksConnector(FIXTURES / "mock_quickbooks.csv")
        assert qb.validate()

    def test_strips_whitespace_from_string_columns(self):
        qb = QuickBooksConnector(FIXTURES / "mock_quickbooks.csv")
        df = qb.fetch()
        # No leading/trailing whitespace in string cols.
        for col in ["Entity", "Account ID", "Account Name"]:
            if col in df.columns:
                non_null = df[col].dropna()
                assert not any(v != v.strip() for v in non_null if isinstance(v, str))

    def test_raises_on_missing_required_columns(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("col1,col2\n1,2\n")
        with pytest.raises(ValueError, match="missing columns"):
            QuickBooksConnector(bad_csv).fetch()


# ---------------------------------------------------------------------------
# ClickUpConnector
# ---------------------------------------------------------------------------

from core.connectors.clickup import ClickUpConnector


class TestClickUpConnector:
    def test_reads_csv(self):
        cu = ClickUpConnector(FIXTURES / "mock_clickup.csv")
        df = cu.fetch()
        assert isinstance(df, pd.DataFrame)
        assert "name" in df.columns

    def test_normalizes_column_names_to_snake_case(self):
        cu = ClickUpConnector(FIXTURES / "mock_clickup.csv")
        df = cu.fetch()
        for col in df.columns:
            assert col == col.lower().replace(" ", "_")

    def test_drops_empty_name_rows(self):
        cu = ClickUpConnector(FIXTURES / "mock_clickup.csv")
        df = cu.fetch()
        assert df["name"].notna().all()
        assert (df["name"].str.len() > 0).all()

    def test_coerces_date_columns(self):
        cu = ClickUpConnector(FIXTURES / "mock_clickup.csv")
        df = cu.fetch()
        if "date_created" in df.columns:
            non_null = df["date_created"].dropna()
            assert len(non_null) > 0
            assert pd.api.types.is_datetime64_any_dtype(df["date_created"])

    def test_validate_returns_true(self):
        assert ClickUpConnector(FIXTURES / "mock_clickup.csv").validate()


# ---------------------------------------------------------------------------
# DataRailsConnector
# ---------------------------------------------------------------------------

from core.connectors.datarails import DataRailsConnector


class TestDataRailsConnector:
    def test_reads_csv(self):
        dr = DataRailsConnector(FIXTURES / "mock_staged_gl.csv")
        df = dr.fetch()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_deduplicates_rows(self):
        # mock_staged_gl.csv has a duplicate row (H lot 1 appears twice).
        dr = DataRailsConnector(FIXTURES / "mock_staged_gl.csv")
        df = dr.fetch()
        raw = pd.read_csv(FIXTURES / "mock_staged_gl.csv")
        assert len(df) < len(raw)

    def test_entity_filter(self):
        dr = DataRailsConnector(
            FIXTURES / "mock_staged_gl.csv",
            entity_filter="Building Construction Partners LLC",
        )
        df = dr.fetch()
        assert (df["entity_name"] == "Building Construction Partners LLC").all()

    def test_validate_returns_true(self):
        assert DataRailsConnector(FIXTURES / "mock_staged_gl.csv").validate()

    def test_validate_returns_false_for_missing(self):
        assert not DataRailsConnector(FIXTURES / "no_such.parquet").validate()
