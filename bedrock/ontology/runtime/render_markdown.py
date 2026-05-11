"""Render YAML ontology specs back into human-readable markdown views.

Markdown views land under ontology/generated/. CI uses --check to assert
that committed markdown matches the YAML; any drift fails the build.

CLI:
    python -m bedrock.ontology.runtime.render_markdown                 # write generated MD
    python -m bedrock.ontology.runtime.render_markdown --check         # exit 1 if drift
    python -m bedrock.ontology.runtime.render_markdown --root ontology --out ontology/generated
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import List, Optional

from bedrock.ontology.runtime.loader import OntologyRegistry
from bedrock.ontology.runtime.schema import (
    EntitySpec,
    MetricSpec,
    RelationshipSpec,
)


HEADER = (
    "<!-- Generated from ontology/{kind}/{name}.yaml by "
    "bedrock.ontology.runtime.render_markdown. Do not edit by hand. -->\n\n"
)


def render_entity(spec: EntitySpec) -> str:
    out: List[str] = [HEADER.format(kind="entities", name=spec.entity_type)]
    out.append(f"# {spec.canonical_name}\n")
    out.append(f"**Entity type**: `{spec.entity_type}`  \n")
    out.append(f"**Vertical**: `{spec.vertical}`  \n")
    out.append(f"**Schema version**: `{spec.schema_version}`\n\n")
    out.append("## Description\n\n")
    out.append(spec.business_description.strip() + "\n\n")

    if spec.retrieval_tags:
        out.append("## Retrieval Tags\n\n")
        out.append(", ".join(f"`{t}`" for t in spec.retrieval_tags) + "\n\n")

    if spec.source_lineage:
        out.append("## Source Lineage\n\n")
        for s in spec.source_lineage:
            out.append(f"- `{s}`\n")
        out.append("\n")

    if spec.example_queries:
        out.append("## Example Queries\n\n")
        for q in spec.example_queries:
            out.append(f"- {q}\n")
        out.append("\n")

    out.append("## Field Definitions\n\n")
    out.append("| Field | Type | Nullable | Derived | Description |\n")
    out.append("|---|---|---|---|---|\n")
    for f in spec.field_definitions:
        out.append(
            f"| `{f.name}` | {f.type} | {'yes' if f.nullable else 'no'} | "
            f"{'yes' if f.derived else 'no'} | {f.description.strip()} |\n"
        )
    out.append("\n")

    if any(f.aliases for f in spec.field_definitions):
        out.append("### Field Aliases\n\n")
        for f in spec.field_definitions:
            if f.aliases:
                out.append(f"- `{f.name}` ← {', '.join('`' + a + '`' for a in f.aliases)}\n")
        out.append("\n")

    if spec.semantic_aliases:
        out.append("## Semantic Aliases\n\n")
        for a in spec.semantic_aliases:
            note = f" — {a.note}" if a.note else ""
            out.append(f"- `{a.alias}` → `{a.resolves_to}`{note}\n")
        out.append("\n")

    if spec.relationships:
        out.append("## Relationships\n\n")
        for r in spec.relationships:
            via = f" via `{r.via_field}`" if r.via_field else ""
            out.append(
                f"- **{r.name}** → `{r.target_entity}` ({r.cardinality}){via}: {r.description}\n"
            )
        out.append("\n")

    if spec.approved_join_paths:
        out.append("## Approved Join Paths\n\n")
        for j in spec.approved_join_paths:
            keys = ", ".join(f"`{k}`" for k in j.join_keys)
            note = f"  \n  _{j.note.strip()}_" if j.note else ""
            out.append(f"- **{j.name}** → `{j.target_entity}` ({j.cardinality}) on {keys}{note}\n")
        out.append("\n")

    if spec.confidence_rules:
        out.append("## Confidence Rules\n\n")
        for c in spec.confidence_rules:
            out.append(f"- `{c.field}` → **{c.confidence}** — {c.reason.strip()}\n")
        out.append("\n")

    if spec.validation_rules:
        out.append("## Validation Rules\n\n")
        for v in spec.validation_rules:
            out.append(f"- **{v.name}** _(severity: {v.severity})_: {v.rule.strip()}\n")
        out.append("\n")

    if spec.semantic_warnings:
        out.append("## Semantic Warnings\n\n")
        for w in spec.semantic_warnings:
            out.append(f"- **{w.name}** (applies to `{w.applies_to}`): {w.message.strip()}\n")
        out.append("\n")

    out.append("## Embedding Payload Template\n\n")
    out.append("```text\n")
    out.append(spec.embedding_payload.template.rstrip() + "\n")
    out.append("```\n\n")
    if spec.embedding_payload.fields_to_include:
        fields = ", ".join(f"`{f}`" for f in spec.embedding_payload.fields_to_include)
        out.append(f"**Fields to include**: {fields}\n\n")

    if spec.historical_behavior:
        out.append("## Historical Behavior\n\n")
        out.append(spec.historical_behavior.strip() + "\n")

    return "".join(out)


def render_relationship(spec: RelationshipSpec) -> str:
    out: List[str] = [HEADER.format(kind="relationships", name=spec.name)]
    out.append(f"# Relationship: {spec.name}\n\n")
    out.append(f"- **Source entity**: `{spec.source_entity}`\n")
    out.append(f"- **Target entity**: `{spec.target_entity}`\n")
    out.append(f"- **Cardinality**: `{spec.cardinality}`\n")
    out.append(f"- **Confidence**: `{spec.confidence}`\n")
    out.append(f"- **Join keys**: {', '.join('`' + k + '`' for k in spec.join_keys)}\n\n")
    out.append("## Description\n\n")
    out.append(spec.description.strip() + "\n")
    if spec.semantic_warnings:
        out.append("\n## Semantic Warnings\n\n")
        for w in spec.semantic_warnings:
            out.append(f"- **{w.name}**: {w.message.strip()}\n")
    return "".join(out)


def render_metric(spec: MetricSpec) -> str:
    out: List[str] = [HEADER.format(kind="metrics", name=spec.name)]
    out.append(f"# Metric: {spec.name}\n\n")
    out.append(f"- **Unit**: `{spec.unit}`\n")
    out.append(f"- **Confidence**: `{spec.confidence}`\n")
    if spec.source_definition:
        out.append(f"- **Source definition**: `{spec.source_definition}`\n")
    if spec.aliases:
        out.append(f"- **Aliases**: {', '.join('`' + a + '`' for a in spec.aliases)}\n")
    out.append("\n## Description\n\n")
    out.append(spec.description.strip() + "\n\n")
    out.append("## Formula\n\n")
    out.append("```\n")
    out.append(spec.formula.rstrip() + "\n")
    out.append("```\n\n")
    out.append("## Inputs\n\n")
    for i in spec.inputs:
        out.append(f"- `{i}`\n")
    if spec.notes:
        out.append("\n## Notes\n\n")
        for k, v in spec.notes.items():
            out.append(f"- **{k}**: {str(v).strip()}\n")
    return "".join(out)


def render_all(reg: OntologyRegistry, out_root: Path) -> List[Path]:
    """Render every spec to a file under out_root. Returns the list of paths written."""
    written: List[Path] = []
    entities_dir = out_root / "entities"
    relationships_dir = out_root / "relationships"
    metrics_dir = out_root / "metrics"
    entities_dir.mkdir(parents=True, exist_ok=True)
    relationships_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    for k, spec in sorted(reg.entities.items()):
        path = entities_dir / f"{k}.md"
        path.write_text(render_entity(spec))
        written.append(path)
    for k, spec in sorted(reg.relationships.items()):
        path = relationships_dir / f"{k}.md"
        path.write_text(render_relationship(spec))
        written.append(path)
    for k, spec in sorted(reg.metrics.items()):
        path = metrics_dir / f"{k}.md"
        path.write_text(render_metric(spec))
        written.append(path)
    return written


def check_drift(reg: OntologyRegistry, out_root: Path) -> List[str]:
    """Return list of human-readable diff messages; empty list means no drift."""
    diffs: List[str] = []

    def _check(path: Path, expected: str) -> None:
        if not path.exists():
            diffs.append(f"MISSING: {path} (expected to be present)")
            return
        actual = path.read_text()
        if actual != expected:
            diff = "".join(
                difflib.unified_diff(
                    actual.splitlines(keepends=True),
                    expected.splitlines(keepends=True),
                    fromfile=f"committed: {path}",
                    tofile=f"expected: {path}",
                    n=2,
                )
            )
            diffs.append(f"DRIFT: {path}\n{diff}")

    for k, spec in reg.entities.items():
        _check(out_root / "entities" / f"{k}.md", render_entity(spec))
    for k, spec in reg.relationships.items():
        _check(out_root / "relationships" / f"{k}.md", render_relationship(spec))
    for k, spec in reg.metrics.items():
        _check(out_root / "metrics" / f"{k}.md", render_metric(spec))

    return diffs


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render YAML ontology specs as markdown.")
    parser.add_argument("--root", type=Path, default=Path("ontology"))
    parser.add_argument(
        "--out", type=Path, default=Path("ontology/generated"), help="Where to write MD files"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 if committed MD differs from rendered.",
    )
    args = parser.parse_args(argv)

    reg = OntologyRegistry.load(args.root)

    if args.check:
        diffs = check_drift(reg, args.out)
        if diffs:
            for d in diffs:
                print(d, file=sys.stderr)
            print(f"\nFAILED: {len(diffs)} drift(s) detected.", file=sys.stderr)
            return 1
        print(f"OK: {len(reg.entities) + len(reg.relationships) + len(reg.metrics)} files match.")
        return 0

    written = render_all(reg, args.out)
    for p in written:
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
