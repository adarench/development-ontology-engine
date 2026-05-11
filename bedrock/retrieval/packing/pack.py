"""Deterministic context packer.

Hard constraints (per Phase 4 architectural directive):
  - DETERMINISTIC: same input → same output, including pack_id.
  - INSPECTABLE: every selection / drop / truncation decision is recorded.
  - LINEAGE-PRESERVING: every fact in the pack has a source_file → content_hash entry.
  - INTERNALLY RECONSTRUCTABLE: given the pack alone, you can answer "where did this come from?"
  - NO LLM IN THE LOOP: ordering, classification, dedup, truncation are all explicit rules.

Ordering rules (top → bottom of the pack):
  1. guardrail sections — hits whose source_file lives under */guardrails/*
     OR whose source begins with "routed:" AND title/file is guardrail-tagged.
  2. routed sections — remaining hits whose source begins with "routed:".
  3. evidence sections — everything else (entity hits, chunk lexical hits, fused).
  Within each class, hits are ordered by (score DESC, identity ASC) — the
  identity tiebreaker is what gives floating-point-stable ordering.

Budget enforcement:
  - The packer walks classified+ordered candidates, summing tokens.
  - When a candidate would push over budget, it is dropped (not partially
    truncated) and pack.truncated is set to True. We never split a section
    mid-fact: cutting evidence in half loses lineage integrity.
  - The dropped candidates' identities are recorded under pack notes for
    inspectability.

pack_id:
  - sha256 of a stable input fingerprint (query + budget + ordered hit
    identities + scores rounded to 6 dp + source_files). Same inputs → same
    pack_id; different ordering rule version would also change it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from bedrock.contracts import (
    ContextPack,
    ContextSection,
    LineageRef,
    RetrievalHit,
)
from bedrock.retrieval.packing.budget import count_tokens

ORDERING_RULES_VERSION = "v1"

# Repo root used to resolve source_files for content hashing.
REPO_ROOT = Path(__file__).resolve().parents[3]

# A hit is treated as a guardrail when any of its source_files lives under
# this directory marker OR when its title/text is explicitly tagged.
_GUARDRAIL_PATH_MARKER = "/guardrails/"


def pack(
    hits: List[RetrievalHit],
    query: str,
    budget_tokens: int = 4000,
    extra_warnings: Optional[List[str]] = None,
    repo_root: Optional[Path] = None,
    min_section_tokens: int = 16,
) -> ContextPack:
    """Pack a ranked list of RetrievalHits into a deterministic ContextPack.

    Args:
        hits: ranked input from the orchestrator (or any caller).
        query: the original query — included in the pack and in pack_id.
        budget_tokens: hard token cap for all sections combined.
        extra_warnings: caller-supplied warnings appended verbatim to the pack.
        repo_root: where to resolve source_files for content hashing
            (defaults to the repo root).
        min_section_tokens: a candidate section smaller than this is treated as
            a non-truncatable atom — included whole or dropped whole.

    Returns:
        ContextPack with .pack_id, .sections, .lineage, .semantic_warnings,
        .confidence_summary, .token_count, .truncated set deterministically.
    """
    repo_root = repo_root or REPO_ROOT
    extras = list(extra_warnings or [])

    # ----- Step 1: classify -------------------------------------------------
    classified: List[Tuple[str, RetrievalHit]] = []
    for h in hits:
        kind = _classify(h)
        classified.append((kind, h))

    # ----- Step 2: order deterministically ---------------------------------
    section_order = ("guardrail", "routed", "evidence")
    ordered: List[Tuple[str, RetrievalHit]] = []
    for kind in section_order:
        same_class = [(k, h) for k, h in classified if k == kind]
        same_class.sort(
            key=lambda kh: (-_safe_score(kh[1]), _hit_identity_for_sort(kh[1]))
        )
        ordered.extend(same_class)

    # ----- Step 3: budget walk ---------------------------------------------
    sections: List[ContextSection] = []
    notes: List[str] = []
    running_tokens = 0
    truncated = False
    seen_identities: set = set()

    for kind, h in ordered:
        ident = _hit_identity_for_sort(h)
        if ident in seen_identities:
            # Defensive: fusion should have deduped, but a caller might pass
            # un-fused input. Same identity gets dropped silently — it would
            # only inflate token cost without adding new information.
            notes.append(f"dedup-skip {ident}")
            continue
        seen_identities.add(ident)

        section_text = _render_section_text(h)
        section_tokens = count_tokens(section_text)
        if section_tokens < min_section_tokens:
            # Atom too small to be meaningful — but include it anyway, since
            # lineage value > token cost.
            pass
        if running_tokens + section_tokens > budget_tokens:
            truncated = True
            notes.append(
                f"budget-skip {ident} (would-add={section_tokens}, "
                f"running={running_tokens}, budget={budget_tokens})"
            )
            continue

        sections.append(
            ContextSection(
                section_kind=kind,  # type: ignore[arg-type]
                title=h.title or ident,
                text=section_text,
                hit=h,
                token_count=section_tokens,
            )
        )
        running_tokens += section_tokens

    # ----- Step 4: lineage with content hashes -----------------------------
    lineage = _build_lineage(sections, repo_root)

    # ----- Step 5: warnings ------------------------------------------------
    auto_warnings = _auto_warnings(sections)
    semantic_warnings = _dedup_preserve_order(auto_warnings + extras)

    # ----- Step 6: confidence summary -------------------------------------
    confidence_summary: Dict[str, int] = {}
    for s in sections:
        c = (s.hit.confidence if s.hit else "unknown") or "unknown"
        confidence_summary[c] = confidence_summary.get(c, 0) + 1

    # ----- Step 7: deterministic pack_id ----------------------------------
    pack_id = _compute_pack_id(
        query=query,
        budget_tokens=budget_tokens,
        sections=sections,
        warnings=semantic_warnings,
    )

    pack_obj = ContextPack(
        pack_id=pack_id,
        query=query,
        sections=sections,
        lineage=lineage,
        semantic_warnings=semantic_warnings,
        confidence_summary=confidence_summary,
        token_count=running_tokens,
        truncated=truncated,
    )
    # Notes are not part of ContextPack schema; expose via lineage's
    # cited_by_facts on a synthetic "_pack_notes" entry so the pack remains
    # JSON-serializable as one object.
    if notes:
        pack_obj.lineage.append(
            LineageRef(
                source_file="_pack_notes",
                content_hash=None,
                cited_by_facts=notes,
            )
        )
    return pack_obj


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _classify(h: RetrievalHit) -> str:
    """Return one of 'guardrail', 'routed', 'evidence'."""
    files = h.source_files or []
    if any(_GUARDRAIL_PATH_MARKER in f for f in files):
        return "guardrail"
    if h.source.startswith("routed:") or "routed:" in h.source:
        # Multi-source labels like "chunk+routed:harmony_3tuple" still count.
        return "routed"
    return "evidence"


def _safe_score(h: RetrievalHit) -> float:
    return float(h.score) if h.score is not None else 0.0


def _hit_identity_for_sort(h: RetrievalHit) -> str:
    """Used for stable tiebreaking. Mirrors orchestration/fusion.hit_identity
    but defined locally so the packer doesn't depend on the orchestration module."""
    if h.entity_id:
        return f"E:{h.entity_id}"
    if h.chunk_id:
        return f"C:{h.chunk_id}"
    return f"S:{h.source}::{h.title or ''}"


