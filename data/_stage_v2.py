"""
Build staged_gl_transactions_v2 — normalized multi-source GL.

Sources (transactional only):
  1. data/raw/datarails/gl/GL (1..14).csv         -- DataRails 38-col bundle (3 entities, 2016-2017)
  2. data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv
                                                  -- 46-col schema (BCPD only, 2018-2025)
  3. data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv
                                                  -- 12-col QB register (BCPD only, 2025)

Excludes: GL.csv stub, GL_QBO_*.csv (opening-balance only), every non-GL file type.

Outputs:
  data/staged/staged_gl_transactions_v2.csv
  data/staged/staged_gl_transactions_v2.parquet
  data/staged/staged_gl_transactions_v2_validation_report.md

Does NOT touch staged_gl_transactions_v1 or output/*.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path("/Users/arench/Desktop/development_ontology_engine")
RAW_GL_DIR = REPO / "data" / "raw" / "datarails" / "gl"
VF_PATH = REPO / "data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv"
BCPD_PATH = REPO / "data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv"
STAGED = REPO / "data" / "staged"
REPORTS = REPO / "data" / "reports"

INGESTED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")

# Canonical schema — column order matters for the output.
CANONICAL = [
    # Core identity
    "source_file", "source_schema", "source_row_id",
    "transaction_id", "transaction_number", "line_number",
    "company_code", "company_name", "entity_name",
    # Dates
    "posting_date", "fiscal_year", "fiscal_period", "source_date_column",
    # Money
    "amount", "debit_amount", "credit_amount", "debit_credit",
    "currency", "functional_amount", "functional_currency",
    # Account
    "account_code", "account_name", "account_type", "account_group",
    "major", "minor",
    # Cost / project attribution
    "project", "project_code", "project_name",
    "phase", "lot", "job_phase_stage",
    "division_code", "division_name", "operating_unit",
    "subledger_code", "subledger_name",
    # Context
    "vendor", "memo", "memo_1", "memo_2", "description",
    "batch_description", "source_system",
    # Metadata
    "ingested_at", "raw_column_map_json", "row_hash",
]


def clean_money(s: pd.Series) -> pd.Series:
    """Strip $, commas, whitespace; coerce to float; NaN if unparseable."""
    return pd.to_numeric(
        s.astype(str).str.replace("$", "", regex=False)
                     .str.replace(",", "", regex=False)
                     .str.strip(),
        errors="coerce",
    )


def parse_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def hash_row(parts: list[str]) -> str:
    h = hashlib.sha1()
    h.update("\x1f".join(str(p) for p in parts).encode("utf-8"))
    return h.hexdigest()


# ----------------------- Source 1: DataRails 38-col bundle ----------------------- #

DATARAILS_MAP = {
    "transaction_number": "TransactionNumber",
    "line_number": "LineNo",
    "company_code": "CompanyCode",
    "company_name": "CompanyName",
    "posting_date": "PostingDate",
    "amount": "FunctionalAmount",
    "currency": "Currency",
    "functional_amount": "FunctionalAmount",
    "functional_currency": "FunctionalCurrency",
    "account_code": "AccountCode",
    "account_name": "AccountName",
    "account_type": "AccountType",
    "major": "Major",
    "minor": "Minor",
    "project": "Project",
    "project_code": "ProjectCode",
    "project_name": "ProjectName",
    "lot": "Lot/Phase",
    "job_phase_stage": "JobPhaseStage",
    "division_code": "DivisionCode",
    "division_name": "DivisionName",
    "operating_unit": "OUnit",
    "subledger_code": "SubledgerCode",
    "subledger_name": "SubledgerDesc",
    "memo_1": "Memo1",
    "memo_2": "Memo2",
    "description": "Description",
    "batch_description": "BatchDescription",
    # Notes:
    #   account_group: not present in DataRails 38-col -> null
    #   phase: not separable from lot in source (Lot/Phase combined) -> null
    #   vendor: no explicit field -> null
    #   memo: source has Memo1/Memo2 separately; canonical 'memo' left null (use memo_1 / memo_2)
    #   debit_credit: derived from sign of amount
    #   debit_amount / credit_amount: derived from amount
    #   transaction_id: composite TransactionNumber:LineNo
}


def load_datarails() -> pd.DataFrame:
    """Read GL (1..14).csv; explicitly excludes GL.csv stub."""
    files = sorted(
        [p for p in RAW_GL_DIR.glob("GL (*).csv")],
        key=lambda p: int(re.search(r"GL \((\d+)\)", p.name).group(1)),
    )
    assert len(files) == 14, f"Expected 14 numbered GL files, found {len(files)}"

    frames = []
    for p in files:
        df = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig", low_memory=False)
        df["__source_row__"] = range(len(df))
        df["__source_file__"] = p.name
        frames.append(df)
    raw = pd.concat(frames, axis=0, ignore_index=True)

    # Build canonical
    out = pd.DataFrame(index=raw.index)
    out["source_file"] = raw["__source_file__"]
    out["source_schema"] = "datarails_38col"
    out["source_row_id"] = raw["__source_file__"] + ":" + raw["__source_row__"].astype(str)
    out["transaction_number"] = raw["TransactionNumber"]
    out["line_number"] = raw["LineNo"]
    out["transaction_id"] = raw["TransactionNumber"].astype(str) + ":" + raw["LineNo"].astype(str)
    out["company_code"] = raw["CompanyCode"]
    out["company_name"] = raw["CompanyName"]
    out["entity_name"] = raw["CompanyName"]

    pd_dt = parse_date(raw["PostingDate"])
    out["posting_date"] = pd_dt.dt.date.astype("string")
    out["fiscal_year"] = pd_dt.dt.year.astype("Int64").astype(str).where(pd_dt.notna(), pd.NA)
    out["fiscal_period"] = pd_dt.dt.month.astype("Int64").astype(str).where(pd_dt.notna(), pd.NA)
    out["source_date_column"] = "PostingDate"

    amt = clean_money(raw["FunctionalAmount"])
    out["amount"] = amt
    out["debit_amount"] = amt.where(amt > 0, 0.0)
    out["credit_amount"] = (-amt).where(amt < 0, 0.0)
    out["debit_credit"] = pd.Series(["D" if x > 0 else ("C" if x < 0 else "Z") for x in amt.fillna(0)], index=raw.index)
    out["currency"] = raw["Currency"]
    out["functional_amount"] = amt
    out["functional_currency"] = raw["FunctionalCurrency"]

    out["account_code"] = raw["AccountCode"]
    out["account_name"] = raw["AccountName"]
    out["account_type"] = raw["AccountType"]
    out["account_group"] = pd.NA
    out["major"] = raw["Major"]
    out["minor"] = raw["Minor"]

    out["project"] = raw["Project"]
    out["project_code"] = raw["ProjectCode"]
    out["project_name"] = raw["ProjectName"]
    out["phase"] = pd.NA
    out["lot"] = raw["Lot/Phase"]
    out["job_phase_stage"] = raw["JobPhaseStage"]
    out["division_code"] = raw["DivisionCode"]
    out["division_name"] = raw["DivisionName"]
    out["operating_unit"] = raw["OUnit"]
    out["subledger_code"] = raw["SubledgerCode"]
    out["subledger_name"] = raw["SubledgerDesc"]

    out["vendor"] = pd.NA
    out["memo"] = pd.NA
    out["memo_1"] = raw["Memo1"]
    out["memo_2"] = raw["Memo2"]
    out["description"] = raw["Description"]
    out["batch_description"] = raw["BatchDescription"]
    out["source_system"] = "DataRails"

    out["ingested_at"] = INGESTED_AT
    map_json = json.dumps(DATARAILS_MAP, sort_keys=True)
    out["raw_column_map_json"] = map_json
    out["row_hash"] = [
        hash_row([raw.at[i, "__source_file__"], raw.at[i, "__source_row__"],
                  raw.at[i, "PostingDate"], raw.at[i, "TransactionNumber"],
                  raw.at[i, "LineNo"], raw.at[i, "AccountCode"],
                  raw.at[i, "FunctionalAmount"]])
        for i in raw.index
    ]
    return out[CANONICAL]


# ----------------------- Source 2: Vertical Financials 46-col ----------------------- #

VF_MAP = {
    "company_code": "Company",
    "company_name": "Company Name",
    "posting_date": "Posting Date",
    "fiscal_year_source": "Posting Date FY (preferred) or Fiscal Year",
    "amount": "Amount (currency-formatted, cleaned)",
    "debit_amount": "Debit (cleaned, populated only on summary rows)",
    "credit_amount": "Credit (cleaned, populated only on summary rows)",
    "account_code": "Account",
    "account_name": "Account Name",
    "account_type": "Account Type",
    "account_group": "Account Group",
    "major": "Major",
    "minor": "Minor",
    "project": "Project",
    "project_code": "Project",
    "lot": "Lot",
    "division_code": "Division",
    "division_name": "Division Name",
    "operating_unit": "OUnit",
    "subledger_code": "Sub-Ledger",
    "subledger_name": "Sub-Ledger Name",
    "memo_1": "Memo 1",
    "memo_2": "Memo 2",
    "transaction_number": "Trans No",
    "line_number": "Line No",
    "batch_description": "Journal Code",
    # Notes:
    #   currency / functional_currency: not present -> assumed 'USD'
    #   project_name / phase / vendor / job_phase_stage / memo / description: not present -> null
    #   debit_credit: derived from sign of amount
    #   row filter: Line Type contains "detail" (drops subtotal rows)
}


def load_vertical_financials() -> pd.DataFrame:
    raw = pd.read_csv(VF_PATH, dtype=str, keep_default_na=False, encoding="utf-8-sig", low_memory=False)
    raw["__source_row__"] = range(len(raw))
    pre_n = len(raw)

    # Filter to detail lines only (per Line Type). Subtotals/headers are excluded.
    line_type = raw["Line Type"].astype(str).str.strip().str.lower()
    is_detail = line_type.str.contains("detail", na=False)
    dropped_summary = int((~is_detail).sum())
    raw = raw.loc[is_detail].reset_index(drop=True)

    out = pd.DataFrame(index=raw.index)
    out["source_file"] = "Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv"
    out["source_schema"] = "vertical_financials_46col"
    out["source_row_id"] = "vf:" + raw["__source_row__"].astype(str)
    out["transaction_number"] = raw["Trans No"]
    out["line_number"] = raw["Line No"]
    out["transaction_id"] = raw["Trans No"].astype(str) + ":" + raw["Line No"].astype(str)
    out["company_code"] = raw["Company"]
    out["company_name"] = raw["Company Name"]
    out["entity_name"] = raw["Company Name"]

    pd_dt = parse_date(raw["Posting Date"])
    out["posting_date"] = pd_dt.dt.date.astype("string")
    # Prefer Posting Date FY (the FY of the posting), fall back to derived from posting_date
    fy_src = pd.to_numeric(raw["Posting Date FY"], errors="coerce")
    out["fiscal_year"] = fy_src.fillna(pd_dt.dt.year).astype("Int64").astype(str).where(fy_src.notna() | pd_dt.notna(), pd.NA)
    out["fiscal_period"] = pd_dt.dt.month.astype("Int64").astype(str).where(pd_dt.notna(), pd.NA)
    out["source_date_column"] = "Posting Date"

    amt = clean_money(raw["Amount"])
    deb = clean_money(raw["Debit"])
    cred = clean_money(raw["Credit"])
    # On detail rows, Amount is populated and Debit/Credit are typically empty.
    # If amount is null but debit/credit are present, fall back to debit-credit.
    fallback = (deb.fillna(0) - cred.fillna(0)).where(amt.isna(), amt)
    out["amount"] = fallback
    out["debit_amount"] = deb.fillna(out["amount"].where(out["amount"] > 0, 0.0))
    out["credit_amount"] = cred.fillna((-out["amount"]).where(out["amount"] < 0, 0.0))
    out["debit_credit"] = pd.Series(
        ["D" if x > 0 else ("C" if x < 0 else "Z") for x in out["amount"].fillna(0)], index=raw.index
    )
    out["currency"] = "USD"  # not in source; assumed
    out["functional_amount"] = out["amount"]
    out["functional_currency"] = "USD"  # not in source; assumed

    out["account_code"] = raw["Account"]
    out["account_name"] = raw["Account Name"]
    out["account_type"] = raw["Account Type"]
    out["account_group"] = raw["Account Group"]
    out["major"] = raw["Major"]
    out["minor"] = raw["Minor"]

    out["project"] = raw["Project"]
    out["project_code"] = raw["Project"]  # source has no separate code/name; same value in both slots
    out["project_name"] = pd.NA
    out["phase"] = pd.NA
    out["lot"] = raw["Lot"]
    out["job_phase_stage"] = pd.NA
    out["division_code"] = raw["Division"]
    out["division_name"] = raw["Division Name"]
    out["operating_unit"] = raw["OUnit"]
    out["subledger_code"] = raw["Sub-Ledger"]
    out["subledger_name"] = raw["Sub-Ledger Name"]

    out["vendor"] = pd.NA
    out["memo"] = pd.NA
    out["memo_1"] = raw["Memo 1"]
    out["memo_2"] = raw["Memo 2"]
    out["description"] = pd.NA
    out["batch_description"] = raw["Journal Code"]
    out["source_system"] = "DataRails Vertical Financials"

    out["ingested_at"] = INGESTED_AT
    out["raw_column_map_json"] = json.dumps(VF_MAP, sort_keys=True)
    out["row_hash"] = [
        hash_row(["vf", raw.at[i, "__source_row__"], raw.at[i, "Posting Date"],
                  raw.at[i, "Trans No"], raw.at[i, "Line No"],
                  raw.at[i, "Account"], raw.at[i, "Amount"]])
        for i in raw.index
    ]

    print(f"  Vertical Financials: dropped {dropped_summary} non-detail rows out of {pre_n}")
    return out[CANONICAL]


# ----------------------- Source 3: BCPD GL Detail (QB register) ----------------------- #

BCPD_MAP = {
    "transaction_number": "Num",
    "transaction_id": "Num",
    "company_code": "constant '1000' (BCPD code from DataRails bundle)",
    "company_name": "constant 'Building Construction Partners, LLC' (implied by filename)",
    "posting_date": "Date",
    "amount": "Debit - Credit (signed; positive = debit)",
    "debit_amount": "Debit (cleaned)",
    "credit_amount": "Credit (cleaned)",
    "account_code": "parsed from forward-filled account header (e.g. '110-104 · Checking' -> '110-104')",
    "account_name": "parsed from forward-filled account header (e.g. 'Checking')",
    "vendor": "Name (QB Name field is vendor/customer)",
    "description": "Memo",
    "batch_description": "Type (transaction type: Bill, Bill Pmt, Check, Deposit, Credit, General Journal)",
    # Notes:
    #   account_type / account_group / project / lot / phase / etc.: not present -> null
    #   currency / functional_currency: not present -> assumed 'USD'
    #   line_number / fiscal_year / etc.: not present -> derived where possible
    #   row filter: keep only rows where Type is non-empty (excludes account headers, subtotals, blank lines)
}

ACCT_PATTERN = re.compile(r"^(\d+(?:-\d+)?)\s*·\s*(.+?)\s*$")


def load_bcpd_register() -> pd.DataFrame:
    raw = pd.read_csv(BCPD_PATH, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw = raw.rename(columns={"Unnamed: 0": "account_header"})
    raw["__source_row__"] = range(len(raw))
    pre_n = len(raw)

    # Forward-fill account header. Only header rows (not "Total ...") set a new account.
    def parse_acct(s: str) -> tuple[str | None, str | None]:
        if not s or s.strip() == "":
            return (None, None)
        s = s.strip()
        if s.lower().startswith("total"):
            return (None, None)  # total rows don't set a new current account
        m = ACCT_PATTERN.match(s)
        if m:
            return (m.group(1), m.group(2).strip())
        return (None, None)

    current_code, current_name = None, None
    code_col, name_col = [], []
    for v in raw["account_header"]:
        c, n = parse_acct(str(v))
        if c is not None:
            current_code, current_name = c, n
        code_col.append(current_code)
        name_col.append(current_name)
    raw["__acct_code__"] = code_col
    raw["__acct_name__"] = name_col

    # Keep only rows where Type is populated (real transactions). Drops headers, totals, blank lines.
    is_txn = raw["Type"].astype(str).str.strip() != ""
    dropped_non_txn = int((~is_txn).sum())
    raw = raw.loc[is_txn].reset_index(drop=True)

    out = pd.DataFrame(index=raw.index)
    out["source_file"] = "Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv"
    out["source_schema"] = "qb_register_12col"
    out["source_row_id"] = "bcpd:" + raw["__source_row__"].astype(str)
    out["transaction_number"] = raw["Num"]
    out["line_number"] = pd.NA
    out["transaction_id"] = raw["Num"]
    out["company_code"] = "1000"
    out["company_name"] = "Building Construction Partners, LLC"
    out["entity_name"] = "Building Construction Partners, LLC"

    pd_dt = parse_date(raw["Date"])
    out["posting_date"] = pd_dt.dt.date.astype("string")
    out["fiscal_year"] = pd_dt.dt.year.astype("Int64").astype(str).where(pd_dt.notna(), pd.NA)
    out["fiscal_period"] = pd_dt.dt.month.astype("Int64").astype(str).where(pd_dt.notna(), pd.NA)
    out["source_date_column"] = "Date"

    deb = clean_money(raw["Debit"])
    cred = clean_money(raw["Credit"])
    amt = (deb.fillna(0) - cred.fillna(0))
    out["amount"] = amt
    out["debit_amount"] = deb.fillna(0)
    out["credit_amount"] = cred.fillna(0)
    out["debit_credit"] = pd.Series(
        ["D" if x > 0 else ("C" if x < 0 else "Z") for x in amt], index=raw.index
    )
    out["currency"] = "USD"
    out["functional_amount"] = amt
    out["functional_currency"] = "USD"

    out["account_code"] = raw["__acct_code__"]
    out["account_name"] = raw["__acct_name__"]
    out["account_type"] = pd.NA
    out["account_group"] = pd.NA
    out["major"] = pd.NA
    out["minor"] = pd.NA

    out["project"] = pd.NA
    out["project_code"] = pd.NA
    out["project_name"] = pd.NA
    out["phase"] = pd.NA
    out["lot"] = pd.NA
    out["job_phase_stage"] = pd.NA
    out["division_code"] = pd.NA
    out["division_name"] = pd.NA
    out["operating_unit"] = pd.NA
    out["subledger_code"] = pd.NA
    out["subledger_name"] = pd.NA

    out["vendor"] = raw["Name"]
    out["memo"] = raw["Memo"]
    out["memo_1"] = pd.NA
    out["memo_2"] = pd.NA
    out["description"] = raw["Memo"]
    out["batch_description"] = raw["Type"]  # transaction type lives here
    out["source_system"] = "QuickBooks Desktop"

    out["ingested_at"] = INGESTED_AT
    out["raw_column_map_json"] = json.dumps(BCPD_MAP, sort_keys=True)
    out["row_hash"] = [
        hash_row(["bcpd", raw.at[i, "__source_row__"], raw.at[i, "Date"],
                  raw.at[i, "Num"], raw.at[i, "__acct_code__"],
                  raw.at[i, "Debit"], raw.at[i, "Credit"]])
        for i in raw.index
    ]

    print(f"  BCPD GL Detail: dropped {dropped_non_txn} non-transaction rows (headers/totals/blanks) out of {pre_n}")
    return out[CANONICAL]


# ----------------------- Validation report ----------------------- #

def _fr(df: pd.DataFrame, c: str) -> float:
    """Fill rate = fraction of non-null AND non-empty-string values."""
    if c not in df.columns:
        return float("nan")
    s = df[c]
    if s.dtype == object or pd.api.types.is_string_dtype(s):
        return 1.0 - float(s.isna().mean() + (s.astype(str).str.strip() == "").mean() - (s.isna().mean() if s.isna().any() else 0))
    return 1.0 - float(s.isna().mean())


def fill_rate(df: pd.DataFrame, c: str) -> float:
    if c not in df.columns:
        return float("nan")
    s = df[c]
    if pd.api.types.is_numeric_dtype(s):
        return 1.0 - float(s.isna().mean())
    s2 = s.astype("string").fillna("").str.strip()
    return 1.0 - float((s2 == "").mean())


def write_validation_report(df: pd.DataFrame, per_source: dict, dropped: dict) -> str:
    n = len(df)
    pd_dt = pd.to_datetime(df["posting_date"], errors="coerce")

    by_year = df.groupby(pd_dt.dt.year.astype("Int64")).size().sort_index()
    by_schema = df.groupby("source_schema").size().sort_values(ascending=False)
    by_entity = df.groupby("entity_name").size().sort_values(ascending=False)

    # Null rates by source schema for cost/project fields
    cost_fields = ["project", "project_code", "project_name", "phase", "lot",
                   "account_code", "account_name", "subledger_code", "subledger_name",
                   "vendor", "memo", "memo_1", "memo_2", "description"]

    null_by_schema = {}
    for sc, sub in df.groupby("source_schema"):
        null_by_schema[sc] = {f: 1.0 - fill_rate(sub, f) for f in cost_fields}

    # Project/phase/lot usability by year + schema
    usability_rows = []
    for sc, sub in df.groupby("source_schema"):
        sub_dt = pd.to_datetime(sub["posting_date"], errors="coerce")
        for y in sorted(sub_dt.dt.year.dropna().astype(int).unique()):
            ysub = sub[sub_dt.dt.year == y]
            usability_rows.append({
                "source_schema": sc,
                "year": int(y),
                "rows": len(ysub),
                "project_fill": fill_rate(ysub, "project"),
                "lot_fill": fill_rate(ysub, "lot"),
                "phase_fill": fill_rate(ysub, "phase"),
                "job_phase_stage_fill": fill_rate(ysub, "job_phase_stage"),
                "account_code_fill": fill_rate(ysub, "account_code"),
            })
    usability_df = pd.DataFrame(usability_rows)

    # Dup rates
    dup_row_hash = int(df.duplicated(subset=["row_hash"]).sum())
    has_txn_id = df["transaction_id"].astype("string").fillna("").str.strip() != ""
    has_line = df["line_number"].astype("string").fillna("").str.strip() != ""
    composite_key = df["source_schema"].astype(str) + "|" + df["transaction_id"].astype(str) + "|" + df["line_number"].astype(str)
    dup_txn_line = int(df[has_txn_id & has_line].assign(_k=composite_key[has_txn_id & has_line]).duplicated(subset=["_k"]).sum())
    dup_in_scope = int(has_txn_id.sum())

    lines = []
    lines.append("# Staged GL Transactions v2 — Validation Report")
    lines.append("")
    lines.append(f"**Built**: {INGESTED_AT}")
    lines.append("**Outputs**: `data/staged/staged_gl_transactions_v2.csv` and `.parquet`")
    lines.append("**Sources** (transactional GL only):")
    lines.append("- `data/raw/datarails/gl/GL (1..14).csv` — DataRails 38-col bundle")
    lines.append("- `data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Vertical Financials.csv` — 46-col schema")
    lines.append("- `data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - BCPD GL Detail.csv` — 12-col QB register")
    lines.append("")
    lines.append("**Excluded** (per `gl_coverage_report.md`):")
    lines.append("- `GL.csv` (6-row stub)")
    lines.append("- `GL_QBO_*.csv` (opening-balance summaries; no transaction dates)")
    lines.append("- All non-GL files (allocation, collateral, ClickUp, balance sheet, AR, underwriting)")
    lines.append("")

    lines.append("## Headline numbers")
    lines.append("")
    lines.append(f"- **Total v2 rows**: {n:,}")
    lines.append(f"- **min posting_date**: {pd_dt.min().date() if pd_dt.notna().any() else 'n/a'}")
    lines.append(f"- **max posting_date**: {pd_dt.max().date() if pd_dt.notna().any() else 'n/a'}")
    lines.append(f"- **null posting_date rate**: {pd_dt.isna().mean():.2%}")
    lines.append(f"- **canonical columns**: {len(df.columns)}")
    lines.append("")

    lines.append("## Row counts by source")
    lines.append("")
    lines.append("| source_schema | rows ingested | rows dropped | dropped reason |")
    lines.append("|---|---:|---:|---|")
    for sc, info in per_source.items():
        dropped_n = dropped.get(sc, 0)
        lines.append(f"| `{sc}` | {info['rows']:,} | {dropped_n:,} | {info.get('dropped_reason', '—')} |")
    lines.append("")

    lines.append("## Row counts by source_schema (in v2)")
    lines.append("")
    lines.append("| source_schema | rows | share |")
    lines.append("|---|---:|---:|")
    for sc, ct in by_schema.items():
        lines.append(f"| `{sc}` | {int(ct):,} | {ct/n:.1%} |")
    lines.append("")

    lines.append("## Row counts by Posting Year")
    lines.append("")
    lines.append("| year | rows |\n|---:|---:|")
    for y, ct in by_year.items():
        y_label = "(unparseable)" if pd.isna(y) else int(y)
        lines.append(f"| {y_label} | {int(ct):,} |")
    lines.append("")

    lines.append("## Row counts by entity")
    lines.append("")
    lines.append("| entity_name | rows |\n|---|---:|")
    for ent, ct in by_entity.items():
        ent_d = "(blank)" if not str(ent).strip() else ent
        lines.append(f"| {ent_d} | {int(ct):,} |")
    lines.append("")

    lines.append("## Null rates by source_schema for cost/project fields")
    lines.append("")
    lines.append("| field | " + " | ".join(f"`{sc}`" for sc in null_by_schema) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(null_by_schema)) + "|")
    for f in cost_fields:
        lines.append(
            f"| `{f}` | "
            + " | ".join(f"{null_by_schema[sc][f]:.2%}" for sc in null_by_schema)
            + " |"
        )
    lines.append("")

    lines.append("## Project / Phase / Lot usability by year and source_schema")
    lines.append("")
    lines.append("Fill rate by canonical column. Usability threshold: ≥50% means 'usable for cost attribution'.")
    lines.append("")
    lines.append("| source_schema | year | rows | project_fill | lot_fill | phase_fill | job_phase_stage_fill | account_code_fill |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in usability_rows:
        lines.append(
            f"| `{r['source_schema']}` | {r['year']} | {r['rows']:,} | "
            f"{r['project_fill']:.1%} | {r['lot_fill']:.1%} | {r['phase_fill']:.1%} | "
            f"{r['job_phase_stage_fill']:.1%} | {r['account_code_fill']:.1%} |"
        )
    lines.append("")

    lines.append("## Duplicate-row check")
    lines.append("")
    lines.append(f"- Duplicate rows by `row_hash`: **{dup_row_hash}**")
    lines.append(f"- Duplicate rows by `(source_schema, transaction_id, line_number)` "
                 f"(only for rows where both are populated, n={dup_in_scope:,}): **{dup_txn_line}**")
    lines.append("")

    lines.append("## Schema notes — canonical fields not derivable from each source")
    lines.append("")
    lines.append("These are intentionally left null because the source does not carry the field. "
                 "Documented here so consumers can reason about the gaps.")
    lines.append("")
    lines.append("| canonical field | datarails_38col | vertical_financials_46col | qb_register_12col |")
    lines.append("|---|---|---|---|")
    not_in = {
        "phase":           ("not separable from `Lot/Phase`", "not present", "not present"),
        "vendor":          ("not present (use subledger_name as proxy)", "not present", "from `Name`"),
        "project_name":    ("from `ProjectName`", "not present (only `Project`)", "not present"),
        "project_code":    ("from `ProjectCode`", "from `Project` (no separate code/name)", "not present"),
        "account_group":   ("not present", "from `Account Group`", "not present"),
        "account_type":    ("from `AccountType`", "from `Account Type`", "not present"),
        "currency":        ("from `Currency`", "assumed `USD`", "assumed `USD`"),
        "functional_currency": ("from `FunctionalCurrency`", "assumed `USD`", "assumed `USD`"),
        "memo":            ("not present (Memo1/Memo2 separate)", "not present (Memo 1/Memo 2 separate)", "from `Memo`"),
        "description":     ("from `Description`", "not present", "from `Memo` (same as memo)"),
        "subledger_*":     ("from `SubledgerCode`/`SubledgerDesc`", "from `Sub-Ledger`/`Sub-Ledger Name`", "not present"),
        "lot":             ("from `Lot/Phase` (combined w/ phase)", "from `Lot`", "not present"),
        "operating_unit":  ("from `OUnit`", "from `OUnit`", "not present"),
        "major / minor":   ("from `Major`/`Minor`", "from `Major`/`Minor`", "not present"),
        "line_number":     ("from `LineNo`", "from `Line No`", "not present (single-line entries)"),
    }
    for field, (a, b, c) in not_in.items():
        lines.append(f"| `{field}` | {a} | {b} | {c} |")
    lines.append("")

    lines.append("## Sign convention")
    lines.append("")
    lines.append("All three sources are normalized to the same convention: "
                 "**`amount` is signed; positive = debit, negative = credit**.")
    lines.append("")
    lines.append("- DataRails 38-col: `FunctionalAmount` is already signed. The misleadingly named `DebitCredit` "
                 "column is also a signed amount (in transaction currency); not a D/C flag.")
    lines.append("- Vertical Financials 46-col: detail rows carry signed `Amount`. `Debit`/`Credit` are usually "
                 "empty on detail rows; populated only on summary rows (which are filtered out).")
    lines.append("- QB register 12-col: `Debit` and `Credit` are separate positive columns. "
                 "`amount = Debit - Credit`.")
    lines.append("")

    return "\n".join(lines)


# ----------------------- main ----------------------- #

def main():
    print("Loading DataRails 38-col bundle...")
    df1 = load_datarails()
    print(f"  -> {len(df1):,} rows")

    print("Loading Vertical Financials 46-col...")
    df2 = load_vertical_financials()
    print(f"  -> {len(df2):,} rows")

    print("Loading BCPD QB register 12-col...")
    df3 = load_bcpd_register()
    print(f"  -> {len(df3):,} rows")

    print("Concatenating...")
    df = pd.concat([df1, df2, df3], axis=0, ignore_index=True)
    print(f"  v2 total: {len(df):,} rows x {len(df.columns)} cols")

    print("Writing outputs...")
    csv_path = STAGED / "staged_gl_transactions_v2.csv"
    pq_path = STAGED / "staged_gl_transactions_v2.parquet"
    df.to_csv(csv_path, index=False)
    df.to_parquet(pq_path, index=False, engine="pyarrow")

    per_source = {
        "datarails_38col": {"rows": len(df1), "dropped_reason": "no rows dropped (only GL.csv stub excluded by name)"},
        "vertical_financials_46col": {"rows": len(df2), "dropped_reason": "Line Type != 'detail' (subtotal rows)"},
        "qb_register_12col": {"rows": len(df3), "dropped_reason": "Type empty (account headers, total rows, blanks)"},
    }
    # Compute dropped counts directly
    vf_raw_rows = sum(1 for _ in open(VF_PATH, "rb")) - 1
    bcpd_raw_rows = sum(1 for _ in open(BCPD_PATH, "rb")) - 1
    dropped = {
        "datarails_38col": 0,
        "vertical_financials_46col": vf_raw_rows - len(df2),
        "qb_register_12col": bcpd_raw_rows - len(df3),
    }

    print("Writing validation report...")
    rpt = write_validation_report(df, per_source, dropped)
    (STAGED / "staged_gl_transactions_v2_validation_report.md").write_text(rpt)

    summary = {
        "v2_rows": len(df),
        "by_source": per_source,
        "dropped_per_source": dropped,
        "csv_bytes": csv_path.stat().st_size,
        "parquet_bytes": pq_path.stat().st_size,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
