"""BCPD v2.1 RAG-style retrieval/eval harness.

Sibling to the deterministic Q&A harness in `financials/qa/`. This harness
exists to test whether the existing v2.1 state + context + reports support
GROUNDED LLM/RAG-style answers — i.e. whether a retrieval layer over the
existing markdown corpus can recover the right facts, citations, confidence,
caveats, and refusal behavior.

Hard contract:
- Read-only against state/source artifacts.
- No writes outside `financials/qa/rag_eval/` and `output/rag_eval/`.
- Deterministic by default (no API).
- LLM mode is gated on environment variable; not enabled by default.

Modules:
- eval_questions   — 15 eval questions with required facts / guardrails / sources.
- retrieval_index  — lightweight lexical retrieval over the v2.1 markdown corpus.
- run_rag_eval     — end-to-end runner: retrieve → answer → guardrail-check → write.
- score_answers    — scoring functions (retrieval, guardrails, hallucination risk,
                     state_reconstruction_score 0-3).
"""
