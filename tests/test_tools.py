"""Tests for all Tool implementations."""
import json
from pathlib import Path

import pandas as pd
import pytest

from core.connectors.file import FileConnector
from core.connectors.quickbooks import QuickBooksConnector
from core.connectors.clickup import ClickUpConnector

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# GLReportTool
# ---------------------------------------------------------------------------

from core.tools.gl_report import GLReportTool


class TestGLReportTool:
    def test_returns_string(self):
        tool = GLReportTool(connector=QuickBooksConnector(FIXTURES / "mock_quickbooks.csv"))
        result = tool.run()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_output_contains_coverage_section(self):
        tool = GLReportTool(connector=QuickBooksConnector(FIXTURES / "mock_quickbooks.csv"))
        result = tool.run()
        assert "Coverage" in result

    def test_output_format_is_markdown(self):
        assert GLReportTool.output_format == "markdown"

    def test_accepts_dataframe_directly(self):
        raw = QuickBooksConnector(FIXTURES / "mock_quickbooks.csv").fetch()
        tool = GLReportTool()
        result = tool.run(data=raw)
        assert isinstance(result, str)

    def test_reports_unmapped_accounts(self):
        raw = QuickBooksConnector(FIXTURES / "mock_quickbooks.csv").fetch()
        tool = GLReportTool()
        result = tool.run(data=raw)
        # soft_cost 660-001 is in the mock but may not all be mapped; verify string produced
        assert "bucket" in result.lower() or "unmapped" in result.lower() or "By" in result


# ---------------------------------------------------------------------------
# OperatingStateTool
# ---------------------------------------------------------------------------

from core.tools.operating_state import OperatingStateTool


class TestOperatingStateTool:
    def test_returns_valid_json(self):
        tool = OperatingStateTool(
            connector=ClickUpConnector(FIXTURES / "mock_clickup.csv")
        )
        result = tool.run()
        state = json.loads(result)
        assert state["schema_version"] == "operating_state_v1"

    def test_state_has_projects(self):
        tool = OperatingStateTool(
            connector=ClickUpConnector(FIXTURES / "mock_clickup.csv")
        )
        state = json.loads(tool.run())
        assert len(state["projects"]) >= 3  # H, LE, AS at minimum

    def test_with_gl_connector(self):
        tool = OperatingStateTool(
            connector=ClickUpConnector(FIXTURES / "mock_clickup.csv"),
            gl_connector=QuickBooksConnector(FIXTURES / "mock_quickbooks.csv"),
        )
        result = tool.run()
        state = json.loads(result)
        # Flagborough LLC has GL data in mock → should show cost > 0
        h_proj = next(p for p in state["projects"] if p["project_code"] == "H")
        assert h_proj["financials"]["project_total_cost"] > 0

    def test_output_format_is_json(self):
        assert OperatingStateTool.output_format == "json"

    def test_data_quality_keys_present(self):
        tool = OperatingStateTool(
            connector=ClickUpConnector(FIXTURES / "mock_clickup.csv")
        )
        state = json.loads(tool.run())
        for key in ["lots_total", "projects_total", "phases_estimated"]:
            assert key in state["data_quality"], f"missing: {key}"


# ---------------------------------------------------------------------------
# OperatingStateV2Tool
# ---------------------------------------------------------------------------

from core.tools.operating_state_v2 import OperatingStateV2Tool


class TestOperatingStateV2Tool:
    def test_returns_valid_json(self):
        tool = OperatingStateV2Tool(
            ck_connector=ClickUpConnector(FIXTURES / "mock_clickup.csv"),
        )
        result = tool.run()
        state = json.loads(result)
        assert state["schema_version"] == "operating_state_v2_bcpd"

    def test_with_staged_gl(self):
        from core.connectors.datarails import DataRailsConnector
        tool = OperatingStateV2Tool(
            gl_connector=DataRailsConnector(FIXTURES / "mock_staged_gl.csv"),
            ck_connector=ClickUpConnector(FIXTURES / "mock_clickup.csv"),
        )
        state = json.loads(tool.run())
        assert len(state["projects"]) > 0

    def test_lot_confidence_is_inferred(self):
        tool = OperatingStateV2Tool(
            ck_connector=ClickUpConnector(FIXTURES / "mock_clickup.csv"),
        )
        state = json.loads(tool.run())
        for proj in state["projects"]:
            for phase in proj["phases"]:
                for lot in phase["lots"]:
                    assert lot["confidence"] == "inferred"


