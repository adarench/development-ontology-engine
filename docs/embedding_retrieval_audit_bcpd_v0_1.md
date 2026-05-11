# Embedding & Retrieval Audit — BCPD v0.1 (Skill v2.1 runtime)

**Date:** 2026-05-11
**Scope:** the embedding/retrieval layer that backs the six BCPD workflow tools
and any future Q&A surface that runs against `output/operating_state_v2_1_bcpd.json`
and the agent-chunk corpus.
**Out of scope:** workflow content, state-file correctness, ontology contents,
Skill packaging artifacts other than what they say about retrieval.

> **Update — branch `bcpd-retrieval-quality-v0`:** Several do-now / do-soon
> items from §9 have landed without changing the v0.1 runtime product
> surface.
>
> - `state/aliases.json` — centralized BCPD alias table (15 groups; 128
>   aliases now loaded into `EntityRetriever._alias_table` on top of 16
>   ontology aliases — total 144).
> - Retrieval-only golden eval — `financials/qa/rag_eval/retrieval_goldens.json`
>   (17 goldens) + `run_retrieval_goldens.py` runner that writes
>   `output/rag_eval/retrieval_goldens_report.{md,json}`. No LLM. No API
>   keys. **Baseline: 10/17 overall pass; 14/17 file recall; 17/17
>   routed-rule recall; 13/17 entity-id recall.** The 7 failures are
>   genuine recall gaps surfaced by the eval (4 missing project entities
>   from entity top-9 due to lots dominating the index 192:1; 3 expected
>   files squeezed out of the 9-slot routed cap).
> - Explicit refusal in `core/tools/bcpd_workflows.py` when
>   `add_entity_source=True` and the entity retrieval stack is missing
>   (the v0.1 Skill package case).
> - Packaging gap documented in `skills/bcpd-operating-state/PACKAGING_CHECKLIST.md`.
>
> Default workflow runtime is unchanged. No protected v2.1 state files
> were touched. Semantic-embedding upgrade remains deferred.

---

## Executive summary

- **Embeddings are not semantic.** The only embedding provider that has been
  exercised against the live state — and the only one whose vectors live on
  disk at `output/bedrock/entity_index.parquet` — is `HashingEmbeddingProvider`
  (`hashing-v1-d256`). It is a deterministic SHA‑256 token‑bucket projection
  with sign, L2‑normalized. It captures **lexical** overlap, not paraphrase
  equivalence. "actual cost" vs "real spend" do not embed close.
- **The runtime that ships the six workflow tools does not use vector
  retrieval today.** `core/tools/bcpd_workflows.py:79–96` builds an
  orchestrator with `ChunkSource` + `RoutedSource` only; `EntitySource` is
  gated behind `add_entity_source=True` and is never enabled in the demo
  path. Workflow content is assembled from **deterministic state lookups**
  + routed/lexical evidence over the markdown corpus.
- **Two providers (`local`, `voyage`) exist as seams but are dormant.**
  `LocalEmbeddingProvider` (sentence-transformers MiniLM, 384‑d) and
  `VoyageEmbeddingProvider` (voyage-3, 1024‑d) implement the same Protocol
  and pass through the same cache, but no live artifact has been built with
  them and no test runs them end-to-end against the parquet index.
- **For v0.1 this is enough — narrowly.** The six workflow tools and the
  curated Q&A surface are bounded enough that lexical hashing + routed rules
  cover the goldens. It is **not** sufficient for arbitrary free-form chat.
- **One concrete package/runtime mismatch.** The Skill at
  `dist/bcpd-operating-state/` ships `bedrock/retrieval/orchestration` and
  `bedrock/retrieval/retrievers/{base,chunk_source,routed_source}.py` but
  ships **no** `bedrock/embeddings/`, **no** `bedrock/retrieval/services/`,
  and **no** entity index. If any caller toggles `add_entity_source=True`
  inside the package, the import will fail at runtime. See §9.
- **Recommendation:** keep deterministic hashing for v0.1; defer Voyage and
  vector-DB upgrades; close one alias/synonym gap before broader usage. No
  urgent code change is required to ship the Skill demo.

---

