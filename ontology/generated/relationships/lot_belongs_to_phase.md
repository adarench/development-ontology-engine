<!-- Generated from ontology/relationships/lot_belongs_to_phase.yaml by bedrock.ontology.runtime.render_markdown. Do not edit by hand. -->

# Relationship: lot_belongs_to_phase

- **Source entity**: `lot`
- **Target entity**: `phase`
- **Cardinality**: `many_to_many`
- **Confidence**: `validated`
- **Join keys**: `canonical_project`, `canonical_phase`

## Description

Each lot belongs to exactly one phase. The 3-tuple (canonical_project, canonical_phase, canonical_lot_number) is the join key required for Harmony cost queries — a flat (project, lot) join collapses different physical assets together.

## Semantic Warnings

- **harmony_3tuple_required**: For Harmony, always use the 3-tuple join. v2.0 used a flat (project, lot) join and collapsed Harm3 ($5.35M for B1 lots 101–116) onto HarmTo ($1.40M for MF1 lots 101–116), causing a ~$6.75M double-count. v2.1 enforces this everywhere via vf_actual_cost_3tuple_usd.
