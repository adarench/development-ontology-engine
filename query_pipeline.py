#!/usr/bin/env python3
"""
Multi-agent RAG data retrieval pipeline for Flagship Homes development data.

Pipeline:
  1. Intent agent (Opus) — expand user prompt into 3 semantic embedding strings
  2. RAG lookup           — match queries against field embeddings [placeholder]
  3. Schema validator     — verify required tables/columns exist; search schema
                            via tool use if RAG results are insufficient
  4. Data retriever       — given verified schema plan, produce retrieval plan

Usage:
    python3 query_pipeline.py "Which lots are in HORIZONTAL_IN_PROGRESS state?"
    python3 query_pipeline.py --verbose "What is the total cost for BCPD phase 3?"
    python3 query_pipeline.py --json "Show me lot lifecycle dates for phase 2"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent

sys.path.insert(0, str(REPO_ROOT))
from schemas.env import load_env

load_env()

OPUS_MODEL = "claude-opus-4-7"

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def _get_client():
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set — check your .env file.")
    return anthropic.Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Company context
# ---------------------------------------------------------------------------

def load_company_context() -> str:
    """Load key business context docs into a single string for agent prompts."""
    candidates = [
        REPO_ROOT / "CONTEXT_PACK.md",
        REPO_ROOT / "docs" / "source_to_field_map.md",
        REPO_ROOT / "docs" / "ontology_v0.md",
    ]
    parts: list[str] = []
    for path in candidates:
        if path.exists():
            parts.append(f"=== {path.name} ===\n{path.read_text()}\n")

    if not parts:
        raise SystemExit("No context files found — expected CONTEXT_PACK.md in repo root.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Agent 1: Intent expander
# ---------------------------------------------------------------------------

_INTENT_SYSTEM = """\
You are a data retrieval specialist for Flagship Homes, a real-estate /
land-development company. Given a user question about their development data,
generate exactly 3 different semantic search strings to use for embedding-based
column lookup.

Each string should:
- Describe what KIND of data is being requested, not the question itself
- Use domain vocabulary that would appear in source data or field descriptions
- Approach the query from a different angle:
    #1 — the entity or record type (lot, phase, project, GL transaction …)
    #2 — the measurement or metric (cost, date, status, count …)
    #3 — the temporal/contextual dimension (period, source system, join key …)
- Be 1–3 dense, factual sentences

Return ONLY a JSON object:
{{
  "embedding_queries": ["string 1", "string 2", "string 3"],
  "reasoning": "one sentence explaining the decomposition strategy"
}}

