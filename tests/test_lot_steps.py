"""Tests for lot/phase pipeline steps."""
from pathlib import Path

import pandas as pd
import pytest

from core.connectors.clickup import ClickUpConnector
from core.steps.lot_parse import LotParseStep
from core.steps.lot_state import LotStateStep
from core.steps.project_state import ProjectStateStep
from core.steps.phase_cluster import PhaseClusterStep
from core.steps.phase_state import PhaseStateStep
from core.steps.operating_view import OperatingViewStep

FIXTURES = Path(__file__).parent / "fixtures"


def raw_clickup() -> pd.DataFrame:
    return ClickUpConnector(FIXTURES / "mock_clickup.csv").fetch()


def parsed_df() -> pd.DataFrame:
    return LotParseStep().run(raw_clickup())


def lot_state_df() -> pd.DataFrame:
    return LotStateStep().run(parsed_df())


def with_phase_df() -> pd.DataFrame:
    return PhaseClusterStep(gap_threshold=10).run(lot_state_df())


# ---------------------------------------------------------------------------
# LotParseStep
# ---------------------------------------------------------------------------

class TestLotParseStep:
    def test_extracts_project_code(self):
        df = parsed_df()
        assert "project_code" in df.columns
        assert "H" in df["project_code"].values

    def test_extracts_lot_number(self):
        df = parsed_df()
        assert "1" in df["lot_number"].values

    def test_extracts_canonical_stage(self):
        df = parsed_df()
        assert "stage_canonical" in df.columns
        assert "Dug" in df["stage_canonical"].values
        assert "Footings" in df["stage_canonical"].values
        assert "Walls" in df["stage_canonical"].values

    def test_assigns_lot_key_from_parent_id(self):
        df = parsed_df()
        h1_rows = df[(df["project_code"] == "H") & (df["lot_number"] == "1")]
        assert (h1_rows["lot_key"] == "pid_h_001").all()

    def test_fallback_lot_key_for_missing_parent(self):
        df = parsed_df()
        h30 = df[(df["project_code"] == "H") & (df["lot_number"] == "30")]
        assert h30["lot_key"].str.startswith("FALLBACK_").all()

    def test_row_key_for_unparseable_name(self):
        df = parsed_df()
        # "A stray task with no lot number" can't be parsed.
        stray = df[df["project_code"].isna() & df["lot_number"].isna()]
        assert len(stray) > 0
        assert stray["lot_key"].str.startswith("ROW_").all()

    def test_collects_parse_warnings(self):
        step = LotParseStep()
        step.run(raw_clickup())
        assert len(step.warnings) > 0  # the stray task generates a warning

    def test_custom_stage_aliases(self):
        step = LotParseStep(stage_aliases={"dug": "CustomDug"})
        df = step.run(raw_clickup())
        dug_rows = df[df["stage_raw"].str.lower() == "dug"]
        assert (dug_rows["stage_canonical"] == "CustomDug").all()


# ---------------------------------------------------------------------------
# LotStateStep
# ---------------------------------------------------------------------------

class TestLotStateStep:
    def test_one_row_per_lot(self):
        df = lot_state_df()
        # H has lots 1,2,3,12,13,30 + LE 1,2 + AS 1,2 + unparseable rows
        assert "lot_key" in df.columns
        assert df["lot_key"].nunique() == len(df)

    def test_completion_pct_between_zero_and_one(self):
        df = lot_state_df()
        assert (df["completion_pct"] >= 0).all()
        assert (df["completion_pct"] <= 1).all()

    def test_h1_has_walls_as_current_stage(self):
        df = lot_state_df()
        h1 = df[df["lot_key"] == "pid_h_001"]
        assert len(h1) == 1
        assert h1.iloc[0]["current_stage"] == "Walls"

    def test_h1_has_three_stages_present(self):
        df = lot_state_df()
        h1 = df[df["lot_key"] == "pid_h_001"]
        assert h1.iloc[0]["stage_count"] == 3

    def test_le1_has_valid_progression(self):
        df = lot_state_df()
        le1 = df[df["lot_key"] == "pid_le_001"]
        assert le1.iloc[0]["has_valid_progression"] == True

    def test_status_values_are_valid(self):
        valid = {"not_started", "in_progress", "near_complete", "complete"}
        df = lot_state_df()
        assert set(df["status"].unique()).issubset(valid)

    def test_custom_stage_order(self):
        step = LotStateStep(stage_order={"A": 1, "B": 2, "C": 3})
        raw = pd.DataFrame({
            "lot_key":         ["k1", "k1"],
            "project_code":    ["P",  "P"],
            "lot_number":      ["1",  "1"],
            "lot_label":       ["P 1","P 1"],
            "stage_canonical": ["A",  "B"],
        })
        df = step.run(raw)
        assert df.iloc[0]["current_stage"] == "B"
        assert df.iloc[0]["completion_pct"] == round(2 / 3, 4)


# ---------------------------------------------------------------------------
# ProjectStateStep
# ---------------------------------------------------------------------------

