# BCPD Ops Readiness — Track A

**Author**: Terminal C
**Date**: 2026-05-01
**Audience**: Terminal A (integrator)

## Definition note

The data refers to multiple "BCP*" identifiers:

| identifier | role in data | location |
|---|---|---|
| `BCP` | vertical home builder (Flagship Homes brand) | `2025Status.HorzCustomer` (2,806 lots), `Lot Data.HorzCustomer` (2,804 lots) |
| `BCPD` | horizontal land developer entity | `Lot Data.HorzSeller` (756 lots) |
| `BCPBL` | BCP Ben Lomond — Lomond Heights horizontal developer | `Lot Data.HorzSeller` (415 lots), entity name in LH allocation workbook |
| `ASD` | Arrowhead Springs Developer (horizontal) | `Lot Data.HorzSeller` (229 lots) |
| `BCPI` | BCP Investor / Industrial? | `Lot Data.HorzSeller` (12 lots) |

Terminal A's example earlier filtered v2 GL by `entity_name == 'Building Construction Partners, LLC'` — that name lines up with the **vertical builder (`BCP`)**. The master plan calls this scope "BCPD Track A" but the underlying entity in the GL files is "BCP" (Building Construction Partners, LLC). **Terminal A: confirm canonical BCPD scope before final ontology lock-in.**

Below I treat BCPD = the v2 scope = lots ultimately built/sold by Building Construction Partners (`HorzCustomer == 'BCP'`). 794 Lennar lots + 26 EXT/EXT-Comm + 1 Church are explicitly out of scope.

---

## BCPD readiness matrix — by source × Track A entity

