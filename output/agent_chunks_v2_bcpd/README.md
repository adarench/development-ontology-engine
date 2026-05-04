# BCPD v2.1 Agent Context Chunks

_Generated: 2026-05-04_  |  _State version: v2.1_  |  _Total chunks: 44_

Source-backed context chunks for retrieval-augmented agent answers. Each chunk is a self-contained markdown file with frontmatter (chunk_id, type, source_files, confidence, allowed_uses, caveats) and a fixed body shape (Plain-English summary, Key facts, Evidence/source files, Confidence, Caveats, Safe questions, Questions to refuse or caveat).

Chunks are **derived artifacts**: they do not invent facts. Every claim is traceable to a v2.1 source file. Confidence labels reflect what's in the source — never promoted.

## Counts by type

| chunk_type | count |
|---|---:|
| cost_sources | 6 |
| coverage | 5 |
| guardrails | 8 |
| projects | 18 |
| sources | 7 |
| **total** | **44** |

## Layout

```
output/agent_chunks_v2_bcpd/
├── README.md                 (this file)
├── index.json                (machine-readable manifest)
├── chunk_quality_report.md   (audit + retrieval strategy)
├── projects/                 (one chunk per BCPD project)
├── coverage/                 (GL/ClickUp/triangle/no-GL/validation queue)
├── cost_sources/             (VF, DR-dedup, QB tie-out, range, commercial, missing-not-zero)
├── guardrails/               (BCPD-only, org-wide-blocked, inferred decoder, 3-tuple, etc.)
└── sources/                  (Inventory, VF, DR, QB, Collateral, Allocation, ClickUp)
```

## How to use these chunks

- **Retrieval pattern**: pull the project chunk relevant to the question, plus any guardrail and source/cost-source chunks the question implicates. Never answer cost/coverage questions from a project chunk alone.
- **Confidence labels**: respect them. A chunk labeled `inferred` has not been source-owner-validated; cite that label in any answer that uses it.
- **Refusals**: every chunk has a 'Questions to refuse or caveat' section. Use it.
- **Regeneration**: `python3 financials/build_agent_chunks_v2_bcpd.py`. Idempotent if upstream artifacts haven't changed.

See `chunk_quality_report.md` for the full audit + recommended retrieval strategy.
