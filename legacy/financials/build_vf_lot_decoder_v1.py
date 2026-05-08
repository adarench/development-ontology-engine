"""
W1.5 — Revised VF lot-code decoder, applying findings from:
  scratch/vf_decoder_gl_finance_review.md  (Terminal B)
  scratch/vf_decoder_ops_allocation_review.md  (Terminal C)

Required changes (per A_integrator instructions):
1. AultF B-suffix → B1 (was B2). PWFS2 B-suffix stays at B2.
2. Harmony: require (project, phase, lot) 3-tuple join — flat (project, lot) double-counts $6.75M.
3. HarmCo split: residential A01-B10 → MF2 (inferred); X-X parcels → non-lot inventory (inferred-unknown).
4. SctLot canonical_project = "Scattered Lots" (not Scarlet Ridge); inferred-unknown.
5. Range entries: keep at project+phase grain; do not expand. v1 v0-treatment.
6. Lomond Heights: confirmed 2A SFR (101-171) + 2A TH (172-215); routing unchanged.

Plus: validation harness rebuilt to preserve alpha lots so MF2 (A01-A10, B01-B10) match.

Outputs:
  data/staged/vf_lot_code_decoder_v1.csv
  data/reports/vf_lot_code_decoder_v1_report.md

Confidence stays `inferred` for every rule. None promoted to source-owner-validated.
No modifications to staged_gl_transactions_v2 or any v2 output.
"""
from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
STAGED = REPO / "data/staged"
REPORTS = REPO / "data/reports"

GL_PARQUET = STAGED / "staged_gl_transactions_v2.parquet"
INV_PARQUET = STAGED / "staged_inventory_lots.parquet"
LOT_DATA_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
               "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv"
STATUS_CSV = REPO / "data/raw/datarails_unzipped/phase_cost_starter" / \
             "Collateral Dec2025 01 Claude.xlsx - 2025Status.csv"

# In-scope VF project codes.
# Note: Per Terminal B Q5, range entries exist in MCreek, SaleTT, SaleTR,
# WilCrk too — those are not in the W1 phase-decoder scope (their lot strings
# don't need phase decoding) but their range rows DO need flagging. We profile
# them separately in the "all VF projects with range rows" section.
VF_TO_CANONICAL = {
    "Harm3":  "Harmony",
    "HarmCo_residential": "Harmony",      # virtual code: numeric-suffix subset of HarmCo
    "HarmCo_commercial":  "Harmony",      # virtual code: X-X subset of HarmCo
    "HarmTo": "Harmony",
    "LomHS1": "Lomond Heights",
    "LomHT1": "Lomond Heights",
    "PWFS2":  "Parkway Fields",
    "PWFT1":  "Parkway Fields",
    "AultF":  "Parkway Fields",
    "ArroS1": "Arrowhead Springs",
    "ArroT1": "Arrowhead Springs",
    "ScaRdg": "Scarlet Ridge",
    "SctLot": "Scattered Lots",  # CHANGED in v1 per Terminal B Q4
}

# Phase normalization between Lot Data and inventory
PHASE_INV_TO_LD = {
    ("Lomond Heights", "2-A"): "2A",
    ("Arrowhead Springs", "1,2,3"): "123",
    ("Arrowhead Springs", "4,5,6"): "456",
    ("Harmony", "MF 1"): "MF1",
    ("Harmony", "14"): "ADB14",
    ("Harmony", "10"): "A10",
    ("Harmony", "9"): "A9",
    ("Harmony", "8"): "A8",
}


