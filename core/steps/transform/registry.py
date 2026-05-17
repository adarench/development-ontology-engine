from __future__ import annotations
from typing import TYPE_CHECKING

from core.steps.base import ToolStep

if TYPE_CHECKING:
    from core.tools.pipeline import PipelineTool


class StepRegistry:
    """Maps step type-name strings to step classes for runtime hydration.

    Built-in steps register themselves at import time via @StepRegistry.register.
    Custom (code-string) steps bypass the registry entirely and are exec'd directly.
    """

    _registry: dict[str, type[ToolStep]] = {}

    @classmethod
    def register(cls, step_cls: type[ToolStep]) -> type[ToolStep]:
        """Decorator and direct-call registration. Returns the class unchanged."""
        cls._registry[step_cls.__name__] = step_cls
        return step_cls

    @classmethod
    def get(cls, name: str) -> type[ToolStep]:
        if name not in cls._registry:
            registered = list(cls._registry)
            raise KeyError(f"No step registered as '{name}'. Registered: {registered}")
        return cls._registry[name]

    @classmethod
    def names(cls) -> list[str]:
        return list(cls._registry)


class ToolLoader:
    """Reconstructs a PipelineTool from its stored JSON dict.

    Stored format:
        {
            "name": "MyTool",
            "description": "...",
            "steps": [
                {"type": "SomeRegisteredStep", "config": {...}},
                {
                    "type": "ScriptStep",
                    "config": {
                        "name": "MyStep",
                        "description": "...",
                        "code": "def run(input):\\n    return input * 4"
                    }
                },
                {
                    "type": "ProbabilisticScriptStep",
                    "config": {
                        "name": "MyEstimate",
                        "description": "...",
                        "code": "def run(input):\\n    return input",
                        "probabilistic_type": "heuristic",
                        "confidence_level": 0.7,
                        "method_description": "...",
                        "result_caveats": [...]
                    }
                }
            ]
        }
    """

    def from_dict(self, tool_dict: dict) -> "PipelineTool":
        from core.tools.pipeline import PipelineTool

        steps = [self._hydrate_step(s) for s in tool_dict["steps"]]
        return PipelineTool(
            name=tool_dict["name"],
            description=tool_dict.get("description", ""),
            steps=steps,
        )

    def _hydrate_step(self, step_dict: dict) -> ToolStep:
        cls = StepRegistry.get(step_dict["type"])
        return cls(**step_dict.get("config", {}))
