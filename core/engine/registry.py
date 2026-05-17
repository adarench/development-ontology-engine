"""Step registry — the @step decorator and in-process index of registered steps.

A step is a Python function decorated with @step. The decorator records the
step's name, typed input/output ports, effect tags, and description in a
module-level registry. The engine reads the registry to compile graphs, dispatch
steps at run time, and surface step metadata to AI authoring.

Phase 0 scope: marker only. The decorator records metadata. Compiler and runner
integration arrives in Phase 1 (see docs/tool_engine_plan.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class StepSpec:
    """Metadata for one registered step.

    Fields are intentionally minimal — anything not needed for compile-time
    validation or AI authoring stays out.
    """

    name: str
    inputs: dict[str, type]
    outputs: dict[str, type]
    effects: tuple[str, ...]
    description: str
    fn: Callable[..., Any]


class StepRegistrationError(Exception):
    """Raised when a step cannot be registered (e.g. duplicate name)."""


_REGISTRY: dict[str, StepSpec] = {}


def step(
    name: str,
    inputs: dict[str, type],
    outputs: dict[str, type],
    effects: tuple[str, ...] | list[str] = (),
    description: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that registers a function as an engine step.

    Args:
        name: Globally unique, stable identifier. Used by graph definitions
            to reference the step.
        inputs: Mapping of input port name → declared type. Types are
            typically Pydantic models; primitives are also allowed.
        outputs: Mapping of output port name → declared type.
        effects: Effect tags consumed by the engine. See the canonical
            list in docs/tool_engine_implementation.md §5.
        description: Human-readable summary. Used by AI authoring.

    Raises:
        StepRegistrationError: If a step with the same name is already
            registered.
    """

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _REGISTRY:
            existing = _REGISTRY[name].fn
            raise StepRegistrationError(
                f"Step {name!r} is already registered by "
                f"{existing.__module__}.{existing.__qualname__}"
            )
        _REGISTRY[name] = StepSpec(
            name=name,
            inputs=dict(inputs),
            outputs=dict(outputs),
            effects=tuple(effects),
            description=description,
            fn=fn,
        )
        return fn

    return decorate


def get(name: str) -> StepSpec:
    """Look up a registered step by name. Raises KeyError if missing."""
    return _REGISTRY[name]


def all_steps() -> list[StepSpec]:
    """Return every registered step."""
    return list(_REGISTRY.values())


def clear() -> None:
    """Empty the registry. Test-only helper."""
    _REGISTRY.clear()
