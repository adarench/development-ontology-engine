from __future__ import annotations
from typing import Any

from core.connectors.base import Connector
from core.steps.base import ProvenanceSummary, ToolStep


class Tool:
    """LLM-facing interface: orchestrates ToolSteps and returns a string.

    Every Tool must declare:
        name:        unique snake_case identifier the LLM uses to call it
        description: one-sentence plain-English description for the LLM

    output_format signals the kind of string returned — "markdown", "json", or "html".
    Callers decide what to do with the string (pass to LLM, write to file, etc.).

    Provenance:
        When include_provenance=True (the default), the Tool appends a
        ## Data Provenance section to its output listing which steps were
        deterministic (certain) vs probabilistic (estimated). This lets the
        LLM explain uncertainty to the user accurately.
    """

    output_format: str = "markdown"
    name: str = ""
    description: str = ""

    def __init__(
        self,
        connector: Connector | None = None,
        include_provenance: bool = True,
    ):
        self.connector = connector
        self.include_provenance = include_provenance
        self._provenance = ProvenanceSummary()

    def run(self, data: Any = None, **kwargs) -> str:
        raise NotImplementedError

    def input_schema(self) -> dict:
        """Return the JSON schema for this tool's inputs.

        Override in subclasses to declare required and optional parameters.
        Used by ToolRegistry to format the Anthropic tool_use API schema.
        """
        return {"type": "object", "properties": {}, "required": []}

    def to_api_schema(self) -> dict:
        """Return the Anthropic tool_use API schema for this tool."""
        if not self.name:
            raise ValueError(
                f"{self.__class__.__name__}.name must be set to register with ToolRegistry"
            )
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
        }

    def _track(self, step: ToolStep) -> ToolStep:
        """Record a step in the provenance tracker and return it for chaining."""
        self._provenance.record(step)
        return step

    def _provenance_section(self) -> str:
        """Append a ## Data Provenance section — for markdown-format tools only.

        JSON-format tools should use _provenance_dict() to embed provenance
        inside their output dict instead of appending markdown to JSON.
        """
        if not self.include_provenance or not self._provenance.has_probabilistic():
            return ""
        if self.output_format == "json":
            return ""
        return "\n\n" + self._provenance.to_markdown()

    def _provenance_dict(self) -> dict | None:
        """Return a provenance dict for embedding in JSON output, or None."""
        if not self.include_provenance or not self._provenance.has_probabilistic():
            return None
        return self._provenance.to_dict()

    def _reset_provenance(self) -> None:
        self._provenance = ProvenanceSummary()