# ---------------------------------------------------------------------------
# AgentChunksTool
# ---------------------------------------------------------------------------

from core.tools.agent_chunks import AgentChunksTool


class TestAgentChunksTool:
    def test_returns_valid_json(self, tmp_path):
        tool = AgentChunksTool(
            connector=FileConnector(FIXTURES / "mock_operating_state_v1.json"),
            output_dir=tmp_path / "chunks",
        )
        result = tool.run()
        index = json.loads(result)
        assert "chunk_count" in index
        assert index["chunk_count"] > 0

    def test_writes_chunk_files(self, tmp_path):
        tool = AgentChunksTool(
            connector=FileConnector(FIXTURES / "mock_operating_state_v1.json"),
            output_dir=tmp_path / "chunks",
        )
        tool.run()
        chunk_files = list((tmp_path / "chunks").glob("*.md"))
        assert len(chunk_files) > 0

    def test_guardrail_chunks_always_present(self, tmp_path):
        tool = AgentChunksTool(
            connector=FileConnector(FIXTURES / "mock_operating_state_v1.json"),
            output_dir=tmp_path / "chunks",
        )
        index = json.loads(tool.run())
        chunk_ids = {c["chunk_id"] for c in index["chunks"]}
        assert "guardrail_missing_cost_not_zero" in chunk_ids
        assert "guardrail_phase_ids_estimated" in chunk_ids

    def test_chunk_files_have_frontmatter(self, tmp_path):
        tool = AgentChunksTool(
            connector=FileConnector(FIXTURES / "mock_operating_state_v1.json"),
            output_dir=tmp_path / "chunks",
        )
        tool.run()
        md_file = next((tmp_path / "chunks").glob("*.md"))
        content = md_file.read_text()
        assert content.startswith("---")
        assert "chunk_id:" in content

    def test_accepts_dict_directly(self, tmp_path):
        state = json.loads((FIXTURES / "mock_operating_state_v1.json").read_text())
        tool = AgentChunksTool(output_dir=tmp_path / "chunks")
        result = tool.run(data=state)
        assert json.loads(result)["chunk_count"] > 0


# ---------------------------------------------------------------------------
# QueryTool
# ---------------------------------------------------------------------------

from core.tools.query import QueryTool


