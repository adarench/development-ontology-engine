"""EntityRetriever — operational-state retrieval over CanonicalEntity instances.

Returns CanonicalEntity hits (not text chunks). Every result carries a score
broken into components: lexical, vector, alias_match, metadata_boost.
Brute-force cosine over an in-memory NumPy matrix; no ANN, no scaling tricks.

Optimized for: explainability (every score is decomposable), lineage
preservation (every hit names its source files), entity-aware retrieval
(canonical entities are the unit of work, not chunks), inspection (every
call yields a RetrievalTrace).

Deferred to Phase 3: pgvector backend, integration with the existing routed-
rule layer, learned reranking.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bedrock.contracts import CanonicalEntity, EmbeddingProvider, MetadataFilter
from bedrock.embeddings.build import DEFAULT_INDEX_PATH
from bedrock.embeddings.hashing import HashingEmbeddingProvider
from bedrock.ontology.runtime import OntologyRegistry
from bedrock.registry import StateRegistry
from bedrock.retrieval.services.trace import (
    CandidateInfo,
    ExpansionRecord,
    FilterApplication,
    RetrievalTrace,
)


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
        "for", "with", "from", "by", "is", "are", "was", "were", "be",
        "this", "that", "these", "those", "it", "its", "as", "what",
    }
)

DEFAULT_WEIGHTS = {
    "lexical": 0.40,
    "vector": 0.30,
    "alias_match": 0.20,
    "metadata_boost": 0.10,
}


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


@dataclass
class EntityHit:
    entity: CanonicalEntity
    combined_score: float
    score_components: Dict[str, float]
    matched_terms: List[str]
    matched_aliases: List[str]
    confidence: str
    source_files: List[str]


@dataclass
class RetrievalResult:
    hits: List[EntityHit]
    trace: RetrievalTrace


class EntityRetriever:
    """Operational retrieval over the canonical entity index."""

    def __init__(
        self,
        state_registry: StateRegistry,
        ontology_registry: OntologyRegistry,
        index_path: Path = DEFAULT_INDEX_PATH,
        embedder: Optional[EmbeddingProvider] = None,
        score_weights: Optional[Dict[str, float]] = None,
        trace_window: int = 10,
        aliases_path: Optional[Path] = None,
    ) -> None:
        self.state_registry = state_registry
        self.ontology_registry = ontology_registry
        self.index_path = Path(index_path)
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"Entity index not found at {self.index_path}. "
                "Run `python -m bedrock.embeddings.build` first."
            )
        self.embedder = embedder
        self.score_weights = score_weights or dict(DEFAULT_WEIGHTS)
        self.trace_window = trace_window
        # Defaults to <repo_root>/state/aliases.json — the centralized alias
        # table seeded from routing rules and the v1 decoder report.
        self.aliases_path = (
            Path(aliases_path)
            if aliases_path is not None
            else Path(self.index_path).resolve().parents[2] / "state" / "aliases.json"
        )
        self._aliases_loaded_count = 0

        self._load_index()
        self._build_idf()
        self._build_alias_table()

    # ------------------------------------------------------------------
    # one-time setup
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        import numpy as np
        import pandas as pd

        df = pd.read_parquet(self.index_path)
        self._df = df
        self._entity_ids: List[str] = df["entity_id"].tolist()
        self._entity_types: List[str] = df["entity_type"].tolist()
        self._confidences: List[str] = df["confidence"].tolist()
        self._state_versions: List[str] = df["state_version"].tolist()
        self._verticals: List[str] = df["vertical"].tolist()
        self._retrieval_tags: List[List[str]] = [
            list(t) if t is not None else [] for t in df["retrieval_tags"].tolist()
        ]
        self._source_files_col: List[List[str]] = [
            list(s) if s is not None else [] for s in df["source_files"].tolist()
        ]
        self._texts: List[str] = df["text_to_embed"].tolist()
        self._facets: List[Dict[str, Any]] = [
            json.loads(f) for f in df["structured_facets"].tolist()
        ]
        # Vector matrix
        vectors = np.stack([np.asarray(v, dtype=np.float32) for v in df["vector"].tolist()])
        # Replace any pre-existing nan/inf with 0 so they don't poison the matmul.
        vectors = np.nan_to_num(vectors, nan=0.0, posinf=0.0, neginf=0.0)
        # Renormalize defensively (hashed provider already L2-normalizes)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._vectors = (vectors / norms).astype(np.float32)
        # Final scrub — division might have introduced fresh nans on all-zero rows
        # (norms[i] was forced to 1, so 0/1 = 0; but be paranoid).
        self._vectors = np.nan_to_num(self._vectors, nan=0.0, posinf=0.0, neginf=0.0)
        self._dim = int(vectors.shape[1])
        self._model_id = str(df["model_id"].iloc[0]) if len(df) else None

        # Pre-tokenize texts for lexical scoring
        self._tokens: List[List[str]] = [_tokenize(t) for t in self._texts]
        self._token_sets: List[set] = [set(toks) for toks in self._tokens]

    def _build_idf(self) -> None:
        n = len(self._tokens)
        df_count: Counter = Counter()
        for s in self._token_sets:
            df_count.update(s)
        self._idf: Dict[str, float] = {
            t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df_count.items()
        }

    def _build_alias_table(self) -> None:
        """alias-string (lowercased) -> (resolves_to, entity_type, source_alias).

        Sources, in precedence order (first writer wins per alias key):
          1. ontology semantic_aliases — hand-curated per EntitySpec.
          2. state/aliases.json — centralized BCPD project / code /
             concept aliases. Loaded if the file exists; absent → silently
             skipped (no hard dependency).
        """
        self._alias_table: Dict[str, Tuple[str, str, str]] = {}
        for et, spec in self.ontology_registry.entities.items():
            for a in spec.semantic_aliases:
                key = a.alias.lower().strip()
                if key and key not in self._alias_table:
                    self._alias_table[key] = (a.resolves_to, et, a.alias)
        # Layered: aliases.json (centralized table) augments the ontology
        # without overwriting it. Missing or malformed file → skip silently;
        # this is an additive recall improvement, not a hard requirement.
        try:
            extra = self._load_aliases_file(self.aliases_path)
        except (OSError, json.JSONDecodeError, ValueError):
            extra = []
        for alias, resolves_to, kind, source_alias in extra:
            key = alias.lower().strip()
            if key and key not in self._alias_table:
                self._alias_table[key] = (resolves_to, kind, source_alias)
                self._aliases_loaded_count += 1

    @staticmethod
    def _load_aliases_file(path: Path) -> List[Tuple[str, str, str, str]]:
        """Parse state/aliases.json into (alias, resolves_to, kind, source_alias) tuples."""
        p = Path(path)
        if not p.exists() or not p.is_file():
            return []
        data = json.loads(p.read_text())
        out: List[Tuple[str, str, str, str]] = []
        groups = data.get("groups") if isinstance(data, dict) else None
        if not isinstance(groups, list):
            return []
        for g in groups:
            if not isinstance(g, dict):
                continue
            canonical = (g.get("canonical") or "").strip()
            kind = (g.get("kind") or "concept").strip()
            aliases = g.get("aliases") or []
            if not canonical or not isinstance(aliases, list):
                continue
            for a in aliases:
                if not isinstance(a, str):
                    continue
                a_clean = a.strip()
                if not a_clean:
                    continue
                out.append((a_clean, canonical, kind, a_clean))
        return out

    # ------------------------------------------------------------------
    # query-time
    # ------------------------------------------------------------------

    def _expand_query(self, query: str) -> Tuple[List[str], List[ExpansionRecord]]:
        q_lower = query.lower()
        expanded_terms: List[str] = list(_tokenize(query))
        expansions: List[ExpansionRecord] = []
        seen = set(expanded_terms)
        # Substring match against the alias table (catches multi-word aliases like "actual cost").
        for alias_key, (resolves_to, _et, source_alias) in self._alias_table.items():
            if alias_key and alias_key in q_lower:
                # Add the resolves_to as additional retrieval terms.
                for tok in _tokenize(resolves_to):
                    if tok not in seen:
                        expanded_terms.append(tok)
                        seen.add(tok)
                        expansions.append(
                            ExpansionRecord(
                                original_term=alias_key,
                                expansion=tok,
                                source_alias=source_alias,
                                resolved_to=resolves_to,
                            )
                        )
        return expanded_terms, expansions

    def _apply_filters(
        self, candidates: List[int], filters: Optional[MetadataFilter]
    ) -> Tuple[List[int], List[FilterApplication]]:
        applied: List[FilterApplication] = []
        if filters is None:
            return candidates, applied

        def _filter_step(
            indices: List[int], name: str, value: Any, predicate
        ) -> List[int]:
            before = len(indices)
            kept = [i for i in indices if predicate(i)]
            applied.append(
                FilterApplication(
                    filter=name, value=value, candidates_before=before, candidates_after=len(kept)
                )
            )
            return kept

        c = candidates
        if filters.entity_types:
            allow = set(filters.entity_types)
            c = _filter_step(c, "entity_types", filters.entity_types,
                             lambda i: self._entity_types[i] in allow)
        if filters.verticals:
            allow = set(filters.verticals)
            c = _filter_step(c, "verticals", filters.verticals,
                             lambda i: self._verticals[i] in allow)
        if filters.confidences:
            allow = set(filters.confidences)
            c = _filter_step(c, "confidences", filters.confidences,
                             lambda i: self._confidences[i] in allow)
        if filters.state_versions:
            allow = set(filters.state_versions)
            c = _filter_step(c, "state_versions", filters.state_versions,
                             lambda i: self._state_versions[i] in allow)
        if filters.retrieval_tags_any:
            allow = set(filters.retrieval_tags_any)
            c = _filter_step(c, "retrieval_tags_any", filters.retrieval_tags_any,
                             lambda i: bool(allow & set(self._retrieval_tags[i])))
        if filters.retrieval_tags_all:
            need = set(filters.retrieval_tags_all)
            c = _filter_step(c, "retrieval_tags_all", filters.retrieval_tags_all,
                             lambda i: need.issubset(set(self._retrieval_tags[i])))

        return c, applied

    def _score_lexical(self, query_tokens: List[str], candidates: List[int]) -> Dict[int, float]:
        scores: Dict[int, float] = {}
        if not query_tokens:
            return scores
        q_tokens_set = set(query_tokens)
        # Precompute query weights via IDF
        q_weights = {t: self._idf.get(t, 1.0) for t in q_tokens_set}
        max_q = max(q_weights.values()) if q_weights else 1.0

        for idx in candidates:
            doc_tokens = self._token_sets[idx]
            common = q_tokens_set & doc_tokens
            if not common:
                continue
            score = sum(q_weights.get(t, 0.0) for t in common)
            # Length-normalize so very long entity texts don't dominate
            doc_len = max(len(self._tokens[idx]), 1)
            score = score / math.log(1 + doc_len)
            # Normalize against max possible
            scores[idx] = min(score / max_q, 1.0)
        return scores

    def _score_vector(self, query: str, candidates: List[int]) -> Dict[int, float]:
        if self.embedder is None:
            return {}
        import numpy as np

        q_vec_list = self.embedder.embed([query])
        if not q_vec_list:
            return {}
        q = np.asarray(q_vec_list[0], dtype=np.float32)
        if q.shape[0] != self._dim:
            # Different embedder than what built the index; emit empty rather than mix.
            return {}
        n = np.linalg.norm(q)
        if n == 0:
            return {}
        q = q / n
        # Brute-force cosine over the candidate subset
        if not candidates:
            return {}
        idx_arr = np.asarray(candidates, dtype=np.int64)
        sub = self._vectors[idx_arr]
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            sims = sub @ q  # cosine since both are L2-normalized
        sims = np.nan_to_num(sims, nan=0.0, posinf=0.0, neginf=0.0)
        return {int(idx): float(sim) for idx, sim in zip(candidates, sims)}

    def _score_aliases(
        self, query: str, candidates: List[int]
    ) -> Tuple[Dict[int, float], Dict[int, List[str]]]:
        q = query.lower()
        scores: Dict[int, float] = {}
        matched: Dict[int, List[str]] = {}
        for idx in candidates:
            aliases = self._facets[idx].get("aliases") or []
            tags = self._facets[idx].get("retrieval_tags") or []
            hits: List[str] = []
            for a in aliases:
                if a and a.lower() in q:
                    hits.append(a)
            for t in tags:
                if t and t.lower() in q:
                    hits.append(f"#{t}")
            if hits:
                # Score: ratio of hits to total alias+tag pool (capped)
                pool = max(len(aliases) + len(tags), 1)
                scores[idx] = min(len(hits) / pool, 1.0)
                matched[idx] = hits
        return scores, matched

    def _score_metadata_boost(
        self, query: str, candidates: List[int]
    ) -> Dict[int, float]:
        """Boost when a query mentions identifying values an entity actually has.

        All checks are word-boundary anchored — substring matches on single-character
        phase names like 'B' would otherwise generate noise on incidental query
        tokens (e.g., 'b' in 'branch').
        """
        q = query.lower()

        def _has_word(value: str) -> bool:
            if not value:
                return False
            return re.search(rf"\b{re.escape(value.lower())}\b", q) is not None

        scores: Dict[int, float] = {}
        for idx in candidates:
            facets = self._facets[idx]
            boost = 0.0
            project = facets.get("canonical_project") or ""
            phase = facets.get("canonical_phase") or ""
            lot_num = facets.get("canonical_lot_number") or ""
            stage = facets.get("current_stage") or ""

            if _has_word(str(project)):
                boost += 0.4
            if _has_word(str(phase)):
                boost += 0.3
            if _has_word(str(lot_num)):
                boost += 0.2
            stage_phrase = str(stage).replace("_", " ").lower()
            if stage_phrase and stage_phrase in q:
                boost += 0.1
            if boost > 0:
                scores[idx] = min(boost, 1.0)
        return scores

    def _surface_warnings(
        self, hits: List[EntityHit], query: str
    ) -> List[str]:
        warnings: List[str] = []
        seen: set = set()
        q = query.lower()
        # Per-hit confidence warnings
        for h in hits:
            if h.confidence == "inferred":
                msg = f"Hit `{h.entity.entity_id}` carries confidence='inferred'."
                if msg not in seen:
                    warnings.append(msg)
                    seen.add(msg)

        # Ontology-level warnings touching mentioned entity types
        hit_types = {h.entity.entity_type for h in hits}
        for et in hit_types:
            spec = self.ontology_registry.entities.get(et)
            if not spec:
                continue
            for w in spec.semantic_warnings:
                # Apply if the field is referenced in the query OR the hit's payload
                if w.applies_to.lower() in q or any(
                    w.applies_to.lower() in (h.entity.fields.get(w.applies_to) and "" or "")
                    for h in hits
                ):
                    msg = f"[{et}.{w.applies_to}] {w.message.strip()}"
                    if msg not in seen:
                        warnings.append(msg)
                        seen.add(msg)
                else:
                    # Heuristic: surface high-stakes warnings even if the field name isn't in the query.
                    # Always surface 'cost_is_inferred' when any cost-related token appears.
                    if w.name == "cost_is_inferred" and ("cost" in q or "spend" in q or "actual" in q):
                        msg = f"[{et}.{w.applies_to}] {w.message.strip()}"
                        if msg not in seen:
                            warnings.append(msg)
                            seen.add(msg)
                    if w.name == "missing_is_not_zero" and ("zero" in q or "missing" in q):
                        msg = f"[{et}.{w.applies_to}] {w.message.strip()}"
                        if msg not in seen:
                            warnings.append(msg)
                            seen.add(msg)
        return warnings

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[MetadataFilter] = None,
        mode: str = "hybrid",
        explain: bool = True,
    ) -> RetrievalResult:
        if mode not in ("lexical", "vector", "hybrid"):
            raise ValueError(f"unknown mode {mode!r}")

        t0 = time.time()
        n = len(self._entity_ids)

        # Stage 1: filter
        candidates = list(range(n))
        candidates, filter_apps = self._apply_filters(candidates, filters)

        # Stage 2: query expansion
        expanded_tokens, expansions = self._expand_query(query)

        # Stage 3: scoring
        lexical_scores: Dict[int, float] = {}
        vector_scores: Dict[int, float] = {}
        if mode in ("lexical", "hybrid"):
            lexical_scores = self._score_lexical(expanded_tokens, candidates)
        if mode in ("vector", "hybrid"):
            vector_scores = self._score_vector(query, candidates)
        alias_scores, alias_matched = self._score_aliases(query, candidates)
        meta_scores = self._score_metadata_boost(query, candidates)

        # Stage 4: combine
        weights = self.score_weights
        combined: Dict[int, Tuple[float, Dict[str, float]]] = {}
        for idx in candidates:
            comp = {
                "lexical": lexical_scores.get(idx, 0.0),
                "vector": vector_scores.get(idx, 0.0),
                "alias_match": alias_scores.get(idx, 0.0),
                "metadata_boost": meta_scores.get(idx, 0.0),
            }
            score = sum(weights.get(k, 0.0) * v for k, v in comp.items())
            if score > 0:
                combined[idx] = (score, comp)

        ranked = sorted(combined.items(), key=lambda kv: kv[1][0], reverse=True)
        top_indices = [idx for idx, _ in ranked[:top_k]]

        # Stage 5: hydrate hits
        hits: List[EntityHit] = []
        for idx in top_indices:
            entity_id = self._entity_ids[idx]
            entity = self.state_registry.get(entity_id)
            if entity is None:
                continue
            score, comp = combined[idx]
            matched_aliases = alias_matched.get(idx, [])
            doc_tokens = self._token_sets[idx]
            matched_terms = sorted(set(expanded_tokens) & doc_tokens)
            hits.append(
                EntityHit(
                    entity=entity,
                    combined_score=score,
                    score_components=comp,
                    matched_terms=matched_terms,
                    matched_aliases=matched_aliases,
                    confidence=self._confidences[idx],
                    source_files=self._source_files_col[idx],
                )
            )

        # Stage 6: warnings + lineage
        warnings = self._surface_warnings(hits, query)
        lineage_summary = {h.entity.entity_id: h.source_files for h in hits}

        # Stage 7: trace
        trace = RetrievalTrace(
            query=query,
            mode=mode,
            top_k=top_k,
            expanded_terms=expansions,
            applied_filters=filter_apps,
            candidate_count_initial=n,
            candidate_count_after_filters=len(candidates),
            semantic_warnings=warnings,
            lineage_summary=lineage_summary,
            score_weights=weights,
        )

        if explain:
            window = max(top_k + self.trace_window, top_k)
            window_idx = [idx for idx, _ in ranked[:window]]
            for rank, idx in enumerate(window_idx, start=1):
                score, comp = combined[idx]
                trace.top_candidates.append(
                    CandidateInfo(
                        entity_id=self._entity_ids[idx],
                        entity_type=self._entity_types[idx],
                        rank=rank,
                        in_top_k=(rank <= top_k),
                        combined_score=score,
                        score_components=comp,
                        matched_terms=sorted(
                            set(expanded_tokens) & self._token_sets[idx]
                        )[:10],
                        matched_aliases=alias_matched.get(idx, []),
                        confidence=self._confidences[idx],
                        source_files=self._source_files_col[idx],
                    )
                )

        if not combined:
            trace.notes.append("No candidates scored above zero — try a broader query.")

        if mode in ("vector", "hybrid") and self.embedder is None:
            trace.notes.append(
                "vector scoring skipped: no embedder supplied to EntityRetriever; "
                "passed mode requested vector but only lexical/alias/metadata contributed."
            )

        trace.ms_elapsed = (time.time() - t0) * 1000.0
        return RetrievalResult(hits=hits, trace=trace)


def default_retriever(
    index_path: Path = DEFAULT_INDEX_PATH,
    embedder: Optional[EmbeddingProvider] = None,
) -> EntityRetriever:
    """Convenience factory: load registries + index with sensible defaults."""
    state = StateRegistry.from_v2_1_json()
    ontology = OntologyRegistry.load(Path(index_path).resolve().parents[2] / "ontology")
    if embedder is None:
        # Default to the hashing provider — install-free, deterministic.
        embedder = HashingEmbeddingProvider(dim=256)
    return EntityRetriever(
        state_registry=state,
        ontology_registry=ontology,
        index_path=index_path,
        embedder=embedder,
    )
