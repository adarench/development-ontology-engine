from __future__ import annotations
from dataclasses import dataclass, field

from core.steps.base import DeterministicToolStep


@dataclass
class Answer:
    question: str
    direct_answer: str
    evidence: list[dict] = field(default_factory=list)
    confidence: str = "medium"      # "high" | "medium" | "low" | "refused"
    caveats: list[str] = field(default_factory=list)
    cannot_conclude: bool = False
    source_files_used: list[str] = field(default_factory=list)


class QueryExecutionStep(DeterministicToolStep):
    """Executes a single question against an operating state dict.

    Input:  dict with keys:
              "state"    — operating state dict (from OperatingStateTool)
              "question" — str question to answer
    Output: Answer dataclass

    Dispatches to a registered handler by matching question text against
    registered trigger phrases. Falls back to a keyword search over the
    state's companion text when no handler matches.

    To add question handlers at runtime, call register_handler():
        step.register_handler(trigger="which projects", fn=my_handler)
    """

    def __init__(self):
        self._handlers: list[tuple[str, callable]] = []
        self._register_defaults()

    def register_handler(self, trigger: str, fn: callable) -> None:
        self._handlers.append((trigger.lower(), fn))

    def run(self, data: dict) -> Answer:
        state    = data.get("state", {})
        question = str(data.get("question", "")).strip()

        for trigger, fn in self._handlers:
            if trigger in question.lower():
                return fn(state, question)

        return self._fallback(state, question)

    # ------------------------------------------------------------------
    # Default handlers
    # ------------------------------------------------------------------

    def _register_defaults(self) -> None:
        self.register_handler("how many lots",     self._q_lot_counts)
        self.register_handler("which projects",    self._q_project_list)
        self.register_handler("stage distribution", self._q_stage_dist)
        self.register_handler("completion",        self._q_completion)
        self.register_handler("cost",              self._q_cost)
        self.register_handler("scope",             self._q_scope)
        self.register_handler("bottleneck",        self._q_bottleneck)

    def _q_lot_counts(self, state: dict, question: str) -> Answer:
        projects = state.get("projects", [])
        evidence = [
            {"project": p["project_code"], "lots": p.get("lots_total", 0)}
            for p in projects
        ]
        total = sum(e["lots"] for e in evidence)
        return Answer(
            question=question,
            direct_answer=f"There are {total} total lots across {len(projects)} projects.",
            evidence=evidence,
            confidence="high",
            source_files_used=["operating_state_v1.json"],
        )

    def _q_project_list(self, state: dict, question: str) -> Answer:
        projects = [p["project_code"] for p in state.get("projects", [])]
        return Answer(
            question=question,
            direct_answer=f"Projects in scope: {', '.join(projects)}.",
            evidence=[{"projects": projects}],
            confidence="high",
            source_files_used=["operating_state_v1.json"],
        )

    def _q_stage_dist(self, state: dict, question: str) -> Answer:
        evidence = [
            {
                "project": p["project_code"],
                "stage_distribution": p.get("stage_distribution", "n/a"),
            }
            for p in state.get("projects", [])
        ]
        return Answer(
            question=question,
            direct_answer="Stage distributions by project: "
                          + "; ".join(f"{e['project']}: {e['stage_distribution']}" for e in evidence),
            evidence=evidence,
            confidence="high",
            source_files_used=["operating_state_v1.json"],
        )

    def _q_completion(self, state: dict, question: str) -> Answer:
        evidence = [
            {
                "project": p["project_code"],
                "avg_completion_pct": round(p.get("avg_completion_pct", 0) * 100, 1),
            }
            for p in state.get("projects", [])
        ]
        return Answer(
            question=question,
            direct_answer="Average completion by project: "
                          + "; ".join(f"{e['project']}: {e['avg_completion_pct']}%" for e in evidence),
            evidence=evidence,
            confidence="high",
            source_files_used=["operating_state_v1.json"],
        )

    def _q_cost(self, state: dict, question: str) -> Answer:
        evidence = []
        for p in state.get("projects", []):
            fin = p.get("financials", {})
            cost = fin.get("project_total_cost", None)
            evidence.append({
                "project":    p["project_code"],
                "gl_entity":  fin.get("gl_entity"),
                "cost":       cost,
                "confidence": fin.get("financial_confidence", "unknown"),
            })
        no_cost = [e["project"] for e in evidence if not e["cost"]]
        caveats = []
        if no_cost:
            caveats.append(
                f"Missing cost ≠ $0. Projects with no GL data: {', '.join(no_cost)}."
            )
        return Answer(
            question=question,
            direct_answer="Project costs: "
                          + "; ".join(
                              f"{e['project']}: ${e['cost']:,.0f} ({e['confidence']})"
                              if e["cost"] else f"{e['project']}: unknown (no GL)"
                              for e in evidence
                          ),
            evidence=evidence,
            confidence="medium",
            caveats=caveats,
            source_files_used=["operating_state_v1.json"],
        )

    def _q_scope(self, state: dict, question: str) -> Answer:
        dq = state.get("data_quality", {})
        return Answer(
            question=question,
            direct_answer=(
                f"Schema: {state.get('schema_version', 'unknown')}. "
                f"Projects: {dq.get('projects_total', '?')}. "
                f"Lots: {dq.get('lots_total', '?')}."
            ),
            confidence="high",
            source_files_used=["operating_state_v1.json"],
        )

    def _q_bottleneck(self, state: dict, question: str) -> Answer:
        bottlenecks = []
        for p in state.get("projects", []):
            for ph in p.get("phases", []):
                if ph.get("lots_in_phase", 0) >= 5 and ph.get("avg_completion_pct", 1.0) < 0.6:
                    bottlenecks.append({
                        "phase":         ph.get("phase_id_estimated"),
                        "lots":          ph["lots_in_phase"],
                        "dominant_stage": ph.get("dominant_stage"),
                        "avg_pct":       round(ph["avg_completion_pct"] * 100, 1),
                    })
        if not bottlenecks:
            return Answer(
                question=question,
                direct_answer="No bottlenecks detected at current thresholds (≥5 lots, <60% complete).",
                confidence="medium",
            )
        return Answer(
            question=question,
            direct_answer="Bottleneck phases: "
                          + "; ".join(
                              f"{b['phase']} ({b['lots']} lots at {b['dominant_stage']}, {b['avg_pct']}%)"
                              for b in bottlenecks
                          ),
            evidence=bottlenecks,
            confidence="medium",
            source_files_used=["operating_state_v1.json"],
        )

    def _fallback(self, state: dict, question: str) -> Answer:
        return Answer(
            question=question,
            direct_answer="No handler matched this question. Try asking about lots, projects, stages, completion, cost, scope, or bottlenecks.",
            confidence="low",
            cannot_conclude=True,
        )
