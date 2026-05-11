from __future__ import annotations

import json

from core.connectors.base import Connector
from core.steps.query_execution import QueryExecutionStep, Answer
from core.tools.base import Tool


class QueryTool(Tool):
    """Answers a natural-language question against an operating state.

    Input:  question string (via run(question=...) or run(data={"question": ...}))
    Output: formatted markdown answer string

    The state is loaded once from the connector at first call and cached.
    Pass data=dict directly to skip the connector.

    Args:
        connector: FileConnector pointing at operating_state_*.json
    """

    output_format = "markdown"
    name = "query"
    description = (
        "Answers a natural-language question about the operating state: lot counts, "
        "project list, stage distributions, completion percentages, costs, bottlenecks, "
        "or scope. Returns a markdown-formatted answer with confidence and caveats."
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The natural language question to answer about the operating state.",
                }
            },
            "required": ["question"],
        }

    def __init__(self, connector: Connector | None = None):
        super().__init__(connector)
        self._step   = QueryExecutionStep()
        self._cached_state: dict | None = None

    def run(self, data=None, question: str = "", **kwargs) -> str:
        if isinstance(data, dict) and "question" in data:
            question = data["question"]
            state    = data.get("state", self._load_state(None))
        elif isinstance(data, dict):
            state = data
        else:
            state = self._load_state(data)

        if not question and "question" in kwargs:
            question = kwargs["question"]

        answer: Answer = self._step.run({"state": state, "question": question})
        return self._render(answer)

    def _load_state(self, data) -> dict:
        if data is not None:
            return json.loads(data) if isinstance(data, str) else data
        if self._cached_state is not None:
            return self._cached_state
        if self.connector is None:
            return {}
        raw = self.connector.fetch()
        self._cached_state = raw if isinstance(raw, dict) else {}
        return self._cached_state

    def _render(self, answer: Answer) -> str:
        lines = [
            f"**Q:** {answer.question}",
            "",
            f"**A:** {answer.direct_answer}",
            f"**Confidence:** {answer.confidence}",
        ]
        if answer.caveats:
            lines += ["", "**Caveats:**"]
            lines += [f"- {c}" for c in answer.caveats]
        if answer.evidence:
            lines += ["", "**Evidence:**"]
            for e in answer.evidence:
                lines.append(f"- {e}")
        return "\n".join(lines)