| source | covers BCPD lots? | covers BCPD phases? | covers BCPD projects? | Track A usable? | caveat |
|---|---|---|---|---|---|
| `Inventory _ Closing Report (4).xlsx` — INVENTORY | partial: 978 active lots, mix of BCP-built (Harmony, Parkway, Lomond Heights, Salem, etc.) and historical (SL=Silver Lake) | ✅ phase column populated 100% | ✅ 9 communities map to BCPD scope | **YES** | apply community crosswalk; Silver Lake unmapped |
| `Inventory _ Closing Report (4).xlsx` — CLOSED | partial: 2,894 historical closings — most are BCPD-builder, includes pre-2018 communities not in current scope | ✅ phase column populated | mixed: many historical communities | **YES with caveat** | filter `Closing Date <= as_of` for actual closures; older communities (`LEC`, `WILLOWS`, `WESTBROOK`, etc.) not in current 16-project universe |
| `Inventory _ Closing Report (4).xlsx` — CLOSINGS | yes: 929 pending closings | ❌ no phase column (only COMMUNITY + LOT#) | ✅ | partial | join to INVENTORY/CLOSED on (community, lot_num) to enrich phase |
| `2025Status.csv` | ✅ 2,806 BCPD lots (HorzCustomer=BCP) of 3,627 total | ✅ phase 100% | ✅ all 16 projects | **YES** | filter `HorzCustomer == 'BCP'` to scope to BCPD |
| `Lot Data.csv` | ✅ 2,804 BCPD lots | ✅ | ✅ | **YES** (already in v1) | same filter |
| `Collateral Report.csv` | n/a (phase-level not lot-level) | ✅ 41 phase rows | ✅ 9 of 16 BCPD projects (covers Arrowhead, Dry Creek, Harmony, Lomond Heights, Meadow Creek, Parkway, Salem, Scarlet Ridge, Willowcreek) | **YES** | 7 BCPD projects have NO Collateral Report row (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Lewis Estates, Santaquin Estates, Westbridge) |
| `PriorCR.csv` | n/a | ✅ same coverage as Collateral Report | ✅ | **YES** | as-of 2025-06-30 — useful for snapshot delta |
| `IA Breakdown.csv` | n/a | partial: 37 customer/job/phase rows, mix of BCPD + non-BCPD | ✅ | partial | useful for entity-level reconciliation, not lot-level |
| `RBA-TNW.csv` | aggregate-only | aggregate-only | aggregate-only | partial | reconciliation total, not entity input |
| `Cost to Complete Summary.csv` | aggregate-only | aggregate-only | aggregate-only | partial | $538M global; useful for sanity check, not for breakdown |
| `OfferMaster.csv` | n/a | n/a | ✅ 8 of 16 BCPD communities have rows | partial | community×product-type cost reference; fallback for projects without allocation workbook |
| `LH Allocation 2025.10 - LH.csv` | n/a | ✅ 12 phase×prod_type rows for Lomond Heights | ✅ Lomond Heights only | **YES** (already in v1) | Total column blank; reconstructable |
| `Parkway Allocation 2025.10 - PF.csv` | n/a | ✅ 14 phase×prod_type rows for Parkway Fields | ✅ Parkway Fields only | **YES** (already in v1) | full column set |
| `Flagship Allocation v3 - Per-Lot Output.csv` | n/a | covers 8 BCPD communities × 67 (community,phase) pairs | ✅ | mostly EMPTY | budgeting *framework* exists; cells are mostly $0 |
| `Dehart Underwriting (Summary).csv` | n/a | covers 1 project only (Payson Larsen) | partial: outside the 16-project BCPD scope | NO | not stageable as-is; defer |
| `staged_clickup_tasks` (lot-tagged subset, n=1,177) | ✅ all 1,177 tagged tasks fall in BCPD-relevant communities | ✅ phase 92.86% within both-keys | ✅ 9 distinct BCPD communities (with typo variants to crosswalk) | **YES** | apply subdivision crosswalk; flag Arrowhead-173 outlier (75 tasks on one lot) |

### Net BCPD coverage assessment

| Track A entity | BCPD-scoped row count expected | gating risk |
|---|---:|---|
| InventorySnapshot (lot grain, as_of 2026-04-28) | ~3,872 (978 active + 2,894 closed); after `HorzCustomer=BCP` filter, expect ~2,700–3,000 | low — primary source available |
| LotState (lot grain, as_of 2025-12-31) | 2,806 (matches v1's `BCP` HorzCustomer count from 2025Status) | low — already wired |
| CollateralSnapshot (phase grain, as_of 2025-12-31) | 41 phase rows | medium — 7 BCPD projects missing |
| CollateralSnapshot (prior, 2025-06-30) | 41 phase rows | medium — same as primary |
| Allocation (phase × prod_type grain, mixed as_of) | 26 rows total (12 LH + 14 PF) | **HIGH — non-LH/non-PF projects (Harmony, Salem, Arrowhead, etc.) have NO allocation source** for v2 unless OfferMaster fallback is wired in |
| TaskState (lot grain, "current") | 1,177 tasks across ~1,091 distinct lots in 9 BCPD communities | low — straightforward filter |

---

## Org-wide gaps (sources covering non-BCPD entities)

### Files that explicitly cover non-BCPD entities

| file | non-BCPD coverage | what's there | what's missing for org-wide rollup |
|---|---|---|---|
| `2025Status.csv` (HorzCustomer ≠ BCP filter) | 794 Lennar + 20 EXT-Comm + 5 EXT + 1 Church = 820 lots | per-lot status, costs, collateral bucket — full schema | revenue/sales price not in 2025Status; Lennar lots flow through Lennar's sales process, not BCP's |
| `Lot Data.csv` (HorzSeller ≠ BCPD) | 415 BCPBL (Ben Lomond) + 229 ASD (Arrowhead) + 12 BCPI = 656 lots | per-lot lifecycle dates | (covered) |
| `LH Allocation 2025.10 - AAJ.csv` | Ben Lomond entity-level financials | per-phase wide-format GL/balance lines | not lot-level; no per-lot Allocation entity rows |
| `LH Allocation 2025.10 - BSJ.csv` | Salem entity-level financials | per-phase wide-format | same — not lot-level |
| `LH Allocation 2025.10 - PLJ.csv` | Harmony entity-level P&L | per-phase wide-format P&L lines | not lot-level |
| `LH Allocation 2025.10 - BCPBL SB.csv` | Sundance Bay loan terms (Ben Lomond) | static loan terms | reference only |
| `Parkway Allocation 2025.10 - AAJ.csv` | Parkway entity-level financials | per-phase wide-format | not lot-level |
| `Combined BS.csv` | BCP + Adjustments + Consolidated entity columns | balance sheet line items | entity-level only |
| `Dehart Underwriting (Summary).csv` | Payson Larsen project (Dehart) | one-project underwriting model | not stageable as-is; outside the 16 active projects |
| `IA Breakdown.csv` | Ammon, Eagle Vista, Tooele/Grantsville/Erda/Skywalk, Smart Acres, Woolstead-Payson, Nathan, Waddell — all non-BCP-builder pipeline projects | per-customer Inventory Asset balance | tie-out for entity GL only |

### Entities that are NOT covered by any current ops source

Based on `2025Status` projects without Collateral Report rows:

| project | in `2025Status`? | in Collateral Report? | in any allocation workbook? | gap |
|---|---|---|---|---|
| Ammon | ✅ 16 lots | ❌ | ❌ | full gap — no expected cost source |
| Cedar Glen | ✅ 10 lots | ❌ | ❌ | full gap |
| Eagle Vista | ✅ 5 lots | ❌ | ❌ | full gap |
| Eastbridge | ✅ 6 lots | ❌ | ❌ | full gap |
| Erda | ✅ 14 lots | ❌ | ❌ | full gap (mentioned in IA Breakdown via "Tooele, Grantsville, Erda, Skywalk" subtotal) |
| Ironton | ✅ 12 lots | ❌ | ❌ | full gap |
| Santaquin Estates | ✅ 2 lots | ❌ | ❌ | full gap |
| Westbridge | ✅ 6 lots | ❌ | ❌ | full gap |
| Lewis Estates | ✅ 34 lots | ❌ | ❌ | partial — could use OfferMaster (but no row for Lewis Estates in OfferMaster) |
| Dehart / Payson Larsen | ❌ | ❌ | ❌ (Dehart underwriting is wide-format, not stageable) | not in main project universe |

These 9 projects (71 lots total) are the persistent "9 projects with no expected-cost source" pattern v1 already documents.

### Org-wide rollup feasibility

| dimension | feasible for v2 org-wide? | gate |
|---|---|---|
| Lot count by status (LotState distribution) | ✅ yes | 2025Status covers all 16 projects, all 3,627 lots |
| Inventory snapshot (active + closed) | ✅ yes | INVENTORY + CLOSED tabs cover all communities + historical |
| Borrowing base (CollateralSnapshot) | ✅ yes for 9 BCPD projects (in Collateral Report); the other 7 + Lennar/EXT lots have no rows in Collateral Report — they're not in the BCP collateral pool | structural — those projects aren't pledged collateral |
| Expected cost (Allocation) | ❌ no for ~70% of phases | only LH (Lomond Heights) + PF (Parkway Fields) have populated allocation; Flagship workbook has framework but cells are blank |
| Vendor / GL drilldown | (Terminal B's lane) | n/a here |

**Bottom line for org-wide v2**: ✅ for inventory and lot-state; partial for collateral (only the 9 actively-pledged projects); ❌ for expected cost outside LH/PF unless someone fills in the Flagship workbook or we wire in OfferMaster as a community×product-type fallback.

---

## Verdict for Track A guardrail

**Inventory closing report → ready to stage** (proposal in `scratch/ops_inventory_collateral_allocation_findings.md` C1). This unblocks guardrail prerequisite #1.

**Collateral reports → ready to feed CollateralSnapshot at phase grain** for the 9 BCPD projects with rows; document the 7-project gap as a known v2 caveat.

**ClickUp → ready to feed TaskState** for the 1,177-row lot-tagged subset; apply subdivision crosswalk.

**Allocation → can replicate v1 (LH + PF only)**; the Flagship workbook framework is in place but mostly empty. Don't gate v2 on filling it in.

---