Business context:
<context>
{context}
</context>
"""


def _extract_json(text: str) -> Any:
    """Extract the first JSON object or array from a text response."""
    # strip markdown fences
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fenced:
        return json.loads(fenced.group(1))
    # find first { or [
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if m:
        return json.loads(m.group(1))
    return json.loads(text.strip())


def generate_embedding_queries(
    client, prompt: str, context: str, *, verbose: bool = False
) -> list[str]:
    """Agent 1: Expand user prompt into 3 semantic search strings."""
    if verbose:
        print("\n[Agent 1 — intent expander] Generating embedding queries…", file=sys.stderr)

    response = client.messages.create(
        model=OPUS_MODEL,
        max_tokens=1024,
        system=_INTENT_SYSTEM.format(context=context),
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    try:
        data = _extract_json(raw)
        queries: list[str] = data["embedding_queries"]
        if verbose:
            print(f"  Reasoning: {data.get('reasoning', '')}", file=sys.stderr)
            for i, q in enumerate(queries, 1):
                print(f"  Query {i}: {q}", file=sys.stderr)
        return queries
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(
            f"Intent agent returned malformed JSON: {exc}\nRaw response:\n{raw}"
        ) from exc


# ---------------------------------------------------------------------------
# Step 2: RAG lookup — placeholder
# ---------------------------------------------------------------------------

# Representative hardcoded results that cover the most common query surfaces.
# Replace this function with real embedding similarity search when embeddings
# are wired up.
_PLACEHOLDER_RAG_RESULTS: list[dict] = [
    {
        "id": "collateral_dec2025_01_claude.xlsx_-_lot_data.Project",
        "table_name": "Collateral Dec2025 01 Claude.xlsx - Lot Data",
        "field_name": "Project",
        "data_type": "string",
        "description": "Project / subdivision name (e.g. BCPD, Lomond Heights). Primary grouping key for rollups.",
        "data_source": "file:///Users/jakob.klobcic/work-projects/development-ontology-engine/data/raw/financials/Collateral%20Dec2025%2001%20Claude.xlsx%20-%20Lot%20Data.csv",
    },
    {
        "id": "collateral_dec2025_01_claude.xlsx_-_lot_data.Phase",
        "table_name": "Collateral Dec2025 01 Claude.xlsx - Lot Data",
        "field_name": "Phase",
        "data_type": "string",
        "description": "Phase identifier within the project. Combined with LotNo. forms the lot primary key.",
        "data_source": "file:///Users/jakob.klobcic/work-projects/development-ontology-engine/data/raw/financials/Collateral%20Dec2025%2001%20Claude.xlsx%20-%20Lot%20Data.csv",
    },
    {
        "id": "collateral_dec2025_01_claude.xlsx_-_lot_data.LotNo.",
        "table_name": "Collateral Dec2025 01 Claude.xlsx - Lot Data",
        "field_name": "LotNo.",
        "data_type": "string",
        "description": "Lot number within the phase. Combined with Phase forms the primary key for a development lot.",
        "data_source": "file:///Users/jakob.klobcic/work-projects/development-ontology-engine/data/raw/financials/Collateral%20Dec2025%2001%20Claude.xlsx%20-%20Lot%20Data.csv",
    },
    {
        "id": "collateral_dec2025_01_claude.xlsx_-_2025status.current_stage",
        "table_name": "Collateral Dec2025 01 Claude.xlsx - 2025Status",
        "field_name": "Current Stage",
        "data_type": "string",
        "description": "Current lifecycle stage of the lot (HORIZONTAL_IN_PROGRESS, FINISHED_LOT, CLOSED, etc.).",
        "data_source": "file:///Users/jakob.klobcic/work-projects/development-ontology-engine/data/raw/financials/Collateral%20Dec2025%2001%20Claude.xlsx%20-%202025Status.csv",
    },
    {
        "id": "collateral_dec2025_01_claude.xlsx_-_2025status.permits_and_fees",
        "table_name": "Collateral Dec2025 01 Claude.xlsx - 2025Status",
        "field_name": "Permits and Fees",
        "data_type": "float",
        "description": "Permits and Fees cost-to-date component. Part of horizontal actual cost.",
        "data_source": "file:///Users/jakob.klobcic/work-projects/development-ontology-engine/data/raw/financials/Collateral%20Dec2025%2001%20Claude.xlsx%20-%202025Status.csv",
    },
    {
        "id": "collateral_dec2025_01_claude.xlsx_-_2025status.direct_construction",
        "table_name": "Collateral Dec2025 01 Claude.xlsx - 2025Status",
        "field_name": "Direct Construction - Lot",
        "data_type": "float",
        "description": "Direct Construction horizontal cost component (lot scope only, excludes vertical).",
        "data_source": "file:///Users/jakob.klobcic/work-projects/development-ontology-engine/data/raw/financials/Collateral%20Dec2025%2001%20Claude.xlsx%20-%202025Status.csv",
    },
    {
        "id": "lh_allocation_2025.10.xlsx_-_lh.Phase",
        "table_name": "LH Allocation 2025.10.xlsx - LH",
        "field_name": "Phase",
        "data_type": "string",
        "description": "Phase identifier in the Lomond Heights allocation workbook. Joins to inventory and GL.",
        "data_source": "file:///Users/jakob.klobcic/work-projects/development-ontology-engine/data/raw/financials/LH%20Allocation%202025.10.xlsx%20-%20LH.csv",
    },
    {
        "id": "clickup_naming_struct_-_sheet1.name",
        "table_name": "Clickup_Naming_Struct - Sheet1",
        "field_name": "name",
        "data_type": "string",
        "description": "Free-text ClickUp task name embedding lot/phase and work scope.",
        "data_source": "file:///Users/jakob.klobcic/work-projects/development-ontology-engine/data/raw/financials/Clickup_Naming_Struct%20-%20Sheet1.csv",
    },
]


def rag_lookup(queries: list[str], *, verbose: bool = False) -> list[dict]:
    """
    TODO: replace with real embedding similarity search.

    Full implementation requires:

    1. Pre-build an embedding index
       - Read every entry from schemas/datasource_schema.json
       - Call the embeddings API (e.g. text-embedding-3-small) on each entry's
         `embedding_text` field
       - Persist the resulting vectors alongside the entry `id` — a numpy .npy
         file, a FAISS index, or a lightweight sqlite-vec / chromadb store all work

    2. Embed the incoming queries
       - Call the same embeddings model on each of the 3 query strings
         returned by Agent 1

    3. Retrieve top-K per query
       - Compute cosine similarity between each query vector and the index
       - Return the top-K entries (K=10–20 is a reasonable starting point)
       - Deduplicate across the 3 query results by `id` before returning

    4. Keep this function's return type unchanged: list[dict] where each dict
       has at minimum id, table_name, field_name, data_type, description,
       data_source — Agent 2 (schema validator) depends on this shape

    The index only needs to be rebuilt when datasource_schema.json changes
    (i.e. after running schemas/enrich_descriptions.py or fix_descriptions.py).
    """
    if verbose:
        print(
            f"\n[RAG — placeholder] {len(queries)} queries → "
            f"{len(_PLACEHOLDER_RAG_RESULTS)} hardcoded results",
            file=sys.stderr,
        )
    return _PLACEHOLDER_RAG_RESULTS


# ---------------------------------------------------------------------------
# Schema search (tool implementations for Agent 2)
# ---------------------------------------------------------------------------

_schema_index: list[dict] | None = None
SCHEMA_PATH = REPO_ROOT / "schemas" / "datasource_schema.json"


def _load_schema() -> list[dict]:
    global _schema_index
    if _schema_index is None:
        with SCHEMA_PATH.open() as fh:
            _schema_index = json.load(fh)["datasources"]
    return _schema_index


def _tool_list_tables() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for entry in _load_schema():
        t = entry.get("table_name") or ""
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return sorted(out)


def _tool_search_fields(query: str, max_results: int = 20) -> list[dict]:
    """Substring search across field_name, table_name, description."""
    q = query.lower()
    results: list[dict] = []
    for entry in _load_schema():
        haystack = " ".join(filter(None, [
            entry.get("field_name"),
            entry.get("table_name"),
            entry.get("description"),
        ])).lower()
        if q in haystack:
            results.append({
                "id": entry["id"],
                "table_name": entry.get("table_name"),
                "field_name": entry.get("field_name"),
                "data_type": entry.get("data_type"),
                "description": (entry.get("description") or "")[:200],
                "data_source": entry.get("data_source"),
            })
            if len(results) >= max_results:
                break
    return results


def _tool_get_table_fields(table_name: str) -> list[dict]:
    """Return all fields for a table (exact match, then case-insensitive fallback)."""
    exact = [e for e in _load_schema() if e.get("table_name") == table_name]
    pool = exact or [e for e in _load_schema()
                     if (e.get("table_name") or "").lower() == table_name.lower()]
    return [
        {
            "id": e["id"],
            "field_name": e.get("field_name"),
            "data_type": e.get("data_type"),
            "description": (e.get("description") or "")[:200],
        }
        for e in pool
    ]


_SCHEMA_TOOLS = [
    {
        "name": "list_tables",
        "description": (
            "List all table/source names registered in the schema. "
            "Call this first to orient yourself before searching."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_fields",
        "description": (
            "Case-insensitive substring search across field name, table name, "
            "and description. Returns up to max_results entries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword(s)"},
                "max_results": {"type": "integer", "description": "Limit (default 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_table_fields",
        "description": "Get every field for a specific table by its exact name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "Exact table name as returned by list_tables",
                }
            },
            "required": ["table_name"],
        },
    },
]


def _dispatch_tool(name: str, inputs: dict) -> Any:
    if name == "list_tables":
        return _tool_list_tables()
    if name == "search_fields":
        return _tool_search_fields(inputs["query"], inputs.get("max_results", 20))
    if name == "get_table_fields":
        return _tool_get_table_fields(inputs["table_name"])
    return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Agent 2: Schema validator
# ---------------------------------------------------------------------------

_VALIDATOR_SYSTEM = """\
You are a data schema analyst for Flagship Homes. Given a user query and a
candidate set of fields from a RAG lookup, verify that all tables and columns
needed to answer the query exist in the schema registry, then return a complete
field plan.

