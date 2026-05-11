"""Lightweight lexical retrieval over the BCPD v2.1 markdown corpus.

Approach:
- Walk a fixed list of input files (markdown + selected JSON sections).
- Chunk each markdown by H2/H3 sections (preserve full body where short).
- Build an in-memory index of (chunk_id, file, section_title, body, tokens).
- Score by token-overlap (Jaccard-ish: |query ∩ chunk| / sqrt(|chunk|)).
  Adequate for ~14 short markdown files; no external dep required.
- Return top-k chunks with file path + section title.

This is deliberately simple. No vector DB. No external services.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json
import math
import re

REPO = Path(__file__).resolve().parent.parent.parent.parent

# ---- Corpus declaration ----------------------------------------------------
# The harness corpus mirrors the user's input list in the brief, plus the
# architecture doc and the GL validation report (referenced from many of the
# above files).
CORPUS_FILES_MD: tuple[str, ...] = (
    "output/agent_context_v2_1_bcpd.md",
    "output/state_quality_report_v2_1_bcpd.md",
    "output/state_query_examples_v2_1_bcpd.md",
    "output/bcpd_state_qa_examples.md",
    "output/bcpd_state_qa_eval.md",
    "output/bcpd_operating_state_v2_review_memo.md",
    "data/reports/v2_0_to_v2_1_change_log.md",
    "data/reports/join_coverage_v0.md",
    "data/reports/join_coverage_simulation_v1.md",
    "data/reports/coverage_improvement_opportunities.md",
    "data/reports/crosswalk_quality_audit_v1.md",
    "data/reports/vf_lot_code_decoder_v1_report.md",
    "data/reports/guardrail_check_v0.md",
    "data/staged/staged_gl_transactions_v2_validation_report.md",
    "docs/ontology_v0.md",
    "docs/source_to_field_map.md",
    "docs/crosswalk_plan.md",
    "docs/bcpd_operating_state_architecture.md",
)

# Selected sub-sections of the v2.1 state JSON to surface in retrieval.
# The full JSON is large; index only the high-value top-level keys.
CORPUS_FILES_JSON: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "output/operating_state_v2_1_bcpd.json",
        ("metadata", "v2_1_changes_summary", "source_owner_questions_open",
         "data_quality"),
    ),
)

# Optional chunk dir. May not exist.
CHUNK_DIR = "output/agent_chunks_v2_bcpd"


# ---- Tokenization ----------------------------------------------------------
_TOKEN = re.compile(r"[a-z0-9_]+")
_STOP = frozenset(
    "the a an of for and or to in on at is are was were be by it this that "
    "with as but from we i you they our its their these those into not no "
    "if then so do does did has had have can could should would may might "
    "what which who when where why how than vs about per any all".split()
)


def tokenize(text: str) -> list[str]:
    text = text.lower()
    return [t for t in _TOKEN.findall(text) if t not in _STOP and len(t) > 1]


# ---- Chunk dataclass -------------------------------------------------------
@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    file: str            # repo-relative path
    section_title: str
    body: str
    tokens: tuple[str, ...]


# ---- Markdown chunker ------------------------------------------------------
_HEADER_RX = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)


def split_markdown(text: str, file: str) -> list[Chunk]:
    """Split a markdown into chunks at H1/H2/H3/H4 headers.

    Each chunk = header + body up to the next header of equal-or-higher level.
    Maximum chunk size hint ~ 2,500 chars; oversize chunks are kept whole
    (no further splitting) to preserve coherence — the corpus is small.
    """
    matches = list(_HEADER_RX.finditer(text))
    if not matches:
        # No headers — treat the whole file as one chunk.
        return [_make_chunk(file, "(no section)", text, 0)]

    chunks: list[Chunk] = []
    # Prepend any pre-header preamble as its own chunk.
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            chunks.append(_make_chunk(file, "(preamble)", preamble, 0))

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_title = m.group(2).strip()
        body = text[m.start():end].strip()
        chunks.append(_make_chunk(file, section_title, body, i + 1))

    return chunks


def _make_chunk(file: str, section_title: str, body: str, idx: int) -> Chunk:
    chunk_id = f"{file}::{idx:03d}::{section_title[:40]}"
    return Chunk(
        chunk_id=chunk_id,
        file=file,
        section_title=section_title,
        body=body,
        tokens=tuple(tokenize(body)),
    )


# ---- JSON section chunker --------------------------------------------------
def chunk_json_sections(file_rel: str, section_keys: tuple[str, ...]) -> list[Chunk]:
    """Pull selected top-level keys out of a JSON file as text chunks."""
    p = REPO / file_rel
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    chunks: list[Chunk] = []
    for i, k in enumerate(section_keys):
        if k not in data:
            continue
        body_obj = data[k]
        body = f"## {k}\n\n" + json.dumps(body_obj, indent=2, default=str)
        # Cap to ~6KB for retrieval sanity
        if len(body) > 6000:
            body = body[:6000] + "\n\n…(truncated for index)"
        chunks.append(_make_chunk(file_rel, k, body, i))
    return chunks


# ---- Index build -----------------------------------------------------------
@dataclass
class Index:
    chunks: list[Chunk] = field(default_factory=list)
    df: dict[str, int] = field(default_factory=dict)  # document frequency

    def n(self) -> int:
        return len(self.chunks)


def build_index() -> Index:
    idx = Index()
    # Markdown corpus
    for rel in CORPUS_FILES_MD:
        p = REPO / rel
        if not p.exists():
            continue
        text = p.read_text(errors="replace")
        for c in split_markdown(text, rel):
            idx.chunks.append(c)
    # JSON sub-section corpus
    for rel, keys in CORPUS_FILES_JSON:
        for c in chunk_json_sections(rel, keys):
            idx.chunks.append(c)
    # Optional pre-built chunks dir
    chunk_dir = REPO / CHUNK_DIR
    if chunk_dir.is_dir():
        for p in sorted(chunk_dir.rglob("*.md")):
            text = p.read_text(errors="replace")
            rel = str(p.relative_to(REPO))
            for c in split_markdown(text, rel):
                idx.chunks.append(c)

    # Document frequency
    for c in idx.chunks:
        for tok in set(c.tokens):
            idx.df[tok] = idx.df.get(tok, 0) + 1
    return idx


# ---- Retrieval -------------------------------------------------------------
@dataclass
class RetrievalHit:
    chunk: Chunk
    score: float
    matched_tokens: list[str]


def retrieve(idx: Index, query: str, top_k: int = 6,
             must_include_files: tuple[str, ...] = ()) -> list[RetrievalHit]:
    """Score each chunk by sum of TF-IDF over query terms.

    A chunk is filtered in if it has at least one matching query token. If
    `must_include_files` is provided, chunks from those files are scored with
    a 1.5x boost (used to surface canonical guardrail/context files).
    """
    q_tokens = list(set(tokenize(query)))
    if not q_tokens:
        return []
    n_docs = max(idx.n(), 1)

    hits: list[RetrievalHit] = []
    for c in idx.chunks:
        chunk_set = set(c.tokens)
        matches = [t for t in q_tokens if t in chunk_set]
        if not matches:
            continue
        score = 0.0
        for t in matches:
            df = idx.df.get(t, 1)
            idf = math.log((n_docs + 1) / (df + 1)) + 1.0
            tf = c.tokens.count(t) / max(len(c.tokens), 1)
            score += tf * idf
        # Length normalization (favor focused chunks)
        score = score / math.sqrt(max(len(c.tokens), 1))
        # Boost canonical sources if requested
        if must_include_files and c.file in must_include_files:
            score *= 1.5
        hits.append(RetrievalHit(chunk=c, score=score, matched_tokens=sorted(matches)))

    hits.sort(key=lambda h: -h.score)
    return hits[:top_k]


def snippet(chunk: Chunk, max_chars: int = 600) -> str:
    """Short readable preview of a chunk for the retrieval trace."""
    body = chunk.body.strip().replace("\n\n", "\n")
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + " …"
    return body
