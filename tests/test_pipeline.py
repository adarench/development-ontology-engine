"""Tests for PipelineTool, StepRegistry, and ToolLoader."""
from __future__ import annotations

import pytest

from core.steps.base import DeterministicToolStep, ProbabilisticToolStep
from core.steps.registry import StepRegistry, ToolLoader
from core.steps.script import ScriptStep, ProbabilisticScriptStep
from core.tools.pipeline import PipelineTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Double(DeterministicToolStep):
    def run(self, data=None):
        return (data or 0) * 2


class _AddOne(DeterministicToolStep):
    def run(self, data=None):
        return (data or 0) + 1


class _Stringify(DeterministicToolStep):
    def run(self, data=None):
        return str(data)


# ---------------------------------------------------------------------------
# PipelineTool
# ---------------------------------------------------------------------------

class TestPipelineTool:
    def test_single_step(self):
        tool = PipelineTool(name="t", description="", steps=[_Double()])
        assert tool.run(3) == 6

    def test_step_chaining(self):
        # double then add-one: 5 → 10 → 11
        tool = PipelineTool(name="t", description="", steps=[_Double(), _AddOne()])
        assert tool.run(5) == 11

    def test_three_steps(self):
        # 4 → 8 → 9 → "9"
        tool = PipelineTool(name="t", description="", steps=[_Double(), _AddOne(), _Stringify()])
        assert tool.run(4) == "9"

    def test_initial_data_defaults_to_none(self):
        tool = PipelineTool(name="t", description="", steps=[_AddOne()])
        assert tool.run() == 1

    def test_name_and_description(self):
        tool = PipelineTool(name="my_tool", description="does a thing", steps=[])
        assert tool.name == "my_tool"
        assert tool.description == "does a thing"

    def test_empty_steps_returns_input(self):
        tool = PipelineTool(name="t", description="", steps=[])
        assert tool.run(42) == 42

    def test_provenance_tracked(self):
        class _Prob(ProbabilisticToolStep):
            probabilistic_type = "heuristic"
            confidence_level = 0.8
            method_description = "test"
            result_caveats = []
            def run(self, data=None):
                return data

        tool = PipelineTool(name="t", description="", steps=[_Double(), _Prob()])
        tool.run(1)
        assert any(s["step"] == "_Double" for s in tool._provenance.deterministic_steps)
        assert len(tool._provenance.probabilistic_steps) == 1

    def test_provenance_resets_between_runs(self):
        tool = PipelineTool(name="t", description="", steps=[_Double()])
        tool.run(1)
        tool.run(2)
        assert len(tool._provenance.deterministic_steps) == 1


# ---------------------------------------------------------------------------
# StepRegistry
# ---------------------------------------------------------------------------

class TestStepRegistry:
    def setup_method(self):
        # snapshot and restore registry so tests don't pollute each other
        self._original = dict(StepRegistry._registry)

    def teardown_method(self):
        StepRegistry._registry.clear()
        StepRegistry._registry.update(self._original)

    def test_register_and_get(self):
        StepRegistry.register(_Double)
        assert StepRegistry.get("_Double") is _Double

    def test_register_as_decorator(self):
        @StepRegistry.register
        class _Temp(DeterministicToolStep):
            def run(self, data=None):
                return data

        assert StepRegistry.get("_Temp") is _Temp

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="No step registered"):
            StepRegistry.get("NonExistentStep")

    def test_names(self):
        StepRegistry.register(_Double)
        StepRegistry.register(_AddOne)
        assert "_Double" in StepRegistry.names()
        assert "_AddOne" in StepRegistry.names()


# ---------------------------------------------------------------------------
# ToolLoader — registered steps
# ---------------------------------------------------------------------------

