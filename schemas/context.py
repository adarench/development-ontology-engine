"""Load business + data-dictionary context from project files.

Used by `enrich_descriptions.py` to ground LLM-generated field descriptions in
the actual source-of-truth documentation (Flagship Homes business context,
source inventory, per-source agent chunks). The loaded text is prepended to
the system prompt and marked for prompt caching, so every enrichment chunk
sees the same context without paying the input-token cost more than once.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent

# Default set of context files. Order matters — earlier files appear first in
# the assembled context. Override via `load_context(paths=[...])` or
# `--context-files` on the CLI.
DEFAULT_CONTEXT_FILES: tuple[str, ...] = (
    # Business model: what a community / phase / lot is, what "cost by phase" means,
    # what the finance team is actually asking for.
    "Flagship Homes — What The Business Actually Wants From The AI System.pdf",

    # Per-canonical-field map: which upstream source carries which field, in
    # authority order, with cross-source coverage matrix.
    "docs/source_to_field_map.md",

    # Full source inventory: every upstream file, what it is, who owns it,
    # known limitations, dedup rules, era boundaries, ambiguity risks.
    "source_mapping_v1.md",

    # Per-source curated summaries (one chunk per upstream source family).
    "output/agent_chunks_v2_bcpd/sources/source_inventory_closing_report.md",
    "output/agent_chunks_v2_bcpd/sources/source_collateral_reports.md",
    "output/agent_chunks_v2_bcpd/sources/source_gl_vertical_financials.md",
    "output/agent_chunks_v2_bcpd/sources/source_gl_datarails_38col.md",
    "output/agent_chunks_v2_bcpd/sources/source_gl_qb_register.md",
    "output/agent_chunks_v2_bcpd/sources/source_clickup_tasks.md",
    "output/agent_chunks_v2_bcpd/sources/source_allocation_workbooks.md",
)


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit(
            f"Cannot read {path.name}: pypdf not installed. "
            f"Run: pip3 install pypdf"
        ) from exc
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return _read_pdf(path)
    return path.read_text(encoding="utf-8", errors="replace")


def load_context(paths: Iterable[str | Path] | None = None) -> str:
    """Load all configured context files and return one concatenated string.

    Each file becomes a section with a `## From: <relative path>` header.
    Missing files are listed with a placeholder so the absence is visible in
    the prompt rather than silently dropped.
    """
    paths_list = list(paths) if paths is not None else list(DEFAULT_CONTEXT_FILES)
    sections: list[str] = []
    for p in paths_list:
        path = Path(p)
        if not path.is_absolute():
            path = REPO_ROOT / path
        try:
            rel = path.relative_to(REPO_ROOT)
            label = str(rel)
        except ValueError:
            label = str(path)
        if not path.exists():
            sections.append(f"## From: {label}\n\n_(file not found at this path; skipped)_")
            continue
        try:
            text = _read_file(path)
        except Exception as exc:
            sections.append(f"## From: {label}\n\n_(failed to read: {exc})_")
            continue
        sections.append(f"## From: {label}\n\n{text.strip()}")

    return "\n\n---\n\n".join(sections)


def estimate_tokens(text: str) -> int:
    """Rough char-based token estimate (~4 chars per token). For sanity checks."""
    return max(1, len(text) // 4)
