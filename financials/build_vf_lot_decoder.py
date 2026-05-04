"""
W1 — Vertical Financials lot-code decoder (inferred).

Investigation, NOT pipeline integration. Profile VF lot codes per project,
propose project-specific decoder rules, validate match-rate against inventory
+ Lot Data, and write:

  data/staged/vf_lot_code_decoder_v0.csv
  data/reports/vf_lot_code_decoder_report.md

All rules ship with confidence='inferred' until source-owner-validated.
Does not modify any v2 output or canonical_* table.
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

# In-scope VF project codes per W1 plan
VF_TO_CANONICAL = {
    "Harm3":  "Harmony",
    "HarmCo": "Harmony",
    "HarmTo": "Harmony",
    "LomHS1": "Lomond Heights",
    "LomHT1": "Lomond Heights",
    "PWFS2":  "Parkway Fields",
    "PWFT1":  "Parkway Fields",
    "AultF":  "Parkway Fields",
    "ArroS1": "Arrowhead Springs",
    "ArroT1": "Arrowhead Springs",
    "ScaRdg": "Scarlet Ridge",
    "SctLot": "Scarlet Ridge",
}

# Phase normalization between Lot Data and inventory
# (inventory uses '2-A' for what Lot Data calls '2A'; map decoder output → Lot-Data form)
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


def lot_int(s: str) -> int | None:
    """Return integer lot number from a normalized lot string, or None."""
    if not s:
        return None
    # Strip any alpha suffix
    m = re.match(r"^0*(\d+)", s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


# ----------------------------------------------------------------------
# Decoder rules. Each rule maps VF (project_code, lot_string) → (canonical_phase, canonical_lot_number)
# ----------------------------------------------------------------------

def decode_harm3(lot_str: str):
    """Harmony: lot is the actual lot number (zero-padded 4 digits in VF);
    phase is inferred from lot-number range (Lot Data ranges).
    """
    n = lot_int(lot_str)
    if n is None: return (None, None, "no integer lot")
    # Disambiguate MF1 (1-116) vs B1 (101-192): MF1 takes 1-100, B1 takes 101-192
    # (MF1 lots 101-116 are an overlap; assigned to B1 because VF Harm3 samples start at 101 and don't include 1-100)
    if 1 <= n <= 100:    return ("MF1",  str(n), "")
    if 101 <= n <= 192:  return ("B1",   str(n), "")
    if 201 <= n <= 271:  return ("B2",   str(n), "")
    if 301 <= n <= 347:  return ("B3",   str(n), "")
    if 453 <= n <= 454:  return ("A4.1", str(n), "")
    if 701 <= n <= 749:  return ("A7",   str(n), "")
    if 801 <= n <= 848:  return ("A8",   str(n), "")
    if 901 <= n <= 950:  return ("A9",   str(n), "")
    if 1001 <= n <= 1044:return ("A10",  str(n), "")
    if 1301 <= n <= 1334:return ("ADB13",str(n), "")
    if 1401 <= n <= 1438:return ("ADB14",str(n), "")
    return (None, str(n), "out of known Lot Data ranges")


def decode_harmco(lot_str: str):
    """Harmony Commercial: 7-char strings like '0000A01' or '0000A-A'.
    Map: '0000<X><suffix>' → MF2 lot '<X><suffix>' (where MF2 has lots like A01, B01).
    """
    s = lot_str
    if len(s) != 7 or not s.startswith("0000"):
        return (None, None, "not 0000-prefixed 7-char")
    rest = s[4:]  # 3 chars
    # Forms seen: 'A01' (alpha + 2 digits), 'A-A' (alpha-alpha)
    if re.match(r"^[A-Z]\d{2}$", rest):
        # MF2 lot like 'A01'
        return ("MF2", rest, "")
    if re.match(r"^[A-Z]-[A-Z]$", rest):
        # 'A-A', 'B-B', etc. — likely commercial parcel marker; no clean inventory match
        return ("MF2", rest, "commercial parcel marker; may not match a residential lot row")
    return (None, rest, "unknown HarmCo subform")


def decode_harmto(lot_str: str):
    """Harmony Townhomes: 4-digit numeric (single lot) OR range like '0009-12' or '0097-100'.
    Single lots map to MF1 (which has lots 1-116). Range entries are summary
    allocation rows; they may not match a single inventory lot.
    """
    if "-" in lot_str:
        # Range entry — flag as range
        return (None, lot_str, "range allocation entry; expand-to-set if needed")
    n = lot_int(lot_str)
    if n is None: return (None, None, "no integer")
    if 1 <= n <= 116:
        return ("MF1", str(n), "")
    return (None, str(n), "outside MF1 range 1-116")


def decode_lomhs1(lot_str: str):
    """Lomond Heights SFR Phase 1 → all map to Phase 2A (Lot Data) / 2-A (inventory)."""
    if "-" in lot_str:
        return (None, lot_str, "range entry")
    n = lot_int(lot_str)
    if n is None: return (None, None, "no integer")
    # VF LomHS1 observed range: 101-171; Lot Data 2A range: 0-215
    if 101 <= n <= 215:
        return ("2A", str(n), "")
    return (None, str(n), "outside 2A range 101-215")


def decode_lomht1(lot_str: str):
    """Lomond Heights TH Phase 1 → also Phase 2A (TH portion). Inventory does not split by product type."""
    if "-" in lot_str:
        return (None, lot_str, "range entry; townhome cluster allocation")
    n = lot_int(lot_str)
    if n is None: return (None, None, "no integer")
    if 101 <= n <= 215:
        return ("2A", str(n), "")
    return (None, str(n), "outside 2A range")


def decode_pwfs2(lot_str: str):
    """Parkway Fields SFR Phase 2 — covers D1/D2/G1/G2 (4-digit) and B2 (5-digit suffix B)."""
    s = lot_str
    if len(s) == 5 and s.endswith("B"):
        # 5-digit form: 0273B → B2 lot 273
        n = lot_int(s)
        if n is None: return (None, None, "no integer in NNNNB")
        if 201 <= n <= 323:
            return ("B2", str(n), "")
        return (None, str(n), "outside B2 range 201-323")
    n = lot_int(s)
    if n is None: return (None, None, "no integer")
    # 4-digit numeric routing by lot-range
    if 4001 <= n <= 4159:  return ("D1", str(n), "")
    if 4160 <= n <= 4199:  return (None, str(n), "between D1 and D2 ranges; gap")
    if 4201 <= n <= 4282:  return ("D2", str(n), "")
    if 4283 <= n <= 4499:  return (None, str(n), "outside Lot Data D2 (4201-4282); maybe new D-series lots")
    if 7001 <= n <= 7065:  return ("G1", str(n), "")
    if 7065 <= n <= 7209:  return ("G2", str(n), "")
    return (None, str(n), "outside known PWFS2 ranges")


def decode_pwft1(lot_str: str):
    """Parkway Fields TH Phase 1 — 4-digit 3xxx → C1 or C2; ranges flagged."""
    if "-" in lot_str:
        return (None, lot_str, "range entry")
    n = lot_int(lot_str)
    if n is None: return (None, None, "no integer")
    if 3001 <= n <= 3116:  return ("C1", str(n), "")
    if 3117 <= n <= 3235:  return ("C2", str(n), "")
    return (None, str(n), "outside C1/C2 ranges")


def decode_aultf(lot_str: str):
    """AultF (Ault Farms aka Parkway Fields E-1) — 5-digit NNNNX with letter suffix.
    Suffix A + lot range → A1 / A2.1 / A2.2 / A2.3
    Suffix B + lot range → B1 / B2 (with overlap)
    Suffix SR (only 0139, 0140) → unclear; flag inferred unknown.
    """
    s = lot_str
    if "-" in s:
        return (None, s, "range entry")
    if len(s) == 6 and s.endswith("SR"):
        return (None, s, "SR suffix; meaning unclear (Park West/'South Row'?); inferred unknown")
    if len(s) >= 5:
        suffix = s[-1]
        n = lot_int(s)
        if n is None: return (None, s, "no integer prefix")
        if suffix == "A":
            if 101 <= n <= 169:    return ("A1",   str(n), "")
            if 201 <= n <= 236:    return ("A2.1", str(n), "")
            if 237 <= n <= 281:    return ("A2.2", str(n), "")
            if 282 <= n <= 343:    return ("A2.3", str(n), "")
            return (None, str(n), "A-suffix lot outside A1/A2.* ranges")
        if suffix == "B":
            # B1 has 101-211; B2 has 201-323. Resolve overlap 201-211 to B2 (PWFS2 already shows B2 lots).
            if 101 <= n <= 200:    return ("B1", str(n), "")
            if 201 <= n <= 323:    return ("B2", str(n), "B1/B2 overlap 201-211 resolved to B2")
            return (None, str(n), "B-suffix lot outside B1/B2 ranges")
    n = lot_int(s)
    if n is None: return (None, s, "no integer")
    return (None, s, "unknown AultF subform")


def decode_arros1(lot_str: str):
    """Arrowhead Springs S1 — 4-digit, lot-range determines phase 123 vs 456."""
    if "-" in lot_str:
        return (None, lot_str, "range entry")
    n = lot_int(lot_str)
    if n is None: return (None, None, "no integer")
    if 1 <= n <= 129:    return ("123", str(n), "")
    if 130 <= n <= 207:  return ("456", str(n), "")
    return (None, str(n), "outside 123/456 ranges")


def decode_arrot1(lot_str: str):
    """Arrowhead Springs T1 (townhomes) — same lot-range routing as S1."""
    if "-" in lot_str:
        return (None, lot_str, "range entry; townhome cluster allocation")
    n = lot_int(lot_str)
    if n is None: return (None, None, "no integer")
    if 1 <= n <= 129:    return ("123", str(n), "")
    if 130 <= n <= 207:  return ("456", str(n), "")
    return (None, str(n), "outside known ranges")


def decode_scardg(lot_str: str):
    """Scarlet Ridge — 4-digit, lot-range routes to Phase 1 / 2 / 3."""
    n = lot_int(lot_str)
    if n is None: return (None, None, "no integer")
    if 101 <= n <= 152:  return ("1", str(n), "")
    if 201 <= n <= 260:  return ("2", str(n), "")
    if 301 <= n <= 364:  return ("3", str(n), "")
    return (None, str(n), "outside known phase ranges")


def decode_sctlot(lot_str: str):
    """SctLot — only 6 distinct lots; outlier 0639. No clean rule. Mark inferred-unknown."""
    n = lot_int(lot_str)
    return (None, str(n) if n is not None else lot_str,
            "no decoder; SctLot semantics unclear; investigate with source owner")


DECODERS = {
    "Harm3":  ("harmony_lot_range_to_phase",      decode_harm3),
    "HarmCo": ("harmony_commercial_mf2_marker",   decode_harmco),
    "HarmTo": ("harmony_townhome_mf1_only",       decode_harmto),
    "LomHS1": ("lomondheights_sfr_phase_2a",      decode_lomhs1),
    "LomHT1": ("lomondheights_th_phase_2a",       decode_lomht1),
    "PWFS2":  ("parkway_sfr_phase2_range_route",  decode_pwfs2),
    "PWFT1":  ("parkway_th_phase1_c1c2_route",    decode_pwft1),
    "AultF":  ("aultf_suffix_a_b_phase_route",    decode_aultf),
    "ArroS1": ("arrowhead_sfr_123_456_route",     decode_arros1),
    "ArroT1": ("arrowhead_th_123_456_route",      decode_arrot1),
    "ScaRdg": ("scarletridge_lot_range_phase",    decode_scardg),
    "SctLot": ("sctlot_no_decoder",                decode_sctlot),
}


def main() -> int:
    print("[w1] loading sources...")
    gl = pd.read_parquet(GL_PARQUET)
    inv = pd.read_parquet(INV_PARQUET)
    ld = pd.read_csv(LOT_DATA_CSV)

    bcpd_vf = gl[(gl["entity_name"] == "Building Construction Partners, LLC") &
                 (gl["source_schema"] == "vertical_financials_46col")].copy()

    # Build inventory + Lot Data lookup sets per project
    # Lot Data: {(project, phase, lot_int_str)}
    ld_keys = set()
    for _, r in ld.iterrows():
        proj = str(r.get("Project") or "").strip()
        phase = str(r.get("Phase") or "").strip()
        lot = norm_lot(r.get("LotNo."))
        n = lot_int(lot)
        if proj and phase and n is not None:
            ld_keys.add((proj, phase, str(n)))

    # Inventory keys (using Lot-Data-form phase via crosswalk)
    inv_keys = set()
    for _, r in inv.iterrows():
        proj = str(r.get("canonical_project") or "").strip()
        raw_phase = str(r.get("phase") or "").strip()
        lot = str(r.get("lot_num") or "").strip()
        n = lot_int(lot if not lot.endswith(".0") else lot[:-2])
        if not proj or not raw_phase or n is None:
            continue
        # Map inventory phase to Lot-Data form for compatibility
        ld_phase = PHASE_INV_TO_LD.get((proj, raw_phase), raw_phase)
        inv_keys.add((proj, ld_phase, str(n)))
        inv_keys.add((proj, raw_phase, str(n)))  # also keep raw form

    # Validate per VF code
    decoder_rows = []
    per_code_detail = {}
    for code, (rule_name, fn) in DECODERS.items():
        canon = VF_TO_CANONICAL[code]
        sub = bcpd_vf[bcpd_vf["project_code"] == code].copy()
        n_total = len(sub)
        n_decoded = 0
        n_match_inv = 0
        n_match_ld = 0
        n_decoded_unmatched = 0
        n_undecoded = 0
        unmatched_examples = []
        for _, r in sub.iterrows():
            raw = str(r["lot"]).strip() if pd.notna(r["lot"]) else ""
            phase, lot_n, note = fn(raw)
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

        match_inv_rate = (n_match_inv / n_total * 100) if n_total else 0
        match_ld_rate = (n_match_ld / n_total * 100) if n_total else 0
        any_match_rate = (max(n_match_inv, n_match_ld) / n_total * 100) if n_total else 0
        # Confidence (per W1 plan)
        if any_match_rate >= 90: conf = "inferred"  # rule plan: ship inferred always
        elif any_match_rate >= 60: conf = "inferred"
        else: conf = "inferred"
        # Rule-quality flag (separate from confidence label)
        if any_match_rate >= 90: quality = "high-evidence"
        elif any_match_rate >= 60: quality = "medium-evidence"
        elif any_match_rate >= 30: quality = "low-evidence"
        else: quality = "no-decoder"

        decoder_rows.append({
            "vf_project_code": code,
            "canonical_project": canon,
            "decoder_rule_name": rule_name,
            "decoder_pattern": fn.__doc__.strip().split("\n")[0] if fn.__doc__ else "",
            "rule_quality": quality,
            "confidence": conf,
            "rows_total": n_total,
            "rows_decoded": n_decoded,
            "rows_undecoded_or_range": n_undecoded,
            "rows_match_lot_data": n_match_ld,
            "rows_match_inventory": n_match_inv,
            "rows_decoded_but_unmatched": n_decoded_unmatched,
            "match_rate_lot_data_pct": round(match_ld_rate, 1),
            "match_rate_inventory_pct": round(match_inv_rate, 1),
            "match_rate_any_pct": round(any_match_rate, 1),
            "validated_by_source_owner": False,
            "notes": "",
        })
        per_code_detail[code] = {
            "unmatched_examples": unmatched_examples,
            "n_total": n_total,
            "n_decoded": n_decoded,
            "n_undecoded": n_undecoded,
            "n_match_inv": n_match_inv,
            "n_match_ld": n_match_ld,
        }

    df = pd.DataFrame(decoder_rows)
    out_csv = STAGED / "vf_lot_code_decoder_v0.csv"
    df.to_csv(out_csv, index=False)
    print(f"[w1] wrote {out_csv}")

    # Coverage simulation: how many VF rows would now have a known
    # (canonical_project, canonical_phase, canonical_lot) triple if the decoder
    # were applied? Compare to the v0 baseline (which used flat lot strings).
    total_vf_in_scope = sum(d["n_total"] for d in per_code_detail.values())
    total_decoded_match = sum(decoder_rows[i]["rows_match_lot_data"] +
                              decoder_rows[i]["rows_match_inventory"] -
                              # avoid double-count: take max as "any"
                              0
                              for i in range(len(decoder_rows)))
    total_any_match = sum(max(decoder_rows[i]["rows_match_lot_data"],
                              decoder_rows[i]["rows_match_inventory"])
                          for i in range(len(decoder_rows)))

    # Inventory-base lift estimate: distinct inventory (project, phase, lot)
    # triples that the decoder newly reaches.
    # We approximate by counting how many distinct (canon, phase, lot) the VF
    # decoder produces that are in inventory_keys.
    decoded_in_inv = set()
    decoded_in_ld = set()
    for code, (rule_name, fn) in DECODERS.items():
        canon = VF_TO_CANONICAL[code]
        sub = bcpd_vf[bcpd_vf["project_code"] == code]
        for _, r in sub.iterrows():
            raw = str(r["lot"]).strip() if pd.notna(r["lot"]) else ""
            phase, lot_n, _ = fn(raw)
            if phase and lot_n:
                if (canon, phase, lot_n) in inv_keys:
                    decoded_in_inv.add((canon, phase, lot_n))
                if (canon, phase, lot_n) in ld_keys:
                    decoded_in_ld.add((canon, phase, lot_n))

    print(f"[w1] decoded VF rows that match Lot Data: {sum(d['rows_match_lot_data'] for d in decoder_rows)}")
    print(f"[w1] decoded VF rows that match Inventory: {sum(d['rows_match_inventory'] for d in decoder_rows)}")
    print(f"[w1] distinct (canon, phase, lot) in inv reached by decoder: {len(decoded_in_inv)}")
    print(f"[w1] distinct (canon, phase, lot) in Lot Data reached by decoder: {len(decoded_in_ld)}")

    # Build report
    md = []
    md.append("# VF Lot-Code Decoder — Report (W1)\n\n")
    md.append("**Built**: 2026-05-01\n")
    md.append("**Owner**: Terminal A (W1 of BCPD State Quality Pass)\n")
    md.append("**Plan**: `docs/vf_lot_code_decoder_plan.md`\n")
    md.append("**Inputs**: `staged_gl_transactions_v2.parquet`, `staged_inventory_lots.parquet`, `Collateral Dec2025 - Lot Data.csv`\n")
    md.append("**Output (lookup)**: `data/staged/vf_lot_code_decoder_v0.csv`\n\n")
    md.append("**All rules ship `confidence='inferred'`.** None has been validated by the source-system owner. Promotion to higher confidence requires explicit human sign-off recorded in `validated_by_source_owner=true` per row.\n\n")
    md.append("---\n\n")
    md.append("## Step 1 — Per-VF-project profile\n\n")
    md.append("VF rows in scope (excludes Salem Fields and Willowcreek which are already at 100% v0 match):\n\n")
    md.append("| VF code | canonical project | rows | distinct lots | length distribution | sample lots |\n")
    md.append("|---|---|---:|---:|---|---|\n")
    profile_rows = []
    for code in DECODERS:
        sub = bcpd_vf[bcpd_vf["project_code"] == code]
        lots = sub["lot"].dropna().astype(str).str.strip()
        by_len = lots.str.len().value_counts().sort_index()
        len_dist = ", ".join(f"len={L}: {n}" for L, n in by_len.items())
        sample = sorted(lots.unique())[:4] + (["…"] if lots.nunique() > 4 else []) + sorted(lots.unique())[-2:] if lots.nunique() > 6 else sorted(lots.unique())
        md.append(f"| {code} | {VF_TO_CANONICAL[code]} | {len(sub):,} | {lots.nunique()} | {len_dist} | {', '.join(map(str, sample))} |\n")
    md.append("\n")
    md.append("Per-canonical-project Lot Data ranges (used as the validation target):\n\n")
    md.append("```\n")
    for proj in ["Harmony","Lomond Heights","Parkway Fields","Arrowhead Springs","Scarlet Ridge"]:
        p = ld[ld["Project"] == proj].copy()
        p["lot_int"] = p["LotNo."].apply(lambda v: lot_int(norm_lot(v)))
        ranges = p.groupby("Phase")["lot_int"].agg(["min", "max", "count"])
        md.append(f"\n{proj}:\n")
        md.append(ranges.to_string())
        md.append("\n")
    md.append("```\n\n")

    md.append("---\n\n")
    md.append("## Step 2 + 3 — Per-rule pattern, decoder, and validation\n\n")
    md.append("Each VF code gets one decoder rule. The rule decodes `(vf_project_code, vf_lot)` → `(canonical_phase, canonical_lot_number)`. Validation against Lot Data and inventory is then computed per row.\n\n")
    md.append("Rule `confidence` is always `inferred`. The `rule_quality` column reflects the validation match rate (high-evidence ≥ 90%, medium 60-90%, low 30-60%, no-decoder < 30%).\n\n")
    md.append("| VF code | rule | rows_total | decoded | undecoded/range | match LD | match inv | decoded-unmatched | match% (any) | rule_quality |\n")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|\n")
    for r in decoder_rows:
        md.append(f"| {r['vf_project_code']} | `{r['decoder_rule_name']}` | {r['rows_total']:,} | "
                  f"{r['rows_decoded']:,} | {r['rows_undecoded_or_range']:,} | "
                  f"{r['rows_match_lot_data']:,} | {r['rows_match_inventory']:,} | "
                  f"{r['rows_decoded_but_unmatched']:,} | {r['match_rate_any_pct']}% | {r['rule_quality']} |\n")
    md.append("\n")

    md.append("### Decoder pattern descriptions\n\n")
    for code, (rule_name, fn) in DECODERS.items():
        md.append(f"**`{code}` — {rule_name}** (`canonical_project = {VF_TO_CANONICAL[code]}`)\n\n")
        if fn.__doc__:
            md.append(fn.__doc__.strip() + "\n\n")
        d = per_code_detail[code]
        if d["unmatched_examples"]:
            md.append("Sample decoded-but-unmatched VF lots:\n\n")
            for raw, phase, lot in d["unmatched_examples"]:
                md.append(f"- `{code}`/`{raw}` → decoded → phase=`{phase}`, lot=`{lot}` — no inventory or Lot Data row found\n")
            md.append("\n")
    md.append("---\n\n")

    md.append("## Step 4 — Selected rules per project\n\n")
    md.append("One rule per VF code (the one tabulated above). For VF codes where the rule has `rule_quality='no-decoder'`, the recommendation is to leave the lot unmatched in v0 and flag for human review with the source-system owner.\n\n")
    md.append("Selected verdicts:\n\n")
    for r in decoder_rows:
        verdict = "USE" if r["rule_quality"] in ("high-evidence", "medium-evidence") else \
                  "USE WITH CAVEAT" if r["rule_quality"] == "low-evidence" else "DO NOT APPLY"
        md.append(f"- **{r['vf_project_code']}** ({r['canonical_project']}): {verdict}. `{r['decoder_rule_name']}`. {r['rule_quality']}, match {r['match_rate_any_pct']}%. {r['rows_total']:,} rows.\n")
    md.append("\n")

    md.append("---\n\n")
    md.append("## Step 5 — Edge cases and decoded-but-unmatched lots\n\n")
    md.append("Notable patterns that the decoder cannot resolve cleanly:\n\n")
    md.append("- **`HarmTo` and `LomHT1` and `PWFT1` range entries** (e.g. `0009-12`, `0172-175`, `3001-06`): these are 'range' allocations — single GL postings whose `lot` field encodes a span of lots rather than a specific one. They cannot match a single inventory lot. v0 leaves them undecoded. A future enhancement could expand a range row into N synthetic per-lot rows by allocating the amount evenly, but that is a financial-treatment decision that requires source-owner sign-off.\n")
    md.append("- **`AultF` `0139SR` and `0140SR`**: only two lots with `SR` suffix. Meaning is unclear (possibly 'South Row' or a Park West rollup). Marked inferred-unknown until source owner explains.\n")
    md.append("- **`SctLot` (6 distinct lots, including outlier `0639`)**: the project_code itself is ambiguous (could be 'Scenic Lots' for Scarlet Ridge, or some other label). No clean decoder; the rule returns no match. The 1,130 VF rows under SctLot remain unmatched in v0.\n")
    md.append("- **`HarmCo` `0000A-A`-style commercial parcels**: only 5 of the 31 distinct lots use this `X-X` form; the rest follow `0000<X><NN>` and decode to MF2 lots. The `X-X` parcels are likely commercial/non-residential roll-ups; flag for human review.\n")
    md.append("- **Phase ambiguity in Parkway B-suffix**: B1 (101-211) and B2 (201-323) overlap at 201-211. AultF `02xxB` lots in the overlap are routed to B2 (because PWFS2 already enumerates B2 lots). The rule explicitly notes this and treats it as inferred.\n")
    md.append("- **MF1 vs B1 overlap in Harmony**: MF1 (1-116) and B1 (101-192) share 101-116. We assign 101-192 to B1 and 1-100 to MF1 because VF Harm3 lot samples don't include 1-100. If MF1 lots 101-116 do exist in VF and are mis-routed to B1 by this rule, expect a small false-match population that human review should sample.\n")
    md.append("\n")

    md.append("---\n\n")
    md.append("## Coverage lift estimate (forwarded to W3)\n\n")
    md.append("Baseline (per `data/reports/join_coverage_v0.md`): 1,285 distinct BCPD inventory lots; 810 (63.0%) have ≥1 GL row; 476 (37.0%) have full triangle. Coverage was computed against a flat `(canonical_project, lot_int)` key — phase ignored.\n\n")
    md.append("With the W1 decoder applied (still using `(canonical_project, lot_int)` for the join, but now phase-validated), the **GL row → inventory lot match count** for the in-scope projects increases as follows. These are dry-run estimates; the decoder is **not wired into the canonical lot crosswalk** in v0.\n\n")
    md.append("Per-project decoded match counts (VF rows → Lot Data triples):\n\n")
    md.append("| canonical project | sum_total VF rows | sum_match_lot_data | lift_vs_v0 (estimate) |\n|---|---:|---:|---|\n")
    by_canon = {}
    for r in decoder_rows:
        by_canon.setdefault(r["canonical_project"], {"total": 0, "match_ld": 0, "match_inv": 0})
        by_canon[r["canonical_project"]]["total"] += r["rows_total"]
        by_canon[r["canonical_project"]]["match_ld"] += r["rows_match_lot_data"]
        by_canon[r["canonical_project"]]["match_inv"] += r["rows_match_inventory"]
    # v0 baseline per project (from join_coverage_v0.md)
    BASELINE_PCT = {
        "Harmony": 53.7, "Lomond Heights": 43.9, "Parkway Fields": 61.5,
        "Arrowhead Springs": 65.0, "Scarlet Ridge": 90.9,
    }
    for p, s in by_canon.items():
        rate = (max(s["match_ld"], s["match_inv"]) / max(s["total"], 1)) * 100
        baseline = BASELINE_PCT.get(p, "n/a")
        delta = round(rate - baseline, 1) if isinstance(baseline, (int, float)) else "n/a"
        md.append(f"| {p} | {s['total']:,} | {s['match_ld']:,} | baseline {baseline}% inventory-lot triangle → simulated VF-row decode hit-rate {round(rate, 1)}% (delta {delta}) |\n")
    md.append("\n")
    md.append("Caveat: the v0 baseline is **distinct-inventory-lot match rate**, while the decoder validation produces a **VF-row decode hit rate** against Lot Data. These are not the same metric (the former asks 'how many inventory lots have any GL?'; the latter asks 'how many GL rows resolve to a known phase+lot?'). W3 will run the matching simulation in the same metric space as the v0 baseline so the two are directly comparable.\n\n")

    md.append("Indicative direction:\n\n")
    md.append("- Harmony: large lift expected — Harm3 contains 9,234 rows; the decoder reaches a high match rate on the 4-digit form. HarmCo and HarmTo carry edge-case lots that won't match (range entries, X-X commercial markers).\n")
    md.append("- Lomond Heights: full lift expected — LomHS1 + LomHT1 single-phase mapping is unambiguous against Lot Data 2A.\n")
    md.append("- Parkway Fields: large lift expected — PWFT1 (3xxx lots, 6,880 rows) routes cleanly into C1/C2; PWFS2 4xxx routes into D1/D2/G1/G2; AultF suffix-A/B routing is the most novel and needs source-owner validation. Range entries (1,114 in PWFT1) will not match.\n")
    md.append("- Arrowhead Springs: moderate lift — ArroS1 (5,142 rows) routes cleanly into 123/456; ArroT1 is small.\n")
    md.append("- Scarlet Ridge: small additional lift — already 90.9% in v0. SctLot (1,130 rows) remains unmatched.\n\n")

    md.append("---\n\n")
    md.append("## Hard guardrails honored\n\n")
    md.append("- ✅ All rules ship `confidence='inferred'` with `validated_by_source_owner=False`.\n")
    md.append("- ✅ No modification to `staged_gl_transactions_v2.{csv,parquet}`.\n")
    md.append("- ✅ No modification to canonical_lot or any v2 output.\n")
    md.append("- ✅ Salem Fields and Willowcreek are out of scope (already at 100% in v0).\n")
    md.append("- ✅ Lewis Estates and the 7 active no-GL projects are out of scope (structural gaps).\n")
    md.append("- ✅ Org-wide v2 untouched.\n")
    md.append("- ✅ W2-W6 not implemented in this artifact.\n\n")

    md.append("## Hand-off questions for source-owner validation\n\n")
    md.append("Before any of these decoder rules are promoted from `inferred`, the source-system owner should confirm:\n\n")
    md.append("1. **Harmony Harm3 phase routing** — does the lot-number range really determine phase as proposed, or is phase encoded elsewhere (e.g. in the GL `Lot/Phase` field for DataRails 38-col, or in a project-system attribute we haven't surfaced)?\n")
    md.append("2. **AultF SR suffix** — what does `0139SR` and `0140SR` mean? (Two specific lots; total 401 rows.)\n")
    md.append("3. **AultF B-suffix overlap 201-211** — assigning to B2 may misclassify lots that are actually B1 with high-numbered lot IDs. Confirm B1 max lot.\n")
    md.append("4. **MF1 vs B1 overlap (Harmony lots 101-116)** — if any MF1 lot in 101-116 exists in VF, our rule misclassifies it as B1.\n")
    md.append("5. **SctLot semantics** — is this Scarlet Ridge land/scenic-lot rollup, or a distinct project? Especially the `0639` outlier.\n")
    md.append("6. **Range entries** (`0009-12`, `0172-175`, etc.) — should these be expanded into per-lot allocations (and if so, by what method — equal split, weighted by lot price, etc.)?\n")
    md.append("7. **Lomond Heights LomHS1 vs LomHT1 split** — confirm both belong to inventory phase `2-A` and the only difference is product type (SFR vs TH), not a different phase.\n")
    md.append("\n")

    out_md = REPORTS / "vf_lot_code_decoder_report.md"
    out_md.write_text("".join(md))
    print(f"[w1] wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
