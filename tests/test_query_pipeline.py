"""Tests for query_pipeline.py.

Unit tests: no API calls — all Anthropic client interactions are mocked.
E2E test:   makes real API calls; skipped automatically when ANTHROPIC_API_KEY
            is absent.

Run from repo root:
    pytest tests/test_query_pipeline.py -v
    pytest tests/test_query_pipeline.py -v -k e2e   # E2E only
    pytest tests/test_query_pipeline.py -v -k "not e2e"  # unit only
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import query_pipeline as qp

# ---------------------------------------------------------------------------
# Helpers — lightweight SDK response fakes
# ---------------------------------------------------------------------------

def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(tool_id: str, name: str, inp: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=inp)


def _response(content: list, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(content=content, stop_reason=stop_reason)


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_plain_object(self):
        assert qp._extract_json('{"a": 1}') == {"a": 1}

    def test_plain_array(self):
        assert qp._extract_json('[1, 2, 3]') == [1, 2, 3]

    def test_fenced_json_block(self):
        raw = '```json\n{"x": 42}\n```'
        assert qp._extract_json(raw) == {"x": 42}

    def test_fenced_no_language(self):
        raw = '```\n{"x": 99}\n```'
        assert qp._extract_json(raw) == {"x": 99}

    def test_json_embedded_in_prose(self):
        raw = 'Sure, here you go:\n{"key": "value"}\nDone.'
        assert qp._extract_json(raw) == {"key": "value"}

    def test_raises_on_garbage(self):
        with pytest.raises((json.JSONDecodeError, TypeError)):
            qp._extract_json("this is not json at all")


# ---------------------------------------------------------------------------
# Schema tools (read real datasource_schema.json)
# ---------------------------------------------------------------------------

class TestSchemaTools:
    def test_list_tables_returns_sorted_unique_strings(self):
        tables = qp._tool_list_tables()
        assert isinstance(tables, list)
        assert len(tables) > 0
        assert tables == sorted(tables)
        assert len(tables) == len(set(tables))

    def test_list_tables_contains_known_table(self):
        tables = qp._tool_list_tables()
        assert any("Lot Data" in t for t in tables)

    def test_search_fields_finds_phase(self):
        results = qp._tool_search_fields("Phase", max_results=5)
        assert len(results) > 0
        fields = [r["field_name"] for r in results]
        assert any("Phase" in (f or "") for f in fields)

    def test_search_fields_respects_max_results(self):
        results = qp._tool_search_fields("Unnamed", max_results=3)
        assert len(results) <= 3

    def test_search_fields_no_match_returns_empty(self):
        results = qp._tool_search_fields("xyzzy_no_such_field_ever")
        assert results == []

    def test_search_fields_result_shape(self):
        results = qp._tool_search_fields("lot", max_results=1)
        assert len(results) == 1
        r = results[0]
        for key in ("id", "table_name", "field_name", "data_type", "description", "data_source"):
            assert key in r

    def test_get_table_fields_exact_match(self):
        # Grab any real table name from the index
        tables = qp._tool_list_tables()
        table = tables[0]
        fields = qp._tool_get_table_fields(table)
        assert len(fields) > 0
        assert all(f["field_name"] is not None for f in fields)

    def test_get_table_fields_case_insensitive_fallback(self):
        tables = qp._tool_list_tables()
        table = tables[0]
        fields_exact = qp._tool_get_table_fields(table)
        fields_lower = qp._tool_get_table_fields(table.lower())
        # Both should return the same set of field names
        exact_names = {f["field_name"] for f in fields_exact}
        lower_names = {f["field_name"] for f in fields_lower}
        assert exact_names == lower_names

    def test_get_table_fields_unknown_table_returns_empty(self):
        fields = qp._tool_get_table_fields("this_table_does_not_exist_xyz")
        assert fields == []

    def test_get_table_fields_result_shape(self):
        table = qp._tool_list_tables()[0]
        fields = qp._tool_get_table_fields(table)
        for f in fields:
            for key in ("id", "field_name", "data_type", "description"):
                assert key in f


# ---------------------------------------------------------------------------
# _dispatch_tool
# ---------------------------------------------------------------------------

class TestDispatchTool:
    def test_dispatches_list_tables(self):
        result = qp._dispatch_tool("list_tables", {})
        assert isinstance(result, list)
        assert len(result) > 0

    def test_dispatches_search_fields(self):
        result = qp._dispatch_tool("search_fields", {"query": "Phase", "max_results": 3})
        assert isinstance(result, list)

    def test_dispatches_get_table_fields(self):
        table = qp._tool_list_tables()[0]
        result = qp._dispatch_tool("get_table_fields", {"table_name": table})
        assert isinstance(result, list)

    def test_unknown_tool_returns_error_dict(self):
        result = qp._dispatch_tool("does_not_exist", {})
        assert "error" in result


# ---------------------------------------------------------------------------
# rag_lookup
# ---------------------------------------------------------------------------

class TestRagLookup:
    def test_returns_non_empty_list(self):
        results = qp.rag_lookup(["query 1", "query 2"])
        assert isinstance(results, list)
        assert len(results) > 0

    def test_result_entries_have_required_keys(self):
        results = qp.rag_lookup(["anything"])
        for r in results:
            for key in ("id", "table_name", "field_name", "data_type", "description"):
                assert key in r, f"missing key {key!r} in {r}"

    def test_result_is_deterministic(self):
        r1 = qp.rag_lookup(["q1", "q2", "q3"])
        r2 = qp.rag_lookup(["completely different"])
        assert r1 == r2


# ---------------------------------------------------------------------------
# load_company_context
# ---------------------------------------------------------------------------

class TestLoadCompanyContext:
    def test_returns_non_empty_string(self):
        ctx = qp.load_company_context()
        assert isinstance(ctx, str)
        assert len(ctx) > 100

    def test_contains_flagship_context(self):
        ctx = qp.load_company_context()
        # CONTEXT_PACK.md should contain project-specific terms
        assert any(kw in ctx for kw in ("Flagship", "lot", "phase", "pipeline", "LotState"))


# ---------------------------------------------------------------------------
# generate_embedding_queries (mocked client)
# ---------------------------------------------------------------------------

class TestGenerateEmbeddingQueries:
    def _make_client(self, response_text: str) -> MagicMock:
        client = MagicMock()
        client.messages.create.return_value = _response([_text_block(response_text)])
        return client

    def test_returns_three_queries(self):
        payload = {
            "embedding_queries": ["q1", "q2", "q3"],
            "reasoning": "test"
        }
        client = self._make_client(json.dumps(payload))
        queries = qp.generate_embedding_queries(client, "test prompt", "ctx")
        assert queries == ["q1", "q2", "q3"]

    def test_strips_markdown_fence(self):
        payload = {"embedding_queries": ["a", "b", "c"], "reasoning": "r"}
        raw = f"```json\n{json.dumps(payload)}\n```"
        client = self._make_client(raw)
        queries = qp.generate_embedding_queries(client, "test", "ctx")
        assert len(queries) == 3

    def test_passes_prompt_as_user_message(self):
        payload = {"embedding_queries": ["x", "y", "z"], "reasoning": "r"}
        client = self._make_client(json.dumps(payload))
        qp.generate_embedding_queries(client, "my unique prompt", "ctx")
        create_kwargs = client.messages.create.call_args
        messages = create_kwargs.kwargs.get("messages") or create_kwargs.args[0]
        # find messages in kwargs
        all_kwargs = create_kwargs[1] if create_kwargs[1] else {}
        all_args = create_kwargs[0] if create_kwargs[0] else ()
        msg_list = all_kwargs.get("messages", [])
        assert any("my unique prompt" in str(m) for m in msg_list)

    def test_raises_on_malformed_response(self):
        client = self._make_client("this is not json")
        with pytest.raises(RuntimeError, match="malformed JSON"):
            qp.generate_embedding_queries(client, "test", "ctx")

    def test_uses_opus_model(self):
        payload = {"embedding_queries": ["a", "b", "c"], "reasoning": "r"}
        client = self._make_client(json.dumps(payload))
        qp.generate_embedding_queries(client, "test", "ctx")
        kwargs = client.messages.create.call_args[1]
        assert kwargs["model"] == qp.OPUS_MODEL


# ---------------------------------------------------------------------------
# validate_schema (mocked client)
# ---------------------------------------------------------------------------

class TestValidateSchema:
    _VALID_PLAN = {
        "resolved_fields": [
            {
                "table_name": "T",
                "field_name": "f",
                "data_type": "string",
                "data_source": "file://x",
                "purpose": "test"
            }
        ],
        "missing": [],
        "retrieval_notes": "join on lot_num"
    }

    def test_no_tool_use_parses_json(self):
        client = MagicMock()
        client.messages.create.return_value = _response(
            [_text_block(json.dumps(self._VALID_PLAN))]
        )
        result = qp.validate_schema(client, "test query", [])
        assert result["missing"] == []
        assert len(result["resolved_fields"]) == 1

    def test_tool_use_loop_then_final(self):
        # First call returns a tool_use block; second call returns final JSON.
        first = _response(
            [_tool_use_block("tid1", "list_tables", {})],
            stop_reason="tool_use",
        )
        second = _response([_text_block(json.dumps(self._VALID_PLAN))])

        client = MagicMock()
        client.messages.create.side_effect = [first, second]

        result = qp.validate_schema(client, "test query", [])
        assert client.messages.create.call_count == 2
        assert result["retrieval_notes"] == "join on lot_num"

    def test_tool_use_executes_real_dispatch(self):
        # Verify the tool result for search_fields is fed back correctly.
        tool_block = _tool_use_block("tid2", "search_fields", {"query": "Phase"})
        first = _response([tool_block], stop_reason="tool_use")
        second = _response([_text_block(json.dumps(self._VALID_PLAN))])

        client = MagicMock()
        client.messages.create.side_effect = [first, second]

        result = qp.validate_schema(client, "test", [])
        # Second call messages should include tool_result for tid2
        second_call_messages = client.messages.create.call_args_list[1][1]["messages"]
        tool_result_turn = second_call_messages[-1]["content"]
        assert any(tr["tool_use_id"] == "tid2" for tr in tool_result_turn)

    def test_malformed_json_falls_back_to_rag_results(self):
        client = MagicMock()
        client.messages.create.return_value = _response(
            [_text_block("Sorry, I cannot determine the schema.")]
        )
        rag = [{"id": "x", "table_name": "T", "field_name": "f"}]
        result = qp.validate_schema(client, "test", rag)
        assert result["resolved_fields"] == rag

    def test_multiple_tool_calls_in_sequence(self):
        # Three tool calls before final answer.
        turns = [
            _response([_tool_use_block("t1", "list_tables", {})], stop_reason="tool_use"),
            _response([_tool_use_block("t2", "search_fields", {"query": "lot"})], stop_reason="tool_use"),
            _response([_tool_use_block("t3", "get_table_fields", {"table_name": "X"})], stop_reason="tool_use"),
            _response([_text_block(json.dumps(self._VALID_PLAN))]),
        ]
        client = MagicMock()
        client.messages.create.side_effect = turns
        result = qp.validate_schema(client, "q", [])
        assert client.messages.create.call_count == 4
        assert "resolved_fields" in result


# ---------------------------------------------------------------------------
# retrieve_data (mocked client)
# ---------------------------------------------------------------------------

class TestRetrieveData:
    _VALID_PLAN = {
        "retrieval_plan": [
            {
                "step": 1,
                "action": "read_csv",
                "source": "Lot Data",
                "columns": ["Phase", "LotNo."],
                "filter": "Project == BCPD",
                "join_on": None,
                "note": None,
            }
        ],
        "result_shape": "one row per lot",
        "caveats": ["header offset = 3"],
    }

    def test_parses_valid_json(self):
        client = MagicMock()
        client.messages.create.return_value = _response(
            [_text_block(json.dumps(self._VALID_PLAN))]
        )
        result = qp.retrieve_data(client, "test", {})
        assert len(result["retrieval_plan"]) == 1
        assert result["result_shape"] == "one row per lot"

    def test_strips_markdown_fence(self):
        raw = f"```json\n{json.dumps(self._VALID_PLAN)}\n```"
        client = MagicMock()
        client.messages.create.return_value = _response([_text_block(raw)])
        result = qp.retrieve_data(client, "test", {})
        assert result["retrieval_plan"]

    def test_malformed_json_returns_raw_as_result_shape(self):
        client = MagicMock()
        client.messages.create.return_value = _response(
            [_text_block("I cannot determine the retrieval plan.")]
        )
        result = qp.retrieve_data(client, "test", {})
        assert result["retrieval_plan"] == []
        assert "cannot" in result["result_shape"]

    def test_passes_schema_plan_in_prompt(self):
        client = MagicMock()
        client.messages.create.return_value = _response(
            [_text_block(json.dumps(self._VALID_PLAN))]
        )
        schema_plan = {"resolved_fields": [{"table_name": "SentinelTable"}]}
        qp.retrieve_data(client, "query", schema_plan)
        call_kwargs = client.messages.create.call_args[1]
        user_msg = call_kwargs["messages"][0]["content"]
        assert "SentinelTable" in user_msg

    def test_uses_opus_model(self):
        client = MagicMock()
        client.messages.create.return_value = _response(
            [_text_block(json.dumps(self._VALID_PLAN))]
        )
        qp.retrieve_data(client, "test", {})
        assert client.messages.create.call_args[1]["model"] == qp.OPUS_MODEL


# ---------------------------------------------------------------------------
# run_pipeline (all agents mocked)
# ---------------------------------------------------------------------------

class TestRunPipeline:
    def _setup_mocks(self):
        """Return a patched client + expected intermediate values."""
        queries = ["q1", "q2", "q3"]
        schema_plan = {
            "resolved_fields": [
                {"table_name": "T", "field_name": "f", "data_type": "string",
                 "data_source": "file://x", "purpose": "test"}
            ],
            "missing": [],
            "retrieval_notes": "notes",
        }
        retrieval = {
            "retrieval_plan": [{"step": 1, "action": "read_csv", "source": "T",
                                "columns": ["f"], "filter": None, "join_on": None, "note": None}],
            "result_shape": "one row per lot",
            "caveats": [],
        }
        intent_resp = _response([_text_block(json.dumps({
            "embedding_queries": queries, "reasoning": "r"
        }))])
        validator_resp = _response([_text_block(json.dumps(schema_plan))])
        retriever_resp = _response([_text_block(json.dumps(retrieval))])

        client = MagicMock()
        client.messages.create.side_effect = [intent_resp, validator_resp, retriever_resp]
        return client, queries, schema_plan, retrieval

    def test_result_structure(self):
        client, queries, schema_plan, retrieval = self._setup_mocks()
        with patch.object(qp, "_get_client", return_value=client):
            result = qp.run_pipeline("test prompt")
        assert result["prompt"] == "test prompt"
        assert result["embedding_queries"] == queries
        assert result["rag_results_count"] == len(qp._PLACEHOLDER_RAG_RESULTS)
        assert result["schema_plan"] == schema_plan
        assert result["retrieval"] == retrieval

    def test_three_api_calls_made(self):
        client, *_ = self._setup_mocks()
        with patch.object(qp, "_get_client", return_value=client):
            qp.run_pipeline("test")
        assert client.messages.create.call_count == 3

    def test_rag_results_count_is_constant(self):
        client, *_ = self._setup_mocks()
        with patch.object(qp, "_get_client", return_value=client):
            r1 = qp.run_pipeline("q1")
            # Reset side_effect for second run
            intent_resp = _response([_text_block(json.dumps({
                "embedding_queries": ["a", "b", "c"], "reasoning": "r"
            }))])
            schema_plan = {"resolved_fields": [], "missing": [], "retrieval_notes": ""}
            retrieval = {"retrieval_plan": [], "result_shape": "", "caveats": []}
            client.messages.create.side_effect = [
                intent_resp,
                _response([_text_block(json.dumps(schema_plan))]),
                _response([_text_block(json.dumps(retrieval))]),
            ]
            r2 = qp.run_pipeline("q2")
        assert r1["rag_results_count"] == r2["rag_results_count"]


# ---------------------------------------------------------------------------
# CLI (argparse)
# ---------------------------------------------------------------------------

class TestCli:
    def _run_main(self, argv: list[str], mock_result: dict) -> str:
        """Patch run_pipeline and capture stdout."""
        import io
        from contextlib import redirect_stdout

        with patch.object(qp, "run_pipeline", return_value=mock_result):
            with patch("sys.argv", ["query_pipeline.py"] + argv):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    qp.main()
                return buf.getvalue()

    def _sample_result(self) -> dict:
        return {
            "prompt": "how many lots",
            "embedding_queries": ["e1", "e2", "e3"],
            "rag_results_count": 8,
            "schema_plan": {
                "resolved_fields": [
                    {"table_name": "T", "field_name": "f",
                     "data_type": "string", "data_source": "file://x",
                     "purpose": "counts lots"}
                ],
                "missing": [],
                "retrieval_notes": "filter by phase",
            },
            "retrieval": {
                "retrieval_plan": [
                    {"step": 1, "action": "read_csv", "source": "T",
                     "columns": ["f"], "filter": "phase=1",
                     "join_on": None, "note": None}
                ],
                "result_shape": "one row per lot",
                "caveats": ["header offset"],
            },
        }

    def test_human_readable_output_contains_queries(self):
        out = self._run_main(["how many lots"], self._sample_result())
        assert "e1" in out
        assert "e2" in out
        assert "e3" in out

    def test_json_output_is_parseable(self):
        out = self._run_main(["how many lots", "--json"], self._sample_result())
        parsed = json.loads(out)
        assert parsed["prompt"] == "how many lots"

    def test_human_readable_shows_retrieval_steps(self):
        out = self._run_main(["how many lots"], self._sample_result())
        assert "read_csv" in out
        assert "filter" in out

    def test_missing_fields_shown(self):
        result = self._sample_result()
        result["schema_plan"]["missing"] = ["GL transaction date"]
        out = self._run_main(["test query"], result)
        assert "GL transaction date" in out

    def test_caveats_shown(self):
        out = self._run_main(["test query"], self._sample_result())
        assert "header offset" in out


# ---------------------------------------------------------------------------
# E2E (real API — skipped if key absent)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live API test",
)
class TestE2E:
    PROMPT = "Which lots are in HORIZONTAL_IN_PROGRESS state and what are their phase numbers?"

    def test_pipeline_returns_three_embedding_queries(self):
        result = qp.run_pipeline(self.PROMPT)
        assert len(result["embedding_queries"]) == 3
        for q in result["embedding_queries"]:
            assert isinstance(q, str)
            assert len(q) > 10

    def test_pipeline_schema_plan_has_resolved_fields(self):
        result = qp.run_pipeline(self.PROMPT)
        resolved = result["schema_plan"].get("resolved_fields", [])
        assert len(resolved) > 0
        for f in resolved:
            assert "table_name" in f
            assert "field_name" in f

    def test_pipeline_retrieval_has_steps(self):
        result = qp.run_pipeline(self.PROMPT)
        steps = result["retrieval"].get("retrieval_plan", [])
        assert len(steps) > 0
        for step in steps:
            assert "action" in step
            assert "source" in step

    def test_pipeline_does_not_mutate_schema_file(self):
        import hashlib
        schema_bytes = qp.SCHEMA_PATH.read_bytes()
        digest_before = hashlib.sha256(schema_bytes).hexdigest()

        qp.run_pipeline(self.PROMPT)

        digest_after = hashlib.sha256(qp.SCHEMA_PATH.read_bytes()).hexdigest()
        assert digest_before == digest_after, "run_pipeline must not write to datasource_schema.json"

    def test_pipeline_does_not_mutate_context_files(self):
        import hashlib
        ctx_path = REPO / "CONTEXT_PACK.md"
        digest_before = hashlib.sha256(ctx_path.read_bytes()).hexdigest()

        qp.run_pipeline(self.PROMPT)

        digest_after = hashlib.sha256(ctx_path.read_bytes()).hexdigest()
        assert digest_before == digest_after


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
