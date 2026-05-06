from __future__ import annotations

import re

import pandas as pd

from core.steps.base import DeterministicToolStep

# ---- Default configurations (current company) --------------------------------

DEFAULT_ENTITY_MAP: dict[str, tuple[str, str | None]] = {
    "Flagship EM Holdings LLC":          ("holdco",  None),
    "Anderson Geneva LLC":               ("project", "Anderson Geneva"),
    "Flagborough LLC":                   ("project", "Park"),
    "Arrowhead Springs Development LLC": ("project", "Arrowhead Springs"),
    "Geneva Project Manager LLC":        ("service", None),
}

# (compiled pattern, cost_bucket) — first match wins.
DEFAULT_ACCOUNT_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^110-"),                        "cash"),
    (re.compile(r"^(210-|21010|20000$)"),          "accounts_payable"),
    (re.compile(r"^220-"),                         "accounts_payable"),
    (re.compile(r"^(12100$|132-|151-|193-|510-)"), "inventory_cip"),
    (re.compile(r"^260-"),                         "financing"),
    (re.compile(r"^740-"),                         "interest"),
    (re.compile(r"^(660-|670-|81400$)"),           "soft_cost"),
]

# (compiled pattern, group_template, confidence)
DEFAULT_PHASE_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\bblock\s+(\d+[A-Za-z]?)\b", re.I),  r"block \1", "high"),
    (
        re.compile(r"\bLDWIP\s+(\d+)\s+Overall\s+([A-Z.\s]+)", re.I),
        r"LDWIP \1 \2",
        "medium",
    ),
]

# ------------------------------------------------------------------------------


class GLNormalizeStep(DeterministicToolStep):
    """Normalizes a cleaned GL DataFrame into the canonical schema.

    Input:  cleaned DataFrame from GLCleanStep (must have account_name_canonical)
    Output: normalized DataFrame with entity_role, project_id, phase_id,
            cost_bucket, and other canonical fields.

    Args:
        entity_map:     maps raw entity name → (role, project_id)
        account_rules:  ordered list of (pattern, bucket) — first match wins
        phase_rules:    ordered list of (pattern, template, confidence)
    """

    def __init__(
        self,
        entity_map: dict | None = None,
        account_rules: list | None = None,
        phase_rules: list | None = None,
    ):
        self.entity_map = entity_map if entity_map is not None else DEFAULT_ENTITY_MAP
        self.account_rules = account_rules if account_rules is not None else DEFAULT_ACCOUNT_RULES
        self.phase_rules = phase_rules if phase_rules is not None else DEFAULT_PHASE_RULES

    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data
        out = pd.DataFrame()

        if "Posting Date" in df.columns:
            out["posting_date"] = pd.to_datetime(df["Posting Date"], errors="coerce").dt.date
        else:
            out["posting_date"] = pd.NaT

        out["entity"] = df["Entity"] if "Entity" in df.columns else pd.NA

        role_proj = out["entity"].map(
            lambda e: self.entity_map.get(str(e), ("unknown", None)) if pd.notna(e) else ("unknown", None)
        )
        out["entity_role"] = [r for r, _ in role_proj]
        out["project_id"]  = [p for _, p in role_proj]

        acname = df["account_name_canonical"] if "account_name_canonical" in df.columns else pd.Series("", index=df.index)
        phases = acname.apply(self._extract_phase)
        out["phase_id"]         = [p for p, _ in phases]
        out["phase_confidence"] = [c for _, c in phases]

        out["account_id"]   = df["Account ID"] if "Account ID" in df.columns else pd.NA
        out["account_name"] = acname
        out["cost_bucket"]  = out["account_id"].apply(self._classify_account)

        out["vendor"] = df["Vendor"] if "Vendor" in df.columns else pd.NA

        if "Amount" in df.columns:
            out["amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
        else:
            out["amount"] = 0.0

        out["source_system"] = df["DataMapper_Name"] if "DataMapper_Name" in df.columns else pd.NA

        return out.reset_index(drop=True)

    def _classify_account(self, account_id) -> str:
        if pd.isna(account_id) or not str(account_id).strip():
            return "unmapped"
        aid = str(account_id).strip()
        for pat, bucket in self.account_rules:
            if pat.match(aid):
                return bucket
        return "unmapped"

    def _extract_phase(self, account_name) -> tuple[str, str]:
        if pd.isna(account_name) or not str(account_name).strip():
            return "UNALLOCATED", "none"
        name = str(account_name).strip()
        for pat, template, conf in self.phase_rules:
            m = pat.search(name)
            if m:
                phase = pat.sub(template, m.group(0)).strip()
                phase = re.sub(r"\s+", " ", phase)
                return phase, conf
        return "UNALLOCATED", "none"
