<!-- Generated from ontology/entities/project.yaml by bedrock.ontology.runtime.render_markdown. Do not edit by hand. -->

# Project
**Entity type**: `project`  
**Vertical**: `construction`  
**Schema version**: `v1`

## Description

A development project — the top-level grouping that contains many phases and lots. Identity is driven by the canonical_project name (e.g., Parkway Fields, Harmony, Scattered Lots). v2.1 separated SctLot from Scarlet Ridge ($6.55M un-inflated) and isolated HarmCo X-X commercial parcels from residential lots.

## Retrieval Tags

`project`, `portfolio`, `bcpd`, `operational_state`

## Source Lineage

- `output/operating_state_v2_1_bcpd.json (top-level projects[])`
- `data/staged/canonical_project.csv`
- `financials/build_operating_state_v2_1_bcpd.py`
- `financials/build_crosswalks_v0.py`

## Example Queries

- What projects are in BCPD scope?
- How many phases does Harmony have?
- What is the total actuals for Parkway Fields?

## Field Definitions

| Field | Type | Nullable | Derived | Description |
|---|---|---|---|---|
| `canonical_project` | string | no | no | Canonical project name. Authority for project identity in v2.x. |
| `canonical_entity` | enum | no | no | BCPD entity that owns this project. Filters out Hillcrest/Flagship/Lennar/EXT (out of scope). |
| `phase_count` | integer | no | yes | Number of phases in this project. |
| `lot_count` | integer | no | yes | Total lots across all phases. |
| `lot_count_active_2025status` | integer | no | yes | Active lots present in the 2025Status sheet (excludes pure-inventory rows). |
| `actuals` | map | no | yes | Project-level actual cost totals, broken down by source (vf_total, dr_total_dedup, etc.). |
| `commercial_parcels_non_lot` | list | no | yes | HarmCo X-X commercial parcels (~$2.6M, 205 rows). Isolated from residential lots. |
| `phases` | list | no | yes | Nested array of PhaseState records belonging to this project. |

### Field Aliases

- `canonical_project` ← `project_name`, `project_id`

## Semantic Aliases

- `project` → `Project`
- `development project` → `Project`
- `SctLot` → `Scattered Lots` — SctLot is its own canonical project, NOT Scarlet Ridge. v2.1 fix.
- `HarmCo X-X` → `commercial_parcels_non_lot` — Commercial parcels — not residential lots. Isolated in v2.1.

## Relationships

- **contains_phases** → `phase` (many) via `canonical_project`: A project contains many phases.
- **contains_lots** → `lot` (many): A project transitively contains many lots via its phases.

## Approved Join Paths

- **project_to_phases** → `phase` (many) on `canonical_project`
- **project_to_crosswalk** → `project` (one) on `source_value`  
  _data/staged/canonical_project.csv maps source-system project labels to canonical_project._

## Confidence Rules

- `canonical_project` → **high** — Crosswalks are reviewed and committed under data/staged/.
- `actuals` → **inferred** — Project-level actuals roll up from lot-level VF decoder output (inferred).

## Validation Rules

- **bcpd_only_scope** _(severity: error)_: canonical_entity must be one of BCPD, BCPBL, ASD, BCPI. Hillcrest/Flagship/Lennar/EXT are out of scope; refuse org-wide queries.
- **sctlot_not_scarlet** _(severity: error)_: SctLot rows must canonicalize to 'Scattered Lots', never 'Scarlet Ridge'. v2.1 hard rule.
- **harmco_xx_isolated** _(severity: error)_: HarmCo X-X parcels live in commercial_parcels_non_lot, not in any phases[].lots[] array.

## Semantic Warnings

- **org_wide_unavailable** (applies to `canonical_project`): Org-wide rollups (Hillcrest, Flagship Belmont) are explicitly out of scope. Those entities have GL data only through 2017-02. Refuse org-wide queries.
- **sctlot_renamed** (applies to `canonical_project`): In v2.0 SctLot was incorrectly bucketed into Scarlet Ridge, inflating Scarlet by $6.55M. v2.1 isolates SctLot as 'Scattered Lots'. Always cite the v2.1 canonical name.

## Embedding Payload Template

```text
Project — {canonical_name}
{business_description}
Aliases: {aliases}
Tags: {retrieval_tags}
BCPD scope only — entities BCPD/BCPBL/ASD/BCPI. Out of scope: Hillcrest, Flagship, Lennar, EXT.
v2.1 corrections: SctLot → Scattered Lots; HarmCo X-X commercial isolated; AultF B-suffix → B1.
```

**Fields to include**: `canonical_project`, `canonical_entity`, `phase_count`, `lot_count`

## Historical Behavior

v1/v2.0 used a flat Scarlet Ridge bucket that absorbed SctLot rows. v2.1 separates them. v1 had no formal Project entity — it lived implicitly in lot.project_name. v2.1 promoted it to a top-level array in output/operating_state_v2_1_bcpd.json.