You have three tools:
  list_tables      — enumerate all available tables/sources
  search_fields    — substring search by field name, table, or description keyword
  get_table_fields — get every field in a specific table

Use tools to fill gaps the RAG results leave. Keep tool calls targeted.

Your final response must be ONLY a JSON object (no prose before or after):
{
  "resolved_fields": [
    {
      "table_name": "...",
      "field_name": "...",
      "data_type": "...",
      "data_source": "...",
      "purpose": "why this field answers the query"
    }
  ],
  "missing": ["data points that cannot be found in any table"],
  "retrieval_notes": "how to join or filter these sources to answer the query"
}
"""


def validate_schema(
    client, prompt: str, rag_results: list[dict], *, verbose: bool = False
) -> dict:
    """Agent 2: Verify schema coverage; use tools to search schema if needed."""
    if verbose:
        print("\n[Agent 2 — schema validator] Verifying schema coverage…", file=sys.stderr)

    user_msg = (
        f"User query: {prompt}\n\n"
        f"RAG lookup results (may be incomplete or imprecise):\n"
        f"{json.dumps(rag_results, indent=2)}\n\n"
        "Verify these fields and find any additional ones needed to fully answer the query."
    )
    messages: list[dict] = [{"role": "user", "content": user_msg}]

    while True:
        response = client.messages.create(
            model=OPUS_MODEL,
            max_tokens=4096,
            system=_VALIDATOR_SYSTEM,
            tools=_SCHEMA_TOOLS,
            messages=messages,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if verbose:
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    preview = block.text.strip()[:160].replace("\n", " ")
                    print(f"  [validator] {preview}…", file=sys.stderr)

        if response.stop_reason == "end_turn" or not tool_uses:
            text = next(
                (b.text for b in reversed(response.content) if b.type == "text"),
                "{}",
            )
            try:
                return _extract_json(text)
            except (json.JSONDecodeError, TypeError):
                return {
                    "resolved_fields": rag_results,
                    "missing": [],
                    "retrieval_notes": text,
                }

        # Append assistant turn, then tool results
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tu in tool_uses:
            result = _dispatch_tool(tu.name, tu.input)
            if verbose:
                preview = json.dumps(result)[:80]
                print(f"  [tool] {tu.name}({json.dumps(tu.input)[:60]}) → {preview}…", file=sys.stderr)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})


# ---------------------------------------------------------------------------
# Agent 3: Data retriever
# ---------------------------------------------------------------------------

_RETRIEVER_SYSTEM = """\
You are a data retrieval planner for Flagship Homes. Given a user query and a
validated set of tables and columns, produce a concrete retrieval plan.

