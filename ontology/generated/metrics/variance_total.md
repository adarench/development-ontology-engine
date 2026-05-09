<!-- Generated from ontology/metrics/variance_total.yaml by bedrock.ontology.runtime.render_markdown. Do not edit by hand. -->

# Metric: variance_total

- **Unit**: `USD`
- **Confidence**: `inferred`
- **Source definition**: `ontology/phase_state_v1.md §3.E and financials/build_operating_state_v2_1_bcpd.py`
- **Aliases**: `budget variance`, `over/under budget`, `phase variance`

## Description

Phase-level variance between actual cost and expected cost. Sign convention: positive = over budget, negative = under budget. Inherits the inferred confidence of actual_cost_total because actuals roll up from VF-decoder-derived lot costs.

## Formula

```
variance_total       = actual_cost_total - expected_total_cost
variance_per_lot     = actual_cost_per_lot - expected_total_cost_per_lot
variance_pct         = variance_total / expected_total_cost   (null if expected is 0)
```

## Inputs

- `actual_cost_total`
- `expected_total_cost`
- `lot_count_total`

## Notes

- **queryability_gate**: is_queryable = (expected_cost_status == 'FULL') AND variance_meaningful. Only 3 of 125 phases pass in v2.1; the rest have PARTIAL or MISSING expected_cost.
- **null_rule**: variance_pct is null when expected_total_cost is 0 or null.
- **sign_convention**: Positive variance means actuals exceed budget.
