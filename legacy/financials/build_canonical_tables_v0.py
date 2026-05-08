"""
Build canonical entity tables under data/staged/canonical_*.{csv,parquet}.

These are the v0 normalized entity tables — one row per canonical instance
of (legal_entity, project, phase, lot, account, cost_category) with
source_confidence (worst-link rule applied).

Scope: BCPD-first. Non-BCPD legal entities appear in canonical_legal_entity
but their projects/phases/lots are not enumerated (out of v0 scope).
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
STAGED = REPO / "data/staged"
GL_PARQUET = STAGED / "staged_gl_transactions_v2.parquet"
INV_PARQUET = STAGED / "staged_inventory_lots.parquet"
CK_PARQUET = STAGED / "staged_clickup_tasks.parquet"
LOT_DATA_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
               "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv"
STATUS_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
             "Collateral Dec2025 01 Claude.xlsx - 2025Status.csv"

CONF_RANK = {"high": 3, "medium": 2, "low": 1, "unmapped": 0}


def _worst(*confs: str) -> str:
    """Return the lowest-confidence value (worst-link)."""
    vals = [c for c in confs if c]
    if not vals:
        return "unmapped"
    return min(vals, key=lambda c: CONF_RANK.get(c, 0))


def write_pair(df: pd.DataFrame, name: str):
    csv_p = STAGED / f"{name}.csv"
    pq_p  = STAGED / f"{name}.parquet"
    # Coerce object cols to string to avoid pyarrow type errors
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).where(df[c].notna(), None)
    df.to_csv(csv_p, index=False)
    df.to_parquet(pq_p, index=False)
    return csv_p, pq_p


def build_canonical_project() -> pd.DataFrame:
    proj_xwalk = pd.read_csv(STAGED / "staged_project_crosswalk_v0.csv")
    bcpd_xw = proj_xwalk[proj_xwalk["canonical_entity"] == "BCPD"].copy()
    canon_names = sorted(set(bcpd_xw["canonical_project"].dropna()) - {""})
    rows = []
    inv = pd.read_parquet(INV_PARQUET)
    ld = pd.read_csv(LOT_DATA_CSV)
    st = pd.read_csv(STATUS_CSV, header=2)
    gl = pd.read_parquet(GL_PARQUET)
    bcpd_gl = gl[gl["entity_name"] == "Building Construction Partners, LLC"]

    for cname in canon_names:
        # Track presence in each source
        in_inventory = (inv["canonical_project"] == cname).any()
        in_lotdata   = (ld["Project"] == cname).any()
        in_status    = (st["Project"] == cname).any()
        # GL coverage by source — does any project_code map to this canonical?
        proj_codes_gl = bcpd_xw[(bcpd_xw["canonical_project"] == cname) &
                                 (bcpd_xw["source_system"].str.startswith("gl_v2"))][
                                 "source_value"].tolist()
        gl_rows = bcpd_gl[bcpd_gl["project_code"].isin(proj_codes_gl)]
        in_gl_dr  = (gl_rows["source_schema"] == "datarails_38col").any() if len(gl_rows) else False
        in_gl_vf  = (gl_rows["source_schema"] == "vertical_financials_46col").any() if len(gl_rows) else False
        n_gl_rows = len(gl_rows)
        # Lot count from 2025Status
        n_lots_status = int(((st["Project"] == cname) & st["Lot"].notna()).sum())
        n_lots_inv = int(((inv["canonical_project"] == cname) & inv["lot_num"].notna() &
                          (inv["lot_num"] != "")).sum())
        # Confidence: high if appears in 2+ ops sources OR (1 ops + GL)
        ops_count = sum([in_inventory, in_lotdata, in_status])
        gl_count  = sum([in_gl_dr, in_gl_vf])
        conf = "high" if (ops_count >= 2 or (ops_count >= 1 and gl_count >= 1)) else \
               "medium" if (ops_count >= 1 or gl_count >= 1) else "low"
        rows.append({
            "canonical_project": cname,
            "canonical_entity": "BCPD",
            "in_inventory": in_inventory,
            "in_lot_data": in_lotdata,
            "in_2025status": in_status,
            "in_gl_dr_38col": in_gl_dr,
            "in_gl_vf_46col": in_gl_vf,
            "gl_row_count": n_gl_rows,
            "lot_count_2025status": n_lots_status,
            "lot_count_inventory": n_lots_inv,
            "source_confidence": conf,
        })
    return pd.DataFrame(rows).sort_values("canonical_project").reset_index(drop=True)


def build_canonical_phase() -> pd.DataFrame:
    """One row per (canonical_entity, canonical_project, canonical_phase) appearing in any source."""
    rows = {}
    inv = pd.read_parquet(INV_PARQUET)
    ld = pd.read_csv(LOT_DATA_CSV)
    st = pd.read_csv(STATUS_CSV, header=2)

    def add(proj, phase, src):
        proj = str(proj).strip()
        phase = str(phase).strip()
        if not proj or not phase or proj.lower()=="nan" or phase.lower()=="nan":
            return
        key = (proj, phase)
        if key not in rows:
            rows[key] = {"canonical_entity":"BCPD",
                         "canonical_project":proj,
                         "canonical_phase":phase,
                         "in_inventory":False, "in_lot_data":False,
                         "in_2025status":False, "lot_count":0}
        rows[key][src] = True

    for _, r in inv.dropna(subset=["canonical_project","phase"]).iterrows():
        if r["phase"] != "":
            add(r["canonical_project"], r["phase"], "in_inventory")
    for _, r in ld.dropna(subset=["Project","Phase"]).iterrows():
        add(r["Project"], r["Phase"], "in_lot_data")
    for _, r in st.dropna(subset=["Project","Phase"]).iterrows():
        add(r["Project"], r["Phase"], "in_2025status")

    # lot_count from 2025Status
    st_keyed = st.dropna(subset=["Project","Phase","Lot"])
    pc = st_keyed.groupby(["Project","Phase"]).size().to_dict()
    for k, v in pc.items():
        if k in rows:
            rows[k]["lot_count"] = v

    df = pd.DataFrame(list(rows.values()))
    df["source_count"] = df[["in_inventory","in_lot_data","in_2025status"]].sum(axis=1)
    df["source_confidence"] = df["source_count"].map(
        lambda n: "high" if n >= 2 else "medium" if n == 1 else "low")
    df = df.sort_values(["canonical_project","canonical_phase"]).reset_index(drop=True)
    return df


def build_canonical_lot() -> pd.DataFrame:
    """One row per (canonical_project, canonical_phase, canonical_lot_number) for BCPD scope.

    Source confidence = worst-link of (project_xwalk_conf, phase_xwalk_conf, lot_source_conf).
    """
    inv = pd.read_parquet(INV_PARQUET)
    ld = pd.read_csv(LOT_DATA_CSV)
    st = pd.read_csv(STATUS_CSV, header=2)

    rows = {}

    # Inventory rows (active + closed)
    inv_keyed = inv[(inv["canonical_project"].notna() & (inv["canonical_project"] != "")) &
                    inv["lot_num"].notna() & (inv["lot_num"] != "") &
                    inv["phase"].notna() & (inv["phase"] != "")]
    for _, r in inv_keyed.iterrows():
        key = (r["canonical_project"], str(r["phase"]).strip(), str(r["lot_num"]).strip())
        if key not in rows:
            rows[key] = {"canonical_lot_id": r["canonical_lot_id"],
                         "canonical_entity": "BCPD",
                         "canonical_project": key[0],
                         "canonical_phase": key[1],
                         "canonical_lot_number": key[2],
                         "in_inventory": False, "in_lot_data": False,
                         "in_2025status": False,
                         "lot_status": None, "horz_customer": None,
                         "horz_seller": None,
                         "project_confidence": r["project_confidence"]}
        rows[key]["in_inventory"] = True
        rows[key]["lot_status"] = r["lot_status"]

    # Lot Data
    for _, r in ld.dropna(subset=["Project","Phase","LotNo."]).iterrows():
        key = (str(r["Project"]).strip(), str(r["Phase"]).strip(), str(r["LotNo."]).strip())
        if key not in rows:
            rows[key] = {"canonical_lot_id": "",
                         "canonical_entity": "BCPD",
                         "canonical_project": key[0],
                         "canonical_phase": key[1],
                         "canonical_lot_number": key[2],
                         "in_inventory": False, "in_lot_data": False,
                         "in_2025status": False,
                         "lot_status": None,
                         "horz_customer": str(r.get("HorzCustomer","")) or None,
                         "horz_seller": str(r.get("HorzSeller","")) or None,
                         "project_confidence": "high"}
        rows[key]["in_lot_data"] = True
        if rows[key]["horz_seller"] in (None, "", "nan"):
            rows[key]["horz_seller"] = str(r.get("HorzSeller","")) or None
        if rows[key]["horz_customer"] in (None, "", "nan"):
            rows[key]["horz_customer"] = str(r.get("HorzCustomer","")) or None

    # 2025Status
    for _, r in st.dropna(subset=["Project","Phase","Lot"]).iterrows():
        key = (str(r["Project"]).strip(), str(r["Phase"]).strip(), str(r["Lot"]).strip())
        if key not in rows:
            rows[key] = {"canonical_lot_id":"",
                         "canonical_entity":"BCPD",
                         "canonical_project":key[0],
                         "canonical_phase":key[1],
                         "canonical_lot_number":key[2],
                         "in_inventory":False, "in_lot_data":False,
                         "in_2025status":False,
                         "lot_status":None,
                         "horz_customer":str(r.get("HorzCustomer","")) or None,
                         "horz_seller":None,
                         "project_confidence":"high"}
        rows[key]["in_2025status"] = True
        if rows[key]["horz_customer"] in (None, "", "nan"):
            rows[key]["horz_customer"] = str(r.get("HorzCustomer","")) or None

    # Compute canonical_lot_id where missing
    def lot_id(proj, phase, lot):
        return hashlib.blake2s(f"{proj}|{phase}|{lot}".encode(), digest_size=8).hexdigest()

    df = pd.DataFrame(list(rows.values()))
    mask = df["canonical_lot_id"].isna() | (df["canonical_lot_id"] == "")
    df.loc[mask, "canonical_lot_id"] = df.loc[mask].apply(
        lambda r: lot_id(r["canonical_project"], r["canonical_phase"], r["canonical_lot_number"]),
        axis=1)

    # Filter to BCPD-relevant lots: in_lot_data with HorzCustomer=BCP, OR in inventory
    # (allowing historical BCPD-built lots), OR in 2025Status with HorzCustomer=BCP
    bcpd_mask = (
        (df["in_lot_data"] & (df["horz_customer"].astype(str) == "BCP")) |
        (df["in_2025status"] & (df["horz_customer"].astype(str) == "BCP")) |
        df["in_inventory"]
    )
    df["bcpd_scope"] = bcpd_mask

    # source_count + source_confidence
    df["source_count"] = df[["in_inventory","in_lot_data","in_2025status"]].sum(axis=1)
    df["source_confidence"] = df.apply(
        lambda r: _worst(r["project_confidence"],
                         "high" if r["source_count"] >= 2 else "medium" if r["source_count"] == 1 else "low"),
        axis=1)
    return df.sort_values(["canonical_project","canonical_phase","canonical_lot_number"]).reset_index(drop=True)


def build_canonical_account() -> pd.DataFrame:
    gl = pd.read_parquet(GL_PARQUET)
    rows = []
    for src in sorted(gl["source_schema"].dropna().unique()):
        sub = gl[gl["source_schema"] == src]
        agg = sub.groupby(["account_code"]).agg(
            account_name=("account_name", lambda s: s.dropna().value_counts().index[0]
                          if s.dropna().size else ""),
            account_type=("account_type", lambda s: s.dropna().value_counts().index[0]
                          if s.dropna().size else ""),
            account_group=("account_group", lambda s: s.dropna().value_counts().index[0]
                           if s.dropna().size else ""),
            row_count=("amount", "count"),
            sum_amount=("amount", "sum"),
        ).reset_index()
        agg["source_schema"] = src
        rows.append(agg)
    df = pd.concat(rows, ignore_index=True)
    # Confidence
    df["source_confidence"] = df["source_schema"].map({
        "datarails_38col": "high",
        "vertical_financials_46col": "high",
        "qb_register_12col": "medium",
    }).fillna("low")
    return df.sort_values(["source_schema","account_code"]).reset_index(drop=True)


def build_canonical_cost_category() -> pd.DataFrame:
    """v0 cost-category mapping. Uses v1 COST_TO_DATE_COMPONENTS (horizontal-only)
    plus the vertical components from VF account names. Mapping is rule-based
    on (source_schema, account_code → category)."""
    rows = [
        # Horizontal — v1 spec (Lomond / Parkway-style allocation alignment)
        {"category_code": "PERMITS_FEES", "category_name": "Permits and Fees",
         "cost_phase_bucket": "HORIZONTAL", "matches_status_column": "Permits and Fees",
         "vf_account_codes": "1535", "dr_account_codes": "(varies — Permits accounts in legacy chart)",
         "is_actual_only": False, "source_confidence": "high"},
        {"category_code": "DIRECT_CONSTRUCTION_LOT", "category_name": "Direct Construction - Lot",
         "cost_phase_bucket": "HORIZONTAL", "matches_status_column": "Direct Construction - Lot",
         "vf_account_codes": "1547", "dr_account_codes": "(varies)",
         "is_actual_only": False, "source_confidence": "high"},
        {"category_code": "SHARED_COST_ALLOC", "category_name": "Shared Cost Alloc.",
         "cost_phase_bucket": "HORIZONTAL", "matches_status_column": "Shared Cost Alloc.",
         "vf_account_codes": "(none — derived in 2025Status)", "dr_account_codes": "(varies)",
         "is_actual_only": True, "source_confidence": "medium"},
        # Vertical
        {"category_code": "DIRECT_CONSTRUCTION_VERTICAL", "category_name": "Direct Construction (Vertical)",
         "cost_phase_bucket": "VERTICAL", "matches_status_column": "Direct Construction",
         "vf_account_codes": "1540", "dr_account_codes": "(varies)",
         "is_actual_only": False, "source_confidence": "medium",
         "notes": "VF account 1540 is Direct Construction (full); 2025Status 'Direct Construction' mixes vertical+horizontal"},
        {"category_code": "VERTICAL_COSTS", "category_name": "Vertical Costs (rolled up)",
         "cost_phase_bucket": "VERTICAL", "matches_status_column": "Vertical Costs",
         "vf_account_codes": "(rollup)", "dr_account_codes": "n/a",
         "is_actual_only": True, "source_confidence": "medium"},
        # Composite
        {"category_code": "LOT_COST_TOTAL", "category_name": "Lot Cost (total — horizontal + vertical)",
         "cost_phase_bucket": "TOTAL", "matches_status_column": "Lot Cost",
         "vf_account_codes": "1535+1540+1547", "dr_account_codes": "n/a",
         "is_actual_only": True, "source_confidence": "high"},
        # Indirect / other
        {"category_code": "INDIRECTS", "category_name": "Indirects (allocation pools)",
         "cost_phase_bucket": "OVERHEAD", "matches_status_column": "(allocation only)",
         "vf_account_codes": "(allocation)", "dr_account_codes": "n/a",
         "is_actual_only": False, "source_confidence": "low",
         "notes": "from Flagship/LH/PF allocation workbooks; varies by community"},
        {"category_code": "LAND_ACQUISITION", "category_name": "Land Acquisition",
         "cost_phase_bucket": "PRE_DEVELOPMENT", "matches_status_column": "(allocation only)",
         "vf_account_codes": "n/a", "dr_account_codes": "(varies — land accounts)",
         "is_actual_only": False, "source_confidence": "low"},
        {"category_code": "INTEREST_EXPENSE", "category_name": "Interest Expense",
         "cost_phase_bucket": "FINANCING", "matches_status_column": "n/a",
         "vf_account_codes": "n/a", "dr_account_codes": "(varies)",
         "is_actual_only": True, "source_confidence": "low"},
    ]
    return pd.DataFrame(rows)


def main() -> int:
    # Already wrote canonical_legal_entity from build_crosswalks_v0
    le = pd.read_parquet(STAGED / "canonical_legal_entity.parquet")
    print(f"[canonical] legal_entity rows: {len(le)}")

    proj = build_canonical_project()
    write_pair(proj, "canonical_project")
    print(f"[canonical] project rows: {len(proj)}")
    print(proj.to_string())

    phase = build_canonical_phase()
    write_pair(phase, "canonical_phase")
    print(f"[canonical] phase rows: {len(phase)}")

    lot = build_canonical_lot()
    write_pair(lot, "canonical_lot")
    print(f"[canonical] lot rows: {len(lot)} ; bcpd_scope rows: {int(lot['bcpd_scope'].sum())}")

    acct = build_canonical_account()
    write_pair(acct, "canonical_account")
    print(f"[canonical] account rows: {len(acct)}")

    cc = build_canonical_cost_category()
    # add notes col where missing
    if "notes" not in cc.columns:
        cc["notes"] = ""
    cc["notes"] = cc["notes"].fillna("")
    write_pair(cc, "canonical_cost_category")
    print(f"[canonical] cost_category rows: {len(cc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