## 1. Current architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Caller (workflow tool, RAG eval, LLM eval, future agent)                │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ query, top_k, filters
                                     ▼
                       HybridOrchestrator (hybrid.py)
                                     │
        ┌────────────────────────────┼─────────────────────────────┐
        │                            │                             │
        ▼                            ▼                             ▼
   ChunkSource                  RoutedSource                  EntitySource
   (chunk_source.py)            (routed_source.py)            (entity_source.py)
        │                            │                             │ (opt-in)
   wraps                         wraps                         wraps
   retrieval_index.py            route_retrieval.py            EntityRetriever
   - TF-IDF over 18 md           - 16 hardcoded rules          - in services/
     files + agent_chunks        - per-rule required_files     - 5,576 entities
   - 44 + N chunks               - +1000 boost on routed       - 0.4 lex + 0.3 vec
   - tokenize/stopword           - lexical fallback fills      - + 0.2 alias
     basic                         remaining slots               - + 0.1 meta-boost
                                                               - alias query
                                                                 expansion from
                                                                 ontology
                                                               - brute-force
                                                                 cosine over the
                                                                 in-memory
                                                                 NumPy matrix
                                                                 loaded from
                                                                 entity_index
                                                                 .parquet
        │                            │                             │
        └────────────────────────────┴─────────────────────────────┘
                                     │ per-source hits + SourceTrace
                                     ▼
                              RRFFuser (fusion.py)
                              k_constant=60, optional source weights
                              - dedup by (entity_id | chunk_id | source::title)
                              - union source_files, keep highest score's text
                              - aggregate score_components namespaced by source
                                     │
                                     ▼
                              NoOpReranker (rerank.py)
                              (seam only; no learned/LLM reranker yet)
                                     │
                                     ▼
                              ContextPacker (packing/pack.py)
                              - classify {guardrail, routed, evidence}
                              - order: guardrail → routed → evidence
                              - sort within: (score DESC, identity ASC)
                              - drop sections that would overflow budget
                                (atom-level, never split)
                              - emit lineage with sha256 of each source file
                              - deterministic pack_id over inputs+outputs
                                     │
                                     ▼
                       ContextPack {sections, lineage, warnings,
                                    confidence_summary, pack_id}
                                     │
                                     ▼
                       Workflow tool (deterministic) renders Markdown.
                       LLM (if any) consumes the pack.
