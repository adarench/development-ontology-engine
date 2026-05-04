# First Prompts to Run

Three short prompts. Each one tells its terminal to read its lane doc and execute. The lane docs carry the full instructions — these prompts intentionally stay short.

## Run order

1. **Terminal B** and **Terminal C** in parallel (different terminals/sessions). Wait until both finish.
2. Then **Terminal A**.

## Terminal B prompt

```
Read docs/agent_lanes/terminal_b_gl_financials.md and execute the lane in full.

Inputs are listed in priority order in the lane doc. Hard rules and the
out-of-scope list are non-negotiable.

Produce these deliverables and nothing else:
- scratch/gl_financials_findings.md
- scratch/bcpd_financial_readiness.md
- (optional) addendum to data/staged/staged_gl_transactions_v2_validation_report.md

Do not modify output/, ontology/, pipelines/, financials/, any existing
data/staged/* file (other than the optional addendum), or any other terminal's
scratch files. Do not build any operating-state output.

When done, stop. Terminal A will read your findings.
```

## Terminal C prompt

```
Read docs/agent_lanes/terminal_c_ops_inventory_collateral_allocations.md
and execute the lane in priority order:
  1. Inventory closing report (highest priority — unblocks the guardrail)
  2. Collateral reports
  3. ClickUp lot-tagged subset
  4. Allocations / budgets

If you run out of time, finish #1 and #2; the rest can land in a follow-up.

Produce these deliverables and nothing else:
- scratch/ops_inventory_collateral_allocation_findings.md
- scratch/bcpd_ops_readiness.md
- data/staged/ops_inventory_collateral_validation_report.md

Do not modify output/, ontology/, pipelines/, financials/, any other
data/staged/* file, or any other terminal's scratch files. Do not actually
stage staged_inventory_lots — propose; Terminal A will execute.

When done, stop. Terminal A will read your findings.
```

## Terminal A prompt (run AFTER Terminals B and C finish)

```
Both worker findings should now exist under scratch/. Read:
- scratch/gl_financials_findings.md
- scratch/bcpd_financial_readiness.md
- scratch/ops_inventory_collateral_allocation_findings.md
- scratch/bcpd_ops_readiness.md
- data/staged/ops_inventory_collateral_validation_report.md

Then read docs/agent_lanes/terminal_a_integrator.md and execute the integration
step.

The hard pre-build guardrail is mandatory: do NOT build any output/*_v2_bcpd.*
file or v2 query harness until ALL THREE are true:
  1. data/staged/staged_inventory_lots.{csv,parquet} exists and is validated
  2. crosswalk v0 exists with a confidence column
  3. data/reports/join_coverage_v0.md is written

Write data/reports/guardrail_check_v0.md as the explicit GREEN/RED check before
moving past A7. If RED, stop and escalate.

When done (whether v2 ships or not), report status with citations to the
deliverables you produced.
```

## Notes for the human running the terminals

- Each prompt is self-contained with respect to the lane doc — the agent reads its lane doc for the full instruction set.
- B and C are genuinely parallel; their inputs and outputs are disjoint.
- A waits for both. Do not launch A until both B and C have stopped.
- If B or C goes off-script (writes outside its allowed paths), stop the session and re-prompt with the lane doc text inlined.
