from __future__ import annotations

from core.steps.base import DeterministicToolStep, ProbabilisticToolStep
from core.steps.registry import StepRegistry


@StepRegistry.register
class ScriptStep(DeterministicToolStep):
    """A deterministic step that executes a user-supplied ``def run(input): ...`` function.

    JSON config keys:
        code:        required — function string defining ``def run(input): ...``
        name:        display name shown in provenance (defaults to "ScriptStep")
        description: one-line description of what the script does
    """

    def __init__(self, code: str, name: str = "", description: str = ""):
        self._step_name = name or "ScriptStep"
        self._step_description = description
        self._run_fn = _compile(code)

    def run(self, data=None):
        return self._run_fn(data)

    def provenance_metadata(self) -> dict:
        return {
            "step": self._step_name,
            "description": self._step_description,
            "step_type": "deterministic",
        }


@StepRegistry.register
class ProbabilisticScriptStep(ProbabilisticToolStep):
    """A probabilistic step that executes a user-supplied ``def run(input): ...`` function.

    JSON config keys:
        code:                required — function string defining ``def run(input): ...``
        name:                display name shown in provenance
        description:         one-line description of what the script does
        probabilistic_type:  "heuristic" | "llm" | "ml"  (default: "heuristic")
        confidence_level:    float 0–1  (default: 0.5)
        method_description:  one-line description of the estimation method
        result_caveats:      list of warning strings
    """

    def __init__(
        self,
        code: str,
        name: str = "",
        description: str = "",
        probabilistic_type: str = "heuristic",
        confidence_level: float = 0.5,
        method_description: str = "",
        result_caveats: list[str] | None = None,
    ):
        self._step_name = name or "ProbabilisticScriptStep"
        self._step_description = description
        self._probabilistic_type = probabilistic_type
        self._confidence_level = confidence_level
        self._method_description = method_description
        self._result_caveats = result_caveats or []
        self._run_fn = _compile(code)

    def run(self, data=None):
        return self._run_fn(data)

    def provenance_metadata(self) -> dict:
        return {
            "step":               self._step_name,
            "description":        self._step_description,
            "step_type":          "probabilistic",
            "probabilistic_type": self._probabilistic_type,
            "confidence_level":   self._confidence_level,
            "method_description": self._method_description,
            "caveats":            list(self._result_caveats),
        }


_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "chr": chr,
    "dict": dict, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "format": format,
    "frozenset": frozenset, "getattr": getattr, "hasattr": hasattr,
    "hash": hash, "int": int, "isinstance": isinstance,
    "issubclass": issubclass, "iter": iter, "len": len, "list": list,
    "map": map, "max": max, "min": min, "next": next, "None": None,
    "ord": ord, "pow": pow, "range": range, "repr": repr,
    "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
    "type": type, "zip": zip,
    "True": True, "False": False,
}


def _compile(code: str):
    namespace: dict = {"__builtins__": _SAFE_BUILTINS}
    exec(code, namespace)  # noqa: S102
    run_fn = namespace.get("run")
    if run_fn is None:
        raise KeyError("Script code must define a function named 'run'")
    return run_fn
