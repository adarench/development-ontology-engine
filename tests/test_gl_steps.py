"""Tests for GL pipeline steps."""
from pathlib import Path

import pandas as pd
import pytest

from core.connectors.quickbooks import QuickBooksConnector
from core.steps.gl_clean import GLCleanStep
from core.steps.gl_normalize import GLNormalizeStep
from core.steps.gl_aggregate import GLAggregateStep

FIXTURES = Path(__file__).parent / "fixtures"


def raw_df() -> pd.DataFrame:
    return QuickBooksConnector(FIXTURES / "mock_quickbooks.csv").fetch()


# ---------------------------------------------------------------------------
# GLCleanStep
# ---------------------------------------------------------------------------

class TestGLCleanStep:
    def test_drops_opening_balances(self):
        df = GLCleanStep().run(raw_df())
        assert "Opening Balance" not in df["Data Type"].unique()

    def test_drops_invalid_entities(self):
        df = GLCleanStep(invalid_entities={"drywall partners"}).run(raw_df())
        assert "drywall partners" not in df["Entity"].str.lower().tolist()

    def test_replaces_placeholder_vendor(self):
        df = GLCleanStep().run(raw_df())
        assert "Vendor or Supplier name" not in df["Vendor"].dropna().tolist()

    def test_replaces_placeholder_customer(self):
        df = GLCleanStep().run(raw_df())
        assert "Customer or Client name" not in df["Customer"].dropna().tolist()

    def test_adds_account_name_canonical(self):
        df = GLCleanStep().run(raw_df())
        assert "account_name_canonical" in df.columns

    def test_output_is_dataframe(self):
        assert isinstance(GLCleanStep().run(raw_df()), pd.DataFrame)

    def test_only_activity_rows_remain(self):
        df = GLCleanStep().run(raw_df())
        assert (df["Data Type"] == "Activity").all()


# ---------------------------------------------------------------------------
# GLNormalizeStep
# ---------------------------------------------------------------------------

class TestGLNormalizeStep:
    def _normalized(self) -> pd.DataFrame:
        clean = GLCleanStep().run(raw_df())
        return GLNormalizeStep().run(clean)

    def test_output_has_required_columns(self):
        df = self._normalized()
        for col in ["entity_role", "project_id", "cost_bucket", "phase_id", "amount"]:
            assert col in df.columns, f"missing column: {col}"

    def test_flagborough_mapped_to_project(self):
        df = self._normalized()
        flag_rows = df[df["entity"] == "Flagborough LLC"]
        assert (flag_rows["entity_role"] == "project").all()
        assert (flag_rows["project_id"] == "Park").all()

    def test_holdco_mapped_correctly(self):
        df = self._normalized()
        holdco = df[df["entity"] == "Flagship EM Holdings LLC"]
        assert (holdco["entity_role"] == "holdco").all()
        assert holdco["project_id"].isna().all()

    def test_cash_account_bucketed(self):
        df = self._normalized()
        cash = df[df["account_id"].str.startswith("110-", na=False)]
        assert (cash["cost_bucket"] == "cash").all()

    def test_inventory_cip_bucketed(self):
        df = self._normalized()
        cip = df[df["account_id"].str.startswith("510-", na=False)]
        assert (cip["cost_bucket"] == "inventory_cip").all()

    def test_financing_bucketed(self):
        df = self._normalized()
        fin = df[df["account_id"].str.startswith("260-", na=False)]
        assert (fin["cost_bucket"] == "financing").all()

    def test_unknown_entity_gets_unknown_role(self):
        clean = GLCleanStep().run(raw_df())
        clean.loc[0, "Entity"] = "Completely Unknown LLC"
        df = GLNormalizeStep().run(clean)
        unknown = df[df["entity"] == "Completely Unknown LLC"]
        assert (unknown["entity_role"] == "unknown").all()

    def test_custom_entity_map_accepted(self):
        custom_map = {"Flagborough LLC": ("custom_role", "custom_proj")}
        clean = GLCleanStep().run(raw_df())
        df = GLNormalizeStep(entity_map=custom_map).run(clean)
        flag = df[df["entity"] == "Flagborough LLC"]
        assert (flag["entity_role"] == "custom_role").all()


# ---------------------------------------------------------------------------
# GLAggregateStep
# ---------------------------------------------------------------------------

class TestGLAggregateStep:
    def _aggs(self) -> dict:
        clean = GLCleanStep().run(raw_df())
        norm  = GLNormalizeStep().run(clean)
        return GLAggregateStep().run(norm)

    def test_returns_three_keys(self):
        aggs = self._aggs()
        assert set(aggs.keys()) == {"by_project", "by_phase", "by_bucket"}

    def test_by_bucket_has_expected_buckets(self):
        aggs = self._aggs()
        buckets = set(aggs["by_bucket"]["cost_bucket"].tolist())
        assert "cash" in buckets
        assert "inventory_cip" in buckets

    def test_abs_amount_always_positive(self):
        aggs = self._aggs()
        for name, df in aggs.items():
            if "abs_amount" in df.columns:
                assert (df["abs_amount"] >= 0).all(), f"negative abs_amount in {name}"

    def test_by_project_has_project_rows(self):
        aggs = self._aggs()
        roles = set(aggs["by_project"]["entity_role"].tolist())
        assert "project" in roles

    def test_by_phase_only_project_entities(self):
        aggs = self._aggs()
        # by_phase filters to entity_role == "project" only.
        clean = GLCleanStep().run(raw_df())
        norm  = GLNormalizeStep().run(clean)
        project_ids = set(norm[norm["entity_role"] == "project"]["project_id"].dropna())
        phase_proj_ids = set(aggs["by_phase"]["project_id"].dropna())
        assert phase_proj_ids.issubset(project_ids)
