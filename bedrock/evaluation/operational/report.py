"""Render an OperationalRunner RunSummary as markdown / JSON.

The report leads with category-level pass/fail so a reader sees which areas of
operational correctness are weakest. Per-scenario detail follows, with the
narrative shown FIRST so readers understand why the test exists before they
see the verdict.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from bedrock.evaluation.operational.runner import RunSummary, ScenarioResult


def as_markdown(summary: RunSummary) -> str:
    out: List[str] = []
    out.append("# Operational Correctness Eval\n\n")
    out.append(
        f"**Pass rate**: {summary.passed}/{summary.total} "
        f"({summary.pass_rate * 100:.0f}%)\n\n"
    )

    out.append("## By category\n\n")
    out.append("| Category | Passed | Failed |\n|---|---|---|\n")
    cat = summary.by_category()
    for c in sorted(cat):
        b = cat[c]
        out.append(f"| `{c}` | {b['passed']} | {b['failed']} |\n")
    out.append("\n")

    out.append("## By assertion type\n\n")
    out.append("| Assertion | Passed | Failed |\n|---|---|---|\n")
    ab = summary.assertion_breakdown()
    for name in sorted(ab):
        b = ab[name]
        out.append(f"| `{name}` | {b['passed']} | {b['failed']} |\n")
    out.append("\n")

    out.append("## Scenarios\n\n")
    for s in summary.scenarios:
        verdict = "✅ PASS" if s.passed else "❌ FAIL"
        out.append(
            f"### {verdict} — `{s.scenario_name}` _(category: {s.category})_\n\n"
        )
        out.append(f"**Narrative**: {s.narrative.strip()}\n\n")
        out.append(f"**Query**: `{s.query}`\n\n")
        if s.error:
            out.append(f"**ERROR**: {s.error}\n\n")
            continue
        out.append(
            f"- pack_id: `{s.pack_id}` | tokens: {s.pack_token_count} | "
            f"truncated: {s.pack_truncated} | sources: {s.sources_used} | "
            f"elapsed: {s.ms_elapsed:.0f} ms\n"
        )
        out.append(f"- assertions: {s.passes} passed, {s.fails} failed\n\n")
        for a in s.assertion_results:
            mark = "✅" if a.passed else "❌"
            out.append(f"  - {mark} `{a.name}` — {a.description}\n")
            out.append(f"    - {a.message}\n")
        out.append("\n")
    return "".join(out)


def as_json(summary: RunSummary) -> str:
    payload: Dict[str, Any] = {
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "pass_rate": summary.pass_rate,
        "by_category": summary.by_category(),
        "by_assertion": summary.assertion_breakdown(),
        "scenarios": [
            {
                "name": s.scenario_name,
                "category": s.category,
                "narrative": s.narrative,
                "query": s.query,
                "passed": s.passed,
                "passes": s.passes,
                "fails": s.fails,
                "pack_id": s.pack_id,
                "pack_token_count": s.pack_token_count,
                "pack_truncated": s.pack_truncated,
                "sources_used": s.sources_used,
                "ms_elapsed": s.ms_elapsed,
                "error": s.error,
                "assertions": [
                    {
                        "name": a.name,
                        "description": a.description,
                        "passed": a.passed,
                        "message": a.message,
                        "evidence": a.evidence,
                    }
                    for a in s.assertion_results
                ],
            }
            for s in summary.scenarios
        ],
    }
    return json.dumps(payload, indent=2, default=str)
