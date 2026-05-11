"""Render a ContextPack as a deterministic markdown block for an LLM (or a debug UI).

The output is what an LLM caller would feed in as the operational context. It
leads with guardrails, then routed evidence, then general evidence, then a
warnings block, then a lineage manifest.
"""

from __future__ import annotations

from typing import List

from bedrock.contracts import ContextPack, ContextSection


def as_llm_context(pack: ContextPack) -> str:
    """Deterministic LLM-facing render. Same pack -> same string."""
    out: List[str] = []
    out.append(f"# Operational Context Pack `{pack.pack_id}`\n")
    out.append(f"**Query**: {pack.query!r}  \n")
    out.append(
        f"**Tokens**: {pack.token_count}; **truncated**: {pack.truncated}; "
        f"**confidence**: {dict(sorted(pack.confidence_summary.items()))}\n\n"
    )

    grouped = _group_by_kind(pack.sections)

    if grouped["guardrail"]:
        out.append("## Guardrails (READ FIRST)\n\n")
        for s in grouped["guardrail"]:
            out.append(s.text + "\n\n---\n\n")

    if grouped["routed"]:
        out.append("## Routed Evidence\n\n")
        for s in grouped["routed"]:
            out.append(s.text + "\n\n---\n\n")

    if grouped["evidence"]:
        out.append("## Evidence\n\n")
        for s in grouped["evidence"]:
            out.append(s.text + "\n\n---\n\n")

    if pack.semantic_warnings:
        out.append("## Semantic Warnings\n\n")
        for w in pack.semantic_warnings:
            out.append(f"- ⚠ {w}\n")
        out.append("\n")

    if pack.lineage:
        out.append("## Lineage Manifest\n\n")
        out.append("| Source File | sha256 | Cited By |\n")
        out.append("|---|---|---|\n")
        for ref in pack.lineage:
            facts = ", ".join(f"`{f}`" for f in ref.cited_by_facts) or "—"
            content_hash = ref.content_hash or "—"
            out.append(f"| `{ref.source_file}` | `{content_hash}` | {facts} |\n")

    return "".join(out)


def _group_by_kind(sections: List[ContextSection]):
    grouped = {"guardrail": [], "routed": [], "evidence": []}
    for s in sections:
        grouped[s.section_kind].append(s)
    return grouped
