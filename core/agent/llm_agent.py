from __future__ import annotations

from core.agent.registry import ToolRegistry


class LLMAgent:
    """Wraps the Anthropic Messages API in an agentic tool-call loop.

    Sends registered tools to Claude, handles tool_use stop_reason by
    dispatching to the registry, and loops until end_turn or max_iterations.

    Args:
        registry:       ToolRegistry with all tools the agent may call
        model:          Anthropic model ID (default: claude-opus-4-7)
        max_iterations: hard cap on tool-call iterations (prevents infinite loops)
        system:         optional system prompt
        client:         injectable Anthropic client (for testing / custom auth)
    """

    def __init__(
        self,
        registry: ToolRegistry,
        model: str = "claude-opus-4-7",
        max_iterations: int = 10,
        system: str = "",
        client=None,
    ) -> None:
        self.registry       = registry
        self.model          = model
        self.max_iterations = max_iterations
        self.system         = system
        self._client        = client

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def run(self, user_message: str) -> str:
        """Send user_message to the LLM, resolve all tool calls, return final answer.

        Returns:
            The assistant's final text response.
        """
        client   = self._get_client()
        messages = [{"role": "user", "content": user_message}]
        tools    = self.registry.to_api_schemas()

        for _ in range(self.max_iterations):
            kwargs: dict = {
                "model":      self.model,
                "max_tokens": 4096,
                "tools":      tools,
                "messages":   messages,
            }
            if self.system:
                kwargs["system"] = self.system

            response = client.messages.create(**kwargs)

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        try:
                            result = self.registry.dispatch(block.name, block.input)
                        except Exception as exc:
                            result = f"Error calling {block.name}: {exc}"
                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": block.id,
                            "content":     result,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                break

        return "[max_iterations reached without end_turn]"
