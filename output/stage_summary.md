# Stage Dictionary — Data Quality Summary

_Source: `Clickup_Naming_Struct - Sheet1.csv`_
_Total rows: 100 | valid: 99 | unknown stage: 0 | invalid: 1_

## Unique stages observed
- `Backfill` → `Backfill`  (39×)
- `Walls` → `Walls`  (27×)
- `Dig` → `Dug`  (18×)
- `Dug` → `Dug`  (7×)
- `Spec` → `Spec`  (5×)
- `Footings` → `Footings`  (3×)

## Canonical alias mapping (proposed)
- `"Backfill"` → `"Backfill"`
- `"Dig"` → `"Dug"`
- `"Dug"` → `"Dug"`
- `"Footings"` → `"Footings"`
- `"Spec"` → `"Spec"`
- `"Walls"` → `"Walls"`

## Issues found
**Inconsistent naming (same canonical, multiple raw forms):**
- `Dug` ← `Dig`, `Dug`

**Missing expected stages (in canonical ordering, not seen in this sample):**
- `Rough`
- `Finish`
- `Complete`
- `Sold`

**Rare stages (count == 1):**
- (none)

**Unknown stages (parsed but no canonical mapping):**
- (none)

## Invalid row reasons
- trailing portion too long (24 tokens — likely a sentence, not a stage): 1