def _render_section_text(h: RetrievalHit) -> str:
    """Render the section text deterministically from the hit.

    Format:
        TITLE
        (entity/chunk identity, source label, confidence)

        TEXT BODY

        Sources: file1.md, file2.md
    """
    title = h.title or _hit_identity_for_sort(h)
    ident_line_parts = [
        f"identity={_hit_identity_for_sort(h)}",
        f"source={h.source}",
        f"confidence={h.confidence}",
    ]
    if h.score is not None:
        ident_line_parts.append(f"score={h.score:.4f}")
    ident_line = " | ".join(ident_line_parts)

    body = (h.text or "").strip()
    files = ", ".join(h.source_files) if h.source_files else "(no source files)"
    return f"### {title}\n[{ident_line}]\n\n{body}\n\nSources: {files}"


def _build_lineage(sections: List[ContextSection], repo_root: Path) -> List[LineageRef]:
    """Hash each unique source_file. Sorted output for determinism."""
    file_to_facts: Dict[str, List[str]] = {}
    for s in sections:
        if not s.hit:
            continue
        ident = _hit_identity_for_sort(s.hit)
        for f in s.hit.source_files:
            file_to_facts.setdefault(f, []).append(ident)
    out: List[LineageRef] = []
    for f in sorted(file_to_facts):
        facts = sorted(set(file_to_facts[f]))
        h = _content_hash(repo_root / f)
        out.append(
            LineageRef(source_file=f, content_hash=h, cited_by_facts=facts)
        )
    return out


def _content_hash(p: Path) -> Optional[str]:
    try:
        if not p.exists() or not p.is_file():
            return None
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _auto_warnings(sections: List[ContextSection]) -> List[str]:
    """Surface a warning for any inferred-confidence hit in the pack."""
    out: List[str] = []
    inferred_idents = []
    low_idents = []
    for s in sections:
        if not s.hit:
            continue
        if s.hit.confidence == "inferred":
            inferred_idents.append(_hit_identity_for_sort(s.hit))
        elif s.hit.confidence == "low":
            low_idents.append(_hit_identity_for_sort(s.hit))
    if inferred_idents:
        out.append(
            f"{len(inferred_idents)} inferred-confidence hit(s) included; "
            f"do not promote to 'validated': {inferred_idents}"
        )
    if low_idents:
        out.append(
            f"{len(low_idents)} low-confidence hit(s) included: {low_idents}"
        )
    return out


def _dedup_preserve_order(items: Iterable[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _compute_pack_id(
    query: str,
    budget_tokens: int,
    sections: List[ContextSection],
    warnings: List[str],
) -> str:
    """Stable fingerprint over packer inputs + outputs (excluding generation timestamps)."""
    fingerprint = {
        "ordering_rules_version": ORDERING_RULES_VERSION,
        "query": query,
        "budget_tokens": budget_tokens,
        "warnings": sorted(warnings),
        "sections": [
            {
                "kind": s.section_kind,
                "id": _hit_identity_for_sort(s.hit) if s.hit else s.title,
                "score": round(_safe_score(s.hit) if s.hit else 0.0, 6),
                "title": s.title,
                "files": list(s.hit.source_files) if s.hit else [],
                "tokens": s.token_count,
            }
            for s in sections
        ],
    }
    text = json.dumps(fingerprint, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def utc_now() -> str:
    """Helper for tests / CLI to format a generation timestamp consistently."""
    return datetime.now(timezone.utc).isoformat()
