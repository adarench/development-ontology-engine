"""Walk the schema registry and fill in `description` for each field via Claude.

Fields are grouped by (data_source, table_name) so the LLM sees a whole table
in one call — much better cross-field reasoning ("net_amount = gross_amount
minus deductions") and far fewer total API calls than the per-field path.

Large tables are split into chunks of `--chunk-size` (default 50) to stay
within output-token limits.

Usage:
    python3 -m schemas.enrich_descriptions                  # missing only
    python3 -m schemas.enrich_descriptions --force          # rewrite all
    python3 -m schemas.enrich_descriptions --chunk-size 30  # smaller chunks
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

from schemas.context import DEFAULT_CONTEXT_FILES, estimate_tokens, load_context
from schemas.env import load_env
from schemas.registry import DEFAULT_REGISTRY_PATH, DatasourceField, SchemaRegistry

DEFAULT_MODEL      = "claude-haiku-4-5-20251001"
DEFAULT_CHUNK_SIZE = 50
MAX_TOKENS         = 8192

# Guard patterns: descriptions that match any of these contain code/internal
# artifact references and should be flagged for retry.
import re as _re
_CODE_REF_PATTERNS = [
    _re.compile(p, _re.IGNORECASE) for p in [
        r"\.py\b",
        r"\bstage_dictionary\b",
        r"\bclickup_pipeline\b",
        r"\bbuild_[a-z_]+\b",
        r"\bpipelines?/",
        r"\bdata/staged/",
        r"\bstaged_[a-z_]+",
        r"\bcanonical_[a-z_]+_v\d",
        r"\b(LOT_STATE_WATERFALL|LotState waterfall)\b",
    ]
]


def _has_code_reference(description: str) -> bool:
    return any(p.search(description) for p in _CODE_REF_PATTERNS)

STUB_DESCRIPTION = "[stub description — replace by wiring describe_table() to the LLM API]"

INSTRUCTIONS = """You are a data dictionary writer for Flagship Homes' land development data.

# HARD RULE — read this before anything else
DESCRIPTIONS DESCRIBE THE DATA. NOT THE CODE THAT PROCESSES IT.

NEVER mention any of the following in any description, under any circumstance:
  • Python files, scripts, modules, or pipeline code (anything ending in `.py`,
    or named like `stage_dictionary`, `clickup_pipeline`, `build_phase_state`,
    `pipelines/...`)
  • Staged / canonical artifact names (`staged_*`, `canonical_*_v0`,
    `staged_clickup_tasks`, `staged_project_crosswalk_v0`)
  • Internal repo paths (`data/staged/...`, `output/...`)
  • Phrases like "used by [code]", "consumed by [code]", "validated by [code]",
    "applied via [code]"

The context block below references these things — that is background for YOU,
not output. Mention upstream BUSINESS SYSTEMS and SOURCE FILES (the data
itself), never the consuming pipeline.

If you violate this rule the description is unusable.

# Task
You will be given a TABLE (its source and logical name) and a list of FIELDS in
that table — each with its name, data_type, sample values, and other metadata.
Write a dense, factual description for EACH field (1-2 sentences, ~30-60 words).

Each description must be DATA-CENTRIC. Describe:
  • what the field semantically represents,
  • what kinds of values it holds (using its samples and data type),
  • what upstream BUSINESS SYSTEM or SOURCE FILE it comes from (e.g. "DataRails
    GL extract", "ClickUp task export", "Vertical Financials workbook",
    "Collateral Report"),
  • how it relates to OTHER fields in the same table when relevant.

Every description MUST begin with the literal `field_name` followed by a colon
and a space, e.g. `LotArea(sqft): Lot area in square feet, ...`. This is
required so descriptions embed well for vector retrieval — the column name
must appear at the start of the text, exactly as it appears in the source
header (preserve casing, punctuation, whitespace).

Use the table context and the OTHER fields in the same table to inform each
description. For example, if you see paired fields like `gross_amount` and
`net_amount`, describe their relationship. If field names follow a pattern
(`<entity>_id`, `<entity>_name`), call out the pattern.

The BUSINESS CONTEXT block below covers: how the business is structured
(community → phase → lot), the upstream source systems (DataRails GL,
Vertical Financials, QuickBooks, ClickUp, inventory closing reports,
collateral reports, allocation workbooks), canonical field authority,
known data quirks (DataRails 2.16× row multiplication, VF lot-code decoding,
era boundaries, 0% phase fill on GL), and the confidence vocabulary
(`high`, `medium`, `low`, `inferred`, `inferred-unknown`, `unmapped`,
`tie-out only`).

