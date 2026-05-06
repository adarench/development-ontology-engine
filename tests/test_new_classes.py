"""Tests for DeterministicToolStep, ProbabilisticToolStep, ProvenanceSummary,
Tool API schema, ToolRegistry, LLMAgent, and DashboardRenderer."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Step type and provenance metadata
# ---------------------------------------------------------------------------

from core.steps.base import (
    DeterministicToolStep,
    ProbabilisticToolStep,
    ProvenanceSummary,
    ToolStep,
)


class _NullDeterministic(DeterministicToolStep):
    def run(self, data=None):
        return data


class _NullProbabilistic(ProbabilisticToolStep):
    probabilistic_type = "heuristic"
    confidence_level = 0.7
    method_description = "trivial test step"
    result_caveats = ["caveat A", "caveat B"]

    def run(self, data=None):
        return data


class _LLMProbabilistic(ProbabilisticToolStep):
    probabilistic_type = "llm"
    confidence_level = 0.9
    method_description = "llm-based extraction"
    result_caveats = []

    def run(self, data=None):
        return data


class TestDeterministicToolStep:
    def test_step_type(self):
        assert _NullDeterministic.step_type == "deterministic"

    def test_provenance_metadata(self):
        md = _NullDeterministic.provenance_metadata()
        assert md["step"] == "_NullDeterministic"
        assert md["step_type"] == "deterministic"

    def test_run_passthrough(self):
        assert _NullDeterministic().run(42) == 42

    def test_is_toolstep(self):
        assert issubclass(_NullDeterministic, ToolStep)


class TestProbabilisticToolStep:
    def test_step_type(self):
        assert _NullProbabilistic.step_type == "probabilistic"

    def test_provenance_metadata_fields(self):
        md = _NullProbabilistic.provenance_metadata()
        assert md["step"] == "_NullProbabilistic"
        assert md["step_type"] == "probabilistic"
        assert md["probabilistic_type"] == "heuristic"
        assert md["confidence_level"] == 0.7
        assert md["method_description"] == "trivial test step"
        assert md["caveats"] == ["caveat A", "caveat B"]

    def test_caveats_are_a_copy(self):
        md1 = _NullProbabilistic.provenance_metadata()
        md1["caveats"].append("injected")
        md2 = _NullProbabilistic.provenance_metadata()
        assert "injected" not in md2["caveats"]

    def test_llm_type(self):
        md = _LLMProbabilistic.provenance_metadata()
        assert md["probabilistic_type"] == "llm"
        assert md["confidence_level"] == 0.9

    def test_is_toolstep(self):
        assert issubclass(_NullProbabilistic, ToolStep)


# ---------------------------------------------------------------------------
# ProvenanceSummary
# ---------------------------------------------------------------------------


class TestProvenanceSummary:
    def test_record_deterministic(self):
        ps = ProvenanceSummary()
        ps.record(_NullDeterministic())
        assert "_NullDeterministic" in ps.deterministic_steps
        assert ps.probabilistic_steps == []

    def test_record_probabilistic(self):
        ps = ProvenanceSummary()
        ps.record(_NullProbabilistic())
        assert ps.deterministic_steps == []
        assert len(ps.probabilistic_steps) == 1
        assert ps.probabilistic_steps[0]["step"] == "_NullProbabilistic"

    def test_has_probabilistic_false(self):
        ps = ProvenanceSummary()
        ps.record(_NullDeterministic())
        assert not ps.has_probabilistic()

    def test_has_probabilistic_true(self):
        ps = ProvenanceSummary()
        ps.record(_NullProbabilistic())
        assert ps.has_probabilistic()

    def test_to_markdown_contains_sections(self):
        ps = ProvenanceSummary()
        ps.record(_NullDeterministic())
        ps.record(_NullProbabilistic())
        md = ps.to_markdown()
        assert "## Data Provenance" in md
        assert "Certain" in md
        assert "Estimated" in md
        assert "_NullDeterministic" in md
        assert "_NullProbabilistic" in md

    def test_to_markdown_shows_confidence(self):
        ps = ProvenanceSummary()
        ps.record(_NullProbabilistic())
        md = ps.to_markdown()
        assert "70%" in md

    def test_to_markdown_shows_caveats(self):
        ps = ProvenanceSummary()
        ps.record(_NullProbabilistic())
        md = ps.to_markdown()
        assert "caveat A" in md

    def test_to_markdown_llm_badge(self):
        ps = ProvenanceSummary()
        ps.record(_LLMProbabilistic())
        md = ps.to_markdown()
        assert "✦" in md

    def test_empty_summary_returns_empty(self):
        ps = ProvenanceSummary()
        assert ps.to_markdown() == ""

    def test_to_dict_structure(self):
        ps = ProvenanceSummary()
        ps.record(_NullDeterministic())
        ps.record(_NullProbabilistic())
        d = ps.to_dict()
        assert "deterministic_steps" in d
        assert "probabilistic_steps" in d
        assert "_NullDeterministic" in d["deterministic_steps"]
        assert d["probabilistic_steps"][0]["step"] == "_NullProbabilistic"


# ---------------------------------------------------------------------------
# Tool API schema and input_schema
# ---------------------------------------------------------------------------

from core.tools.base import Tool
from core.tools.query import QueryTool
from core.tools.qa_harness import QAHarnessTool
from core.tools.operating_state import OperatingStateTool
from core.tools.agent_chunks import AgentChunksTool
from core.tools.coverage_report import CoverageReportTool
from core.tools.gl_report import GLReportTool
from core.tools.operating_state_v2 import OperatingStateV2Tool


class _NamedTool(Tool):
    name = "test_tool"
    description = "A test tool."

    def run(self, data=None, **kwargs):
        return "ok"


class _UnnamedTool(Tool):
    def run(self, data=None, **kwargs):
        return "ok"


class TestToolAPISchema:
    def test_to_api_schema_structure(self):
        schema = _NamedTool().to_api_schema()
        assert schema["name"] == "test_tool"
        assert schema["description"] == "A test tool."
        assert "input_schema" in schema

    def test_to_api_schema_raises_without_name(self):
        with pytest.raises(ValueError, match="name must be set"):
            _UnnamedTool().to_api_schema()

    def test_default_input_schema(self):
        schema = _NamedTool().input_schema()
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_query_tool_schema_has_question(self):
        schema = QueryTool().input_schema()
        assert "question" in schema["properties"]
        assert "question" in schema.get("required", [])

    def test_qa_harness_schema_has_questions(self):
        schema = QAHarnessTool().input_schema()
        assert "questions" in schema["properties"]

    def test_all_tools_have_name(self):
        tools = [
            GLReportTool(),
            OperatingStateTool(),
            OperatingStateV2Tool(),
            AgentChunksTool(),
            QueryTool(),
            QAHarnessTool(),
            CoverageReportTool(),
        ]
        for tool in tools:
            assert tool.name, f"{tool.__class__.__name__} has no name"

    def test_all_tools_have_description(self):
        tools = [
            GLReportTool(),
            OperatingStateTool(),
            OperatingStateV2Tool(),
            AgentChunksTool(),
            QueryTool(),
            QAHarnessTool(),
            CoverageReportTool(),
        ]
        for tool in tools:
            assert tool.description, f"{tool.__class__.__name__} has no description"

    def test_all_tools_produce_valid_api_schema(self):
        tools = [
            GLReportTool(),
            OperatingStateTool(),
            OperatingStateV2Tool(),
            AgentChunksTool(),
            QueryTool(),
            QAHarnessTool(),
            CoverageReportTool(),
        ]
        for tool in tools:
            s = tool.to_api_schema()
            assert "name" in s and "description" in s and "input_schema" in s


# ---------------------------------------------------------------------------
# Provenance tracking wired into Tool
# ---------------------------------------------------------------------------

from core.connectors.file import FileConnector


class TestToolProvenance:
    def test_operating_state_embeds_provenance_in_json(self):
        from core.connectors.clickup import ClickUpConnector
        tool = OperatingStateTool(
            connector=ClickUpConnector(FIXTURES / "mock_clickup.csv")
        )
        state = json.loads(tool.run())
        assert "provenance" in state
        assert "probabilistic_steps" in state["provenance"]
        assert len(state["provenance"]["probabilistic_steps"]) > 0

    def test_operating_state_provenance_names_phase_cluster(self):
        from core.connectors.clickup import ClickUpConnector
        tool = OperatingStateTool(
            connector=ClickUpConnector(FIXTURES / "mock_clickup.csv")
        )
        state = json.loads(tool.run())
        step_names = [s["step"] for s in state["provenance"]["probabilistic_steps"]]
        assert "PhaseClusterStep" in step_names

    def test_provenance_absent_when_only_deterministic(self):
        # QueryTool has no probabilistic steps → no provenance in output
        raw = FileConnector(FIXTURES / "mock_operating_state_v1.json").fetch()
        tool = QueryTool()
        result = tool.run(data={"state": raw, "question": "How many lots?"})
        assert "## Data Provenance" not in result

    def test_markdown_tool_appends_provenance_section(self):
        # A markdown-format tool with a probabilistic step appends the section
        class _ProbMarkdownTool(Tool):
            name = "prob_md_tool"
            description = "test"
            output_format = "markdown"

            def run(self, data=None, **kwargs) -> str:
                self._reset_provenance()
                self._track(_NullProbabilistic())
                return "body" + self._provenance_section()

        result = _ProbMarkdownTool().run()
        assert "## Data Provenance" in result

    def test_reset_provenance_clears_state(self):
        tool = _NamedTool()
        tool._provenance.record(_NullProbabilistic())
        assert tool._provenance.has_probabilistic()
        tool._reset_provenance()
        assert not tool._provenance.has_probabilistic()


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

from core.agent.registry import ToolRegistry


class TestToolRegistry:
    def _make_registry(self):
        r = ToolRegistry()
        r.register(QueryTool())
        r.register(QAHarnessTool())
        return r

    def test_register_and_len(self):
        r = self._make_registry()
        assert len(r) == 2

    def test_contains(self):
        r = self._make_registry()
        assert "query" in r
        assert "qa_harness" in r
        assert "missing" not in r

    def test_to_api_schemas_count(self):
        r = self._make_registry()
        schemas = r.to_api_schemas()
        assert len(schemas) == 2

    def test_to_api_schemas_names(self):
        r = self._make_registry()
        names = {s["name"] for s in r.to_api_schemas()}
        assert names == {"query", "qa_harness"}

    def test_register_raises_without_name(self):
        r = ToolRegistry()
        with pytest.raises(ValueError, match="name must be set"):
            r.register(_UnnamedTool())

    def test_dispatch_known_tool(self):
        raw = FileConnector(FIXTURES / "mock_operating_state_v1.json").fetch()
        tool = QueryTool()
        tool._cached_state = raw
        r = ToolRegistry()
        r.register(tool)
        result = r.dispatch("query", {"question": "How many lots?"})
        assert isinstance(result, str)

    def test_dispatch_unknown_tool_raises(self):
        r = ToolRegistry()
        with pytest.raises(KeyError, match="Unknown tool"):
            r.dispatch("nonexistent", {})

    def test_register_returns_self_for_chaining(self):
        r = ToolRegistry()
        result = r.register(_NamedTool())
        assert result is r

    def test_repr_shows_names(self):
        r = ToolRegistry()
        r.register(_NamedTool())
        assert "test_tool" in repr(r)


# ---------------------------------------------------------------------------
# LLMAgent (mocked Anthropic client)
# ---------------------------------------------------------------------------

from core.agent.llm_agent import LLMAgent


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(name: str, inputs: dict, use_id: str = "tu_123"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = inputs
    block.id = use_id
    return block


def _make_response(stop_reason: str, content: list):
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content
    return resp


class TestLLMAgent:
    def _registry_with_tool(self):
        raw = FileConnector(FIXTURES / "mock_operating_state_v1.json").fetch()
        qt = QueryTool()
        qt._cached_state = raw
        r = ToolRegistry()
        r.register(qt)
        return r

    def test_end_turn_returns_text(self):
        client = MagicMock()
        client.messages.create.return_value = _make_response(
            "end_turn", [_make_text_block("Final answer.")]
        )
        agent = LLMAgent(self._registry_with_tool(), client=client)
        result = agent.run("Hello")
        assert result == "Final answer."

    def test_tool_use_then_end_turn(self):
        raw = FileConnector(FIXTURES / "mock_operating_state_v1.json").fetch()
        qt = QueryTool()
        qt._cached_state = raw

        registry = ToolRegistry()
        registry.register(qt)

        tool_use_block = _make_tool_use_block("query", {"question": "How many lots?"})
        text_block     = _make_text_block("There are 10 lots.")

        client = MagicMock()
        client.messages.create.side_effect = [
            _make_response("tool_use", [tool_use_block]),
            _make_response("end_turn",  [text_block]),
        ]

        agent = LLMAgent(registry, client=client)
        result = agent.run("How many lots are there?")

        assert result == "There are 10 lots."
        assert client.messages.create.call_count == 2

    def test_tool_error_propagated_as_string(self):
        registry = ToolRegistry()
        registry.register(_NamedTool())

        broken_block = _make_tool_use_block("test_tool", {"bad": "input"})
        text_block   = _make_text_block("Error handled.")

        # Patch dispatch to raise
        original_dispatch = registry.dispatch
        def raising_dispatch(name, inputs):
            raise RuntimeError("simulated failure")
        registry.dispatch = raising_dispatch

        client = MagicMock()
        client.messages.create.side_effect = [
            _make_response("tool_use", [broken_block]),
            _make_response("end_turn",  [text_block]),
        ]

        agent = LLMAgent(registry, client=client)
        result = agent.run("trigger error")

        # Second call to messages.create should include the error string
        second_call_messages = client.messages.create.call_args_list[1][1]["messages"]
        tool_result_msg = second_call_messages[-1]
        assert tool_result_msg["role"] == "user"
        error_content = tool_result_msg["content"][0]["content"]
        assert "simulated failure" in error_content

    def test_max_iterations_guard(self):
        client = MagicMock()
        # Always return tool_use, never end_turn
        tool_use_block = _make_tool_use_block("test_tool", {})
        client.messages.create.return_value = _make_response(
            "tool_use", [tool_use_block]
        )

        registry = ToolRegistry()
        registry.register(_NamedTool())

        agent = LLMAgent(registry, max_iterations=3, client=client)
        result = agent.run("infinite loop test")

        assert result == "[max_iterations reached without end_turn]"
        assert client.messages.create.call_count == 3

    def test_system_prompt_passed(self):
        client = MagicMock()
        client.messages.create.return_value = _make_response(
            "end_turn", [_make_text_block("ok")]
        )
        agent = LLMAgent(self._registry_with_tool(), system="You are helpful.", client=client)
        agent.run("test")
        kwargs = client.messages.create.call_args[1]
        assert kwargs["system"] == "You are helpful."

    def test_no_system_prompt_omitted(self):
        client = MagicMock()
        client.messages.create.return_value = _make_response(
            "end_turn", [_make_text_block("ok")]
        )
        agent = LLMAgent(self._registry_with_tool(), client=client)
        agent.run("test")
        kwargs = client.messages.create.call_args[1]
        assert "system" not in kwargs

    def test_model_forwarded(self):
        client = MagicMock()
        client.messages.create.return_value = _make_response(
            "end_turn", [_make_text_block("ok")]
        )
        agent = LLMAgent(self._registry_with_tool(), model="claude-haiku-4-5-20251001", client=client)
        agent.run("test")
        kwargs = client.messages.create.call_args[1]
        assert kwargs["model"] == "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# DashboardRenderer
# ---------------------------------------------------------------------------

from core.renderers.base import Renderer
from core.renderers.dashboard import DashboardRenderer


class TestDashboardRenderer:
    def _load_state(self):
        return FileConnector(FIXTURES / "mock_operating_state_v1.json").fetch()

    def test_is_renderer(self):
        assert issubclass(DashboardRenderer, Renderer)

    def test_output_format_is_html(self):
        assert DashboardRenderer.output_format == "html"

    def test_render_returns_html(self):
        state = self._load_state()
        result = DashboardRenderer().render(data=state)
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result

    def test_render_contains_project_codes(self):
        state = self._load_state()
        result = DashboardRenderer().render(data=state)
        for proj in state.get("projects", []):
            assert proj["project_code"] in result

    def test_render_kpi_section(self):
        state = self._load_state()
        result = DashboardRenderer().render(data=state)
        assert "kpis" in result or "Projects" in result

    def test_render_via_connector(self):
        conn = FileConnector(FIXTURES / "mock_operating_state_v1.json")
        result = DashboardRenderer(connector=conn).render()
        assert "<!DOCTYPE html>" in result

    def test_render_json_string_input(self):
        state = self._load_state()
        result = DashboardRenderer().render(data=json.dumps(state))
        assert "<!DOCTYPE html>" in result

    def test_render_empty_state_no_crash(self):
        result = DashboardRenderer().render(data={})
        assert isinstance(result, str)

    def test_not_a_tool(self):
        assert not isinstance(DashboardRenderer(), Tool)
