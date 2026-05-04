"""
Build output/operating_state_v2_bcpd.json — the BCPD-scoped operating state v2.

Mirrors the structure of output/operating_state_v1.json but uses v2 source data
and the v0 canonical tables / crosswalks.

Layers:
- metadata
- data_quality summary
- guardrail_status
- caveats
- projects (per-project rollup)
  - phases
    - lots (high-level identity + status)
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
STAGED = REPO / "data/staged"
OUT = REPO / "output" / "operating_state_v2_bcpd.json"

GL_PARQUET = STAGED / "staged_gl_transactions_v2.parquet"
INV_PARQUET = STAGED / "staged_inventory_lots.parquet"
CK_PARQUET = STAGED / "staged_clickup_tasks.parquet"
LOT_DATA_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
               "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv"
STATUS_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
             "Collateral Dec2025 01 Claude.xlsx - 2025Status.csv"
COLLATERAL_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
                 "Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv"
CANON_PROJECT = STAGED / "canonical_project.parquet"
CANON_PHASE = STAGED / "canonical_phase.parquet"
CANON_LOT = STAGED / "canonical_lot.parquet"
PROJ_XWALK = STAGED / "staged_project_crosswalk_v0.csv"


def _norm_lot(s) -> str:
    if pd.isna(s): return ""
    s = str(s).strip()
    if s.endswith(".0"): s = s[:-2]
    if s.isdigit(): return str(int(s))
    i = 0
    while i < len(s) and s[i].isdigit(): i += 1
    if i > 0:
        num = s[:i].lstrip("0") or "0"
        return num + s[i:]
    return s


def dr_dedup_key(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate DR 38-col rows on the canonical financial+narrative key,
    preferring the row with most non-null metadata."""
    key_cols = ["entity_name", "posting_date", "account_code", "amount",
                "project_code", "lot", "memo_1", "description", "batch_description"]
    df = df.copy()
    # metadata richness score: count non-null in (account_name, account_type)
    df["_meta_score"] = (df["account_name"].notna().astype(int) +
                         df["account_type"].notna().astype(int))
    df = df.sort_values("_meta_score", ascending=False)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    df = df.drop(columns=["_meta_score"])
    return df