Sources in this system are:
  - CSV files (from Excel exports, paths in data_source are file:// URIs)
  - Parquet staged tables under data/staged/
  - Future SQL queries are possible but not yet implemented

For each retrieval step specify: which file/table, which columns, filters, joins.

Return ONLY a JSON object:
{
  "retrieval_plan": [
    {
      "step": 1,
      "action": "read_csv | read_parquet | join | filter",
      "source": "table name or file path",
      "columns": ["col1", "col2"],
      "filter": "description of filter condition, or null",
      "join_on": "join key description if applicable, or null",
      "note": "any caveats about this step"
    }
  ],
  "result_shape": "description of what the final dataset looks like",
  "caveats": ["known data quality issues or gaps"]
}

This is a planning step — describe what to do, not the data itself.
"""


def retrieve_data(
    client, prompt: str, schema_plan: dict, *, verbose: bool = False
) -> dict:
    """Agent 3: Given validated schema plan, produce a concrete retrieval plan."""
    if verbose:
        print("\n[Agent 3 — data retriever] Building retrieval plan…", file=sys.stderr)

    user_msg = (
        f"User query: {prompt}\n\n"
        f"Validated schema plan:\n{json.dumps(schema_plan, indent=2)}\n\n"
        "Produce the retrieval plan."
    )
    response = client.messages.create(
        model=OPUS_MODEL,
        max_tokens=2048,
        system=_RETRIEVER_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()
    try:
        return _extract_json(raw)
    except (json.JSONDecodeError, TypeError):
        return {"retrieval_plan": [], "result_shape": raw, "caveats": []}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(prompt: str, *, verbose: bool = False) -> dict:
    """Execute the full 4-stage pipeline and return a structured result."""
    client = _get_client()
    context = load_company_context()

    queries = generate_embedding_queries(client, prompt, context, verbose=verbose)
    rag_results = rag_lookup(queries, verbose=verbose)
    schema_plan = validate_schema(client, prompt, rag_results, verbose=verbose)
    retrieval = retrieve_data(client, prompt, schema_plan, verbose=verbose)

    return {
        "prompt": prompt,
        "embedding_queries": queries,
        "rag_results_count": len(rag_results),
        "schema_plan": schema_plan,
        "retrieval": retrieval,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-agent RAG data retrieval pipeline — Flagship Homes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("prompt", help="Natural language query about the development data")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Stream agent reasoning to stderr")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Dump full result as JSON instead of human-readable summary")
    args = parser.parse_args()

    result = run_pipeline(args.prompt, verbose=args.verbose)

    if args.json_out:
        print(json.dumps(result, indent=2))
        return

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"Query: {result['prompt']}")
    print(sep)

    print("\n--- Embedding Queries ---")
    for i, q in enumerate(result["embedding_queries"], 1):
        print(f"  {i}. {q}")

    plan = result["schema_plan"]
    resolved = plan.get("resolved_fields", [])
    print(f"\n--- Schema Plan ({len(resolved)} fields resolved) ---")
    for f in resolved:
        print(f"  {f.get('table_name')} . {f.get('field_name')}  [{f.get('data_type')}]")
        if f.get("purpose"):
            print(f"    → {f['purpose']}")
    if plan.get("missing"):
        print("  Missing:")
        for m in plan["missing"]:
            print(f"    ✗ {m}")
    if plan.get("retrieval_notes"):
        print(f"  Notes: {plan['retrieval_notes']}")

    retrieval = result["retrieval"]
    steps = retrieval.get("retrieval_plan", [])
    print(f"\n--- Retrieval Plan ({len(steps)} steps) ---")
    for step in steps:
        print(f"  Step {step.get('step')}: {step.get('action')}  ←  {step.get('source')}")
        cols = step.get("columns") or []
        if cols:
            print(f"    columns: {', '.join(cols)}")
        if step.get("filter"):
            print(f"    filter:  {step['filter']}")
        if step.get("join_on"):
            print(f"    join:    {step['join_on']}")
        if step.get("note"):
            print(f"    note:    {step['note']}")
    if retrieval.get("result_shape"):
        print(f"\n  Result shape: {retrieval['result_shape']}")
    if retrieval.get("caveats"):
        print("  Caveats:")
        for c in retrieval["caveats"]:
            print(f"    - {c}")


if __name__ == "__main__":
    main()
