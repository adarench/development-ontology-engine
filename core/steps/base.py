from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class ProvenanceSummary:
    """Records which steps in a pipeline were deterministic vs probabilistic.

    Attached to Tool output so that LLMs (and ultimately users) can understand
    which parts of an answer are certain vs estimated.

    Both deterministic_steps and probabilistic_steps store dicts with at least
    "step" (display name) and "description" keys.
    """

    deterministic_steps: list[dict] = field(default_factory=list)
    probabilistic_steps: list[dict] = field(default_factory=list)

    def record(self, step: "ToolStep") -> None:
        if step.step_type == "deterministic":
            self.deterministic_steps.append(step.provenance_metadata())
        else:
            self.probabilistic_steps.append(step.provenance_metadata())

    def to_markdown(self) -> str:
        if not self.deterministic_steps and not self.probabilistic_steps:
            return ""
        lines = ["## Data Provenance", ""]
        if self.deterministic_steps:
            lines.append("**Certain (deterministic):**")
            for s in self.deterministic_steps:
                desc = f" — {s['description']}" if s.get("description") else ""
                lines.append(f"- {s['step']}{desc}")
        if self.probabilistic_steps:
            if self.deterministic_steps:
                lines.append("")
            lines.append("**Estimated (probabilistic):**")
            for s in self.probabilistic_steps:
                badge = {"heuristic": "~", "llm": "✦", "ml": "◈"}.get(
                    s.get("probabilistic_type", "heuristic"), "~"
                )
                conf = s.get("confidence_level", 0.5)
                desc = f" — {s['description']}" if s.get("description") else ""
                lines.append(
                    f"- {badge} **{s['step']}**{desc} "
                    f"(confidence: {conf:.0%}, type: {s.get('probabilistic_type', 'heuristic')})"
                )
                for cav in s.get("caveats", []):
                    lines.append(f"  - ⚠ {cav}")
        return "\n".join(lines)

    def has_probabilistic(self) -> bool:
        return len(self.probabilistic_steps) > 0

    def to_dict(self) -> dict:
        return {
            "deterministic_steps": list(self.deterministic_steps),
            "probabilistic_steps": list(self.probabilistic_steps),
        }


class ToolStep:
    """Base class for all pipeline steps.

    Subclass DeterministicToolStep or ProbabilisticToolStep — do not extend
    ToolStep directly unless the step type is genuinely unknown.

    Class attributes:
        name:        display name shown in provenance and LLM context
        description: one-line description of what this step does
    """

    step_type: ClassVar[str] = "deterministic"
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def run(self, data: Any = None) -> Any:
        raise NotImplementedError

    @classmethod
    def provenance_metadata(cls) -> dict:
        return {
            "step": cls.name or cls.__name__,
            "description": cls.description,
            "step_type": cls.step_type,
        }


class DeterministicToolStep(ToolStep):
    """A step whose output is fully determined by its input.

    Same input always produces the same output. No estimation, no ML, no LLM.
    Examples: GL normalization, account bucketing, lot-key assignment, joins.
    """

    step_type: ClassVar[str] = "deterministic"

    @classmethod
    def provenance_metadata(cls) -> dict:
        return {
            "step": cls.name or cls.__name__,
            "description": cls.description,
            "step_type": "deterministic",
        }


class ProbabilisticToolStep(ToolStep):
    """A step whose output involves estimation, heuristics, ML, or LLM inference.

    Output is approximate and carries explicit confidence metadata. The LLM and
    users should be told which parts of an answer came from probabilistic steps.

    Class attributes to override in subclasses:
        probabilistic_type:   "heuristic" | "llm" | "ml"
        confidence_level:     float 0–1 (class-level default; instances may vary)
        method_description:   one-line plain-English description of the method
        result_caveats:       standard warnings that apply to every output of this step
    """

    step_type: ClassVar[str] = "probabilistic"
    probabilistic_type: ClassVar[str] = "heuristic"
    confidence_level: ClassVar[float] = 0.5
    method_description: ClassVar[str] = ""
    result_caveats: ClassVar[list[str]] = []

    @classmethod
    def provenance_metadata(cls) -> dict:
        return {
            "step":               cls.name or cls.__name__,
            "description":        cls.description,
            "step_type":          "probabilistic",
            "probabilistic_type": cls.probabilistic_type,
            "confidence_level":   cls.confidence_level,
            "method_description": cls.method_description,
            "caveats":            list(cls.result_caveats),
        }