def main() -> int:
    print("[v2-build] loading inputs...")
    gl = pd.read_parquet(GL_PARQUET)
    inv = pd.read_parquet(INV_PARQUET)
    ck = pd.read_parquet(CK_PARQUET)
    canon_proj = pd.read_parquet(CANON_PROJECT)
    canon_phase = pd.read_parquet(CANON_PHASE)
    canon_lot = pd.read_parquet(CANON_LOT)
    proj_xw = pd.read_csv(PROJ_XWALK)
    ld = pd.read_csv(LOT_DATA_CSV)
    st = pd.read_csv(STATUS_CSV, header=2)
    cr = pd.read_csv(COLLATERAL_CSV, header=8)

    # BCPD scope: HorzCustomer=BCP active per 2025Status, plus historicals via inventory
    bcpd_lots = canon_lot[canon_lot["bcpd_scope"] == True].copy()
    bcpd_lots["canonical_lot_number_norm"] = bcpd_lots["canonical_lot_number"].apply(_norm_lot)

    # GL BCPD rows
    bcpd_gl = gl[gl["entity_name"] == "Building Construction Partners, LLC"].copy()
    bcpd_gl["lot_norm"] = bcpd_gl["lot"].astype(str).apply(_norm_lot)
    bcpd_gl["year"] = pd.to_datetime(bcpd_gl["posting_date"]).dt.year

    # DR dedup
    dr = bcpd_gl[bcpd_gl["source_schema"] == "datarails_38col"].copy()
    dr_d = dr_dedup_key(dr)
    print(f"[v2-build] DR dedup: {len(dr):,} → {len(dr_d):,} rows ({len(dr_d)/len(dr)*100:.1f}%)")
    vf = bcpd_gl[bcpd_gl["source_schema"] == "vertical_financials_46col"].copy()
    qb = bcpd_gl[bcpd_gl["source_schema"] == "qb_register_12col"].copy()  # tie-out only

    # Map GL project_code → canonical_project
    gl_xw = proj_xw[proj_xw["source_system"].str.startswith("gl_v2")][
        ["source_value", "canonical_project", "source_system"]
    ].rename(columns={"source_value": "project_code"})

    dr_d = dr_d.merge(gl_xw[gl_xw["source_system"]=="gl_v2.datarails_38col.project_code"][
        ["project_code","canonical_project"]], on="project_code", how="left")
    vf = vf.merge(gl_xw[gl_xw["source_system"]=="gl_v2.vertical_financials_46col.project_code"][
        ["project_code","canonical_project"]], on="project_code", how="left")

    # 2025Status filtered to BCP
    bcp_status = st[st["HorzCustomer"]=="BCP"].copy()

    # Derive current_stage per lot using v1 waterfall on Lot Data dates
    LOT_STATE_WATERFALL = [
        ("VertClose",    "CLOSED"),
        ("VertSale",     "SOLD_NOT_CLOSED"),
        ("VertCO",       "VERTICAL_COMPLETE"),
        ("VertStart",    "VERTICAL_IN_PROGRESS"),
        ("VertPurchase", "VERTICAL_PURCHASED"),
        ("HorzRecord",   "FINISHED_LOT"),
        ("HorzStart",    "HORIZONTAL_IN_PROGRESS"),
        ("HorzPurchase", "LAND_OWNED"),
    ]
    LOT_STATE_TO_PCT = {
        "PROSPECT": None, "LAND_OWNED": 0.05, "HORIZONTAL_IN_PROGRESS": 0.15,
        "FINISHED_LOT": 0.30, "VERTICAL_PURCHASED": 0.35,
        "VERTICAL_IN_PROGRESS": 0.55, "VERTICAL_COMPLETE": 0.85,
        "SOLD_NOT_CLOSED": 0.95, "CLOSED": None,
    }

    def waterfall(row):
        for col, state in LOT_STATE_WATERFALL:
            v = row.get(col)
            if pd.notna(v) and str(v).strip() not in ("", "1899-12-30 00:00:00", "1899-12-30"):
                # Treat the Excel sentinel as null
                try:
                    d = pd.to_datetime(v)
                    if d.year < 1900:
                        continue
                except Exception:
                    pass
                return state
        return "PROSPECT"

    ld_bcp = ld[ld["HorzCustomer"]=="BCP"].copy()
    ld_bcp["current_stage"] = ld_bcp.apply(waterfall, axis=1)
    ld_bcp["completion_pct"] = ld_bcp["current_stage"].map(LOT_STATE_TO_PCT)
    # Build a (project, phase, lot_norm) → stage lookup
    ld_bcp["lot_norm"] = ld_bcp["LotNo."].astype(str).apply(_norm_lot)
    ld_bcp_u = ld_bcp.drop_duplicates(subset=["Project","Phase","lot_norm"], keep="first")
    stage_by_key = ld_bcp_u.set_index(["Project","Phase","lot_norm"])[
        ["current_stage","completion_pct","HorzSeller"]].to_dict("index")

    # Inventory status overlay
    inv_status_by_key = {}
    for _, r in inv.iterrows():
        if r["canonical_project"] and r["lot_num"] and r["phase"]:
            k = (r["canonical_project"], str(r["phase"]).strip(), _norm_lot(r["lot_num"]))
            inv_status_by_key[k] = r["lot_status"]

    # ClickUp lot-tagged map (project, lot_norm) → list of statuses + dates
    ck_xw = proj_xw[proj_xw["source_system"]=="clickup.subdivision"][
        ["source_value","canonical_project"]].rename(columns={"source_value":"subdivision"})
    ck_lot = ck[ck["subdivision"].notna() & ck["lot_num"].notna()].copy()
    ck_lot = ck_lot.merge(ck_xw, on="subdivision", how="inner")
    ck_lot = ck_lot[ck_lot["canonical_project"] != ""]
    ck_lot["lot_norm"] = ck_lot["lot_num"].astype(str).apply(_norm_lot)
    ck_by_key = {}
    for _, r in ck_lot.iterrows():
        k = (r["canonical_project"], r["lot_norm"])
        info = ck_by_key.setdefault(k, {"statuses": [], "actual_c_of_o": None,
                                         "due_date": None, "projected_close_date": None})
        if pd.notna(r.get("status")):
            info["statuses"].append(str(r["status"]))
        for fld in ["actual_c_of_o","due_date","projected_close_date"]:
            v = r.get(fld)
            if pd.notna(v) and info[fld] is None:
                info[fld] = str(v)

    # ---- Build per-project / per-phase / per-lot rollups ----
    # Use the high-confidence canonical projects only for the body
    high_proj = canon_proj[canon_proj["source_confidence"]=="high"]["canonical_project"].tolist()

    # Per-project actual_cost from GL
    proj_actuals = {}
    for cp in high_proj:
        vf_rows = vf[vf["canonical_project"] == cp]
        dr_rows = dr_d[dr_d["canonical_project"] == cp]
        proj_actuals[cp] = {
            "vf_2018_2025_sum": float(vf_rows["amount"].sum()),
            "vf_2018_2025_rows": int(len(vf_rows)),
            "dr_2016_2017_sum_dedup": float(dr_rows["amount"].sum()),
            "dr_2016_2017_rows_dedup": int(len(dr_rows)),
        }

    # Collateral by (project, phase)
    cr = cr.dropna(subset=["Project"]).copy()
    coll_by_pp = {}
    for _, r in cr.iterrows():
        proj = str(r["Project"]).strip()
        phase = str(r.get("Phase","")).strip()
        if not proj or not phase or phase.lower()=="nan":
            continue
        coll_by_pp[(proj, phase)] = {
            "lot_count": (None if pd.isna(r.get("# of Lots")) else float(r["# of Lots"])),
            "total_lot_value": (None if pd.isna(r.get("Total Lot Value")) else float(r["Total Lot Value"])),
            "advance_pct": (None if pd.isna(r.get("Advance %")) else float(r["Advance %"])),
            "loan_dollars": (None if pd.isna(r.get("Loan $")) else float(r["Loan $"])),
            "total_dev_cost": (None if pd.isna(r.get("Total Dev Cost (Spent + Remaining)")) else float(r["Total Dev Cost (Spent + Remaining)"])),
            "remaining_dev_costs": (None if pd.isna(r.get("Remaining Dev Costs")) else float(r["Remaining Dev Costs"])),
        }

    # Build the JSON
    projects_out = []
    total_lots = 0
    total_lots_with_gl = 0
    total_lots_with_clickup = 0
    total_lots_high_conf = 0
    total_lots_med_conf = 0
    total_lots_low_conf = 0

    for cp in sorted(high_proj):
        # Phases for this project
        proj_phases = canon_phase[canon_phase["canonical_project"] == cp].copy()
        # Lots
        proj_lots = bcpd_lots[bcpd_lots["canonical_project"] == cp].copy()
        if proj_lots.empty and proj_phases.empty:
            continue

        phases_out = []
        for _, ph in proj_phases.iterrows():
            phase_name = ph["canonical_phase"]
            phase_lots = proj_lots[proj_lots["canonical_phase"] == phase_name]
            lot_dicts = []
            for _, lot in phase_lots.iterrows():
                key_status = (cp, phase_name, lot["canonical_lot_number_norm"])
                stage_info = stage_by_key.get(key_status, {})
                inv_status = inv_status_by_key.get(key_status)
                ck_info = ck_by_key.get((cp, lot["canonical_lot_number_norm"]), {})
                d = {
                    "canonical_lot_id": lot["canonical_lot_id"],
                    "canonical_lot_number": lot["canonical_lot_number"],
                    "horz_customer": lot.get("horz_customer") if not pd.isna(lot.get("horz_customer")) else None,
                    "horz_seller": stage_info.get("HorzSeller"),
                    "lot_status_inventory": inv_status,
                    "current_stage": stage_info.get("current_stage"),
                    "completion_pct": stage_info.get("completion_pct"),
                    "in_inventory": bool(lot["in_inventory"]),
                    "in_lot_data": bool(lot["in_lot_data"]),
                    "in_2025status": bool(lot["in_2025status"]),
                    "in_clickup_lottagged": bool(ck_info),
                    "clickup_status": ck_info.get("statuses", [None])[0] if ck_info.get("statuses") else None,
                    "actual_c_of_o": ck_info.get("actual_c_of_o"),
                    "source_confidence": lot["source_confidence"],
                }
                lot_dicts.append(d)
                total_lots += 1
                if lot["source_confidence"] == "high": total_lots_high_conf += 1
                elif lot["source_confidence"] == "medium": total_lots_med_conf += 1
                else: total_lots_low_conf += 1

            collateral = coll_by_pp.get((cp, phase_name))
            phases_out.append({
                "canonical_phase": phase_name,
                "lot_count_observed": len(lot_dicts),
                "in_inventory": bool(ph["in_inventory"]),
                "in_lot_data": bool(ph["in_lot_data"]),
                "in_2025status": bool(ph["in_2025status"]),
                "phase_confidence": ph["source_confidence"],
                "collateral": collateral,
                "lots": lot_dicts,
            })

        cost = proj_actuals.get(cp, {})
        projects_out.append({
            "canonical_project": cp,
            "canonical_entity": "BCPD",
            "phase_count": len(phases_out),
            "lot_count": int(proj_lots.shape[0]),
            "lot_count_active_2025status": int(((bcp_status["Project"]==cp) &
                bcp_status["Lot"].notna()).sum()),
            "actuals": {
                "vf_2018_2025_sum_usd": cost.get("vf_2018_2025_sum"),
                "vf_2018_2025_rows": cost.get("vf_2018_2025_rows"),
                "dr_2016_2017_sum_usd_dedup": cost.get("dr_2016_2017_sum_dedup"),
                "dr_2016_2017_rows_dedup": cost.get("dr_2016_2017_rows_dedup"),
                "qb_2025_treatment": "tie-out only — excluded from primary rollups (see guardrail_check_v0.md)",
                "gap_2017_03_to_2018_06": "GL has zero rows in this 15-month window",
            },
            "phases": phases_out,
        })

    # GL/ClickUp triangle stats — re-derive
    inv_pl = set()
    for _, r in inv[(inv["canonical_project"].notna()) & (inv["canonical_project"]!="") &
                    (inv["lot_num"].notna()) & (inv["lot_num"]!="") &
                    (inv["project_confidence"]=="high")].iterrows():
        inv_pl.add((r["canonical_project"], _norm_lot(r["lot_num"])))
    gl_pl = set()
    for _, r in vf.iterrows():
        if pd.notna(r.get("canonical_project")) and r.get("lot_norm"):
            gl_pl.add((r["canonical_project"], r["lot_norm"]))
    for _, r in dr_d.iterrows():
        if pd.notna(r.get("canonical_project")) and r.get("lot_norm"):
            gl_pl.add((r["canonical_project"], r["lot_norm"]))
    ck_pl = set()
    for _, r in ck_lot.iterrows():
        ck_pl.add((r["canonical_project"], r["lot_norm"]))

    n_inv = len(inv_pl)
    n_inv_gl = len(inv_pl & gl_pl)
    n_inv_ck = len(inv_pl & ck_pl)
    n_tri = len(inv_pl & gl_pl & ck_pl)

    payload = {
        "schema_version": "operating_state_v2_bcpd",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "as_of_date_inventory": "2026-04-29",
            "as_of_date_collateral": "2025-12-31",
            "as_of_date_collateral_prior": "2025-06-30",
            "as_of_date_gl_max": "2025-12-31",
            "entities_in_scope": ["BCPD", "BCPBL", "ASD", "BCPI"],
            "entity_filter_applied": "GL: entity_name='Building Construction Partners, LLC'; Lot Data/2025Status: HorzCustomer='BCP'",
            "ontology_version": "v0",
            "field_map_version": "v0",
            "guardrail_status": "GREEN — see data/reports/guardrail_check_v0.md",
            "source_versions": {
                "staged_gl_transactions_v2": "210,440 rows; BCPD subset 197,852",
                "staged_inventory_lots": "3,872 rows from Inventory _ Closing Report (2).xlsx",
                "staged_clickup_tasks": "5,509 rows; lot-tagged subset 1,177",
                "Collateral Report.csv": "as_of 2025-12-31; 41 phase rows (9 of 16 BCPD active projects)",
                "PriorCR.csv": "as_of 2025-06-30; same schema; 41 rows",
                "LH Allocation 2025.10": "Lomond Heights — 12 phase × prod_type rows",
                "Parkway Allocation 2025.10": "Parkway Fields — 14 rows",
            },
        },
        "data_quality": {
            "lots_total_in_canonical": int(total_lots),
            "lots_high_confidence": int(total_lots_high_conf),
            "lots_medium_confidence": int(total_lots_med_conf),
            "lots_low_confidence": int(total_lots_low_conf),
            "join_coverage_inventory_base": n_inv,
            "join_coverage_with_gl": n_inv_gl,
            "join_coverage_with_clickup": n_inv_ck,
            "join_coverage_full_triangle": n_tri,
            "join_coverage_pct_gl": round(n_inv_gl/max(n_inv,1)*100, 1),
            "join_coverage_pct_clickup": round(n_inv_ck/max(n_inv,1)*100, 1),
            "join_coverage_pct_triangle": round(n_tri/max(n_inv,1)*100, 1),
            "datarails_38col_dedup_applied": True,
            "datarails_38col_multiplicity": 2.16,
            "datarails_38col_post_dedup_rows": int(len(dr_d)),
            "vertical_financials_46col_rows": int(len(vf)),
            "qb_register_12col_treatment": "tie-out only; excluded from primary rollups",
        },
        "caveats": [
            "Org-wide v2 is blocked: Hillcrest Road at Saratoga, LLC and Flagship Belmont Phase two LLC have GL data only through 2017-02; cannot publish org-wide rollup without a fresh export.",
            "GL gap 2017-03 → 2018-06 (~15 months, zero rows for any entity). Pre-2018 BCPD cost rollups are limited to 2016-02 → 2017-02 with DataRails 38-col after dedup.",
            "DataRails 38-col is 2.16× row-multiplied at the source. We deduplicate before any cost rollup; raw v2 parquet is preserved unchanged.",
            "Vertical Financials 46-col is a one-sided cost-accumulation feed (asset-side debit only; structural by design). Use as primary cost basis for BCPD 2018-2025; do not expect debit-credit balance.",
            "QB register 12-col uses a different chart of accounts with zero account_code overlap to DR/VF — excluded from primary rollups; tie-out only.",
            "Phase grain is unsupported in GL (0% phase fill across all 3 source schemas). Phase rollups derive from inventory + Lot Data + 2025Status + ClickUp.",
            "GL VF lot codes encode phase+lot for some projects (e.g., Harm3 lot 1034 likely encodes Harmony Phase 3 Lot 34). v0 normalizer strips zeros only; phase-aware decoder is a v1 follow-up.",
            "Lewis Estates (34 BCPD lots) has zero GL rows and no Collateral Report row — full structural gap.",
            "Allocation/budget is populated only for Lomond Heights (LH Allocation) and Parkway Fields (Parkway Allocation). Other BCPD projects have framework (Flagship Allocation Workbook v3) but cells are mostly empty.",
            "ClickUp lot-tagged subset is sparse (1,177 of 5,509 tasks). Lots without ClickUp coverage rely on inventory + GL only.",
            "Collateral Report only covers 9 of 16 active BCPD projects (the pledged-collateral universe). The 7 missing projects (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge) are structural — not pledged collateral.",
            "Inventory file source choice: workbook (2) was used (deliberate deviation from lane-doc claim that (4) is canonical/latest; data shows (2) is freshest by ~2 days and carries 1 net-new sale event). See staged_inventory_lots_validation_report.md.",
        ],
        "projects": projects_out,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[v2-build] wrote {OUT} ({OUT.stat().st_size:,} B)")
    print(f"[v2-build] projects in body: {len(projects_out)}; lots in body: {total_lots:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