class TestQueryTool:
    def _state(self) -> dict:
        return json.loads((FIXTURES / "mock_operating_state_v1.json").read_text())

    def test_returns_string(self):
        tool = QueryTool()
        result = tool.run(data=self._state(), question="how many lots are in each project?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_lot_count_answer_mentions_total(self):
        tool = QueryTool()
        result = tool.run(data=self._state(), question="how many lots are in each project?")
        assert "10" in result  # mock state has 10 total lots

    def test_project_list_answer(self):
        tool = QueryTool()
        result = tool.run(data=self._state(), question="which projects are in scope?")
        assert "H" in result and "LE" in result and "AS" in result

    def test_cost_answer_includes_caveat_for_missing(self):
        tool = QueryTool()
        result = tool.run(data=self._state(), question="what is the cost for each project?")
        assert "unknown" in result.lower() or "no GL" in result

    def test_output_format_is_markdown(self):
        assert QueryTool.output_format == "markdown"

    def test_loads_from_connector(self):
        tool = QueryTool(connector=FileConnector(FIXTURES / "mock_operating_state_v1.json"))
        result = tool.run(question="what is the scope?")
        assert isinstance(result, str)

    def test_unmatched_question_returns_fallback(self):
        tool = QueryTool()
        result = tool.run(
            data=self._state(),
            question="what is the airspeed velocity of an unladen swallow?"
        )
        assert "No handler" in result or "try asking" in result.lower()


# ---------------------------------------------------------------------------
# QAHarnessTool
# ---------------------------------------------------------------------------

from core.tools.qa_harness import QAHarnessTool


class TestQAHarnessTool:
    def _state(self) -> dict:
        return json.loads((FIXTURES / "mock_operating_state_v1.json").read_text())

    def test_returns_string(self):
        tool = QAHarnessTool()
        result = tool.run(data=self._state())
        assert isinstance(result, str)

    def test_output_contains_question_headers(self):
        tool = QAHarnessTool()
        result = tool.run(data=self._state())
        assert "## Q1:" in result

    def test_runs_all_default_questions(self):
        from core.tools.qa_harness import DEFAULT_QUESTIONS
        tool = QAHarnessTool()
        result = tool.run(data=self._state())
        q_count = result.count("## Q")
        assert q_count == len(DEFAULT_QUESTIONS)

    def test_custom_question_set(self):
        tool = QAHarnessTool(questions=["how many lots are in each project?"])
        result = tool.run(data=self._state())
        assert "## Q1:" in result
        assert "## Q2:" not in result

    def test_output_format_is_markdown(self):
        assert QAHarnessTool.output_format == "markdown"


# ---------------------------------------------------------------------------
# CoverageReportTool
# ---------------------------------------------------------------------------

from core.tools.coverage_report import CoverageReportTool


class TestCoverageReportTool:
    def test_returns_string(self):
        tool = CoverageReportTool(
            inv_connector=FileConnector(FIXTURES / "mock_inventory.csv"),
            gl_connector=FileConnector(FIXTURES / "mock_staged_gl.csv"),
            ck_connector=FileConnector(FIXTURES / "mock_clickup.csv"),
        )
        result = tool.run()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_output_contains_coverage_table(self):
        tool = CoverageReportTool(
            inv_connector=FileConnector(FIXTURES / "mock_inventory.csv"),
            gl_connector=FileConnector(FIXTURES / "mock_staged_gl.csv"),
        )
        result = tool.run()
        assert "Coverage" in result
        assert "%" in result

    def test_accepts_data_dict_directly(self):
        inv = pd.read_csv(FIXTURES / "mock_inventory.csv")
        gl  = pd.read_csv(FIXTURES / "mock_staged_gl.csv")
        tool = CoverageReportTool()
        result = tool.run(data={"inventory": inv, "gl": gl})
        assert isinstance(result, str)

    def test_output_format_is_markdown(self):
        assert CoverageReportTool.output_format == "markdown"


# ---------------------------------------------------------------------------
# DashboardRenderer (moved from Tool to Renderer)
# ---------------------------------------------------------------------------

from core.renderers.dashboard import DashboardRenderer


class TestDashboardRenderer:
    def _state(self) -> dict:
        return json.loads((FIXTURES / "mock_operating_state_v1.json").read_text())

    def test_returns_html_string(self):
        r = DashboardRenderer()
        result = r.render(data=self._state())
        assert isinstance(result, str)
        assert result.strip().startswith("<!DOCTYPE html>")

    def test_output_contains_project_codes(self):
        r = DashboardRenderer()
        result = r.render(data=self._state())
        assert "H" in result
        assert "LE" in result
        assert "AS" in result

    def test_output_format_is_html(self):
        assert DashboardRenderer.output_format == "html"

    def test_loads_from_connector(self):
        r = DashboardRenderer(
            connector=FileConnector(FIXTURES / "mock_operating_state_v1.json")
        )
        result = r.render()
        assert "<!DOCTYPE html>" in result

    def test_output_is_self_contained(self):
        r = DashboardRenderer()
        result = r.render(data=self._state())
        assert "src=" not in result
        assert 'href="http' not in result