```

Where the **six workflow tools** plug in: `BcpdContext` in
`core/tools/bcpd_workflows.py` instantiates the orchestrator with only
`ChunkSource + RoutedSource`. Each workflow tool calls
`context.retrieve(query)` to surface narrative evidence and also reads the
state JSON directly for numbers. The output goes to
`output/runtime_demo/*.md` via `bedrock/workflows/cli.py`.

---

## 2. What is embedded

### 2.1 The entity index

Artifact: `output/bedrock/entity_index.parquet` (1.18 MB, 5,576 rows).
Columns: `id, entity_id, entity_type, vertical, confidence, state_version,
retrieval_tags, source_files, text_to_embed, structured_facets, vector,
vector_dim, content_hash, model_id`.

| entity_type | count |
|-------------|-------|
| lot         | 5,366 |
| phase       | 184   |
| project     | 26    |

All rows are stamped `model_id = "hashing-v1-d256"`, `vector_dim = 256`.

### 2.2 What goes into `text_to_embed`

Per `bedrock/embeddings/payload.py:`

```
<instance label, e.g. "Lot Harmony::B1::101 stage=COMPLETED cost=$182,500">
<ontology template render, including canonical_name, business_description,
 aliases (verbatim), retrieval_tags>
Confidence: <conf>; state_version: v2.1; decoder: <decoder_version?>
Sources: <source_files...>
```

`structured_facets` separately carries `entity_type`, `vertical`,
`confidence`, `state_version`, `source_files`, `retrieval_tags`,
`aliases`, and a small entity-type-specific allowlist
(`canonical_project`, `canonical_phase`, `canonical_lot_number`, …).

### 2.3 What is **not** embedded

- The **agent chunks** under `output/agent_chunks_v2_bcpd/` (44 chunks).
  These are retrieved lexically (TF-IDF) via `retrieval_index.py`.
- The **markdown corpus** (state quality reports, change log, decoder
  report, agent_context). Same: TF-IDF only.
- The **state JSON itself**. Workflow tools read it directly; selected
  top-level keys (`metadata`, `v2_1_changes_summary`,
  `source_owner_questions_open`, `data_quality`) are chunked as text into
  the lexical index but never vectorized.
- The **ontology entity descriptions** as a standalone corpus. They flow
  into entity payloads but no "ontology-aware" retrieval exists.

---

## 3. What each retrieval layer plays

| Layer | Role | File |
|-------|------|------|
| Routed | Deterministic guardrails — 16 hardcoded triggers map a query to a known set of required files (e.g. `aultf_correction`, `harmony_3tuple`, `false_precision`). Routed hits carry a +1000 score boost so the fuser keeps them at the top. | `financials/qa/llm_eval/route_retrieval.py`, wrapped by `routed_source.py` |
| Lexical (chunk) | TF-IDF over markdown corpus + agent_chunks. Token-overlap with IDF and √-length normalization. Handles exact phrase / filename / project-code matches. No filters supported. | `financials/qa/rag_eval/retrieval_index.py`, wrapped by `chunk_source.py` |
| Entity | Per-entity hybrid: lexical IDF over the payload text + brute-force cosine over hashed vectors + alias substring + metadata word-boundary boost. Supports `MetadataFilter` (entity_types / verticals / confidences / state_versions / retrieval_tags_any/all). | `bedrock/retrieval/services/entity_retriever.py`, wrapped by `entity_source.py` |
| Fusion | RRF (Cormack 2009), k=60, optional per-source weights. Dedup by entity_id / chunk_id. Keeps every source's score components keyed `<source>.<component>` for explainability. | `bedrock/retrieval/orchestration/fusion.py` |
| Rerank | NoOp seam. Reserved for a later learned or LLM reranker. | `bedrock/retrieval/orchestration/rerank.py` |
| Pack | Deterministic context assembler: classify, order, budget, lineage, warnings, `pack_id`. Drops sections that would overflow budget; never partially truncates a section. | `bedrock/retrieval/packing/pack.py` |

The **routed layer is where most of the retrieval intelligence lives today.**
It is the layer that knows "Harmony cost questions need the 3‑tuple
guardrail", "Parkway Fields needs the AultF B‑suffix correction story",
"org-wide questions need the orgwide_unavailable guardrail." Vector
retrieval contributes when entities matter; otherwise it is dormant.

---

## 4. Embedding method detail

| Provider | Deterministic? | Offline? | API key? | Built? | Used by tests? | Notes |
|---|---|---|---|---|---|---|
| `HashingEmbeddingProvider` (`hashing-v1-d256`) | yes | yes | no | yes — current index | yes — `test_hashing_provider_is_deterministic`, `test_returns_canonical_entity_hits`, etc. | SHA-256 token-bucket + sign, L2-normalized. Lexical-sparse, not semantic. |
| `LocalEmbeddingProvider` (sentence-transformers `all-MiniLM-L6-v2`, 384‑d) | yes (model weights) | yes (after model download) | no | no | no | Lazy import. Would be a real semantic upgrade. Not exercised. |
| `VoyageEmbeddingProvider` (`voyage-3`, 1024‑d) | depends on Voyage | no | yes (`VOYAGE_API_KEY`) | no | no | Architecture plan calls this the eventual production default. Not exercised. |

**Cache:** `bedrock/embeddings/cache.py` is content-addressed
(`sha256(model_id + "::" + text)`) and stored in
`output/bedrock/embeddings_cache.parquet` (474 KB). Cache hits skip the
embedding call entirely. Combined with the hashing provider, retrieval is
**fully offline-deterministic** today — no network, no API key.

### What the hashing provider can and cannot do

It can:
- Distinguish `Harmony::B1::101` from `Harmony::MF1::101` (different
  payload text → different vectors).
- Score a query like "Harmony lot 101 cost" higher against the right
  lot than against a random project, because token overlap drives the
  vector and the lexical/alias/metadata components all reinforce it.

It cannot:
- Map "actual spend" → "vf_actual_cost" without an alias entry.
- Map "land development cost" → "site improvements" without an alias entry.
- Handle paraphrase like "where are we exposed to wrong cost numbers" →
  the false-precision guardrail; that has to be done by the routed layer.

The `EntityRetriever` partially compensates with:
- **Query expansion** via the ontology's `semantic_aliases` table:
  substring-matching the query against every alias and adding the
  `resolves_to` tokens to the lexical/vector query. This gives a
  controlled, ontology-driven synonym layer **but only for aliases that
  have been hand-curated.**
- **Alias / tag substring scoring** as a separate score component (0.2
  weight) so a query containing "actual cost" gets credit on any entity
  whose ontology aliases include that phrase.
- **Metadata word-boundary boost** (0.1 weight) — if the query mentions
  the canonical project / phase / lot number / stage by name, the
  matching entity gets +0.4 / +0.3 / +0.2 / +0.1 respectively. This is
  the single largest signal for project-specific queries because it is
  unaffected by embedding quality.

---

## 5. Is this enough for BCPD v0.1?

The six workflow tools:

| Tool | Retrieval used | Sufficient? |
|---|---|---|
| project_brief | Routed (`project_parkway_fields`, etc.) + state lookups | **Yes.** Project identity is selected by name from state; routed rules surface caveats. |
| margin_readiness | Routed (`reporting_readiness`, `false_precision`) + `data_quality` reads | **Yes.** Curated routing covers every assertion. |
| false_precision | Routed (`false_precision`) + state caveats | **Yes.** Rule was authored for this question. |
| change_impact | Routed (`version_change`, `aultf_correction`) + `v2_1_changes_summary` | **Yes.** Routed rules carry the dollar story. |
| meeting_prep | Routed (`meeting_prep`) + `source_owner_questions_open` | **Yes.** |
| owner_update | Routed (`executive_update`) + state metadata | **Yes.** |

Verdict on the scale requested:

- **Sufficient for controlled workflow tools:** **yes.**
- **Sufficient for bounded Q&A** (against the curated business / workflow
  / readiness eval sets that already exist under `financials/qa/`): **yes,**
  because the routed layer was authored to cover those questions.
- **Sufficient for arbitrary free-form chat:** **no.** The hashing
  embedding cannot bridge paraphrase, and the routed layer is finite —
  any question outside the 16 trigger families collapses to plain
  TF-IDF and ad-hoc lexical matching against project / phase / lot
  tokens.
- **Production-grade:** **not yet.** No semantic embeddings, no
  retrieval-quality / "insufficient evidence" threshold, no learned
  rerank, no golden retrieval-eval set distinct from the answer-eval set,
  no graph-style traversal between project → phase → lot → cost source.

---

## 6. Strengths

- **Offline-deterministic by construction.** Same input → same vectors,
  same hits, same `pack_id`. No network surface, no API key gating, no
  flaky tests. 150/150 tests pass green on a clean clone.
- **Explainability is built in, not bolted on.** Every entity hit
  decomposes into `lexical / vector / alias_match / metadata_boost`.
  Every fused hit keeps each source's components keyed by source name.
  The pack itself emits a deterministic `pack_id` over inputs + outputs
  and includes a sha256 content-hash per source file (`packing/pack.py`).
- **Lineage is preserved end-to-end.** `EmbeddingPayload.source_files`
  flows into `EntityHit.source_files` → `RetrievalHit.source_files` →
  the pack's `LineageRef` list. A caller can always answer
  "which file backs this fact."
- **Routed layer is high-precision and inspectable.** 16 explicit rules,
  each with a `name`, `triggers`, `required_files`, optional
  `preferred_sections`. Boost is uniform (+1000) and pack-time
  classification places routed/guardrail evidence first — by
  construction, the model cannot miss the guardrail when the rule fires.
- **Adapter discipline.** `bedrock/retrieval/retrievers/base.py` defines
  one Protocol; orchestrator/fuser/reranker never branch on source name.
  A learned dense source or a graph source plugs in by writing one new
  adapter file (`base.py` docstring §4).
- **Three embedding providers behind one Protocol.** Swapping from
  hashing to Voyage is a `--provider voyage` flag; the cache
  re-uses by `(model_id, text)` so re-builds amortize.
- **Filters are typed.** `MetadataFilter` lets a caller narrow to e.g.
  `entity_types=["lot"], confidences=["high"], retrieval_tags_any=["cost_bearing"]`
  before any scoring happens; the trace records each `(before, after)`
  candidate count for inspection.

---

## 7. Weaknesses

| # | Weakness | Where it bites | Severity |
|---|----------|----------------|---|
| 7.1 | Hashing embedding is not semantically rich. | Paraphrase recall, "what's exposed to false precision" style queries that don't share tokens with the canonical text. | **High** for free-form, **Low** for v0.1 workflow demo. |
| 7.2 | Routed layer is finite and hand-authored. 16 rules cover the goldens; a 17th class of question is undetected. | New question categories from real users; demo robustness in front of an audience that asks something unscripted. | **Medium** for demo, **High** for chat. |
| 7.3 | No synonym/alias table for **project code variants**. Routed triggers list specific aliases (`aultf`, `ault-f`, `pwft1`) per rule, but the entity index relies on the ontology's `semantic_aliases` plus whatever happens to appear in `canonical_project`. A query that uses an unlisted nickname routes to plain lexical and may miss. | Project nicknames spoken in meetings (e.g. "the Ammon job") that aren't canonical. | **Medium.** |
| 7.4 | No learned dense embedding model in the live index. Both upgrade paths (`local`, `voyage`) exist as classes but have **zero test coverage past instantiation** and no live parquet built with them. The pipeline contract is in place; the proof that swapping providers actually improves recall is not. | Trust in the upgrade path. | **Medium.** |
| 7.5 | No persistent vector DB. The retriever brute-forces cosine over an in-memory 5,576 × 256 matrix; at MiniLM (384‑d) or Voyage (1,024‑d) that grows to ~22 MB per provider. Still fine on a laptop, but doesn't scale beyond BCPD to org-wide. | If/when we widen to Hillcrest + Flagship Belmont, or add operational entities beyond lot/phase/project. | **Low** for v0.1, **High** later. |
| 7.6 | No cross-entity graph traversal. Retrieving a lot does not pull in its phase, its project, its cost sources, its guardrails — each layer must be queried separately and the pack assembled later. The orchestrator does not know lots belong to phases. | Composite workflow questions ("for Parkway PWFS2 cost basis, what evidence?") rely on the rules layer to know to surface project + phase + decoder. | **Medium.** |
| 7.7 | No query expansion beyond ontology aliases. No spelling tolerance, no number-token expansion (`B1` vs `b-1` vs `phase B`), no abbreviation fanout. | Real meeting transcripts that misspell or abbreviate. | **Medium.** |
| 7.8 | No retrieval confidence score or "insufficient evidence" threshold. The retriever always returns top‑k; callers can read `trace.candidate_count_after_filters` and per-hit `combined_score`, but no callsite branches on "the best hit's score is below X — refuse instead of answer." | False-confidence on out-of-scope questions. | **High** for chat, **Low** for workflow demo (refusal is in the system prompt). |
| 7.9 | No retrieval eval **distinct from answer eval**. The closest thing is `financials/qa/rag_eval/`, but its scoring measures answer quality, not whether the right chunk was retrieved before the LLM saw the context. | We cannot regression-test "did we surface guardrail X before answering question Y" independently of the answer text. | **Medium.** |
| 7.10 | Package/runtime mismatch in the Skill. `dist/bcpd-operating-state/` includes `bedrock/retrieval/orchestration` and `bedrock/retrieval/retrievers/{base,chunk_source,routed_source}.py` but **does not include** `bedrock/embeddings/` or `bedrock/retrieval/services/entity_retriever.py` and **does not include** `output/bedrock/entity_index.parquet`. If any caller inside the package flips `BcpdContext(add_entity_source=True)`, the lazy import inside `bcpd_workflows.py:88–89` raises `ModuleNotFoundError`. The MANIFEST and PACKAGING_CHECKLIST never list these as runtime-required. | A future engineer enabling EntitySource will fail at import. The Skill is consistent with what it actually runs today (the demo path does not toggle it on), but the latent gap is silent. | **Medium.** Not urgent because the path is dead in v0.1, but should be documented. |
| 7.11 | `_surface_warnings` in `entity_retriever.py:373–378` contains a confusing list comprehension over `h.entity.fields.get(w.applies_to) and "" or ""` that always evaluates to `False`. The fallback branches still produce useful warnings (the `cost_is_inferred` / `missing_is_not_zero` heuristics catch the live cases), but the intended primary path is effectively dead code. | Warning surface narrower than designed. | **Low.** Cosmetic but worth a note. |

---

## 8. Does this support the operating-state thesis?

In plain English: **yes for structured / known questions, partially for
free-form questions.**

**Where it is strong:**
- Project / phase / lot identity grounding. The metadata-boost component
  reliably pulls the right lot when a query names project + phase + lot.
- Lineage. Every retrieved fact carries its source file; the packer
  hashes those files; the LLM has no ambiguity about provenance.
- Guardrail coverage. The routed layer means high-stakes caveats
  (org-wide unavailable, range/shell rows, inferred decoder rules,
  Harmony 3-tuple) always lead the pack when their triggers fire.
- Confidence propagation. `EmbeddingPayload` carries `confidence`,
  `EntityHit` carries it, `RetrievalHit` carries it, the pack surfaces
  auto-warnings for `inferred` / `low` hits.

**Where it is still mostly heuristic:**
- Paraphrase / synonym recall depends on hand-curated aliases.
- "Which project does this nickname refer to" depends on the routed
  rules' trigger lists.
- "Reconstruct the operating state for X" composite reasoning is
  emergent from the LLM, not the retriever — the retriever returns a
  flat ranked list and the packer concatenates; no graph traversal.

---

## 9. Recommended next steps

### Do now — before demo

- **D-NOW-1: Document the package/runtime gap.** Add a short
  PACKAGING note that `add_entity_source=True` is **not** supported in
  the shipped Skill and either (a) ship the missing modules and parquet,
  or (b) refuse-with-a-helpful-error when the flag is toggled inside the
  package. Choice (b) is one `try/except ImportError` change. This is
  about removing a hidden cliff, not adding capability.
- **D-NOW-2: Sweep dead branch in `_surface_warnings`.** The expression
  at `bedrock/retrieval/services/entity_retriever.py:373–378` is a
  no-op. Either delete it or replace it with the intended logic
  (test the field's value against the warning's `applies_to`). Cosmetic
  but it is in a hot path that a reviewer will read first. No urgent
  behavior change.

### Do soon — before broader Q&A usage

- **D-SOON-1: Add a project-alias / nickname table.** A single
  `state/aliases.json` keyed by `canonical_project` listing every
  spoken variant (e.g. `"Ammon": ["the Ammon job", "ammon site",
  "AM", "AMM"]`). Loaded into both (a) the EntityRetriever's
  `_alias_table` (already substring-matched against the query) and
  (b) the routed layer's trigger lists. This is one file + one loader
  + one test; low blast radius, immediate paraphrase win.
- **D-SOON-2: Build the parquet with `LocalEmbeddingProvider` once.**
  Run `python -m bedrock.embeddings.build --provider local` and commit
  the parquet to an alternate path
  (`output/bedrock/entity_index.minilm.parquet`). Add one test that
  loads it and runs the same five queries the hashing tests use. This
  validates the provider seam works end-to-end and gives us a known-good
  semantic baseline without changing the default.
- **D-SOON-3: Retrieval-only eval set.** A golden file under
  `financials/qa/rag_eval/retrieval_goldens.json` listing
  `{query → required_source_files / required_entity_ids}` for the six
  workflow tools' representative questions. Score is purely "did the
  top-k contain the required hit?" — independent of any LLM. Run in CI
  with both `hashing` and `local` providers so a future upgrade can be
  evaluated.
- **D-SOON-4: Retrieval confidence threshold.** Expose
  `trace.combined_score_max` and let callers refuse when it falls below
  a documented floor (e.g. 0.15 with hashing). The infrastructure is
  already present in `RetrievalTrace.top_candidates`; no new state.

### Do later — for production

- **D-LATER-1: Replace hashing with Voyage (or local MiniLM) as the
  default once D-SOON-2/3 demonstrate a recall delta.** No
  architectural change; flip the default in `_build_provider`.
- **D-LATER-2: Cross-entity graph traversal.** A `GraphSource` adapter
  that takes a retrieved lot and pulls its phase, project, and
  associated cost sources by id before fusion. Implements the existing
  Retriever Protocol; no orchestrator change.
- **D-LATER-3: Persistent vector DB.** Only if/when we widen the
  vertical to non-BCPD entities, or the index exceeds ~50 k rows. With
  256–1,024 dims that is still in-memory territory; brute force at
  current scale is fine and explainable. Avoid premature DB adoption.
- **D-LATER-4: Learned reranker** plugged into the existing `Reranker`
  seam. Defer until D-SOON-3 gives us a numerator to measure against.

---

## 10. Should we upgrade embeddings now?

**Recommendation: keep current deterministic hashing for v0.1 and add
semantic embeddings as an optional second layer once a retrieval eval
exists.**

Reasoning:
- The six workflow tools do not use vector retrieval today
  (`bcpd_workflows.py:79–96`). Upgrading the provider does not change
  any tool output.
- The Skill demo path is offline-deterministic, which is a feature, not
  an accident. Adding Voyage now would either add an API-key gate or
  silently fall back to hashing — both worse than the current explicit
  default.
- Without a retrieval-only golden set (D-SOON-3), there is no way to
  prove the upgrade helped beyond anecdote.
- The seam already supports `--provider local|voyage`; flipping it later
  is a one-line change. No architecture is being painted into a corner.

Defer until after the Skill demo; revisit if/when the BCPD agent moves
into a free-form-chat surface.

---

## Appendix A — Tests run

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest \
    tests/test_entity_retrieval.py \
    tests/test_context_packing.py \
    tests/test_hybrid_orchestration.py \
    tests/test_route_retrieval.py \
    tests/test_bcpd_workflows.py
```

Result: **150 passed in 9.24s**. Notable assertions covered:

- Hashing provider is deterministic over repeated calls and across cache
  reload (`tests/test_entity_retrieval.py:98–102`).
- Cache keys are deterministic and content-addressed
  (`test_cache_key_is_content_addressed`).
- Every entity hit carries the four score components
  (`test_score_components_present_per_hit`).
- 3-tuple distinction is preserved in entity results
  (`test_3tuple_distinction_preserved_in_results`).
- Inferred-cost warning fires on cost queries
  (`test_inferred_cost_warning_fires_on_cost_query`).
- Lexical-only mode yields zero vector score
  (`test_lexical_only_mode_returns_no_vector_score`).
- An unmatchable query produces hits below the vector noise floor
  (`test_unmatchable_query_returns_only_noise_floor`).
- Pack `pack_id` is deterministic on identical input, changes on query
  or budget change, and the pack is internally reconstructable from its
  own lineage.
- Routing rules `aultf_correction`, `harmco_commercial`, etc., fire on
  their triggers and do not false-positive on adjacent phrasings.

## Appendix B — Files inventoried

Core code paths:
- `bedrock/embeddings/build.py` — entity index builder, CLI, idempotent cache.
- `bedrock/embeddings/hashing.py` — `HashingEmbeddingProvider`, dim=256 default.
- `bedrock/embeddings/local.py` — sentence-transformers wrapper (dormant).
- `bedrock/embeddings/voyage.py` — Voyage wrapper (dormant; gated by `VOYAGE_API_KEY`).
- `bedrock/embeddings/cache.py` — content-addressed parquet cache.
- `bedrock/embeddings/payload.py` — `CanonicalEntity → EmbeddingPayload`.
- `bedrock/retrieval/services/entity_retriever.py` — hybrid scoring + trace.
- `bedrock/retrieval/orchestration/{hybrid,fusion,rerank,trace}.py`.
- `bedrock/retrieval/retrievers/{base,chunk_source,entity_source,routed_source}.py`.
- `bedrock/retrieval/packing/pack.py` — deterministic context assembler.
- `financials/qa/rag_eval/retrieval_index.py` — markdown / JSON-section TF-IDF index.
- `financials/qa/llm_eval/route_retrieval.py` — 16 routing rules.
- `core/tools/bcpd_workflows.py:49–101` — `BcpdContext`, where the orchestrator is wired (without EntitySource by default).

Artifacts:
- `output/bedrock/entity_index.parquet` — 5,576 rows, `hashing-v1-d256`, dim 256.
- `output/bedrock/embeddings_cache.parquet` — 474 KB, parquet, content-addressed.
- `output/agent_chunks_v2_bcpd/index.json` — 44 chunks indexed; **not vectorized**.
- `output/runtime_demo/*.md` — six workflow tool outputs, all written by the
  deterministic packer path (no embeddings involved).
- `dist/bcpd-operating-state/MANIFEST.json` — 103 files, 5.45 MB; ships
  `bedrock/retrieval/orchestration` + `bedrock/retrieval/retrievers/{base,chunk_source,routed_source}.py`
  + the state JSON + the agent chunks. **Does not ship** `bedrock/embeddings/`,
  `bedrock/retrieval/services/entity_retriever.py`, or `output/bedrock/entity_index.parquet`.