class TestToolLoaderRegistered:
    def setup_method(self):
        self._original = dict(StepRegistry._registry)
        StepRegistry.register(_Double)
        StepRegistry.register(_AddOne)

    def teardown_method(self):
        StepRegistry._registry.clear()
        StepRegistry._registry.update(self._original)

    def test_from_dict_single_step(self):
        spec = {
            "name": "double_tool",
            "description": "doubles input",
            "steps": [{"type": "_Double", "config": {}}],
        }
        tool = ToolLoader().from_dict(spec)
        assert isinstance(tool, PipelineTool)
        assert tool.name == "double_tool"
        assert tool.run(3) == 6

    def test_from_dict_chained_steps(self):
        spec = {
            "name": "t",
            "description": "",
            "steps": [
                {"type": "_Double", "config": {}},
                {"type": "_AddOne", "config": {}},
            ],
        }
        tool = ToolLoader().from_dict(spec)
        assert tool.run(5) == 11

    def test_from_dict_missing_description_defaults(self):
        spec = {"name": "t", "steps": [{"type": "_Double", "config": {}}]}
        tool = ToolLoader().from_dict(spec)
        assert tool.description == ""

    def test_from_dict_unknown_step_raises(self):
        spec = {"name": "t", "steps": [{"type": "Nonexistent"}]}
        with pytest.raises(KeyError, match="No step registered"):
            ToolLoader().from_dict(spec)


# ---------------------------------------------------------------------------
# ToolLoader — custom Python steps
# ---------------------------------------------------------------------------

class TestToolLoaderScriptStep:
    def test_script_step_deterministic(self):
        spec = {
            "name": "triple_tool",
            "description": "",
            "steps": [
                {
                    "type": "ScriptStep",
                    "config": {
                        "name": "TripleStep",
                        "description": "multiplies by three",
                        "code": "def run(input):\n    return (input or 0) * 3\n",
                    },
                }
            ],
        }
        tool = ToolLoader().from_dict(spec)
        assert tool.run(4) == 12

    def test_script_step_probabilistic(self):
        spec = {
            "name": "t",
            "description": "",
            "steps": [
                {
                    "type": "ProbabilisticScriptStep",
                    "config": {
                        "name": "GuessStep",
                        "description": "rough estimate",
                        "probabilistic_type": "heuristic",
                        "confidence_level": 0.6,
                        "method_description": "rough guess",
                        "result_caveats": [],
                        "code": "def run(input):\n    return 'estimated'\n",
                    },
                }
            ],
        }
        tool = ToolLoader().from_dict(spec)
        assert tool.run() == "estimated"

    def test_script_step_missing_run_raises(self):
        with pytest.raises(KeyError, match="must define a function named 'run'"):
            ScriptStep(code="x = 1\n")

    def test_script_step_name_in_provenance(self):
        spec = {
            "name": "t",
            "description": "",
            "steps": [
                {
                    "type": "ScriptStep",
                    "config": {
                        "name": "MyNamedStep",
                        "description": "does something",
                        "code": "def run(input):\n    return input\n",
                    },
                }
            ],
        }
        tool = ToolLoader().from_dict(spec)
        tool.run(1)
        assert any(s["step"] == "MyNamedStep" for s in tool._provenance.deterministic_steps)

    def test_script_step_description_in_provenance(self):
        spec = {
            "name": "t",
            "description": "",
            "steps": [
                {
                    "type": "ScriptStep",
                    "config": {
                        "name": "DoubleStep",
                        "description": "multiplies input by two",
                        "code": "def run(input):\n    return input * 2\n",
                    },
                }
            ],
        }
        tool = ToolLoader().from_dict(spec)
        tool.run(3)
        entry = tool._provenance.deterministic_steps[0]
        assert entry["step"] == "DoubleStep"
        assert entry["description"] == "multiplies input by two"

    def test_script_step_and_registered_steps_mixed(self):
        self._original = dict(StepRegistry._registry)
        StepRegistry.register(_Double)
        spec = {
            "name": "t",
            "description": "",
            "steps": [
                {"type": "_Double", "config": {}},
                {
                    "type": "ScriptStep",
                    "config": {
                        "name": "SubtractOne",
                        "description": "subtracts one",
                        "code": "def run(input):\n    return (input or 0) - 1\n",
                    },
                },
            ],
        }
        tool = ToolLoader().from_dict(spec)
        assert tool.run(5) == 9  # 5*2=10, 10-1=9
        StepRegistry._registry.clear()
        StepRegistry._registry.update(self._original)