def norm_lot(s) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def lot_int(s: str):
    """Return integer lot number from a normalized lot string (numeric prefix only), or None."""
    if not s:
        return None
    m = re.match(r"^0*(\d+)", s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def lot_canonical(s: str) -> str:
    """Preserve alpha-only lots (e.g. 'A01') as-is; numeric → int-stripped."""
    if not s:
        return ""
    s = str(s).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if s.isdigit():
        return str(int(s))
    return s


def is_range_lot(lot_str: str) -> bool:
    """4-digit-NN-2or3digit pattern: e.g. '0009-12', '0172-175', '3001-06'."""
    if not lot_str or "-" not in lot_str:
        return False
    return bool(re.match(r"^\d{4}-\d{2,3}$", lot_str))


# ----------------------------------------------------------------------
# Decoder rules (v1)
# ----------------------------------------------------------------------

def decode_harm3(lot_str: str):
    """Harmony Harm3 — phase routed by lot-number range (Lot Data ranges).
    Phase is NOT encoded elsewhere (per Terminal B Q1). Downstream joins MUST use
    the (project, phase, lot) 3-tuple — flat (project, lot) joins double-count $6.75M.
    """
    if is_range_lot(lot_str):
        return ("RANGE", None, lot_str, "range entry — keep at project+phase grain")
    n = lot_int(lot_str)
    if n is None:
        return (None, None, None, "no integer lot")
    if 1 <= n <= 100:    return ("MF1",   "MF1", str(n), "")
    if 101 <= n <= 192:  return ("B1",    "B1",  str(n), "")
    if 201 <= n <= 271:  return ("B2",    "B2",  str(n), "")
    if 301 <= n <= 347:  return ("B3",    "B3",  str(n), "")
    if 453 <= n <= 454:  return ("A4.1",  "A4.1",str(n), "")
    if 701 <= n <= 749:  return ("A7",    "A7",  str(n), "")
    if 801 <= n <= 848:  return ("A8",    "A8",  str(n), "")
    if 901 <= n <= 950:  return ("A9",    "A9",  str(n), "")
    if 1001 <= n <= 1044:return ("A10",   "A10", str(n), "")
    if 1301 <= n <= 1334:return ("ADB13", "ADB13", str(n), "")
    if 1401 <= n <= 1438:return ("ADB14", "ADB14", str(n), "")
    return (None, None, str(n), "out of known Lot Data ranges")


def decode_harmco_residential(lot_str: str):
    """HarmCo residential subset — `0000<X><NN>` where X∈A-B, NN∈01-10 → Harmony MF2 lot `<X><NN>`.
    Per Terminal C Q2, MF2 has 20 lots A01-A10 + B01-B10. v0 validation harness dropped them.
    """
    s = lot_str
    if len(s) != 7 or not s.startswith("0000"):
        return (None, None, None, "not 0000-prefixed 7-char")
    rest = s[4:]
    if re.match(r"^[AB]\d{2}$", rest):
        return ("MF2_RESIDENTIAL", "MF2", rest, "")
    return (None, None, None, "not residential MF2 form")


def decode_harmco_commercial(lot_str: str):
    """HarmCo commercial parcels — `0000<X>-<X>` where X∈A-K → Harmony commercial pad `<X>`.
    NOT in Lot Data / inventory / allocation. Treat as non-lot inventory.
    """
    s = lot_str
    if len(s) != 7 or not s.startswith("0000"):
        return (None, None, None, "not 0000-prefixed 7-char")
    rest = s[4:]
    if re.match(r"^[A-K]-[A-K]$", rest):
        return ("COMMERCIAL_PAD", None, rest[0],
                "non-lot inventory; commercial parcel; no phase/lot in master")
    return (None, None, None, "not commercial X-X form")


def decode_harmto(lot_str: str):
    """Harmony Townhomes — single 4-digit lot → MF1; range → keep at phase grain."""
    if is_range_lot(lot_str):
        return ("RANGE", "MF1", lot_str, "range entry — shared-shell allocation")
    n = lot_int(lot_str)
    if n is None: return (None, None, None, "no integer")
    if 1 <= n <= 116:
        return ("MF1", "MF1", str(n), "")
    return (None, None, str(n), "outside MF1 range 1-116")


def decode_lomhs1(lot_str: str):
    """Lomond Heights LomHS1 — phase 2A (SFR product-type subset 101-171)."""
    if is_range_lot(lot_str):
        return ("RANGE", "2A", lot_str, "range entry")
    n = lot_int(lot_str)
    if n is None: return (None, None, None, "no integer")
    if 101 <= n <= 215:
        return ("2A", "2A", str(n), "")
    return (None, None, str(n), "outside 2A range")


def decode_lomht1(lot_str: str):
    """Lomond Heights LomHT1 — phase 2A (TH product-type subset 172-215). Many rows are range entries (shell allocations)."""
    if is_range_lot(lot_str):
        return ("RANGE", "2A", lot_str, "range entry — shared shell")
    n = lot_int(lot_str)
    if n is None: return (None, None, None, "no integer")
    if 101 <= n <= 215:
        return ("2A", "2A", str(n), "")
    return (None, None, str(n), "outside 2A range")


def decode_pwfs2(lot_str: str):
    """Parkway PWFS2 — 4-digit numeric → D1/D2/G1/G2 by lot range; 5-digit B-suffix → B2."""
    s = lot_str
    if is_range_lot(s):
        return ("RANGE", None, s, "range entry")
    if len(s) == 5 and s.endswith("B"):
        n = lot_int(s)
        if n is None: return (None, None, None, "no integer in NNNNB")
        if 201 <= n <= 323:
            return ("B2", "B2", str(n), "")
        return (None, None, str(n), "B-suffix outside B2 range")
    n = lot_int(s)
    if n is None: return (None, None, None, "no integer")
    if 4001 <= n <= 4159:  return ("D1", "D1", str(n), "")
    if 4160 <= n <= 4199:  return (None, None, str(n), "between D1 and D2 ranges; gap")
    if 4201 <= n <= 4282:  return ("D2", "D2", str(n), "")
    if 4283 <= n <= 4499:  return (None, None, str(n), "outside Lot Data D2 (4201-4282)")
    if 7001 <= n <= 7065:  return ("G1", "G1", str(n), "")
    if 7065 <= n <= 7209:  return ("G2", "G2", str(n), "")
    return (None, None, str(n), "outside known PWFS2 ranges")


def decode_pwft1(lot_str: str):
    """Parkway PWFT1 — 4-digit 3xxx → C1 or C2; range → keep at phase grain."""
    if is_range_lot(lot_str):
        return ("RANGE", None, lot_str, "range entry — shared shell")
    n = lot_int(lot_str)
    if n is None: return (None, None, None, "no integer")
    if 3001 <= n <= 3116:  return ("C1", "C1", str(n), "")
    if 3117 <= n <= 3235:  return ("C2", "C2", str(n), "")
    return (None, None, str(n), "outside C1/C2 ranges")


def decode_aultf(lot_str: str):
    """AultF (Parkway Fields E-1, Ault Farms) — 5-digit NNNNX with letter suffix.
    REVISED v1: A-suffix → A1/A2.x by range; B-suffix → B1 (was B2 in v0; corrected per Terminal B Q2).
    SR-suffix → inferred-unknown (per Terminal C Q1).
    """
    s = lot_str
    if is_range_lot(s):
        return ("RANGE", None, s, "range entry")
    if len(s) == 6 and s.endswith("SR"):
        return ("SR_INFERRED_UNKNOWN", None, s,
                "SR suffix; meaning unknown; routes to lot 139/140 in inferred phase, flag phase_inferred=True")
    if len(s) >= 5:
        suffix = s[-1]
        n = lot_int(s)
        if n is None: return (None, None, s, "no integer prefix")
        if suffix == "A":
            if 101 <= n <= 169:    return ("A1",   "A1",   str(n), "")
            if 201 <= n <= 236:    return ("A2.1", "A2.1", str(n), "")
            if 237 <= n <= 281:    return ("A2.2", "A2.2", str(n), "")
            if 282 <= n <= 343:    return ("A2.3", "A2.3", str(n), "")
            return (None, None, str(n), "A-suffix outside A1/A2.* ranges")
        if suffix == "B":
            # CORRECTED v1: AultF B-suffix → B1 (was B2 in v0; Terminal B Q2)
            if 101 <= n <= 211:    return ("B1", "B1", str(n), "")
            return (None, None, str(n), "B-suffix outside B1 range 101-211 (AultF should not carry B2)")
    n = lot_int(s)
    if n is None: return (None, None, s, "no integer")
    return (None, None, s, "unknown AultF subform")


def decode_arros1(lot_str: str):
    if is_range_lot(lot_str):
        return ("RANGE", None, lot_str, "range entry")
    n = lot_int(lot_str)
    if n is None: return (None, None, None, "no integer")
    if 1 <= n <= 129:    return ("123", "123", str(n), "")
    if 130 <= n <= 207:  return ("456", "456", str(n), "")
    return (None, None, str(n), "outside 123/456 ranges")


def decode_arrot1(lot_str: str):
    if is_range_lot(lot_str):
        return ("RANGE", None, lot_str, "range entry — shared shell")
    n = lot_int(lot_str)
    if n is None: return (None, None, None, "no integer")
    if 1 <= n <= 129:    return ("123", "123", str(n), "")
    if 130 <= n <= 207:  return ("456", "456", str(n), "")
    return (None, None, str(n), "outside known ranges")


def decode_scardg(lot_str: str):
    if is_range_lot(lot_str):
        return ("RANGE", None, lot_str, "range entry")
    n = lot_int(lot_str)
    if n is None: return (None, None, None, "no integer")
    if 101 <= n <= 152:  return ("1", "1", str(n), "")
    if 201 <= n <= 260:  return ("2", "2", str(n), "")
    if 301 <= n <= 364:  return ("3", "3", str(n), "")
    return (None, None, str(n), "outside known phase ranges")


def decode_sctlot(lot_str: str):
    """SctLot → 'Scattered Lots' canonical project. No phase decoder; project-grain only."""
    n = lot_int(lot_str)
    return ("PROJECT_GRAIN_ONLY", None, str(n) if n is not None else lot_str,
            "scattered/custom lots; no master-plan phase; project-grain rollup only")


# Map raw VF project_code → list of (rule_name, decoder_fn). HarmCo splits into 2.
DECODERS = [
    ("Harm3",  "harmony_lot_range_to_phase",       decode_harm3,  "Harm3"),
    ("HarmCo", "harmony_mf2_residential",          decode_harmco_residential,  "HarmCo_residential"),
    ("HarmCo", "harmony_commercial_pad_nonlot",    decode_harmco_commercial,   "HarmCo_commercial"),
    ("HarmTo", "harmony_townhome_mf1_only",        decode_harmto,  "HarmTo"),
    ("LomHS1", "lomondheights_sfr_phase_2a",       decode_lomhs1,  "LomHS1"),
    ("LomHT1", "lomondheights_th_phase_2a",        decode_lomht1,  "LomHT1"),
    ("PWFS2",  "parkway_sfr_phase2_range_route",   decode_pwfs2,   "PWFS2"),
    ("PWFT1",  "parkway_th_phase1_c1c2_route",     decode_pwft1,   "PWFT1"),
    ("AultF",  "aultf_suffix_a_b_phase_route_v1",  decode_aultf,   "AultF"),
    ("ArroS1", "arrowhead_sfr_123_456_route",      decode_arros1,  "ArroS1"),
    ("ArroT1", "arrowhead_th_123_456_route",       decode_arrot1,  "ArroT1"),
    ("ScaRdg", "scarletridge_lot_range_phase",     decode_scardg,  "ScaRdg"),
    ("SctLot", "sctlot_project_grain_only_v1",     decode_sctlot,  "SctLot"),
]


def main() -> int:
    print("[v1-decoder] loading sources...")
    gl = pd.read_parquet(GL_PARQUET)
    inv = pd.read_parquet(INV_PARQUET)
    ld = pd.read_csv(LOT_DATA_CSV)

    bcpd_vf = gl[(gl["entity_name"] == "Building Construction Partners, LLC") &
                 (gl["source_schema"] == "vertical_financials_46col")].copy()

    # Build Lot Data + inventory key sets, PRESERVING alpha lots (v1 fix)
    ld_keys = set()
    for _, r in ld.iterrows():
        proj = str(r.get("Project") or "").strip()
        phase = str(r.get("Phase") or "").strip()
        lot = lot_canonical(norm_lot(r.get("LotNo.")))
        if proj and phase and lot:
            ld_keys.add((proj, phase, lot))

    inv_keys = set()
    for _, r in inv.iterrows():
        proj = str(r.get("canonical_project") or "").strip()
        raw_phase = str(r.get("phase") or "").strip()
        lot = lot_canonical(str(r.get("lot_num") or "").strip())
        if not proj or not raw_phase or not lot:
            continue
        ld_phase = PHASE_INV_TO_LD.get((proj, raw_phase), raw_phase)
        inv_keys.add((proj, ld_phase, lot))
        inv_keys.add((proj, raw_phase, lot))

    # Apply decoder per virtual VF code
    decoder_rows = []
    per_virtual_detail = {}
    range_rows_by_proj = {}  # (canon, phase) → rows / dollars

    for raw_vf_code, rule_name, fn, virtual_code in DECODERS:
        canon = VF_TO_CANONICAL[virtual_code]
        sub = bcpd_vf[bcpd_vf["project_code"] == raw_vf_code].copy()

        # Filter to the subset this rule covers
        # For HarmCo we need to split based on lot pattern
        if virtual_code == "HarmCo_residential":
            sub = sub[sub["lot"].astype(str).str.match(r"^0000[AB]\d{2}$", na=False)]
        elif virtual_code == "HarmCo_commercial":
            sub = sub[sub["lot"].astype(str).str.match(r"^0000[A-K]-[A-K]$", na=False)]

        n_total = len(sub)
        n_decoded = 0
        n_match_inv = 0
        n_match_ld = 0
        n_decoded_unmatched = 0
        n_undecoded = 0
        n_range = 0
        range_dollars = 0.0
        n_commercial = 0
        commercial_dollars = 0.0
        n_sr = 0
        n_project_grain_only = 0
        unmatched_examples = []

        for _, r in sub.iterrows():
            raw = str(r["lot"]).strip() if pd.notna(r["lot"]) else ""
            amount = float(r.get("amount") or 0)
            tag, phase, lot_n, note = fn(raw)
            if tag == "RANGE":
                n_range += 1
                range_dollars += abs(amount)
                key = (canon, phase or "(unphased)")
                d = range_rows_by_proj.setdefault(key, {"rows": 0, "dollars": 0.0})
                d["rows"] += 1
                d["dollars"] += abs(amount)
                continue
            if tag == "COMMERCIAL_PAD":
                n_commercial += 1
                commercial_dollars += abs(amount)
                continue
            if tag == "SR_INFERRED_UNKNOWN":
                n_sr += 1
                continue
            if tag == "PROJECT_GRAIN_ONLY":
                n_project_grain_only += 1
                continue
            if phase and lot_n:
                n_decoded += 1
                if (canon, phase, lot_n) in inv_keys:
                    n_match_inv += 1
                if (canon, phase, lot_n) in ld_keys:
                    n_match_ld += 1
                if (canon, phase, lot_n) not in inv_keys and (canon, phase, lot_n) not in ld_keys:
                    n_decoded_unmatched += 1
                    if len(unmatched_examples) < 5:
                        unmatched_examples.append((raw, phase, lot_n))
            else:
                n_undecoded += 1

        # Effective denominator for match-rate: exclude the categories we
        # explicitly removed from lot-level matching (range / commercial / SR /
        # project-grain-only).
        n_lot_grain_eligible = n_total - n_range - n_commercial - n_sr - n_project_grain_only
        match_inv_rate = (n_match_inv / n_lot_grain_eligible * 100) if n_lot_grain_eligible else 0
        match_ld_rate = (n_match_ld / n_lot_grain_eligible * 100) if n_lot_grain_eligible else 0
        any_match_rate = (max(n_match_inv, n_match_ld) / n_lot_grain_eligible * 100) if n_lot_grain_eligible else 0

        if any_match_rate >= 90: quality = "high-evidence"
        elif any_match_rate >= 60: quality = "medium-evidence"
        elif any_match_rate >= 30: quality = "low-evidence"
        elif n_lot_grain_eligible == 0: quality = "non-lot-only"
        else: quality = "no-decoder"

        # Recommendation: which layer is this rule safe to feed?
        if virtual_code == "HarmCo_commercial":
            recommendation = "non-lot inventory only; do not feed lot-level cost"
        elif virtual_code == "SctLot":
            recommendation = "project-grain only; do not feed lot-level cost"
        elif quality == "high-evidence":
            recommendation = "safe for v2.1 simulation as inferred mapping"
        elif quality == "medium-evidence":
            recommendation = "safe for v2.1 simulation as inferred mapping; range rows excluded"
        elif quality == "low-evidence":
            recommendation = "simulation-only; project-grain-only for cost rollups"
        else:
            recommendation = "do not apply; investigate with source owner"

        decoder_rows.append({
            "vf_project_code": raw_vf_code,
            "virtual_code": virtual_code,
            "canonical_project": canon,
            "decoder_rule_name": rule_name,
            "decoder_pattern": fn.__doc__.strip().split("\n")[0] if fn.__doc__ else "",
            "rule_quality": quality,
            "confidence": "inferred",
            "rows_total": n_total,
            "rows_lot_grain_eligible": n_lot_grain_eligible,
            "rows_decoded_to_lot": n_decoded,
            "rows_undecoded": n_undecoded,
            "rows_range": n_range,
            "rows_commercial_nonlot": n_commercial,
            "rows_sr_inferred_unknown": n_sr,
            "rows_project_grain_only": n_project_grain_only,
            "rows_match_lot_data": n_match_ld,
            "rows_match_inventory": n_match_inv,
            "rows_decoded_but_unmatched": n_decoded_unmatched,
            "match_rate_lot_data_pct": round(match_ld_rate, 1),
            "match_rate_inventory_pct": round(match_inv_rate, 1),
            "match_rate_any_pct": round(any_match_rate, 1),
            "range_dollars_summary": round(range_dollars, 2),
            "commercial_dollars": round(commercial_dollars, 2),
            "recommendation": recommendation,
            "validated_by_source_owner": False,
            "notes": "",
        })
        per_virtual_detail[virtual_code] = {
            "unmatched_examples": unmatched_examples,
            "n_total": n_total,
            "n_lot_eligible": n_lot_grain_eligible,
            "n_range": n_range,
            "range_dollars": range_dollars,
            "n_commercial": n_commercial,
            "commercial_dollars": commercial_dollars,
            "n_sr": n_sr,
        }

    # Add rows for OTHER projects with range entries (per Terminal B Q5: MCreek, SaleTT, SaleTR, WilCrk also have ranges)
    additional_range_codes = ["MCreek", "SaleTT", "SaleTR", "WilCrk"]
    add_canonical = {"MCreek": "Meadow Creek", "SaleTT": "Salem Fields",
                     "SaleTR": "Salem Fields", "WilCrk": "Willowcreek"}
    for code in additional_range_codes:
        sub = bcpd_vf[bcpd_vf["project_code"] == code]
        n_total = len(sub)
        n_range = 0
        range_dollars = 0.0
        for _, r in sub.iterrows():
            raw = str(r["lot"]).strip() if pd.notna(r["lot"]) else ""
            if is_range_lot(raw):
                n_range += 1
                range_dollars += abs(float(r.get("amount") or 0))
        if n_range == 0:
            continue
        decoder_rows.append({
            "vf_project_code": code,
            "virtual_code": code,
            "canonical_project": add_canonical[code],
            "decoder_rule_name": "range_entry_passthrough",
            "decoder_pattern": "range entries kept at project+phase grain (no W1 phase decoder needed; v0 lot match was already 100%)",
            "rule_quality": "non-lot-only",
            "confidence": "inferred",
            "rows_total": n_total,
            "rows_lot_grain_eligible": n_total - n_range,
            "rows_decoded_to_lot": 0,
            "rows_undecoded": 0,
            "rows_range": n_range,
            "rows_commercial_nonlot": 0,
            "rows_sr_inferred_unknown": 0,
            "rows_project_grain_only": 0,
            "rows_match_lot_data": 0,
            "rows_match_inventory": 0,
            "rows_decoded_but_unmatched": 0,
            "match_rate_lot_data_pct": None,
            "match_rate_inventory_pct": None,
            "match_rate_any_pct": None,
            "range_dollars_summary": round(range_dollars, 2),
            "commercial_dollars": 0.0,
            "recommendation": "project+phase grain; do not feed lot-level cost; preserve dollars in summary rollup",
            "validated_by_source_owner": False,
            "notes": "added in v1 per Terminal B Q5 — these projects also carry range entries",
        })

    df = pd.DataFrame(decoder_rows)
    out_csv = STAGED / "vf_lot_code_decoder_v1.csv"
    df.to_csv(out_csv, index=False)
    print(f"[v1-decoder] wrote {out_csv}")

    # Summarize range $ across ALL projects
    total_range_rows = df["rows_range"].sum()
    total_range_dollars = df["range_dollars_summary"].sum()
    total_commercial_rows = df["rows_commercial_nonlot"].sum()
    total_commercial_dollars = df["commercial_dollars"].sum()

    # Build report
    md = []
    md.append("# VF Lot-Code Decoder v1 — Report\n\n")
    md.append("**Built**: 2026-05-01\n")
    md.append("**Owner**: Terminal A (W1.5 of BCPD State Quality Pass)\n")
    md.append("**Inputs**: W1 report + reviews from Terminal B (`scratch/vf_decoder_gl_finance_review.md`) and Terminal C (`scratch/vf_decoder_ops_allocation_review.md`)\n")
    md.append("**Output (lookup)**: `data/staged/vf_lot_code_decoder_v1.csv`\n\n")
    md.append("All rules ship `confidence='inferred'` with `validated_by_source_owner=False`.\n\n")
    md.append("---\n\n")
    md.append("## Changes from v0\n\n")
    md.append("### 1. AultF B-suffix correction (Terminal B Q2)\n\n")
    md.append("**Before (v0)**: AultF B-suffix lots routed to B2 with overlap caveat; this misclassified 1,499 rows / **$4.0M**.\n\n")
    md.append("**After (v1)**: AultF B-suffix → **B1** (entire 101-211 range). PWFS2 B-suffix continues to → B2 (273-323 range). Empirically, AultF and PWFS2 B-suffix lot ranges are disjoint (AultF max=211, PWFS2 min=273), so the routing is unambiguous in the actual GL data even though Lot Data shows overlap.\n\n")
    md.append("### 2. Harmony 3-tuple join requirement (Terminal B Q1, Q3)\n\n")
    md.append("Phase is not encoded in any GL field other than the lot-number range. Harm3 collapses 9+ Lot Data phases under one VF code; MF1 and B1 share lot numbers 101-116 in inventory. **Any downstream join MUST use `(canonical_project, canonical_phase, canonical_lot)`. A flat `(canonical_project, lot)` join double-counts $6.75M** ($1.4M MF1 + $5.3M B1 colliding on 16 inventory lots). The decoder rule is unchanged; the join-key requirement is now explicit.\n\n")
    md.append("### 3. HarmCo split (Terminal C Q2)\n\n")
    md.append("HarmCo's 374 rows split into two virtual codes:\n\n")
    md.append("- `HarmCo_residential` — 20 lots `0000A01`-`0000B10` → MF2 lots `A01`-`B10`. **Lot-grain mappable**, inferred. (v0's 0% match was a validation-harness artifact: the index dropped alpha lots.)\n")
    md.append("- `HarmCo_commercial` — 11 parcels `0000A-A` through `0000K-K` → Harmony commercial pad `<X>`. **Non-lot inventory**, no Lot Data row. Should NOT enter the canonical lot crosswalk's match-rate denominator.\n\n")
    md.append("### 4. SctLot canonical project change (Terminal B Q4)\n\n")
    md.append("**Before (v0)**: `canonical_project = 'Scarlet Ridge'`. This silently inflated Scarlet Ridge's project-grain cost by ~46% (+$6.55M / 1,130 rows).\n\n")
    md.append("**After (v1)**: `canonical_project = 'Scattered Lots'` (new inferred project). Evidence: zero lot-number overlap with ScaRdg; \"SctLot\" appears in invoice IDs (e.g. `Inv.:SctLot-000032-01:Turner Excavating`); vendor mix is custom-build / scattered-construction; multi-year history 2018-2025. SctLot rules feed project-grain rollups only. Confidence remains `inferred-unknown`.\n\n")
    md.append("### 5. Range entries — broader scope (Terminal B Q5)\n\n")
    md.append("Range-form lots (`NNNN-NN` or `NNNN-NNN`) appear in **8 VF project codes** (W1 only listed 3): HarmTo, LomHT1, PWFT1, ArroT1, plus MCreek, SaleTT, SaleTR, WilCrk that W1 considered out-of-scope. Total range exposure:\n\n")
    md.append(f"- **{total_range_rows:,} range rows** across all 8 codes\n")
    md.append(f"- **${total_range_dollars:,.2f}** of capitalized cost — ~13% of total VF cost basis\n\n")
    md.append("Treatment in v1: keep at **project+phase grain**, do NOT expand to per-lot synthetic rows, do NOT exclude. Memo evidence (`'shell allocation'`, design/engineering vendors, shared-infra accounts) plus per-row dollar magnitude (~$3-14K) confirms these are real shared-shell / shared-infrastructure costs. Equal-split expansion is a v2 candidate that requires source-owner sign-off on the allocation method.\n\n")
    md.append("### 6. Lomond Heights confirmed single-phase (Terminal C Q3)\n\n")
    md.append("LomHS1 (SFR, lots 101-171) and LomHT1 (TH, lots 172-215) both route to phase **2A**. The W1 routing was correct; the LomHT1 low match rate was range-entry noise, not a routing error. Product-type split (SFR vs TH) lives at the lot level via `Lot Data.ProdType`, not as a separate phase.\n\n")
    md.append("---\n\n")
    md.append("## Per-rule v1 results\n\n")
    md.append("| virtual code | canonical project | rule | rows total | lot-eligible | range | commercial | SR | project-grain | match% (any) | quality | recommendation |\n")
    md.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|\n")
    for r in decoder_rows:
        md.append(f"| {r['virtual_code']} | {r['canonical_project']} | `{r['decoder_rule_name']}` | "
                  f"{r['rows_total']:,} | {r['rows_lot_grain_eligible']:,} | {r['rows_range']:,} | "
                  f"{r['rows_commercial_nonlot']:,} | {r['rows_sr_inferred_unknown']:,} | "
                  f"{r['rows_project_grain_only']:,} | "
                  f"{r['match_rate_any_pct']}% | {r['rule_quality']} | {r['recommendation']} |\n")
    md.append("\n")

    md.append("---\n\n")
    md.append("## Range and non-lot summary\n\n")
    md.append(f"- **Range rows excluded from lot-level denominator**: {int(total_range_rows):,} rows, ${total_range_dollars:,.2f}\n")
    md.append(f"- **Commercial parcel rows (HarmCo X-X)**: {int(total_commercial_rows):,} rows, ${total_commercial_dollars:,.2f}\n")
    md.append("- **SR-suffix rows (AultF 0139SR/0140SR)**: 401 rows (per Terminal C Q1), inferred-unknown\n")
    md.append("- **SctLot project-grain-only rows**: 1,130 rows / $6.55M routing to canonical_project='Scattered Lots'\n\n")
    md.append("Range $ by canonical project (for project+phase grain rollup):\n\n")
    md.append("| canonical project | range rows | range $ |\n|---|---:|---:|\n")
    for r in sorted(decoder_rows, key=lambda x: -x["range_dollars_summary"]):
        if r["rows_range"] > 0:
            md.append(f"| {r['canonical_project']} ({r['vf_project_code']}) | {r['rows_range']:,} | ${r['range_dollars_summary']:,.2f} |\n")
    md.append("\n")

    md.append("---\n\n")
    md.append("## Per-rule pattern descriptions\n\n")
    for raw_code, rule_name, fn, vcode in DECODERS:
        md.append(f"**`{vcode}` — {rule_name}** (`canonical_project = {VF_TO_CANONICAL[vcode]}`)\n\n")
        if fn.__doc__:
            md.append(fn.__doc__.strip() + "\n\n")
    md.append("---\n\n")

    md.append("## Recommendation matrix (per A_integrator instructions)\n\n")
    md.append("| rule | safe for v2.1 simulation? | safe for v2.1 inferred mapping in lot-level cost? | safe for project/phase only? | requires source-owner validation? |\n|---|---|---|---|---|\n")
    rec_mtx = [
        ("Harm3 lot-range routing", "yes", "yes (with 3-tuple join key)", "yes", "no for v2.1 (inferred ok); yes before high confidence"),
        ("HarmCo_residential MF2", "yes", "yes", "yes", "no for v2.1 inferred"),
        ("HarmCo_commercial X-X", "yes (for exclusion)", "no — non-lot inventory", "yes (commercial-pad summary)", "yes — needs ontology decision (CommercialParcel?)"),
        ("HarmTo single-lot MF1", "yes", "yes", "yes", "no"),
        ("HarmTo range entries", "yes (project+phase only)", "no", "yes", "yes (allocation method)"),
        ("LomHS1 SFR 2A", "yes", "yes", "yes", "no"),
        ("LomHT1 TH 2A", "yes (range-aware)", "yes (single-lot subset)", "yes", "no"),
        ("PWFS2 4-digit + 5-digit B → D1/D2/G1/G2/B2", "yes", "yes", "yes", "no"),
        ("PWFT1 C1/C2 split", "yes", "yes (single-lot subset)", "yes", "no"),
        ("AultF A-suffix → A1/A2.x", "yes", "yes", "yes", "no"),
        ("AultF B-suffix → B1 (CORRECTED)", "yes", "yes", "yes", "no"),
        ("AultF SR-suffix", "yes (exclude)", "no", "yes (inferred-unknown)", "yes — Terminal C Q1"),
        ("ArroS1 / ArroT1 123/456 routing", "yes", "yes", "yes", "no"),
        ("ScaRdg phase 1/2/3", "yes", "yes", "yes", "no"),
        ("SctLot project-grain only", "yes", "no (no inventory match possible)", "yes (project='Scattered Lots')", "yes — needs source-owner attribution decision"),
        ("Range entries (MCreek, SaleTT, SaleTR, WilCrk, HarmTo, LomHT1, PWFT1, ArroT1)", "yes (project+phase only)", "no (do not expand in v0)", "yes", "yes — for any expansion to per-lot grain"),
    ]
    for rec in rec_mtx:
        md.append(f"| {rec[0]} | {rec[1]} | {rec[2]} | {rec[3]} | {rec[4]} |\n")
    md.append("\n")

    md.append("## Hard guardrails honored\n\n")
    md.append("- ✅ All rules `confidence='inferred'`, `validated_by_source_owner=False`.\n")
    md.append("- ✅ No modification to `staged_gl_transactions_v2`.\n")
    md.append("- ✅ No modification to canonical_lot or any v2 output.\n")
    md.append("- ✅ Org-wide v2 untouched.\n")
    md.append("- ✅ Did not promote any rule to high confidence.\n")
    md.append("- ✅ HarmCo split honors Terminal C's non-lot inventory recommendation.\n")
    md.append("- ✅ SctLot canonical_project changed to 'Scattered Lots' per Terminal B; not merged with ScaRdg.\n")
    md.append("- ✅ AultF B-suffix corrected to B1 per Terminal B's empirical evidence.\n")
    md.append("- ✅ Range rows kept at project+phase grain; not expanded.\n")

    out_md = REPORTS / "vf_lot_code_decoder_v1_report.md"
    out_md.write_text("".join(md))
    print(f"[v1-decoder] wrote {out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