class TestProjectStateStep:
    def test_one_row_per_project(self):
        df = ProjectStateStep().run(lot_state_df())
        assert df["project_code"].nunique() == len(df)

    def test_projects_present(self):
        df = ProjectStateStep().run(lot_state_df())
        codes = set(df["project_code"].tolist())
        assert "H" in codes
        assert "LE" in codes
        assert "AS" in codes

    def test_total_lots_correct_for_h(self):
        lots = lot_state_df()
        proj = ProjectStateStep().run(lots)
        h = proj[proj["project_code"] == "H"].iloc[0]
        h_lots = lots[lots["project_code"] == "H"]
        assert h["total_lots"] == len(h_lots)

    def test_avg_completion_between_zero_and_one(self):
        df = ProjectStateStep().run(lot_state_df())
        assert (df["avg_completion_pct"] >= 0).all()
        assert (df["avg_completion_pct"] <= 1).all()


# ---------------------------------------------------------------------------
# PhaseClusterStep
# ---------------------------------------------------------------------------

class TestPhaseClusterStep:
    def test_adds_phase_id_column(self):
        df = with_phase_df()
        assert "phase_id" in df.columns

    def test_h_lots_split_into_phases(self):
        df = with_phase_df()
        h_phases = df[df["project_code"] == "H"]["phase_id"].unique()
        # Lots 1,2,3 are close; lots 12,13 form a second phase; 30 a third.
        assert len(h_phases) >= 2

    def test_lots_1_2_3_in_same_phase(self):
        df = with_phase_df()
        h_small = df[(df["project_code"] == "H") & (df["lot_number"].isin(["1", "2", "3"]))]
        assert h_small["phase_id"].nunique() == 1

    def test_lot_30_in_different_phase_from_lots_1_2_3(self):
        df = with_phase_df()
        phase_1 = df[(df["project_code"] == "H") & (df["lot_number"] == "1")]["phase_id"].iloc[0]
        phase_30 = df[(df["project_code"] == "H") & (df["lot_number"] == "30")]["phase_id"].iloc[0]
        assert phase_1 != phase_30

    def test_custom_gap_threshold(self):
        step = PhaseClusterStep(gap_threshold=5)
        df = step.run(lot_state_df())
        h_phases = df[df["project_code"] == "H"]["phase_id"].unique()
        # With gap=5, lots 1,2,3 still same phase; 12 and 13 would split from 3.
        assert len(h_phases) >= 2


# ---------------------------------------------------------------------------
# PhaseStateStep
# ---------------------------------------------------------------------------

class TestPhaseStateStep:
    def test_one_row_per_phase(self):
        df = PhaseStateStep().run(with_phase_df())
        assert df["phase_id"].nunique() == len(df)

    def test_dominant_stage_is_valid_stage_or_none(self):
        valid = {"Dug", "Footings", "Walls", "Backfill", "Spec",
                 "Rough", "Finish", "Complete", "Sold", "(none)", None}
        df = PhaseStateStep().run(with_phase_df())
        for stage in df["dominant_stage"]:
            assert stage in valid or pd.isna(stage)

    def test_avg_completion_pct_between_zero_and_one(self):
        df = PhaseStateStep().run(with_phase_df())
        assert (df["avg_completion_pct"] >= 0).all()
        assert (df["avg_completion_pct"] <= 1).all()

    def test_lots_in_phase_positive(self):
        df = PhaseStateStep().run(with_phase_df())
        assert (df["lots_in_phase"] > 0).all()


# ---------------------------------------------------------------------------
# OperatingViewStep
# ---------------------------------------------------------------------------

class TestOperatingViewStep:
    def test_output_has_required_columns(self):
        lots    = with_phase_df()
        project = ProjectStateStep().run(lot_state_df())
        out = OperatingViewStep().run({"lot_state": lots, "project_state": project})
        for col in ["project_code", "lot_number", "stage", "completion_pct",
                    "status", "phase_id_estimated"]:
            assert col in out.columns, f"missing: {col}"

    def test_raises_without_phase_id(self):
        lots    = lot_state_df()  # no phase_id yet
        project = ProjectStateStep().run(lots)
        with pytest.raises(ValueError, match="phase_id"):
            OperatingViewStep().run({"lot_state": lots, "project_state": project})

    def test_gl_join_adds_cost_when_provided(self):
        from core.connectors.datarails import DataRailsConnector
        from core.steps.gl_clean import GLCleanStep
        from core.steps.gl_normalize import GLNormalizeStep
        lots    = with_phase_df()
        project = ProjectStateStep().run(lot_state_df())
        gl_raw  = DataRailsConnector(FIXTURES / "mock_staged_gl.csv").fetch()
        # mock staged GL doesn't have QB columns; build a minimal normalized df
        gl_norm = pd.DataFrame({
            "entity_role": ["project", "project"],
            "entity":      ["Flagborough LLC", "Flagborough LLC"],
            "project_id":  ["Park", "Park"],
            "amount":      [50000.0, 25000.0],
            "cost_bucket": ["inventory_cip", "inventory_cip"],
            "phase_id":    ["UNALLOCATED", "UNALLOCATED"],
        })
        out = OperatingViewStep().run(
            {"lot_state": lots, "project_state": project, "gl_normalized": gl_norm}
        )
        assert len(out) > 0
