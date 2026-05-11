<!-- Generated from ontology/metrics/cost_to_date.yaml by bedrock.ontology.runtime.render_markdown. Do not edit by hand. -->

# Metric: cost_to_date

- **Unit**: `USD`
- **Confidence**: `inferred`
- **Source definition**: `pipelines/config.py:COST_TO_DATE_COMPONENTS`
- **Aliases**: `actual cost`, `lot cost`, `vf_actual_cost_3tuple_usd`

## Description

Total actual cost incurred to date for a single lot. Horizontal-only by design — vertical spend lives in separate fields and is excluded to avoid double-counting with Direct Construction.

## Formula

```
cost_to_date = `Permits and Fees` + `Direct Construction - Lot` + `Shared Cost Alloc.`
```

## Inputs

- `Permits and Fees`
- `Direct Construction - Lot`
- `Shared Cost Alloc.`

## Notes

- **exclusions**: Direct Construction (mixes horizontal+vertical), Vertical Costs, and Lot Cost are excluded. Lot Cost would double-count with Direct Construction - Lot.
- **decoder_note**: Per-lot allocation of GL postings to canonical lots is performed by the v1 VF decoder (financials/build_vf_lot_decoder_v1.py). Decoder rules are heuristic and inferred until source-owner sign-off.
- **range_rows**: $45.75M / 4,020 GL rows are 'range rows' that span multiple lots and live at project+phase grain only. Do NOT allocate range-row dollars to specific lots.
