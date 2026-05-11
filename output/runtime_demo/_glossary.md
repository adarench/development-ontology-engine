# BCPD Operating State — Glossary

_Plain-English definitions for the terms the six runtime demos use. The
underscore prefix keeps this file at the top of the directory listing._

## Project + scope

**BCPD**  
The BCPD entity family — the four legal entities Building Construction Partners (BCPD), BCPBL, ASD, and BCPI. The v2.1 operating state covers only these entities. Hillcrest and Flagship Belmont are out of scope because their GL data ends 2017-02.

**operating state**  
The single canonical JSON file (`output/operating_state_v2_1_bcpd.json`) that summarizes every BCPD lot, phase, and project with the v2.1 decoder rules applied. The runtime tools read from this file rather than from raw source systems.

**org-wide v2**  
A consolidated view across BCPD + Hillcrest + Flagship Belmont. **Not available.** It needs three new GL streams (Hillcrest, Flagship Belmont, and a back-fill of the 2017-03 → 2018-06 data gap) before consolidation is possible.

## Cost sources

**GL — general ledger**  
The accounting system of record. BCPD's GL data lives in three formats that are NOT combined raw: Vertical Financials (VF), DataRails (DR), and QuickBooks Register (QB).

**VF — Vertical Financials**  
The primary 2018–2025 lot-cost source. 46-column GL extract. Decoder rules in v2.1 derive per-lot cost from VF line items.

**DR — DataRails**  
Legacy 2016–2017 GL extract. 38 columns. Carries a known 2.16× row-multiplication issue that the pipeline deduplicates at load.

**QB — QuickBooks Register**  
2025 vendor/cash transactions, 12 columns. Different chart of accounts. Used for tie-out only — excluded from primary cost rollups.

## Confidence levels

**inferred**  
A field derived by the v1 VF decoder (heuristic rules; not source-owner-validated). Marked `inferred (high-evidence)` when the decoder rule has supporting evidence, `inferred-unknown` when even the canonical name is pending sign-off.

**validated**  
A field signed off by the source owner (Finance / Land / Ops, depending on the field). v2.1 ships with zero validated decoder rules; promotion requires the source-owner review queue.

**unknown, not zero**  
The rule for projects with no GL coverage: their lot-level cost is **unknown** (null / blank), not $0. Reporting $0 inflates apparent margin and is factually wrong.

**source-owner validation**  
The sign-off process by which inferred decoder rules become validated. Tracked in `output/bcpd_data_gap_audit_for_streamline_session.md`. v2.2 ships when these are resolved; this is the real bottleneck, not engineering.

## Grain (the level a number applies to)

**cost grain**  
The level at which a cost number is meaningful. v2.1 surfaces three grains: lot-level, project+phase level, and project level.

**lot-level**  
A single physical lot (e.g., Harmony B1 lot 101). The most granular layer. Per-lot VF cost is decoder-derived (inferred).

**project+phase level**  
A grouping of lots inside a project (e.g., Parkway Fields phase A1). Range / shell GL rows live here — they cannot be safely allocated down to individual lots without a source-owner-signed allocation method.

**range / shell rows**  
GL postings whose lot identifier looks like a range (`'3001-06'`, `'0009-12'`) or a placeholder. In v2.1: $45,752,047 across 4,020 rows. They are NOT expanded to per-lot synthetic rows; they stay at project+phase grain by design.

## Identifiers + joins

**3-tuple join**  
The required join key `(canonical_project, canonical_phase, canonical_lot_number)`. v2.0 used a flat `(project, lot)` key and double-counted ~$6.75M on Harmony where MF1 lot 101 and B1 lot 101 are different physical assets.

**crosswalk**  
A mapping table that translates source-system labels (e.g., GL account names, ClickUp project codes) to the canonical project / phase / lot names used everywhere else.

**decoder**  
The v1 VF decoder — a set of heuristic rules in `data/reports/vf_lot_code_decoder_v1_report.md` that read a VF line item's code and derive `(canonical_project, canonical_phase, canonical_lot_number)`. Inferred until source-owner sign-off.

**full triangle**  
A lot that appears in all three feeds: inventory, GL, and ClickUp. The percentage of lots in the full triangle (37.2% in v2.1) is a quality signal — the higher, the more confidently we can report on those lots.

## Special-case lot identifiers (v2.1 corrections)

**AultF B-suffix**  
Lots labeled `0127B`–`0211B` in the VF GL. v2.0 misrouted these to phase B2; v2.1 corrects them to **B1**. Magnitude: 1,499 rows / $4,006,662.

**AultF SR-suffix**  
Lots labeled `0139SR`, `0140SR` — "special-rate" lots. Held as **inferred-unknown** in v2.1 because the canonical phase is pending source-owner sign-off. Magnitude: 401 rows / $1,183,859.

**SctLot**  
A VF-system label for the **Scattered Lots** program (a separate canonical project in v2.1). v2.0 silently bucketed these rows into Scarlet Ridge, inflating Scarlet Ridge by $6,553,893 / 1,130 rows.

**HarmCo X-X parcels**  
Commercial parcels with X-X lot codes (`A-A` through `K-K`). 205 rows. **Commercial, not residential** — must be excluded from per-lot residential rollups.

## Process

**inferred → validated promotion**  
The act of taking a decoder rule from "we think this is right based on evidence" to "the source owner has signed off". Requires a meeting with Finance / Land / Ops; the runtime tool `prepare_finance_land_review` is the agenda for that meeting.

**read-only**  
The runtime never writes to v2.1 source artifacts. The seven protected files (operating_state_v2_1_bcpd.json, agent_context_v2_1_bcpd.md, state_quality_report_v2_1_bcpd.md, change log, coverage opportunities, crosswalk audit, decoder report) are byte-identical after any tool run. Verified by `tests/test_bcpd_workflows.py::test_workflow_tools_did_not_modify_protected_files`.