Lean on this context to ground field meanings. If the table's `data_source`
URI matches a file described in the context (e.g. `Vertical Financials.csv`,
`Collateral Report`, `Lot Data`, `2025Status`, `LH Allocation`,
`Inventory _ Closing Report`, `api-upload.csv`), tie each field back to that
source's business role. Use specific business terminology (community, phase,
lot, BCPD scope, GL, collateral pool, decoder, etc.) when it fits.

Do NOT invent meanings for cryptic abbreviations or jargon that the context
does not cover. If a field name plus its samples does not support a confident
interpretation AND nothing in the context maps to it, describe what is
observable (data type, sample shape, nullability) and explicitly note that
the semantic meaning is unclear from the available metadata.

Return ONLY a JSON object mapping each field's `id` to its description string.
No prose outside the JSON. No markdown. No code fences. Every input field id
must appear as a key in the output."""

# Loaded once on first use; reused across all chunks in a run so prompt caching
# keeps the cost flat regardless of how many chunks we process.
_CONTEXT_TEXT: str | None = None
_CONTEXT_PATHS: tuple[str, ...] = DEFAULT_CONTEXT_FILES


def configure_context(paths: tuple[str, ...] | list[str] | None) -> None:
    """Override the set of context files. Reset the cache so the next call reloads."""
    global _CONTEXT_TEXT, _CONTEXT_PATHS
    _CONTEXT_TEXT  = None
    _CONTEXT_PATHS = tuple(paths) if paths else DEFAULT_CONTEXT_FILES


def _get_context_text() -> str:
    global _CONTEXT_TEXT
    if _CONTEXT_TEXT is None:
        _CONTEXT_TEXT = load_context(_CONTEXT_PATHS)
    return _CONTEXT_TEXT


def _build_system_blocks() -> list[dict]:
    """Build the system prompt as cacheable blocks: instructions + context."""
    context_block_text = (
        "# BUSINESS CONTEXT (authoritative — do not contradict)\n\n"
        + _get_context_text()
    )
    # Two blocks: short instructions (uncached, may evolve) + long context
    # (marked ephemeral so subsequent calls within the 5-min TTL hit the cache).
    return [
        {"type": "text", "text": INSTRUCTIONS},
        {"type": "text", "text": context_block_text,
         "cache_control": {"type": "ephemeral"}},
    ]


def _build_user_prompt(table_key: tuple[str, str | None], fields: list[DatasourceField]) -> str:
    data_source, table_name = table_key
    payload = {
        "table": {
            "data_source": data_source,
            "table_name":  table_name,
            "source_type": fields[0].source_type,
            "field_count": len(fields),
        },
        "fields": [{
            "id":              f.id,
            "field_name":      f.field_name,
            "field_path":      f.field_path,
            "data_type":       f.data_type,
            "nullable":        f.nullable,
            "sample_values":   f.sample_values,
            "raw_description": f.raw_description,
        } for f in fields],
    }
    return "Describe every field in this table:\n\n" + json.dumps(payload, indent=2, default=str)


def get_anthropic_client():
    try:
        import anthropic
    except ImportError as exc:
        raise SystemExit("anthropic SDK not installed. Run: pip3 install anthropic") from exc
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY environment variable is not set")
    return anthropic.Anthropic()


def _parse_json_object(text: str) -> dict[str, str]:
    """Tolerantly parse a JSON object out of an LLM reply.

    Walks brace depth (string-aware) to extract the first balanced `{...}` —
    this is robust against trailing prose / commentary / a second JSON object
    that the model sometimes appends despite instructions.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()

    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found in response")

    depth     = 0
    in_string = False
    escape    = False
    end       = -1
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        raise ValueError(f"Unbalanced JSON object starting at char {start}")

    obj = json.loads(text[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object, got {type(obj).__name__}")
    return {str(k): str(v) for k, v in obj.items()}


def _stub_describe_table(client, model, table_key, fields) -> dict[str, str]:
    return {f.id: STUB_DESCRIPTION for f in fields}


def _real_describe_table(client, model, table_key, fields) -> dict[str, str]:
    response = client.messages.create(
        model      = model,
        max_tokens = MAX_TOKENS,
        system     = _build_system_blocks(),
        messages   = [{"role": "user", "content": _build_user_prompt(table_key, fields)}],
    )
    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    return _parse_json_object(text)


# Swap to `_real_describe_table` once you're ready to call the LLM.
describe_table = _real_describe_table


def _group_by_table(fields: Iterable[DatasourceField]) -> "OrderedDict[tuple[str, str | None], list[DatasourceField]]":
    groups: OrderedDict[tuple[str, str | None], list[DatasourceField]] = OrderedDict()
    for f in fields:
        key = (f.data_source, f.table_name)
        groups.setdefault(key, []).append(f)
    return groups


def _chunked(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def enrich(
    registry_path:    Path,
    *,
    force:            bool = False,
    model:            str  = DEFAULT_MODEL,
    client                 = None,
    chunk_size:       int  = DEFAULT_CHUNK_SIZE,
    checkpoint_every: int  = 25,
    limit:            int | None = None,
) -> tuple[int, int, int]:
    """Enrich descriptions in-place. Returns (updated, skipped, failed).

    Fields are grouped by table; each group is split into chunks of
    `chunk_size` and described in one LLM call. Saves the registry every
    `checkpoint_every` updates so a crash mid-run loses ≤ that many calls.
    """
    registry = SchemaRegistry(registry_path)
    if len(registry) == 0:
        print(f"Registry at {registry_path} is empty; nothing to enrich.", file=sys.stderr)
        return 0, 0, 0

    if client is None and describe_table is not _stub_describe_table:
        client = get_anthropic_client()

    todo = [f for f in registry if force or not f.description]
    skipped = len(registry) - len(todo)
    if limit is not None and limit > 0:
        todo = todo[:limit]
        print(f"--limit {limit}: processing first {len(todo)} of the un-described fields",
              file=sys.stderr)
    if not todo:
        print("All fields already described. Use --force to redo.", file=sys.stderr)
        return 0, skipped, 0

    groups = _group_by_table(todo)
    total_chunks = sum(((len(v) + chunk_size - 1) // chunk_size) for v in groups.values())
    print(
        f"Enriching {len(todo)} field(s) across {len(groups)} table(s) "
        f"in {total_chunks} chunk(s) of <= {chunk_size}",
        file=sys.stderr,
    )

    updated = 0
    failed  = 0
    pending = 0
    chunk_i = 0

    for table_key, fields in groups.items():
        for chunk in _chunked(fields, chunk_size):
            chunk_i += 1
            data_source, table_name = table_key
            label = f"{table_name or '<no table>'} ({len(chunk)} fields)"
            print(f"  [chunk {chunk_i}/{total_chunks}] {label}", file=sys.stderr)
            try:
                descriptions = describe_table(client, model, table_key, chunk)
            except Exception as exc:
                failed += len(chunk)
                print(f"    FAILED chunk: {exc}", file=sys.stderr)
                continue

            requested_ids = {f.id for f in chunk}
            returned_ids  = set(descriptions.keys())
            missing       = requested_ids - returned_ids
            extra         = returned_ids - requested_ids
            if missing:
                print(f"    WARN missing {len(missing)} id(s) in response (will retry next run): "
                      f"{sorted(missing)[:3]}{'...' if len(missing) > 3 else ''}",
                      file=sys.stderr)
            if extra:
                print(f"    WARN response had {len(extra)} unrequested id(s); ignored",
                      file=sys.stderr)

            for f in chunk:
                desc = descriptions.get(f.id)
                if not desc:
                    failed += 1
                    continue
                if _has_code_reference(desc):
                    print(f"    REJECTED {f.id}: description contains code reference; "
                          f"left null for retry", file=sys.stderr)
                    failed += 1
                    continue
                f.description = desc
                updated += 1
                pending += 1

            if checkpoint_every and pending >= checkpoint_every:
                registry.save()
                pending = 0
                print(f"    [checkpoint] saved {updated} so far", file=sys.stderr)

    registry.save()
    return updated, skipped, failed


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path",  type=Path, default=DEFAULT_REGISTRY_PATH,
                        help="Path to registry JSON")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Anthropic model ID")
    parser.add_argument("--force", action="store_true",
                        help="Re-describe fields that already have a description")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                        help=f"Fields per LLM call (default {DEFAULT_CHUNK_SIZE})")
    parser.add_argument("--checkpoint-every", type=int, default=25,
                        help="Save the registry every N updates (default 25, 0=only at end)")
    parser.add_argument("--context-files", nargs="*", default=None,
                        help="Override the default context files (repo-relative paths). "
                             "Pass an empty list to disable context entirely.")
    parser.add_argument("--show-context", action="store_true",
                        help="Print the loaded context size and file list, then exit.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only the first N un-described fields (test runs).")
    args = parser.parse_args(argv)

    if args.context_files is not None:
        configure_context(args.context_files)

    if args.show_context:
        text = _get_context_text()
        print(f"Context: {len(_CONTEXT_PATHS)} file(s), "
              f"{len(text):,} chars (~{estimate_tokens(text):,} tokens)",
              file=sys.stderr)
        for p in _CONTEXT_PATHS:
            print(f"  - {p}", file=sys.stderr)
        return 0

    updated, skipped, failed = enrich(
        args.path,
        force            = args.force,
        model            = args.model,
        chunk_size       = args.chunk_size,
        checkpoint_every = args.checkpoint_every,
        limit            = args.limit,
    )
    print(f"Done. updated={updated} skipped={skipped} failed={failed} path={args.path}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
