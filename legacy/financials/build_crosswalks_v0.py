"""
Build v0 entity / project / phase / lot crosswalks.

Outputs (under data/staged/):
  staged_entity_crosswalk_v0.{csv,parquet}
  staged_project_crosswalk_v0.{csv,parquet}
  staged_phase_crosswalk_v0.{csv,parquet}
  staged_lot_crosswalk_v0.{csv,parquet}
  staged_entity_project_crosswalk_v0.{csv,parquet}  # combined, BCPD-scoped, satisfies guardrail #2

Each table carries: source_system, source_value, canonical_value, confidence, evidence_file, notes.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
STAGED = REPO / "data/staged"
GL_PARQUET = STAGED / "staged_gl_transactions_v2.parquet"
INV_PARQUET = STAGED / "staged_inventory_lots.parquet"
CLICKUP_PARQUET = STAGED / "staged_clickup_tasks.parquet"
LOT_DATA_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
               "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv"
STATUS_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
             "Collateral Dec2025 01 Claude.xlsx - 2025Status.csv"
COLLATERAL_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
                 "Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv"


# -----------------------------------------------------------------
# Canonical entity / project authority list
# -----------------------------------------------------------------

# Canonical entity codes (BCPD = vertical builder; horizontal entities differ)
ENTITY_AUTHORITY = [
    {"canonical_entity": "BCPD",                "long_name": "Building Construction Partners, LLC",
     "role": "vertical builder + horizontal developer (BCPD subset)", "in_scope": True},
    {"canonical_entity": "BCPBL",               "long_name": "BCP Ben Lomond (Lomond Heights horizontal)",
     "role": "horizontal developer", "in_scope": True},
    {"canonical_entity": "ASD",                 "long_name": "Arrowhead Springs Developer",
     "role": "horizontal developer", "in_scope": True},
    {"canonical_entity": "BCPI",                "long_name": "BCP Investor",
     "role": "horizontal developer (small)", "in_scope": True},
    {"canonical_entity": "Hillcrest",           "long_name": "Hillcrest Road at Saratoga, LLC",
     "role": "legacy entity (frozen 2017-02)", "in_scope": False},
    {"canonical_entity": "Flagship Belmont",    "long_name": "Flagship Belmont Phase two LLC",
     "role": "legacy entity (frozen 2017-02)", "in_scope": False},
    {"canonical_entity": "Lennar",              "long_name": "Lennar (third-party builder customer)",
     "role": "vertical builder customer", "in_scope": False},
    {"canonical_entity": "EXT",                 "long_name": "External / commercial / church (mixed)",
     "role": "non-BCP customer types", "in_scope": False},
]

# -----------------------------------------------------------------
# Project crosswalks — SOURCE_VALUE → CANONICAL_PROJECT
# -----------------------------------------------------------------

# 2025Status / Lot Data — already canonical (these are the 16 BCPD-active projects)
STATUS_PROJECTS = [
    "Ammon", "Arrowhead Springs", "Cedar Glen", "Eagle Vista", "Eastbridge",
    "Erda", "Harmony", "Ironton", "Lewis Estates", "Lomond Heights",
    "Parkway Fields", "Salem Fields", "Santaquin Estates", "Scarlet Ridge",
    "Westbridge", "Willowcreek",
]
# Plus Meadow Creek which appears in Collateral Report but not in 2025Status
COLLATERAL_EXTRA = ["Meadow Creek"]

# GL DataRails 38-col (BCPD subset — pre-2018 communities + Silver Lake era)
DR38_TO_CANONICAL = {
    "3AHptn": ("Hamptons",                "high"),
    "Bdgprt": ("Bridgeport",              "high"),
    "BeckP":  ("Beck Pines",              "high"),
    "Blmont": ("Belmont Plaza",           "high"),  # non-BCPD entity
    "CottFH": ("Cottages at Fox Hollow",  "high"),
    "Cscade": ("Cascade",                 "high"),
    "HIllcr": ("Hillcrest",               "high"),  # non-BCPD entity
    "HllcrM": ("Hillcrest",               "high"),
    "HllcrN": ("Hillcrest",               "high"),
    "HllcrO": ("Hillcrest",               "high"),
    "HllcrP": ("Hillcrest",               "high"),
    "HllcrQ": ("Hillcrest",               "high"),
    "HllcrR": ("Hillcrest",               "high"),
    "HllcrS": ("Hillcrest",               "high"),
    "LeChem": ("LeCheminant",             "high"),
    "Miller": ("Miller Estates",          "high"),
    "Prksde": ("Parkside",                "high"),
    "SL14C":  ("Silver Lake",             "high"),
    "SL14S":  ("Silver Lake",             "high"),
    "SilvTh": ("Silver Lake",             "high"),  # SL14T → "Silver Towns"
    "SL15C":  ("Silver Lake",             "high"),
    "SL15S":  ("Silver Lake",             "high"),
    "SL15T":  ("Silver Lake",             "high"),
    "SilvLk": ("Silver Lake",             "high"),
    "SprCls": ("The Springs Cluster",     "high"),
    "Spring": ("The Springs",             "high"),
    "SprnCk": ("Spring Creek Ranch",      "high"),
    "Vintar": ("Villages at Vintaro",     "high"),
    "WIllis": ("Willis",                  "high"),
    "Westbk": ("Westbrook",               "high"),
    "WhtRl":  ("White Rail",              "high"),
    "Willws": ("Willows",                 "high"),
}

# GL Vertical Financials 46-col (BCPD subset, 2018-2025)
VF46_TO_CANONICAL = {
    "ArroS1": ("Arrowhead Springs",  "high"),
    "ArroT1": ("Arrowhead Springs",  "high"),
    "AultF":  ("Parkway Fields",     "high"),  # Ault Farms aka Parkway Fields
    "Harm3":  ("Harmony",            "high"),
    "HarmCo": ("Harmony",            "high"),  # Commercial
    "HarmTo": ("Harmony",            "high"),  # Townhomes
    "LomHS1": ("Lomond Heights",     "high"),
    "LomHT1": ("Lomond Heights",     "high"),
    "MCreek": ("Meadow Creek",       "high"),
    "PWFS2":  ("Parkway Fields",     "high"),
    "PWFT1":  ("Parkway Fields",     "high"),
    "SalemS": ("Salem Fields",       "high"),
    "SaleTR": ("Salem Fields",       "high"),
    "SaleTT": ("Salem Fields",       "high"),
    "ScaRdg": ("Scarlet Ridge",      "high"),
    "SctLot": ("Scarlet Ridge",      "medium"),  # "Scarlet Lot" — name unclear
    "WilCrk": ("Willowcreek",        "high"),
}

# Inventory subdiv → canonical (mirrors stage_inventory_lots.SUBDIV_TO_PROJECT)
INV_SUBDIV_TO_CANONICAL = {
    "HARMONY":         ("Harmony",            "high"),
    "PARKWAY":         ("Parkway Fields",     "high"),
    "LOMOND HEIGHTS":  ("Lomond Heights",     "high"),
    "WILLOW CREEK":    ("Willowcreek",        "high"),
    "SALEM":           ("Salem Fields",       "high"),
    "LEWIS ESTATES":   ("Lewis Estates",      "high"),
    "SCARLET RIDGE":   ("Scarlet Ridge",      "high"),
    "ARROWHEAD":       ("Arrowhead Springs",  "high"),
    "SL":              ("Silver Lake",        "low"),
    # Historicals from CLOSED tab
    "LEC":             ("LeCheminant",        "medium"),  # confidence: probable
    "WILLOWS":         ("Willows",            "high"),
    "HAMPTON":         ("Hamptons",           "high"),
    "BRIDGEPORT":      ("Bridgeport",         "high"),
    "WESTBROOK":       ("Westbrook",          "high"),
    "SPRINGS":         ("The Springs",        "medium"),
    "WINDSOR":         ("Windsor",            "low"),  # not in v1 master
    "BECK PINES":      ("Beck Pines",         "high"),
    "CASCADE":         ("Cascade",            "high"),
    "JAMES BAY":       ("James Bay",          "low"),
    "WILLIS":          ("Willis",             "high"),
    "MAPLE FIELDS":    ("Maple Fields",       "low"),
    "MEADOW CREEK":    ("Meadow Creek",       "high"),
    "PARKSIDE":        ("Parkside",           "high"),
    "COUNTRY VIEW":    ("Country View",       "low"),
    "F. SPRINGS":      ("F. Springs",         "low"),
    "SPRING LEAF":     ("Spring Leaf",        "low"),
    "ANTHEM WEST":     ("Anthem West",        "low"),
    "VINTARO":         ("Villages at Vintaro","high"),
    "WR":              ("White Rail",         "medium"),  # WR = White Rail
    "SPEC":            ("",                   "unmapped"),  # generic spec marker
    "MIDWAY":          ("Midway",             "low"),
    "ML":              ("",                   "unmapped"),
    "TO BE":           ("",                   "unmapped"),
}

# ClickUp subdivision → canonical
CLICKUP_SUBDIVISION_TO_CANONICAL = {
    "Harmony":          ("Harmony",            "high"),
    "Arrowhead":        ("Arrowhead Springs",  "high"),
    "Aarowhead":        ("Arrowhead Springs",  "medium"),  # typo
    "Aarrowhead":       ("Arrowhead Springs",  "medium"),  # typo
    "Park Way":         ("Parkway Fields",     "high"),
    "Lomond Heights":   ("Lomond Heights",     "high"),
    "Salem Fields":     ("Salem Fields",       "high"),
    "Willow Creek":     ("Willowcreek",        "high"),
    "Lewis Estates":    ("Lewis Estates",      "high"),
    "Scarlett Ridge":   ("Scarlet Ridge",      "medium"),  # typo
    "P2 14":            ("",                   "unmapped"),  # likely Harmony Phase A Plat 14
}

# QB register entity hint (from filename)
QB_ENTITY_HINT = ("Building Construction Partners, LLC", "BCPD", "high")


def write_pair(df: pd.DataFrame, name: str) -> tuple[Path, Path]:
    csv_p = STAGED / f"{name}.csv"
    pq_p  = STAGED / f"{name}.parquet"
    df.to_csv(csv_p, index=False)
    df.to_parquet(pq_p, index=False)
    return csv_p, pq_p


def build_entity_crosswalk() -> pd.DataFrame:
    rows = []
    # GL entity_name canonical mappings
    for ent, can in [
        ("Building Construction Partners, LLC", "BCPD"),
        ("Hillcrest Road at Saratoga, LLC",     "Hillcrest"),
        ("Flagship Belmont Phase two LLC",      "Flagship Belmont"),
    ]:
        rows.append({"source_system": "gl_v2.entity_name", "source_value": ent,
                     "canonical_entity": can, "confidence": "high",
                     "evidence_file": "data/staged/staged_gl_transactions_v2.parquet",
                     "notes": "company_code = 1000 for BCPD; other entities via DataRails CompanyCode"})
    # 2025Status HorzCustomer
    for src, can, conf, note in [
        ("BCP",      "BCPD",   "high",   "vertical-builder customer; matches GL 'Building Construction Partners, LLC'"),
        ("Lennar",   "Lennar", "high",   "third-party builder; out of BCPD v2 scope"),
        ("EXT",      "EXT",    "low",    "small external category"),
        ("EXT-Comm", "EXT",    "low",    "external commercial"),
        ("Church",   "EXT",    "low",    "single church lot"),
    ]:
        rows.append({"source_system": "2025Status.HorzCustomer", "source_value": src,
                     "canonical_entity": can, "confidence": conf,
                     "evidence_file": "Collateral Dec2025 01 Claude.xlsx - 2025Status.csv",
                     "notes": note})
    # Lot Data HorzSeller
    for src, can, conf in [
        ("BCPD",  "BCPD",  "high"),
        ("BCPBL", "BCPBL", "high"),
        ("ASD",   "ASD",   "high"),
        ("BCPI",  "BCPI",  "medium"),
    ]:
        rows.append({"source_system": "LotData.HorzSeller", "source_value": src,
                     "canonical_entity": can, "confidence": conf,
                     "evidence_file": "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv",
                     "notes": "horizontal-developer entity"})
    # QB register (single-entity by filename)
    rows.append({"source_system": "qb_register_12col.source_file",
                 "source_value": "Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv",
                 "canonical_entity": "BCPD", "confidence": "high",
                 "evidence_file": "data/staged/staged_gl_transactions_v2.parquet",
                 "notes": "filename + content scope confirm single-entity BCPD"})
    df = pd.DataFrame(rows)
    return df


def build_project_crosswalk() -> pd.DataFrame:
    rows = []
    # 2025Status / Lot Data — identity mapping (already canonical)
    for p in STATUS_PROJECTS:
        rows.append({"source_system": "2025Status.Project", "source_value": p,
                     "canonical_project": p, "canonical_entity": "BCPD",
                     "confidence": "high",
                     "evidence_file": "Collateral Dec2025 01 Claude.xlsx - 2025Status.csv",
                     "notes": "identity mapping; canonical name already used"})
        rows.append({"source_system": "LotData.Project", "source_value": p,
                     "canonical_project": p, "canonical_entity": "BCPD",
                     "confidence": "high",
                     "evidence_file": "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv",
                     "notes": "identity mapping"})
    # Collateral Report — adds Meadow Creek (not in 2025Status)
    for p in STATUS_PROJECTS + COLLATERAL_EXTRA:
        rows.append({"source_system": "CollateralReport.Project", "source_value": p,
                     "canonical_project": p, "canonical_entity": "BCPD",
                     "confidence": "high",
                     "evidence_file": "Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv",
                     "notes": "Meadow Creek not in 2025Status — partial gap"})
    # GL DR 38-col
    for code, (canon, conf) in DR38_TO_CANONICAL.items():
        # Determine canonical_entity: BCPD codes vs Hillcrest / Flagship Belmont codes
        if code in ("HIllcr","HllcrM","HllcrN","HllcrO","HllcrP","HllcrQ","HllcrR","HllcrS"):
            ce = "Hillcrest"
        elif code == "Blmont":
            ce = "Flagship Belmont"
        else:
            ce = "BCPD"
        rows.append({"source_system": "gl_v2.datarails_38col.project_code",
                     "source_value": code, "canonical_project": canon,
                     "canonical_entity": ce, "confidence": conf,
                     "evidence_file": "data/staged/staged_gl_transactions_v2.parquet",
                     "notes": "pre-2018 era code; Silver Lake variants collapse to a single canonical project"})
    # GL VF 46-col (all BCPD)
    for code, (canon, conf) in VF46_TO_CANONICAL.items():
        rows.append({"source_system": "gl_v2.vertical_financials_46col.project_code",
                     "source_value": code, "canonical_project": canon,
                     "canonical_entity": "BCPD", "confidence": conf,
                     "evidence_file": "data/staged/staged_gl_transactions_v2.parquet",
                     "notes": "2018-2025 era code; product-type variants (S1/T1/S2/T2/Co/To) collapse to one project"})
    # Inventory
    for sub, (canon, conf) in INV_SUBDIV_TO_CANONICAL.items():
        rows.append({"source_system": "inventory.subdiv", "source_value": sub,
                     "canonical_project": canon, "canonical_entity": "BCPD" if conf in ("high","medium") and canon else "BCPD",
                     "confidence": conf,
                     "evidence_file": "data/staged/staged_inventory_lots.parquet",
                     "notes": "INVENTORY + CLOSED  union; SL/Silver Lake is historical not in v1 master"})
    # ClickUp
    for sub, (canon, conf) in CLICKUP_SUBDIVISION_TO_CANONICAL.items():
        rows.append({"source_system": "clickup.subdivision", "source_value": sub,
                     "canonical_project": canon, "canonical_entity": "BCPD",
                     "confidence": conf,
                     "evidence_file": "data/staged/staged_clickup_tasks.parquet",
                     "notes": "lot-tagged subset only; typos flagged"})
    df = pd.DataFrame(rows)
    return df


def build_phase_crosswalk(proj_xwalk: pd.DataFrame) -> pd.DataFrame:
    """Phase crosswalk: enumerate every (canonical_project, raw_phase) seen in
    each source. The canonical phase rule is whitespace-normalize per
    pipelines/config.py normalize_phase, and emit a `(canonical_project, canonical_phase)` pair.
    """
    rows = []

    # Inventory phases
    inv = pd.read_parquet(INV_PARQUET)
    inv = inv[inv["canonical_project"].notna() & (inv["canonical_project"] != "")]
    inv = inv[inv["phase"].notna() & (inv["phase"] != "")]
    for (cp, raw_p), g in inv.groupby(["canonical_project", "phase"]):
        rows.append({"source_system": "inventory.phase",
                     "source_value": f"{cp}::{raw_p}",
                     "raw_phase": raw_p, "canonical_project": cp,
                     "canonical_phase": str(raw_p).strip(),
                     "occurrence_count": len(g),
                     "confidence": "high" if cp in STATUS_PROJECTS + COLLATERAL_EXTRA else "low",
                     "evidence_file": "data/staged/staged_inventory_lots.parquet",
                     "notes": ""})
    # Lot Data phases
    ld = pd.read_csv(LOT_DATA_CSV)
    for (proj, raw_p), g in ld.dropna(subset=["Project","Phase"]).groupby(["Project","Phase"]):
        rows.append({"source_system": "LotData.Phase",
                     "source_value": f"{proj}::{raw_p}",
                     "raw_phase": str(raw_p), "canonical_project": str(proj),
                     "canonical_phase": str(raw_p).strip(),
                     "occurrence_count": len(g),
                     "confidence": "high",
                     "evidence_file": "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv",
                     "notes": ""})
    # 2025Status phases
    st = pd.read_csv(STATUS_CSV, header=2)
    for (proj, raw_p), g in st.dropna(subset=["Project","Phase"]).groupby(["Project","Phase"]):
        rows.append({"source_system": "2025Status.Phase",
                     "source_value": f"{proj}::{raw_p}",
                     "raw_phase": str(raw_p), "canonical_project": str(proj),
                     "canonical_phase": str(raw_p).strip(),
                     "occurrence_count": len(g),
                     "confidence": "high",
                     "evidence_file": "Collateral Dec2025 01 Claude.xlsx - 2025Status.csv",
                     "notes": ""})
    # ClickUp phases (only within lot-tagged subset)
    ck = pd.read_parquet(CLICKUP_PARQUET)
    ck_tag = ck[ck["subdivision"].notna() & ck["lot_num"].notna()].copy()
    ck_tag["canonical_project"] = ck_tag["subdivision"].map(
        lambda v: CLICKUP_SUBDIVISION_TO_CANONICAL.get(v, ("",""))[0]
    )
    ck_tag = ck_tag[ck_tag["canonical_project"] != ""]
    for (cp, raw_p), g in ck_tag.dropna(subset=["phase"]).groupby(["canonical_project","phase"]):
        rows.append({"source_system": "clickup.phase",
                     "source_value": f"{cp}::{raw_p}",
                     "raw_phase": str(raw_p), "canonical_project": cp,
                     "canonical_phase": str(raw_p).strip(),
                     "occurrence_count": len(g),
                     "confidence": "medium",  # ClickUp phase fill is sparse
                     "evidence_file": "data/staged/staged_clickup_tasks.parquet",
                     "notes": ""})
    df = pd.DataFrame(rows)
    return df


def build_lot_crosswalk(proj_xwalk: pd.DataFrame) -> pd.DataFrame:
    """Lot-level crosswalk: enumerate the population by source.

    For BCPD scope:
      - inventory.{subdiv,phase,lot_num} → canonical_lot_id
      - LotData.{Project,Phase,LotNo.}
      - 2025Status.{Project,Phase,Lot}
      - clickup.{subdivision,phase,lot_num}
      - GL VF 46-col {project_code → canonical, lot}  (BCPD-only)
      - GL DR 38-col {project_code → canonical, lot}  (BCPD-only, partial)
    """
    rows = []

    # Inventory
    inv = pd.read_parquet(INV_PARQUET)
    inv = inv[inv["canonical_project"].notna() & (inv["canonical_project"] != "") &
              inv["phase"].notna() & (inv["phase"] != "") &
              inv["lot_num"].notna() & (inv["lot_num"] != "")]
    for _, r in inv.iterrows():
        rows.append({
            "source_system": "inventory",
            "source_key": f"{r['subdiv']}::{r['phase']}::{r['lot_num']}",
            "raw_subdiv": r["subdiv"], "raw_phase": r["phase"], "raw_lot": r["lot_num"],
            "canonical_entity": "BCPD",
            "canonical_project": r["canonical_project"],
            "canonical_phase": str(r["phase"]).strip(),
            "canonical_lot_number": str(r["lot_num"]).strip(),
            "canonical_lot_id": r["canonical_lot_id"],
            "confidence": "high" if r["project_confidence"] == "high" else r["project_confidence"],
            "evidence_file": "data/staged/staged_inventory_lots.parquet",
        })

    # Lot Data
    ld = pd.read_csv(LOT_DATA_CSV)
    ld = ld.dropna(subset=["Project","Phase","LotNo."])
    for _, r in ld.iterrows():
        rows.append({
            "source_system": "LotData",
            "source_key": f"{r['Project']}::{r['Phase']}::{r['LotNo.']}",
            "raw_subdiv": r["Project"], "raw_phase": str(r["Phase"]), "raw_lot": str(r["LotNo."]),
            "canonical_entity": "BCPD",  # all 16 BCPD-active projects
            "canonical_project": str(r["Project"]),
            "canonical_phase": str(r["Phase"]).strip(),
            "canonical_lot_number": str(r["LotNo."]).strip(),
            "canonical_lot_id": "",  # filled in below
            "confidence": "high",
            "evidence_file": "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv",
        })

    # 2025Status
    st = pd.read_csv(STATUS_CSV, header=2)
    st = st.dropna(subset=["Project","Phase","Lot"])
    for _, r in st.iterrows():
        rows.append({
            "source_system": "2025Status",
            "source_key": f"{r['Project']}::{r['Phase']}::{r['Lot']}",
            "raw_subdiv": r["Project"], "raw_phase": str(r["Phase"]), "raw_lot": str(r["Lot"]),
            "canonical_entity": "BCPD" if str(r.get("HorzCustomer","")) == "BCP" else "EXT",
            "canonical_project": str(r["Project"]),
            "canonical_phase": str(r["Phase"]).strip(),
            "canonical_lot_number": str(r["Lot"]).strip(),
            "canonical_lot_id": "",
            "confidence": "high",
            "evidence_file": "Collateral Dec2025 01 Claude.xlsx - 2025Status.csv",
        })

    # ClickUp lot-tagged
    ck = pd.read_parquet(CLICKUP_PARQUET)
    ck_tag = ck[ck["subdivision"].notna() & ck["lot_num"].notna()].copy()
    for _, r in ck_tag.iterrows():
        canon, conf = CLICKUP_SUBDIVISION_TO_CANONICAL.get(r["subdivision"], ("","unmapped"))
        if not canon:
            continue
        rows.append({
            "source_system": "clickup",
            "source_key": f"{r['subdivision']}::{r.get('phase') or ''}::{r['lot_num']}",
            "raw_subdiv": r["subdivision"], "raw_phase": str(r.get("phase") or ""),
            "raw_lot": str(r["lot_num"]),
            "canonical_entity": "BCPD",
            "canonical_project": canon,
            "canonical_phase": str(r.get("phase") or "").strip(),
            "canonical_lot_number": str(r["lot_num"]).strip(),
            "canonical_lot_id": "",
            "confidence": conf,
            "evidence_file": "data/staged/staged_clickup_tasks.parquet",
        })

    # GL VF 46-col (BCPD)
    gl = pd.read_parquet(GL_PARQUET)
    bcpd_vf = gl[(gl["entity_name"]=="Building Construction Partners, LLC") &
                 (gl["source_schema"]=="vertical_financials_46col") &
                 (gl["lot"].notna())].copy()
    bcpd_vf["lot_str"] = bcpd_vf["lot"].astype(str).str.strip()
    bcpd_vf = bcpd_vf[bcpd_vf["lot_str"] != ""]
    triples = bcpd_vf.groupby(["project_code","lot_str"]).size().reset_index(name="rows")
    for _, r in triples.iterrows():
        canon_proj, conf = VF46_TO_CANONICAL.get(r["project_code"], ("", "unmapped"))
        if not canon_proj:
            continue
        rows.append({
            "source_system": "gl_v2.vertical_financials_46col",
            "source_key": f"{r['project_code']}::::{r['lot_str']}",
            "raw_subdiv": r["project_code"], "raw_phase": "", "raw_lot": r["lot_str"],
            "canonical_entity": "BCPD",
            "canonical_project": canon_proj,
            "canonical_phase": "",
            "canonical_lot_number": r["lot_str"],
            "canonical_lot_id": "",
            "confidence": conf,
            "evidence_file": "data/staged/staged_gl_transactions_v2.parquet",
        })

    # GL DR 38-col (BCPD only — pre-2018)
    bcpd_dr = gl[(gl["entity_name"]=="Building Construction Partners, LLC") &
                 (gl["source_schema"]=="datarails_38col") &
                 (gl["lot"].notna())].copy()
    bcpd_dr["lot_str"] = bcpd_dr["lot"].astype(str).str.strip()
    bcpd_dr = bcpd_dr[bcpd_dr["lot_str"] != ""]
    triples_dr = bcpd_dr.groupby(["project_code","lot_str"]).size().reset_index(name="rows")
    for _, r in triples_dr.iterrows():
        canon_proj, conf = DR38_TO_CANONICAL.get(r["project_code"], ("", "unmapped"))
        if not canon_proj:
            continue
        rows.append({
            "source_system": "gl_v2.datarails_38col",
            "source_key": f"{r['project_code']}::::{r['lot_str']}",
            "raw_subdiv": r["project_code"], "raw_phase": "", "raw_lot": r["lot_str"],
            "canonical_entity": "BCPD",
            "canonical_project": canon_proj,
            "canonical_phase": "",
            "canonical_lot_number": r["lot_str"],
            "canonical_lot_id": "",
            "confidence": conf,
            "evidence_file": "data/staged/staged_gl_transactions_v2.parquet",
        })

    df = pd.DataFrame(rows)
    # Compute canonical_lot_id consistently for non-inventory sources
    import hashlib
    def lot_id(r):
        if r["canonical_lot_id"]:
            return r["canonical_lot_id"]
        parts = [str(r["canonical_project"]), str(r["canonical_phase"]),
                 str(r["canonical_lot_number"])]
        return hashlib.blake2s("|".join(parts).encode(), digest_size=8).hexdigest()
    df["canonical_lot_id"] = df.apply(lot_id, axis=1)
    return df


def main() -> int:
    # Entity authority
    ent_auth = pd.DataFrame(ENTITY_AUTHORITY)
    csv_p, pq_p = write_pair(ent_auth, "canonical_legal_entity")
    print(f"[xwalk] wrote canonical_legal_entity: {csv_p.stat().st_size:,} B / {pq_p.stat().st_size:,} B")

    ent_xwalk = build_entity_crosswalk()
    csv_p, pq_p = write_pair(ent_xwalk, "staged_entity_crosswalk_v0")
    print(f"[xwalk] entity crosswalk rows: {len(ent_xwalk)}")

    proj_xwalk = build_project_crosswalk()
    csv_p, pq_p = write_pair(proj_xwalk, "staged_project_crosswalk_v0")
    print(f"[xwalk] project crosswalk rows: {len(proj_xwalk)}")

    # Phase
    phase_xwalk = build_phase_crosswalk(proj_xwalk)
    # Coerce all to strings to avoid mixed-type parquet errors
    for c in phase_xwalk.columns:
        if phase_xwalk[c].dtype == object:
            phase_xwalk[c] = phase_xwalk[c].astype(str)
    csv_p, pq_p = write_pair(phase_xwalk, "staged_phase_crosswalk_v0")
    print(f"[xwalk] phase crosswalk rows: {len(phase_xwalk)}")

    # Lot
    lot_xwalk = build_lot_crosswalk(proj_xwalk)
    for c in lot_xwalk.columns:
        if lot_xwalk[c].dtype == object:
            lot_xwalk[c] = lot_xwalk[c].astype(str)
    csv_p, pq_p = write_pair(lot_xwalk, "staged_lot_crosswalk_v0")
    print(f"[xwalk] lot crosswalk rows: {len(lot_xwalk)}")

    # Combined entity-project crosswalk (BCPD-scoped) — guardrail satisfier
    combo = proj_xwalk[proj_xwalk["canonical_entity"] == "BCPD"].copy()
    combo = combo.reset_index(drop=True)
    csv_p, pq_p = write_pair(combo, "staged_entity_project_crosswalk_v0")
    print(f"[xwalk] entity_project (BCPD) crosswalk rows: {len(combo)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
