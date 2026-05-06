from __future__ import annotations

from core.tools.base import Tool


class ToolRegistry:
    """Holds registered Tools and formats them for the Anthropic tool_use API.

    Usage:
        registry = ToolRegistry()
        registry.register(QueryTool(connector=...))
        registry.register(QAHarnessTool(connector=...))

        # Pass to LLMAgent or format manually:
        schemas = registry.to_api_schemas()   # list[dict] for anthropic tools= param
        result  = registry.dispatch("query", {"question": "..."})
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        if not tool.name:
            raise ValueError(
                f"{tool.__class__.__name__}.name must be set before registering"
            )
        self._tools[tool.name] = tool
        return self

    def to_api_schemas(self) -> list[dict]:
        return [t.to_api_schema() for t in self._tools.values()]

    def dispatch(self, name: str, inputs: dict) -> str:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name!r}. Available: {list(self._tools)}")
        return self._tools[name].run(**inputs)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"ToolRegistry({list(self._tools.keys())})"
