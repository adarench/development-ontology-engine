from __future__ import annotations

import pandas as pd

from core.steps.base import DeterministicToolStep

PLACEHOLDER_CUSTOMER = "Customer or Client name"
PLACEHOLDER_VENDOR = "Vendor or Supplier name"


class GLCleanStep(DeterministicToolStep):
    """Cleans a raw QuickBooks GL DataFrame.

    Input:  raw DataFrame from QuickBooksConnector
    Output: cleaned DataFrame (Activity rows only, whitespace stripped,
            placeholder nulls replaced, account_name_canonical added)

    Args:
        invalid_entities: entity names to drop (e.g. vendor names that leaked
                          into the Entity column). Defaults to known bad values.
    """

    def __init__(self, invalid_entities: set[str] | None = None):
        self.invalid_entities = invalid_entities or {"drywall partners"}

    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        # Keep only transaction rows; drop opening balances and subtotals.
        if "Data Type" in df.columns:
            df = df[df["Data Type"] == "Activity"]

        # Drop rows where the Entity column was contaminated with vendor names.
        if "Entity" in df.columns:
            df = df[~df["Entity"].str.lower().isin(
                {e.lower() for e in self.invalid_entities}
            )]

        # Normalize string columns.
        str_cols = ["Account ID", "Account Name", "Customer", "Vendor",
                    "Memo/Description", "Entity"]
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype("string").str.strip()

        # Replace known placeholder strings with NA.
        if "Customer" in df.columns:
            df.loc[df["Customer"] == PLACEHOLDER_CUSTOMER, "Customer"] = pd.NA
        if "Vendor" in df.columns:
            df.loc[df["Vendor"] == PLACEHOLDER_VENDOR, "Vendor"] = pd.NA

        # Canonical account name: collapse whitespace, title-case known variants.
        if "Account Name" in df.columns:
            df["account_name_canonical"] = (
                df["Account Name"].fillna("").str.strip()
                .str.replace(r"\s+", " ", regex=True)
            )
            df.loc[
                df["account_name_canonical"].str.lower() == "accounts payable",
                "account_name_canonical",
            ] = "Accounts Payable"
        else:
            df["account_name_canonical"] = ""

        return df.reset_index(drop=True)
