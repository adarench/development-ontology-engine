---
chunk_id: guardrail_read_only_qa
chunk_type: guardrail
title: Guardrail: Read-only Q&A rules
project: n/a
source_files:
  - financials/qa/__init__.py
  - financials/qa/bcpd_state_qa.py
  - tests/test_bcpd_state_qa_readonly.py
state_version: v2.1
confidence: high
last_generated: 2026-05-04
allowed_uses:
  - RAG grounding for refusal / caveat decisions
  - Anchor for any answer that touches this guardrail's scope
caveats:
  - Optional LLM mode requires explicit API key in env; default is deterministic.
---

## Plain-English summary

The Q&A layer (`financials/qa/`) is strictly read-only against the v2.1 state and all source / staged / report files. It writes ONLY to three allowed paths: `output/bcpd_state_qa_results.json`, `output/bcpd_state_qa_examples.md`, `output/bcpd_state_qa_eval.md`. A test (`tests/test_bcpd_state_qa_readonly.py`) verifies this contract every run.

## Key facts

- Protected paths: 11 (state JSON + companion docs + reports + ontology + field map + source map).
- Allowed writes: 3 (results JSON, examples MD, eval MD).
- Default mode: deterministic, no API calls, 15 fixed handlers.
- Optional LLM mode: gated on ANTHROPIC_API_KEY env var; never hardcoded.
- Test verifies sha256 + size of every protected path before/after run.

## Evidence / source files

- `financials/qa/__init__.py`
- `financials/qa/bcpd_state_qa.py`
- `tests/test_bcpd_state_qa_readonly.py`

## Confidence

High confidence; enforced by code + test.

## Caveats

- Optional LLM mode requires explicit API key in env; default is deterministic.

## Safe questions this chunk grounds

- What does the read-only Q&A harness write?
- How is the read-only contract enforced?
- Can the harness call an external LLM API?

## Questions to refuse or caveat

- Modify the v2.1 state JSON via the Q&A harness? — REFUSE.
- Write to source / staged / canonical files from the QA layer? — REFUSE.
