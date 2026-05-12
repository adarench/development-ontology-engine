# `state/process_rules/`

Versioned, hand-authored process rules for BCP Dev allocation and accounting. Read by v0.2 tools registered in `core/tools/bcp_dev_workflows.py`.

## What lives here

| File | Purpose |
|---|---|
| `account_prefix_matrix_v1.json` | The 8 posting + 5 alloc accounts and the prefix-validity matrix (which job prefix can hit which account). |
| `account_chart_v1.json` | Posting / Alloc account chart — full names, categories, paired-account relationships. |
| `allocation_methods_v1.json` | Ratified and unratified allocation methods (land_at_mda, water_by_letter, direct_per_phase, indirect_community, warranty_at_sale, range_row_unratified). |
| `clickup_gl_event_map_v1.json` | Mapping from ClickUp lifecycle status changes to AccountingEvent ids, required fields, and GL entries to fire. |
| `job_prefix_glossary_v1.json` | LND / MPL / IND / DIR / WTR / CPI definitions and scope. |
| `monthly_review_checks_v1.json` | Inventory-by-Job style detective controls (~6–10 checks). |
| `status_taxonomy_v1.json` | ~14 ClickUp lot lifecycle statuses with GL relevance flags and event triggers. |

## Conventions

- **Schema version in filename.** Bump the suffix (`_v2`) on breaking changes; never edit a versioned file in place after publication.
- **`generated_at` and `source`** are required top-level fields on every file.
- **`verification_status: "pending_source_doc_review"`** marks rules authored from briefing text before originals are recovered. Removed only after Finance one-pass review.
- **`ratified: true|false`** marks whether the rule has source-owner sign-off. Unratified rules trigger explicit refusal in tools.

## Ownership

- **Authoring** — Agent C (Process Rules) on Day 2 of the v0.2 plan.
- **Verification** — Finance (account / prefix matrix); Finance + Land (allocation methods); Operations (status taxonomy).
- **Cadence** — Reviewed at month-end; updated when underlying process changes.

## How tools consume these files

Tools load via `BcpDevContext` (`core/agent/bcp_dev_context.py`). Tools never mutate. Each tool declares which rule files it reads in its provenance block.

## Source of truth

The narrative behind these files is `docs/bcp_dev_process_ontology_v1.md`. The implementation plan is `docs/bcp_dev_allocation_accounting_tool_family_plan.md`.

When the original `.docx` / `.pptx` source guides are recovered, they land in `data/raw/process_docs/` and are referenced by `source:` fields in each rule file.
