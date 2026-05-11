"""OperationalRunner — runs scenarios through the orchestrator + packer + assertions.

The runner does NOT make pass/fail judgments beyond what each individual
assertion reports. Aggregation is per-scenario, per-category, per-assertion-name —
all visible in the report. Failures are not crashes; they are data points
the operational eval is designed to surface.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bedrock.evaluation.operational.assertions import AssertionResult
from bedrock.evaluation.operational.scenarios import (
    OperationalScenario,
    SCENARIOS,
)
from bedrock.retrieval.orchestration import HybridOrchestrator, RRFFuser
from bedrock.retrieval.packing import pack as build_pack
from bedrock.retrieval.retrievers.chunk_source import ChunkSource
from bedrock.retrieval.retrievers.entity_source import EntitySource
from bedrock.retrieval.retrievers.routed_source import RoutedSource
from bedrock.retrieval.services.entity_retriever import default_retriever


@dataclass
class ScenarioResult:
    scenario_name: str
    category: str
    narrative: str
    query: str
    assertion_results: List[AssertionResult] = field(default_factory=list)
    pack_id: Optional[str] = None
    pack_token_count: int = 0
    pack_truncated: bool = False
    sources_used: List[str] = field(default_factory=list)
    ms_elapsed: float = 0.0
    error: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(a.passed for a in self.assertion_results)

    @property
    def passes(self) -> int:
        return sum(1 for a in self.assertion_results if a.passed)

    @property
    def fails(self) -> int:
        return sum(1 for a in self.assertion_results if not a.passed)


@dataclass
class RunSummary:
    scenarios: List[ScenarioResult]

    @property
    def total(self) -> int:
        return len(self.scenarios)

    @property
    def passed(self) -> int:
        return sum(1 for s in self.scenarios if s.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        return self.passed / max(self.total, 1)

    def by_category(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for s in self.scenarios:
            bucket = out.setdefault(s.category, {"total": 0, "passed": 0, "failed": 0})
            bucket["total"] += 1
            if s.passed:
                bucket["passed"] += 1
            else:
                bucket["failed"] += 1
        return out

    def assertion_breakdown(self) -> Dict[str, Dict[str, int]]:
        """Per-assertion-name pass/fail counts across all scenarios."""
        out: Dict[str, Dict[str, int]] = {}
        for s in self.scenarios:
            for a in s.assertion_results:
                bucket = out.setdefault(a.name, {"passed": 0, "failed": 0})
                if a.passed:
                    bucket["passed"] += 1
                else:
                    bucket["failed"] += 1
        return out


class OperationalRunner:
    """Runs scenarios through the standard orchestrator + packer."""

    def __init__(self, orchestrator: Optional[HybridOrchestrator] = None) -> None:
        self.orchestrator = orchestrator or _default_orchestrator()

    def run(
        self,
        scenarios: Optional[List[OperationalScenario]] = None,
    ) -> RunSummary:
        scenarios = scenarios if scenarios is not None else SCENARIOS
        results: List[ScenarioResult] = []
        for sc in scenarios:
            results.append(self._run_one(sc))
        return RunSummary(scenarios=results)

    def _run_one(self, scenario: OperationalScenario) -> ScenarioResult:
        t0 = time.time()
        try:
            res = self.orchestrator.retrieve(
                query=scenario.query, top_k=scenario.top_k
            )
            pack_obj = build_pack(
                hits=res.hits,
                query=scenario.query,
                budget_tokens=scenario.budget_tokens,
                extra_warnings=_warnings_from_trace(res.trace),
            )
        except Exception as e:
            return ScenarioResult(
                scenario_name=scenario.name,
                category=scenario.category,
                narrative=scenario.narrative,
                query=scenario.query,
                ms_elapsed=(time.time() - t0) * 1000,
                error=f"{type(e).__name__}: {e}",
            )

        assertion_results = [
            a.check(scenario.query, res.hits, pack_obj, res.trace)
            for a in scenario.assertions
        ]
        return ScenarioResult(
            scenario_name=scenario.name,
            category=scenario.category,
            narrative=scenario.narrative,
            query=scenario.query,
            assertion_results=assertion_results,
            pack_id=pack_obj.pack_id,
            pack_token_count=pack_obj.token_count,
            pack_truncated=pack_obj.truncated,
            sources_used=list(res.trace.sources_used),
            ms_elapsed=(time.time() - t0) * 1000,
        )


def _default_orchestrator() -> HybridOrchestrator:
    return HybridOrchestrator(
        retrievers=[
            EntitySource(default_retriever()),
            ChunkSource(),
            RoutedSource(),
        ],
        fuser=RRFFuser(),
    )


def _warnings_from_trace(trace) -> List[str]:
    out: List[str] = []
    for src_name, src_trace in trace.per_source.items():
        for n in src_trace.notes:
            if n.startswith("[") or any(
                k in n.lower()
                for k in ("inferred", "warning", "caveat", "do not promote")
            ):
                out.append(f"[from {src_name}] {n}")
    return out
