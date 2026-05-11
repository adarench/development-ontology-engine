"""Read-only BCPD v2.1 State Q&A harness.

Validates that an LLM or deterministic retrieval layer can answer business
questions from the structured BCPD v2.1 operating state with evidence,
confidence, caveats, and refusal rules.

This package is strictly read-only against:
  - output/operating_state_v2_1_bcpd.json
  - output/agent_context_v2_1_bcpd.md
  - output/state_quality_report_v2_1_bcpd.md
  - output/state_query_examples_v2_1_bcpd.md
  - data/reports/v2_0_to_v2_1_change_log.md
  - data/reports/join_coverage_v0.md
  - data/reports/coverage_improvement_opportunities.md
  - data/reports/vf_lot_code_decoder_v1_report.md
  - docs/ontology_v0.md
  - docs/field_map_v0.csv
  - docs/source_to_field_map.md

Allowed writes (only):
  - output/bcpd_state_qa_results.json
  - output/bcpd_state_qa_examples.md
  - output/bcpd_state_qa_eval.md
  - tests/test_bcpd_state_qa_readonly.py (test scaffold)
"""

__version__ = "0.1.0"
