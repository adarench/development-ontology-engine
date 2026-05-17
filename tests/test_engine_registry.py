"""Tests for core.engine.registry — the @step decorator and registry."""

from __future__ import annotations

import pytest

from core.engine.registry import (
    StepRegistrationError,
    StepSpec,
    all_steps,
    clear,
    get,
    step,
)


@pytest.fixture(autouse=True)
def _empty_registry():
    """Each test starts with an empty registry."""
    clear()
    yield
    clear()


def test_step_records_metadata():
    @step(
        name="example",
        inputs={"x": int},
        outputs={"y": int},
        effects=("read",),
        description="Doubles x.",
    )
    def example(x):
        return {"y": x * 2}

    spec = get("example")
    assert isinstance(spec, StepSpec)
    assert spec.name == "example"
    assert spec.inputs == {"x": int}
    assert spec.outputs == {"y": int}
    assert spec.effects == ("read",)
    assert spec.description == "Doubles x."
    assert spec.fn is example


def test_step_passes_function_through_unchanged():
    @step(name="passthrough", inputs={}, outputs={})
    def passthrough():
        return 42

    assert passthrough() == 42


def test_duplicate_name_raises():
    @step(name="dup", inputs={}, outputs={})
    def first():
        pass

    with pytest.raises(StepRegistrationError, match="already registered"):

        @step(name="dup", inputs={}, outputs={})
        def second():
            pass


def test_all_steps_returns_every_registration():
    @step(name="a", inputs={}, outputs={})
    def a():
        pass

    @step(name="b", inputs={}, outputs={})
    def b():
        pass

    names = {s.name for s in all_steps()}
    assert names == {"a", "b"}


def test_effects_accepts_list_or_tuple():
    @step(name="list_effects", inputs={}, outputs={}, effects=["read", "cost"])
    def list_effects():
        pass

    @step(name="tuple_effects", inputs={}, outputs={}, effects=("read", "cost"))
    def tuple_effects():
        pass

    assert get("list_effects").effects == ("read", "cost")
    assert get("tuple_effects").effects == ("read", "cost")


def test_missing_step_raises_keyerror():
    with pytest.raises(KeyError):
        get("does_not_exist")


def test_inputs_and_outputs_are_copied():
    """Mutating the dict passed in must not affect the registered spec."""
    inputs = {"x": int}
    outputs = {"y": int}

    @step(name="copies", inputs=inputs, outputs=outputs)
    def copies(x):
        pass

    inputs["sneaky"] = str
    outputs["sneaky"] = str

    assert "sneaky" not in get("copies").inputs
    assert "sneaky" not in get("copies").outputs
