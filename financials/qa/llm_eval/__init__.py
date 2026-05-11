"""BCPD v2.1 Claude A/B eval harness.

Compares two answer modes on the same question set:

- Mode A (ungrounded): Claude with only a generic framing.
- Mode B (state-grounded): Claude given BCPD v2.1 retrieved chunks + guardrails
  + required answer format.

Read-only over BCPD state files. Writes only under output/llm_eval/.
Uses ANTHROPIC_API_KEY from the environment; never persists the key.
"""
