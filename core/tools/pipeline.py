from __future__ import annotations
from typing import Any

from core.steps.base import ToolStep
from core.tools.base import Tool


class PipelineTool(Tool):
    """A Tool constructed from an ordered list of Steps.

    Steps execute in sequence; each step receives the previous step's output as
    its input. The first step receives the initial data argument passed to run().

    Construct directly or via ToolLoader.from_dict(tool_dict).
    """

    def __init__(
        self,
        name: str,
        description: str,
        steps: list[ToolStep],
        include_provenance: bool = True,
    ):
        super().__init__(include_provenance=include_provenance)
        self.name = name
        self.description = description
        self.steps = steps

    def run(self, data: Any = None, **kwargs) -> Any:
        self._reset_provenance()
        result = data
        for step in self.steps:
            self._track(step)
            result = step.run(result)
        return result
