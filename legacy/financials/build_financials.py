"""
GL → normalized financials pipeline.

Input:  DataRails QuickBooks export (Excel)
Output: financials_normalized.{csv,parquet} + 3 aggregate CSVs in /output/
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = Path("/Users/arench/Desktop/FInancials_Sample_Struct.xlsx")
OUTPUT_DIR = REPO_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

PLACEHOLDER_CUSTOMER = "Customer or Client name"
PLACEHOLDER_VENDOR = "Vendor or Supplier name"
INVALID_ENTITIES = {"drywall partners"}

ENTITY_MAP = {
    "Flagship EM Holdings LLC":          ("holdco",  None),
    "Anderson Geneva LLC":               ("project", "Anderson Geneva"),
    "Flagborough LLC":                   ("project", "Park"),
    "Arrowhead Springs Development LLC": ("project", "Arrowhead Springs"),
    "Geneva Project Manager LLC":        ("service", None),
}

# Account ID prefix → cost bucket. Order matters; first match wins.
# Handles QBD pattern (NNN-NNN), QBO numeric (5-digit), and edge cases.
ACCOUNT_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^110-"),                   "cash"),
    (re.compile(r"^(210-|21010|20000$)"),    "accounts_payable"),
    (re.compile(r"^220-"),                   "accounts_payable"),     # retention
    (re.compile(r"^(12100$|132-|151-|193-|510-)"), "inventory_cip"),
    (re.compile(r"^260-"),                   "financing"),
    (re.compile(r"^740-"),                   "interest"),
    (re.compile(r"^(660-|670-|81400$)"),     "soft_cost"),
]

PHASE_RULES: list[tuple[re.Pattern, str, str]] = [
    # (pattern, group_template, confidence)
    (re.compile(r"\bblock\s+(\d+[A-Za-z]?)\b", re.I),         r"block \1", "high"),
    (re.compile(r"\bLDWIP\s+(\d+)\s+Overall\s+([A-Z.\s]+)", re.I),
                                                              r"LDWIP \1 \2", "medium"),
]


def classify_account(account_id: str | None) -> str:
    if not account_id:
        return "unmapped"
    aid = str(account_id).strip()
    for pat, bucket in ACCOUNT_RULES:
        if pat.match(aid):
            return bucket
    return "unmapped"


def extract_phase(account_name: str | None) -> tuple[str, str]:
    """Returns (phase_id, confidence). 'UNALLOCATED' / 'none' when no rule matches."""
    if not account_name:
        return "UNALLOCATED", "none"
    name = str(account_name).strip()
    for pat, template, conf in PHASE_RULES:
        m = pat.search(name)
        if m:
            phase = pat.sub(template, m.group(0)).strip()
            phase = re.sub(r"\s+", " ", phase)
            return phase, conf
    return "UNALLOCATED", "none"


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Drop opening balances (zero-amount, all-null rows).
    df = df[df["Data Type"] == "Activity"]

    # Drop entity-column leakage (vendor names appearing in Entity).
    df = df[~df["Entity"].isin(INVALID_ENTITIES)]

    # Strip whitespace + null placeholders.
    for col in ["Account ID", "Account Name", "Customer", "Vendor", "Memo/Description", "Entity"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
    df.loc[df["Customer"] == PLACEHOLDER_CUSTOMER, "Customer"] = pd.NA
    df.loc[df["Vendor"] == PLACEHOLDER_VENDOR, "Vendor"] = pd.NA

    # Normalize account name case to canonical form (collapse "Accounts payable" / "Accounts Payable").
    df["account_name_canonical"] = (
        df["Account Name"].fillna("").str.strip().str.replace(r"\s+", " ", regex=True)
    )
    # Title-case only the case-variant duplicates we know about.
    df.loc[df["account_name_canonical"].str.lower() == "accounts payable",
           "account_name_canonical"] = "Accounts Payable"

    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["posting_date"] = pd.to_datetime(df["Posting Date"]).dt.date
    out["entity"] = df["Entity"]

    role_proj = df["Entity"].map(lambda e: ENTITY_MAP.get(e, ("unknown", None)))
    out["entity_role"] = [r for r, _ in role_proj]
    out["project_id"]  = [p for _, p in role_proj]

    phases = df["account_name_canonical"].apply(extract_phase)
    out["phase_id"]         = [p for p, _ in phases]
    out["phase_confidence"] = [c for _, c in phases]

    out["account_id"]       = df["Account ID"]
    out["account_name"]     = df["account_name_canonical"]
    out["cost_bucket"]      = df["Account ID"].apply(classify_account)
    out["vendor"]           = df["Vendor"]
    out["amount"]           = df["Amount"].astype(float)
    out["source_system"]    = df["DataMapper_Name"]
    return out.reset_index(drop=True)


def aggregate(norm: pd.DataFrame) -> dict[str, pd.DataFrame]:
    # Use absolute amount for "spend" rollups so cash CR / liability DR don't cancel real activity.
    n = norm.copy()
    n["abs_amount"] = n["amount"].abs()

    by_project = (
        n.groupby(["entity_role", "project_id", "entity"], dropna=False)
         .agg(rows=("amount", "size"),
              net_amount=("amount", "sum"),
              abs_amount=("abs_amount", "sum"))
         .reset_index()
         .sort_values("abs_amount", ascending=False)
    )

    proj_only = n[n["entity_role"] == "project"]
    by_phase = (
        proj_only.groupby(["project_id", "phase_id", "phase_confidence"], dropna=False)
                 .agg(rows=("amount", "size"),
                      net_amount=("amount", "sum"),
                      abs_amount=("abs_amount", "sum"))
                 .reset_index()
                 .sort_values(["project_id", "abs_amount"], ascending=[True, False])
    )

    by_bucket = (
        n.groupby("cost_bucket", dropna=False)
         .agg(rows=("amount", "size"),
              net_amount=("amount", "sum"),
              abs_amount=("abs_amount", "sum"))
         .reset_index()
         .sort_values("abs_amount", ascending=False)
    )

    return {"by_project": by_project, "by_phase": by_phase, "by_bucket": by_bucket}


def coverage_report(norm: pd.DataFrame) -> str:
    total_rows = len(norm)
    total_abs  = norm["amount"].abs().sum()

    proj = norm[norm["entity_role"] == "project"]
    proj_rows = len(proj)
    proj_abs  = proj["amount"].abs().sum()

    phased = proj[proj["phase_id"] != "UNALLOCATED"]
    phased_rows = len(phased)
    phased_abs  = phased["amount"].abs().sum()

    bucket_unmapped = norm[norm["cost_bucket"] == "unmapped"]

    pct = lambda a, b: (100.0 * a / b) if b else 0.0
    lines = [
        "=" * 60,
        "COVERAGE REPORT",
        "=" * 60,
        f"Activity rows (post-clean):           {total_rows}",
        f"  cost_bucket mapped:                 {total_rows - len(bucket_unmapped):>4}  ({pct(total_rows - len(bucket_unmapped), total_rows):.1f}%)",
        f"  cost_bucket unmapped:               {len(bucket_unmapped):>4}  ({pct(len(bucket_unmapped), total_rows):.1f}%)",
        "",
        f"Rows assigned to a project entity:    {proj_rows:>4}  ({pct(proj_rows, total_rows):.1f}%)",
        f"  ↳ phase_id resolved (not UNALLOC):  {phased_rows:>4}  ({pct(phased_rows, proj_rows):.1f}% of project rows)",
        f"  ↳ phase_id UNALLOCATED:             {proj_rows - phased_rows:>4}  ({pct(proj_rows - phased_rows, proj_rows):.1f}% of project rows)",
        "",
        f"Total |amount|:                       ${total_abs:>14,.2f}",
        f"  on project entities:                ${proj_abs:>14,.2f}  ({pct(proj_abs, total_abs):.1f}%)",
        f"  resolved to a real phase:           ${phased_abs:>14,.2f}  ({pct(phased_abs, total_abs):.1f}% of total |amount|)",
        "=" * 60,
    ]
    return "\n".join(lines)


def main() -> None:
    raw = pd.read_excel(INPUT_FILE)
    cleaned = clean(raw)
    norm = normalize(cleaned)

    norm.to_csv(OUTPUT_DIR / "financials_normalized.csv", index=False)
    norm.to_parquet(OUTPUT_DIR / "financials_normalized.parquet", index=False)

    aggs = aggregate(norm)
    for name, frame in aggs.items():
        frame.to_csv(OUTPUT_DIR / f"financials_{name}.csv", index=False)

    print(f"Wrote {len(norm)} rows → {OUTPUT_DIR}/financials_normalized.csv")
    print()
    print(coverage_report(norm))
    print()

    print("--- by_bucket ---")
    print(aggs["by_bucket"].to_string(index=False))
    print()
    print("--- by_project ---")
    print(aggs["by_project"].to_string(index=False))
    print()
    print("--- by_phase (project entities only) ---")
    print(aggs["by_phase"].to_string(index=False))

    unmapped = norm[norm["cost_bucket"] == "unmapped"]
    if len(unmapped):
        print()
        print("--- account_id values that did not map to a cost_bucket ---")
        print(unmapped[["account_id", "account_name"]].drop_duplicates().to_string(index=False))


if __name__ == "__main__":
    main()
