from __future__ import annotations

import json
from dataclasses import asdict

from core.connectors.base import Connector
from core.steps.query_execution import QueryExecutionStep, Answer
from core.tools.base import Tool

DEFAULT_QUESTIONS = [
    "What is the current operating state scope?",
    "How many lots are in each project?",
    "Which projects have strong GL coverage?",
    "What is the stage distribution across projects?",
    "What is the average completion percentage per project?",
    "What does missing cost mean?",
    "What are the current bottlenecks?",
    "What data would most improve the next version?",
]


class QAHarnessTool(Tool):
    """Runs a fixed question set against an operating state and returns an eval report.

    Input:  operating state dict (via connector or data= param)
    Output: markdown eval report string

    Args:
        connector:  FileConnector pointing at operating_state_*.json
        questions:  list of question strings (defaults to DEFAULT_QUESTIONS)
    """

    output_format = "markdown"
    name = "qa_harness"
    description = (
        "Runs a structured set of questions against the operating state and returns "
        "a full eval report with confidence levels. Useful for validating data quality "
        "or getting a comprehensive overview of what the state can and cannot answer."
    )

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of questions. Defaults to the standard 8-question eval set.",
                }
            },
        }

    def __init__(
        self,
        connector: Connector | None = None,
        questions: list[str] | None = None,
    ):
        super().__init__(connector)
        self.questions = questions if questions is not None else DEFAULT_QUESTIONS
        self._step     = QueryExecutionStep()

    def run(self, data=None, **kwargs) -> str:
        if data is None:
            raw = self.connector.fetch()
            state = raw if isinstance(raw, dict) else {}
        elif isinstance(data, str):
            state = json.loads(data)
        else:
            state = data

        answers: list[Answer] = [
            self._step.run({"state": state, "question": q})
            for q in self.questions
        ]
        return self._render(answers, state)

    def _render(self, answers: list[Answer], state: dict) -> str:
        schema = state.get("schema_version", "unknown")
        lines = [
            f"# QA Harness Eval — {schema}",
            "",
            f"Questions: {len(answers)}  |  "
            f"High confidence: {sum(1 for a in answers if a.confidence == 'high')}  |  "
            f"Refused: {sum(1 for a in answers if a.cannot_conclude)}",
            "",
            "---",
            "",
        ]
        for i, answer in enumerate(answers, start=1):
            conf_badge = {
                "high": "✓", "medium": "~", "low": "?", "refused": "✗"
            }.get(answer.confidence, "?")
            lines += [
                f"## Q{i}: {answer.question}",
                "",
                f"**{conf_badge} [{answer.confidence}]** {answer.direct_answer}",
            ]
            if answer.caveats:
                lines += ["", "_Caveats: " + "; ".join(answer.caveats) + "_"]
            if answer.cannot_conclude:
                lines.append("_Cannot conclude from available data._")
            lines.append("")

        return "\n".join(lines)
