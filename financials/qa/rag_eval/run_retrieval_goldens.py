"""Retrieval-only golden eval — no LLM, no API keys.

Loads `retrieval_goldens.json` and runs each query against:
  - the routed/lexical chunk index (always available)
  - the EntityRetriever (only if `output/bedrock/entity_index.parquet` exists)

For each golden, computes recall over expected_source_files,
expected_route_rules, and expected_entity_ids. Writes a deterministic
markdown report to `output/rag_eval/retrieval_goldens_report.md` and a
JSON sidecar to `output/rag_eval/retrieval_goldens_report.json`.

Exit code is 0 on success (regardless of pass rate) so this can be
called from CI / wrappers and the report inspected; non-zero only on
infrastructure failure (missing goldens file, malformed JSON, etc.).

Usage:
    python financials/qa/rag_eval/run_retrieval_goldens.py
    python financials/qa/rag_eval/run_retrieval_goldens.py --top-k 12
    python financials/qa/rag_eval/run_retrieval_goldens.py --no-entity
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
# Ensure the repo root is importable when this file is invoked directly
# (`python financials/qa/rag_eval/run_retrieval_goldens.py`) rather than via
# `python -m`. Idempotent — no-op if already on sys.path.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_GOLDENS = REPO_ROOT / "financials" / "qa" / "rag_eval" / "retrieval_goldens.json"
DEFAULT_REPORT_MD = REPO_ROOT / "output" / "rag_eval" / "retrieval_goldens_report.md"
DEFAULT_REPORT_JSON = REPO_ROOT / "output" / "rag_eval" / "retrieval_goldens_report.json"
DEFAULT_ENTITY_INDEX = REPO_ROOT / "output" / "bedrock" / "entity_index.parquet"


@dataclass
class GoldenResult:
    id: str
    query: str
    files_expected: List[str]
    files_found: List[str]
    files_missing: List[str]
    rules_expected: List[str]
    rules_found: List[str]
    rules_missing: List[str]
    entities_expected: List[str]
    entities_found: List[str]
    entities_missing: List[str]
    entity_status: str  # "ok" | "skipped:no-index" | "skipped:by-flag"
    notes: str = ""

    @property
    def files_pass(self) -> bool:
        return not self.files_missing

    @property
    def rules_pass(self) -> bool:
        return not self.rules_missing

    @property
    def entities_pass(self) -> bool:
        if self.entity_status != "ok":
            return True  # not counted as fail when skipped
        return not self.entities_missing

    @property
    def overall_pass(self) -> bool:
        return self.files_pass and self.rules_pass and self.entities_pass


def _load_goldens(path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    data = json.loads(path.read_text())
    goldens = data.get("goldens") or []
    if not isinstance(goldens, list):
        raise ValueError(f"{path}: 'goldens' must be a list")
    return data, goldens


def _eval_routed(idx, query: str, top_k: int) -> Tuple[List[str], List[str]]:
    """Return (matched_rule_names, files_in_top_k) for the routed+lexical hybrid."""
    from financials.qa.llm_eval.route_retrieval import build_routed_evidence

    hits, rule_names = build_routed_evidence(idx, query, max_total=top_k)
    files = sorted({h.chunk.file for h in hits})
    return rule_names, files


def _eval_entity(retriever, query: str, top_k: int) -> List[str]:
    res = retriever.retrieve(query=query, top_k=top_k)
    return [h.entity.entity_id for h in res.hits]


def run(
    goldens_path: Path = DEFAULT_GOLDENS,
    report_md: Path = DEFAULT_REPORT_MD,
    report_json: Path = DEFAULT_REPORT_JSON,
    top_k: int = 9,
    use_entity: bool = True,
) -> int:
    if not goldens_path.exists():
        print(f"ERROR: goldens file not found at {goldens_path}", file=sys.stderr)
        return 2

    meta, goldens = _load_goldens(goldens_path)
    print(f"[goldens] loaded {len(goldens)} goldens from {goldens_path}")

    # Build the lexical index once.
    from financials.qa.rag_eval.retrieval_index import build_index

    t0 = time.time()
    idx = build_index()
    t_idx = (time.time() - t0) * 1000.0
    print(f"[goldens] lexical index ready in {t_idx:.0f} ms ({idx.n()} chunks)")

    # Entity retriever — only if index exists AND --no-entity not set.
    entity_retriever = None
    entity_status: str
    if not use_entity:
        entity_status = "skipped:by-flag"
    elif not DEFAULT_ENTITY_INDEX.exists():
        entity_status = "skipped:no-index"
    else:
        try:
            from bedrock.retrieval.services.entity_retriever import default_retriever

            entity_retriever = default_retriever()
            entity_status = "ok"
            n_aliases = getattr(entity_retriever, "_aliases_loaded_count", 0)
            total = len(getattr(entity_retriever, "_alias_table", {}))
            print(
                f"[goldens] entity retriever ready (alias table: {total} entries, "
                f"{n_aliases} from state/aliases.json)"
            )
        except (ImportError, FileNotFoundError, RuntimeError) as e:
            entity_status = f"skipped:error:{type(e).__name__}"

    results: List[GoldenResult] = []
    for g in goldens:
        gid = str(g.get("id") or "<no-id>")
        query = str(g.get("query") or "")
        files_exp = [str(x) for x in (g.get("expected_source_files") or [])]
        rules_exp = [str(x) for x in (g.get("expected_route_rules") or [])]
        ents_exp = [str(x) for x in (g.get("expected_entity_ids") or [])]
        notes = str(g.get("notes") or "")

        rule_names, files_found = _eval_routed(idx, query, top_k=top_k)
        files_missing = [f for f in files_exp if f not in files_found]
        rules_missing = [r for r in rules_exp if r not in rule_names]

        if entity_status == "ok" and entity_retriever is not None:
            ents_found = _eval_entity(entity_retriever, query, top_k=top_k)
            ents_missing = [e for e in ents_exp if e not in ents_found]
            this_entity_status = "ok"
        else:
            ents_found = []
            ents_missing = []
            this_entity_status = entity_status

        results.append(
            GoldenResult(
                id=gid,
                query=query,
                files_expected=files_exp,
                files_found=files_found,
                files_missing=files_missing,
                rules_expected=rules_exp,
                rules_found=rule_names,
                rules_missing=rules_missing,
                entities_expected=ents_exp,
                entities_found=ents_found,
                entities_missing=ents_missing,
                entity_status=this_entity_status,
                notes=notes,
            )
        )

    _write_reports(
        results,
        report_md=report_md,
        report_json=report_json,
        top_k=top_k,
        entity_status=entity_status,
        meta=meta,
    )

    total = len(results)
    passed = sum(1 for r in results if r.overall_pass)
    print(f"[goldens] {passed}/{total} goldens pass (overall)")
    print(f"[goldens] report: {report_md}")
    return 0


def _write_reports(
    results: List[GoldenResult],
    report_md: Path,
    report_json: Path,
    top_k: int,
    entity_status: str,
    meta: Dict[str, Any],
) -> None:
    report_md.parent.mkdir(parents=True, exist_ok=True)

    total = len(results)
    pass_overall = sum(1 for r in results if r.overall_pass)
    pass_files = sum(1 for r in results if r.files_pass)
    pass_rules = sum(1 for r in results if r.rules_pass)
    pass_ents = sum(
        1 for r in results if r.entity_status == "ok" and r.entities_pass
    )
    n_ent_evaluated = sum(1 for r in results if r.entity_status == "ok")

    lines: List[str] = []
    lines.append("# Retrieval golden eval — BCPD v0.1")
    lines.append("")
    lines.append(f"- goldens file: `{DEFAULT_GOLDENS.relative_to(REPO_ROOT)}`")
    lines.append(f"- top_k: {top_k}")
    lines.append(f"- entity layer: **{entity_status}**")
    lines.append(f"- total goldens: **{total}**")
    lines.append(f"- overall pass: **{pass_overall}/{total}**")
    lines.append(f"- files recall pass: **{pass_files}/{total}**")
    lines.append(f"- routed-rule recall pass: **{pass_rules}/{total}**")
    if n_ent_evaluated:
        lines.append(
            f"- entity-id recall pass: **{pass_ents}/{n_ent_evaluated}** "
            f"(evaluated only when entity layer is available)"
        )
    else:
        lines.append(
            f"- entity-id recall pass: not evaluated (entity layer status = {entity_status})"
        )
    lines.append("")
    lines.append("## Per-golden results")
    lines.append("")
    lines.append(
        "| id | overall | files | rules | entities | query |"
    )
    lines.append(
        "|----|---------|-------|-------|----------|-------|"
    )
    for r in results:
        ov = "✅" if r.overall_pass else "❌"
        fp = "✅" if r.files_pass else "❌"
        rp = "✅" if r.rules_pass else "❌"
        if r.entity_status == "ok":
            ep = "✅" if r.entities_pass else "❌"
        else:
            ep = f"⊘ ({r.entity_status})"
        q = r.query.replace("|", "\\|")
        lines.append(f"| `{r.id}` | {ov} | {fp} | {rp} | {ep} | {q} |")
    lines.append("")

    # Detail blocks for any failures.
    failures = [r for r in results if not r.overall_pass]
    if failures:
        lines.append("## Failures — detail")
        lines.append("")
        for r in failures:
            lines.append(f"### {r.id}")
            lines.append(f"**Query:** {r.query}")
            if r.files_missing:
                lines.append(
                    f"- **files missing from top-{top_k}:** "
                    + ", ".join(f"`{f}`" for f in r.files_missing)
                )
            if r.rules_missing:
                lines.append(
                    f"- **routed rules missing:** "
                    + ", ".join(f"`{x}`" for x in r.rules_missing)
                )
            if r.entity_status == "ok" and r.entities_missing:
                lines.append(
                    f"- **entity ids missing:** "
                    + ", ".join(f"`{e}`" for e in r.entities_missing)
                )
            if r.notes:
                lines.append(f"- _notes:_ {r.notes}")
            lines.append("")

    report_md.write_text("\n".join(lines) + "\n")

    sidecar: Dict[str, Any] = {
        "schema_version": "v0.1",
        "top_k": top_k,
        "entity_status": entity_status,
        "summary": {
            "total": total,
            "overall_pass": pass_overall,
            "files_pass": pass_files,
            "rules_pass": pass_rules,
            "entities_pass": pass_ents,
            "entities_evaluated": n_ent_evaluated,
        },
        "goldens_meta": {k: meta.get(k) for k in ("schema_version", "purpose")},
        "results": [
            {
                "id": r.id,
                "query": r.query,
                "overall_pass": r.overall_pass,
                "files_pass": r.files_pass,
                "rules_pass": r.rules_pass,
                "entity_status": r.entity_status,
                "entities_pass": r.entities_pass,
                "files_expected": r.files_expected,
                "files_missing": r.files_missing,
                "files_found": r.files_found,
                "rules_expected": r.rules_expected,
                "rules_missing": r.rules_missing,
                "rules_found": r.rules_found,
                "entities_expected": r.entities_expected,
                "entities_missing": r.entities_missing,
                "entities_found": r.entities_found,
            }
            for r in results
        ],
    }
    report_json.write_text(json.dumps(sidecar, indent=2, sort_keys=True))


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    p.add_argument("--goldens", type=Path, default=DEFAULT_GOLDENS)
    p.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    p.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    p.add_argument("--top-k", type=int, default=9)
    p.add_argument(
        "--no-entity",
        action="store_true",
        help="Skip the entity-retriever layer even if the index is available.",
    )
    args = p.parse_args(argv)

    return run(
        goldens_path=args.goldens,
        report_md=args.report_md,
        report_json=args.report_json,
        top_k=args.top_k,
        use_entity=(not args.no_entity),
    )


if __name__ == "__main__":
    raise SystemExit(main())
