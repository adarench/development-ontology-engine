"""
W6 — Build BCPD Operating State v2.1.

Additive rebuild that incorporates the v1 VF decoder + Terminal B/C review fixes.
v2.0 outputs remain untouched. v2.1 sits alongside as a strictly more accurate
artifact at `inferred` confidence.

Required changes from v2.0:
1. AultF B-suffix → B1 (was B2). $4.0M / 1,499 rows correctly routed.
2. Harmony 3-tuple join discipline — every cost rollup uses (project, phase, lot).
3. HarmCo split: residential A01-B10 → MF2; X-X commercial parcels → non-lot exception.
4. SctLot → 'Scattered Lots' canonical project (was Scarlet Ridge). $6.55M removed
   from Scarlet Ridge inflation.
5. Range rows kept at project+phase grain; surfaced as unattributed_shell_dollars
   per project ($45.75M / 4,020 rows total).
6. All decoder-derived mappings ship confidence='inferred',
   validated_by_source_owner=False.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
STAGED = REPO / "data/staged"
OUT = REPO / "output" / "operating_state_v2_1_bcpd.json"

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
DECODER_CSV = STAGED / "vf_lot_code_decoder_v1.csv"

# Reuse v1 decoder rules
from build_vf_lot_decoder_v1 import (  # type: ignore
    DECODERS, VF_TO_CANONICAL, PHASE_INV_TO_LD,
    lot_int, lot_canonical, is_range_lot,
)


def norm_lot(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def dr_dedup_key(df: pd.DataFrame) -> pd.DataFrame:
    """Apply DataRails 38-col 2.16x row-multiplication dedup."""
    key_cols = ["entity_name", "posting_date", "account_code", "amount",
                "project_code", "lot", "memo_1", "description", "batch_description"]
    df = df.copy()
    df["_meta_score"] = (df["account_name"].notna().astype(int) +
                         df["account_type"].notna().astype(int))
    df = df.sort_values("_meta_score", ascending=False)
    df = df.drop_duplicates(subset=key_cols, keep="first")
    df = df.drop(columns=["_meta_score"])
    return df


def main() -> int:
    print("[v2.1-build] loading inputs...")
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
    decoder_v1 = pd.read_csv(DECODER_CSV)

    bcpd_lots = canon_lot[canon_lot["bcpd_scope"] == True].copy()
    bcpd_lots["canonical_lot_number_norm"] = bcpd_lots["canonical_lot_number"].apply(
        lambda v: lot_canonical(norm_lot(v))
    )

    bcpd_gl = gl[gl["entity_name"] == "Building Construction Partners, LLC"].copy()
    bcpd_gl["lot_norm"] = bcpd_gl["lot"].astype(str).apply(lambda v: lot_canonical(norm_lot(v)))
    bcpd_gl["year"] = pd.to_datetime(bcpd_gl["posting_date"]).dt.year

    # DR dedup (preserved from v2.0)
    dr = bcpd_gl[bcpd_gl["source_schema"] == "datarails_38col"].copy()
    dr_d = dr_dedup_key(dr)
    print(f"[v2.1] DR dedup: {len(dr):,} → {len(dr_d):,} rows")
    vf = bcpd_gl[bcpd_gl["source_schema"] == "vertical_financials_46col"].copy()

    # ===== Apply v1 decoder to VF =====
    raw_to_rules = {}
    for raw, name, fn, vcode in DECODERS:
        raw_to_rules.setdefault(raw, []).append((name, fn, vcode))

    vf_decoded = []  # one row per VF row with attached (canon_proj, canon_phase, canon_lot)
    range_rows_by_proj_phase = {}  # (canon_proj, canon_phase) → {rows, dollars}
    commercial_rows_by_proj_pad = {}  # (canon_proj, pad) → {rows, dollars}
    sr_rows = {"rows": 0, "dollars": 0.0}
    sctlot_rows = {"rows": 0, "dollars": 0.0}

    for _, r in vf.iterrows():
        raw_lot = str(r["lot"]).strip() if pd.notna(r["lot"]) else ""
        code = r["project_code"]
        amount = float(r.get("amount") or 0)
        rules = raw_to_rules.get(code, [])

        if not rules:
            # Out-of-decoder-scope codes: Salem (SalemS/SaleTR/SaleTT), MCreek, WilCrk, etc.
            # Apply v0-style mapping via project crosswalk; range rows still get isolated.
            xw_match = proj_xw[
                (proj_xw["source_system"] == "gl_v2.vertical_financials_46col.project_code") &
                (proj_xw["source_value"] == code)
            ]
            if xw_match.empty:
                continue
            canon = xw_match.iloc[0]["canonical_project"]
            if is_range_lot(raw_lot):
                key = (canon, "(unphased)")
                d = range_rows_by_proj_phase.setdefault(key, {"rows": 0, "dollars": 0.0})
                d["rows"] += 1
                d["dollars"] += abs(amount)
                continue
            n = lot_int(raw_lot)
            if n is None:
                continue
            vf_decoded.append({
                "row_hash": r["row_hash"],
                "canonical_project": canon,
                "canonical_phase": None,  # phase not derived for non-decoder codes
                "canonical_lot_number": str(n),
                "amount": amount,
                "year": r["year"],
                "account_code": r["account_code"],
                "decoder_rule": "v0_passthrough_no_phase",
                "decoder_confidence": "inferred",
            })
            continue

        for rule_name, fn, vcode in rules:
            # HarmCo split: dispatch on lot pattern
            if vcode == "HarmCo_residential" and not re.match(r"^0000[AB]\d{2}$", raw_lot):
                continue
            if vcode == "HarmCo_commercial" and not re.match(r"^0000[A-K]-[A-K]$", raw_lot):
                continue
            if vcode == "HarmCo_residential" and re.match(r"^0000[A-K]-[A-K]$", raw_lot):
                continue

            tag, phase, lot_n, _ = fn(raw_lot)
            canon = VF_TO_CANONICAL[vcode]

            if tag == "RANGE":
                key = (canon, phase or "(unphased)")
                d = range_rows_by_proj_phase.setdefault(key, {"rows": 0, "dollars": 0.0})
                d["rows"] += 1
                d["dollars"] += abs(amount)
                break
            if tag == "COMMERCIAL_PAD":
                key = (canon, lot_n or "?")
                d = commercial_rows_by_proj_pad.setdefault(key, {"rows": 0, "dollars": 0.0})
                d["rows"] += 1
                d["dollars"] += abs(amount)
                break
            if tag == "SR_INFERRED_UNKNOWN":
                sr_rows["rows"] += 1
                sr_rows["dollars"] += abs(amount)
                break
            if tag == "PROJECT_GRAIN_ONLY":
                sctlot_rows["rows"] += 1
                sctlot_rows["dollars"] += abs(amount)
                # Attach to canonical project 'Scattered Lots' at project grain only
                vf_decoded.append({
                    "row_hash": r["row_hash"],
                    "canonical_project": canon,  # 'Scattered Lots'
                    "canonical_phase": None,
                    "canonical_lot_number": None,
                    "amount": amount,
                    "year": r["year"],
                    "account_code": r["account_code"],
                    "decoder_rule": rule_name,
                    "decoder_confidence": "inferred",
                })
                break
            if phase and lot_n:
                vf_decoded.append({
                    "row_hash": r["row_hash"],
                    "canonical_project": canon,
                    "canonical_phase": phase,
                    "canonical_lot_number": lot_n,
                    "amount": amount,
                    "year": r["year"],
                    "account_code": r["account_code"],
                    "decoder_rule": rule_name,
                    "decoder_confidence": "inferred",
                })
                break
            else:
                # Decoded but unmatched
                break

    vf_dec_df = pd.DataFrame(vf_decoded)
    print(f"[v2.1] VF decoded rows: {len(vf_dec_df):,}")
    print(f"[v2.1] range rows isolated at project+phase grain: {sum(d['rows'] for d in range_rows_by_proj_phase.values()):,} ({sum(d['dollars'] for d in range_rows_by_proj_phase.values()):,.0f})")
    print(f"[v2.1] commercial parcel rows isolated: {sum(d['rows'] for d in commercial_rows_by_proj_pad.values()):,}")
    print(f"[v2.1] AultF SR rows isolated: {sr_rows['rows']:,} (${sr_rows['dollars']:,.0f})")
    print(f"[v2.1] SctLot → Scattered Lots rows: {sctlot_rows['rows']:,} (${sctlot_rows['dollars']:,.0f})")

    # ===== DR rows with project crosswalk (project-grain only since DR has no phase) =====
    dr_xw = proj_xw[proj_xw["source_system"] == "gl_v2.datarails_38col.project_code"][
        ["source_value", "canonical_project"]].rename(columns={"source_value": "project_code"})
    dr_d2 = dr_d.merge(dr_xw, on="project_code", how="left")

    # ===== Lifecycle stage from Lot Data (v1 waterfall) =====
    LOT_STATE_WATERFALL = [
        ("VertClose", "CLOSED"),
        ("VertSale", "SOLD_NOT_CLOSED"),
        ("VertCO", "VERTICAL_COMPLETE"),
        ("VertStart", "VERTICAL_IN_PROGRESS"),
        ("VertPurchase", "VERTICAL_PURCHASED"),
        ("HorzRecord", "FINISHED_LOT"),
        ("HorzStart", "HORIZONTAL_IN_PROGRESS"),
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
                try:
                    d = pd.to_datetime(v)
                    if d.year < 1900:
                        continue
                except Exception:
                    pass
                return state
        return "PROSPECT"

    ld_bcp = ld[ld["HorzCustomer"] == "BCP"].copy()
    ld_bcp["current_stage"] = ld_bcp.apply(waterfall, axis=1)
    ld_bcp["completion_pct"] = ld_bcp["current_stage"].map(LOT_STATE_TO_PCT)
    ld_bcp["lot_norm"] = ld_bcp["LotNo."].astype(str).apply(
        lambda v: lot_canonical(norm_lot(v))
    )
    ld_bcp_u = ld_bcp.drop_duplicates(subset=["Project", "Phase", "lot_norm"], keep="first")
    stage_by_key = ld_bcp_u.set_index(["Project", "Phase", "lot_norm"])[
        ["current_stage", "completion_pct", "HorzSeller"]].to_dict("index")

    # ===== Inventory status overlay (3-tuple key) =====
    inv_status_by_key = {}
    for _, r in inv.iterrows():
        if r["canonical_project"] and r["lot_num"] and r["phase"]:
            phase_canon = PHASE_INV_TO_LD.get(
                (r["canonical_project"], str(r["phase"]).strip()),
                str(r["phase"]).strip()
            )
            k = (r["canonical_project"], phase_canon, lot_canonical(norm_lot(r["lot_num"])))
            inv_status_by_key[k] = r["lot_status"]

    # ===== ClickUp lot-tagged map =====
    ck_xw = proj_xw[proj_xw["source_system"] == "clickup.subdivision"][
        ["source_value", "canonical_project"]].rename(columns={"source_value": "subdivision"})
    ck_lot = ck[ck["subdivision"].notna() & ck["lot_num"].notna()].copy()
    ck_lot = ck_lot.merge(ck_xw, on="subdivision", how="inner")
    ck_lot = ck_lot[ck_lot["canonical_project"] != ""]
    ck_lot["lot_norm"] = ck_lot["lot_num"].astype(str).apply(lambda v: lot_canonical(norm_lot(v)))
    ck_by_key = {}  # (canon, lot_norm) → info — phase optional in ClickUp
    for _, r in ck_lot.iterrows():
        k = (r["canonical_project"], r["lot_norm"])
        info = ck_by_key.setdefault(k, {"statuses": [], "actual_c_of_o": None,
                                          "due_date": None, "projected_close_date": None})
        if pd.notna(r.get("status")):
            info["statuses"].append(str(r["status"]))
        for fld in ["actual_c_of_o", "due_date", "projected_close_date"]:
            v = r.get(fld)
            if pd.notna(v) and info[fld] is None:
                info[fld] = str(v)

    # ===== Build per-project / per-phase / per-lot rollups =====
    high_proj = canon_proj[canon_proj["source_confidence"] == "high"]["canonical_project"].tolist()
    # Add 'Scattered Lots' as a new project entry
    if "Scattered Lots" not in high_proj:
        high_proj.append("Scattered Lots")

    # Per-project actuals (3-tuple discipline for VF in decoder scope)
    proj_actuals = {}
    decoder_canon_set = set(VF_TO_CANONICAL.values())

    for cp in high_proj:
        if cp == "Scattered Lots":
            # SctLot project-grain only
            proj_actuals[cp] = {
                "vf_2018_2025_sum_usd": float(sctlot_rows["dollars"]),
                "vf_2018_2025_rows": int(sctlot_rows["rows"]),
                "vf_lot_grain_sum_usd": 0.0,  # no lot grain
                "vf_lot_grain_rows": 0,
                "vf_range_grain_sum_usd": 0.0,
                "vf_range_grain_rows": 0,
                "vf_commercial_grain_sum_usd": 0.0,
                "vf_commercial_grain_rows": 0,
                "vf_unattributed_shell_dollars": 0.0,
                "dr_2016_2017_sum_usd_dedup": 0.0,
                "dr_2016_2017_rows_dedup": 0,
                "scope_note": "v2.1: separated from Scarlet Ridge per Terminal B Q4. Lot-level inventory does not exist for these scattered/custom lots; project-grain rollup only.",
            }
            continue

        # VF in decoder scope → use 3-tuple decoded rows
        vf_lot_grain = vf_dec_df[
            (vf_dec_df["canonical_project"] == cp) &
            (vf_dec_df["canonical_phase"].notna()) &
            (vf_dec_df["canonical_lot_number"].notna())
        ] if not vf_dec_df.empty else vf_dec_df

        # VF outside decoder scope (e.g. Salem, Willowcreek, Meadow Creek) — already decoded with phase=None
        vf_passthrough = vf_dec_df[
            (vf_dec_df["canonical_project"] == cp) &
            (vf_dec_df["decoder_rule"] == "v0_passthrough_no_phase")
        ] if not vf_dec_df.empty else vf_dec_df

        # Range dollars for this project
        range_rows_total = sum(d["rows"] for k, d in range_rows_by_proj_phase.items() if k[0] == cp)
        range_dollars_total = sum(d["dollars"] for k, d in range_rows_by_proj_phase.items() if k[0] == cp)
        # Commercial dollars (only Harmony has these)
        comm_rows_total = sum(d["rows"] for k, d in commercial_rows_by_proj_pad.items() if k[0] == cp)
        comm_dollars_total = sum(d["dollars"] for k, d in commercial_rows_by_proj_pad.items() if k[0] == cp)

        vf_lot_dollars = float(vf_lot_grain["amount"].sum()) if len(vf_lot_grain) else 0.0
        vf_passthrough_dollars = float(vf_passthrough["amount"].sum()) if len(vf_passthrough) else 0.0
        vf_total_dollars = vf_lot_dollars + vf_passthrough_dollars + range_dollars_total + comm_dollars_total
        if cp in decoder_canon_set:
            sr_share = sr_rows["dollars"] if cp == "Parkway Fields" else 0.0
            sr_share_rows = sr_rows["rows"] if cp == "Parkway Fields" else 0
            vf_total_dollars += sr_share
        else:
            sr_share = 0.0
            sr_share_rows = 0

        dr_rows = dr_d2[dr_d2["canonical_project"] == cp]
        proj_actuals[cp] = {
            "vf_2018_2025_sum_usd": float(vf_total_dollars),
            "vf_2018_2025_rows": int(len(vf_lot_grain) + len(vf_passthrough) + range_rows_total +
                                       comm_rows_total + sr_share_rows),
            "vf_lot_grain_sum_usd": float(vf_lot_dollars + vf_passthrough_dollars),
            "vf_lot_grain_rows": int(len(vf_lot_grain) + len(vf_passthrough)),
            "vf_range_grain_sum_usd": float(range_dollars_total),
            "vf_range_grain_rows": int(range_rows_total),
            "vf_commercial_grain_sum_usd": float(comm_dollars_total),
            "vf_commercial_grain_rows": int(comm_rows_total),
            "vf_sr_inferred_unknown_sum_usd": float(sr_share),
            "vf_sr_inferred_unknown_rows": int(sr_share_rows),
            "vf_unattributed_shell_dollars": float(range_dollars_total),
            "dr_2016_2017_sum_usd_dedup": float(dr_rows["amount"].sum()),
            "dr_2016_2017_rows_dedup": int(len(dr_rows)),
        }

    # Collateral by (project, phase)
    cr_clean = cr.dropna(subset=["Project"]).copy()
    coll_by_pp = {}
    for _, r in cr_clean.iterrows():
        proj = str(r["Project"]).strip()
        phase = str(r.get("Phase", "")).strip()
        if not proj or not phase or phase.lower() == "nan":
            continue
        coll_by_pp[(proj, phase)] = {
            "lot_count": (None if pd.isna(r.get("# of Lots")) else float(r["# of Lots"])),
            "total_lot_value": (None if pd.isna(r.get("Total Lot Value")) else float(r["Total Lot Value"])),
            "advance_pct": (None if pd.isna(r.get("Advance %")) else float(r["Advance %"])),
            "loan_dollars": (None if pd.isna(r.get("Loan $")) else float(r["Loan $"])),
            "total_dev_cost": (None if pd.isna(r.get("Total Dev Cost (Spent + Remaining)")) else float(r["Total Dev Cost (Spent + Remaining)"])),
            "remaining_dev_costs": (None if pd.isna(r.get("Remaining Dev Costs")) else float(r["Remaining Dev Costs"])),
        }

    # Per-lot VF cost lookup (3-tuple)
    vf_lot_dollars_by_key = {}
    if not vf_dec_df.empty:
        for (cp, ph, ln), g in vf_dec_df[
            vf_dec_df["canonical_phase"].notna() & vf_dec_df["canonical_lot_number"].notna()
        ].groupby(["canonical_project", "canonical_phase", "canonical_lot_number"]):
            vf_lot_dollars_by_key[(cp, ph, ln)] = (float(g["amount"].sum()), int(len(g)))

    # ===== Build the JSON =====
    projects_out = []
    total_lots = 0
    total_high = total_med = total_low = 0
    bcpd_2t = set()
    gl_2t = set()
    ck_2t = set()
    bcpd_3t = set()
    vf_3t_match = set()

    bcpd_inv_eligible = inv[(inv["canonical_project"].notna()) & (inv["canonical_project"] != "") &
                             (inv["lot_num"].notna()) & (inv["lot_num"] != "") &
                             (inv["phase"].notna()) & (inv["phase"] != "") &
                             (inv["project_confidence"] == "high")].copy()
    for _, r in bcpd_inv_eligible.iterrows():
        ln = lot_canonical(norm_lot(r["lot_num"]))
        ph = PHASE_INV_TO_LD.get((r["canonical_project"], str(r["phase"]).strip()),
                                  str(r["phase"]).strip())
        bcpd_2t.add((r["canonical_project"], ln))
        bcpd_3t.add((r["canonical_project"], ph, ln))

    for _, r in vf_dec_df.iterrows() if not vf_dec_df.empty else []:
        if r["canonical_phase"] and r["canonical_lot_number"]:
            t3 = (r["canonical_project"], r["canonical_phase"], r["canonical_lot_number"])
            if t3 in bcpd_3t:
                vf_3t_match.add(t3)
            gl_2t.add((r["canonical_project"], r["canonical_lot_number"]))
        elif r["canonical_lot_number"]:
            gl_2t.add((r["canonical_project"], r["canonical_lot_number"]))

    for _, r in dr_d2.iterrows():
        if pd.notna(r.get("canonical_project")) and r.get("lot_norm"):
            gl_2t.add((r["canonical_project"], r["lot_norm"]))
    for _, r in ck_lot.iterrows():
        ck_2t.add((r["canonical_project"], r["lot_norm"]))

    n_inv = len(bcpd_2t)
    n_inv_gl = len(bcpd_2t & gl_2t)
    n_inv_ck = len(bcpd_2t & ck_2t)
    n_tri = len(bcpd_2t & gl_2t & ck_2t)

    for cp in sorted(high_proj):
        proj_phases = canon_phase[canon_phase["canonical_project"] == cp].copy()
        proj_lots = bcpd_lots[bcpd_lots["canonical_project"] == cp].copy()

        if cp == "Scattered Lots":
            cost = proj_actuals.get(cp, {})
            projects_out.append({
                "canonical_project": "Scattered Lots",
                "canonical_entity": "BCPD",
                "phase_count": 0,
                "lot_count": 0,
                "lot_count_active_2025status": 0,
                "actuals": cost,
                "v2_1_note": "New canonical project introduced in v2.1. Carries SctLot rows previously misattributed to Scarlet Ridge in v2.0. Project-grain only — no lot-level inventory available; source-owner validation required for canonical name and program identity.",
                "phases": [],
            })
            continue

        if proj_lots.empty and proj_phases.empty:
            continue

        phases_out = []
        for _, ph in proj_phases.iterrows():
            phase_name = ph["canonical_phase"]
            phase_lots = proj_lots[proj_lots["canonical_phase"] == phase_name]
            lot_dicts = []

            for _, lot in phase_lots.iterrows():
                ln = lot["canonical_lot_number_norm"]
                # 3-tuple key for VF lookup
                vf_dollars, vf_rows = vf_lot_dollars_by_key.get((cp, phase_name, ln), (0.0, 0))
                stage_info = stage_by_key.get((cp, phase_name, ln), {})
                inv_status = inv_status_by_key.get((cp, phase_name, ln))
                ck_info = ck_by_key.get((cp, ln), {})

                lot_dict = {
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
                    "vf_actual_cost_3tuple_usd": float(vf_dollars),
                    "vf_actual_cost_rows": int(vf_rows),
                    "vf_actual_cost_join_key": "(canonical_project, canonical_phase, canonical_lot_number)",
                    "vf_actual_cost_confidence": "inferred (v1 decoder; not source-owner-validated)",
                    "source_confidence": lot["source_confidence"],
                }
                lot_dicts.append(lot_dict)
                total_lots += 1
                if lot["source_confidence"] == "high":
                    total_high += 1
                elif lot["source_confidence"] == "medium":
                    total_med += 1
                else:
                    total_low += 1

            # Range dollars at this phase
            range_d = range_rows_by_proj_phase.get((cp, phase_name), {"rows": 0, "dollars": 0.0})
            collateral = coll_by_pp.get((cp, phase_name))

            phases_out.append({
                "canonical_phase": phase_name,
                "lot_count_observed": len(lot_dicts),
                "in_inventory": bool(ph["in_inventory"]),
                "in_lot_data": bool(ph["in_lot_data"]),
                "in_2025status": bool(ph["in_2025status"]),
                "phase_confidence": ph["source_confidence"],
                "collateral": collateral,
                "vf_unattributed_shell_dollars": float(range_d["dollars"]),
                "vf_unattributed_shell_rows": int(range_d["rows"]),
                "vf_unattributed_shell_note": "Range-form GL postings (e.g. '3001-06') that span multiple lots; kept at project+phase grain. Excluded from per-lot rollup. Source-owner sign-off needed to expand to per-lot synthetic rows.",
                "lots": lot_dicts,
            })

        cost = proj_actuals.get(cp, {})
        # Commercial parcels (Harmony only)
        commercial_pads = []
        for (cp_k, pad), d in commercial_rows_by_proj_pad.items():
            if cp_k == cp:
                commercial_pads.append({
                    "pad": pad,
                    "rows": d["rows"],
                    "dollars": d["dollars"],
                    "treatment": "non-lot inventory; commercial parcel; not modeled as residential lot in v2.1",
                })

        projects_out.append({
            "canonical_project": cp,
            "canonical_entity": "BCPD",
            "phase_count": len(phases_out),
            "lot_count": int(proj_lots.shape[0]),
            "lot_count_active_2025status": int(((st["Project"] == cp) & st["Lot"].notna() &
                                                  (st["HorzCustomer"] == "BCP")).sum()),
            "actuals": cost,
            "commercial_parcels_non_lot": commercial_pads,
            "phases": phases_out,
        })

    payload = {
        "schema_version": "operating_state_v2_1_bcpd",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "supersedes": "operating_state_v2_bcpd (additive — v2.0 not modified)",
        "metadata": {
            "as_of_date_inventory": "2026-04-29",
            "as_of_date_collateral": "2025-12-31",
            "as_of_date_collateral_prior": "2025-06-30",
            "as_of_date_gl_max": "2025-12-31",
            "entities_in_scope": ["BCPD", "BCPBL", "ASD", "BCPI"],
            "entity_filter_applied": "GL: entity_name='Building Construction Partners, LLC'; Lot Data/2025Status: HorzCustomer='BCP'",
            "ontology_version": "v0",
            "field_map_version": "v0",
            "decoder_version": "vf_lot_code_decoder_v1 (inferred; not source-owner-validated)",
            "guardrail_status": "GREEN — see data/reports/guardrail_check_v0.md (v0 baseline) and data/reports/join_coverage_simulation_v1.md (v2.1 simulation)",
            "join_key_policy": "3-tuple (canonical_project, canonical_phase, canonical_lot_number) for VF in decoder scope; 2-tuple for DR (no DR phase signal); never flat 2-tuple for Harmony cost rollups (would double-count $6.75M).",
        },
        "v2_1_changes_summary": {
            "aultf_b_to_b1_correction": {
                "rows": 1499, "dollars": 4006662.0,
                "description": "AultF B-suffix lots (0127B-0211B) now route to B1 (was B2 in v0). Empirically AultF and PWFS2 B-suffix lot ranges are disjoint.",
                "evidence": "scratch/vf_decoder_gl_finance_review.md Q2",
                "confidence": "inferred (high-evidence)",
            },
            "harmony_3tuple_join_required": {
                "double_count_prevented": 6750000.0,
                "description": "Harmony joins use (project, phase, lot) 3-tuple. Flat (project, lot) would collapse MF1 lot 101 and B1 lot 101 onto the same inventory row.",
                "evidence": "scratch/vf_decoder_gl_finance_review.md Q1+Q3",
                "confidence": "inferred (high-evidence)",
            },
            "harmco_split": {
                "residential_rows": 169,
                "commercial_rows": 205,
                "description": "HarmCo split: residential A01-B10 → MF2; X-X commercial parcels (A-A through K-K) → non-lot inventory exception. Commercial pads NOT modeled as residential LotState in v2.1.",
                "evidence": "scratch/vf_decoder_ops_allocation_review.md Q2",
                "confidence": "inferred (high-evidence on residential; ontology pending for commercial)",
            },
            "sctlot_to_scattered_lots": {
                "rows_moved": int(sctlot_rows["rows"]),
                "dollars_moved_off_scarlet_ridge": float(sctlot_rows["dollars"]),
                "description": "SctLot is now a separate canonical project 'Scattered Lots'. v0 silently inflated Scarlet Ridge's project-grain cost by ~46%.",
                "evidence": "scratch/vf_decoder_gl_finance_review.md Q4",
                "confidence": "inferred-unknown (canonical name not source-owner-validated)",
            },
            "range_rows_at_project_phase_grain": {
                "rows": int(sum(d["rows"] for d in range_rows_by_proj_phase.values())),
                "dollars": float(sum(d["dollars"] for d in range_rows_by_proj_phase.values())),
                "description": "Range-form lots ('3001-06', '0009-12', etc.) kept at project+phase grain. Surfaced as `vf_unattributed_shell_dollars` per phase. NOT expanded to per-lot synthetic rows in v2.1.",
                "evidence": "scratch/vf_decoder_gl_finance_review.md Q5",
                "confidence": "inferred (high-evidence on interpretation; allocation method pending)",
            },
            "aultf_sr_isolated": {
                "rows": int(sr_rows["rows"]),
                "dollars": float(sr_rows["dollars"]),
                "description": "AultF SR-suffix lots (0139SR, 0140SR) isolated as inferred-unknown; not attached to lot-level cost in v2.1.",
                "evidence": "scratch/vf_decoder_ops_allocation_review.md Q1",
                "confidence": "inferred-unknown",
            },
        },
        "data_quality": {
            "lots_total_in_canonical": int(total_lots),
            "lots_high_confidence": int(total_high),
            "lots_medium_confidence": int(total_med),
            "lots_low_confidence": int(total_low),
            "join_coverage_inventory_base": n_inv,
            "join_coverage_with_gl": n_inv_gl,
            "join_coverage_with_clickup": n_inv_ck,
            "join_coverage_full_triangle": n_tri,
            "join_coverage_pct_gl": round(n_inv_gl / max(n_inv, 1) * 100, 1),
            "join_coverage_pct_clickup": round(n_inv_ck / max(n_inv, 1) * 100, 1),
            "join_coverage_pct_triangle": round(n_tri / max(n_inv, 1) * 100, 1),
            "vf_decoded_3tuple_match_rows": len(vf_3t_match),
            "datarails_38col_dedup_applied": True,
            "datarails_38col_multiplicity": 2.16,
            "datarails_38col_post_dedup_rows": int(len(dr_d)),
            "vertical_financials_46col_rows": int(len(vf)),
            "qb_register_12col_treatment": "tie-out only; excluded from primary rollups",
            "v0_baseline_comparison": {
                "v0_join_coverage_pct_gl": 63.0,
                "v0_join_coverage_pct_triangle": 37.0,
                "v2_1_join_coverage_pct_gl": round(n_inv_gl / max(n_inv, 1) * 100, 1),
                "v2_1_join_coverage_pct_triangle": round(n_tri / max(n_inv, 1) * 100, 1),
                "binary_coverage_lift_modest_note": "Binary coverage delta is modest (+3.6pp GL); the larger v2.1 wins are correctness-not-coverage: $4M re-routed, $6.75M double-count avoided, $6.55M un-inflated, $45.75M shell costs surfaced explicitly.",
            },
        },
        "caveats": [
            "Org-wide v2 is blocked: Hillcrest, Flagship Belmont have GL only through 2017-02. v2.1 remains BCPD-only.",
            "GL gap 2017-03 → 2018-06 (~15 months, zero rows for any entity). Pre-2018 BCPD cost = DR-dedup 2016-02 → 2017-02 only.",
            "DataRails 38-col is 2.16× row-multiplied; build pipeline deduplicates before any cost rollup. Raw v2 parquet preserved unchanged.",
            "Vertical Financials 46-col is one-sided (asset-side debit only). Use as primary cost basis, not as a balanced trial-balance.",
            "QB register uses different chart of accounts (zero overlap with VF/DR). Tie-out only; never aggregate against VF.",
            "Phase grain is unsupported in GL (0% phase fill in DR/VF/QB). Phase rollups derive from the v1 decoder + inventory + Lot Data + 2025Status + ClickUp.",
            "VF lot-code decoder rules ship `confidence='inferred'` and `validated_by_source_owner=False`. Source-owner sign-off required before promotion.",
            "Harmony cost rollups require the 3-tuple (project, phase, lot) join key. A flat (project, lot) join would silently double-count $6.75M (MF1 lot 101 collides with B1 lot 101).",
            "AultF B-suffix lots route to B1 (corrected from v0's B2). $4.0M moved.",
            "SctLot → 'Scattered Lots' canonical project. $6.55M no longer inflates Scarlet Ridge but project-grain only — no lot-level inventory feed exists for these scattered/custom lots.",
            "AultF SR-suffix lots (0139SR, 0140SR; 401 rows) isolated as inferred-unknown until source owner explains. Not in lot-level cost.",
            "HarmCo X-X commercial parcels (205 rows) treated as non-lot inventory exception. NOT modeled as residential LotState. New ontology entity (CommercialParcel) deferred to v0.2.",
            "Range-form GL rows (4,020 rows / $45.75M across 8 VF codes) kept at project+phase grain via `vf_unattributed_shell_dollars`. Not expanded to per-lot. Equal-split expansion is a v0.2 candidate pending allocation-method sign-off.",
            "Lewis Estates (34 lots) and 7 active no-GL projects (Ammon, Cedar Glen, Eagle Vista, Eastbridge, Erda, Ironton, Santaquin Estates, Westbridge) remain structural gaps. No decoder helps; needs new data.",
            "Inventory file selection (workbook 2 vs 4) unchanged from v2.0. Confirm intent if 'newest' was the requirement.",
        ],
        "source_owner_questions_open": [
            "Harm3 lot-range routing — confirm phase is recoverable only via lot range, no source-system attribute we missed.",
            "AultF SR-suffix meaning ('0139SR', '0140SR'; 401 rows / 2 lots).",
            "AultF B-suffix overlap 201-211 — confirm B1 max lot.",
            "MF1 vs B1 overlap 101-116 — sample 5-10 Harm3 rows in this range to confirm they are SFR/B1, not MF1 leakage.",
            "SctLot canonical name and program identity (currently 'Scattered Lots').",
            "Range-entry allocation method (equal split vs sales-weighted vs unit-fixed) before per-lot expansion.",
            "HarmCo X-X commercial parcels — which allocation source covers Harmony commercial? (Currently outside Flagship Allocation Workbook.)",
            "DR 38-col phase recovery — is there a source-system attribute we missed for pre-2018 lots?",
        ],
        "projects": projects_out,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[v2.1] wrote {OUT} ({OUT.stat().st_size:,} B)")
    print(f"[v2.1] projects in body: {len(projects_out)}; lots in body: {total_lots:,}")
    print(f"[v2.1] join coverage: GL={n_inv_gl}/{n_inv} ({n_inv_gl/n_inv*100:.1f}%); triangle={n_tri}/{n_inv} ({n_tri/n_inv*100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
