from __future__ import annotations

import pandas as pd

from core.engine.registry import step
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

        if "Data Type" in df.columns:
            df = df[df["Data Type"] == "Activity"]

        if "Entity" in df.columns:
            df = df[~df["Entity"].str.lower().isin(
                {e.lower() for e in self.invalid_entities}
            )]

        str_cols = ["Account ID", "Account Name", "Customer", "Vendor",
                    "Memo/Description", "Entity"]
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype("string").str.strip()

        if "Customer" in df.columns:
            df.loc[df["Customer"] == PLACEHOLDER_CUSTOMER, "Customer"] = pd.NA
        if "Vendor" in df.columns:
            df.loc[df["Vendor"] == PLACEHOLDER_VENDOR, "Vendor"] = pd.NA

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


@step(
    name="gl_clean",
    inputs={"gl_raw": pd.DataFrame},
    outputs={"gl_clean": pd.DataFrame},
    effects=(),
    description="Clean a raw QuickBooks GL DataFrame: keep Activity rows, strip whitespace, normalize account names.",
)
def gl_clean(gl_raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"gl_clean": GLCleanStep().run(gl_raw)}
